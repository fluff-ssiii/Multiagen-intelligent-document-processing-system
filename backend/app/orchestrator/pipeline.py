import time
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.ingestion_agent import IngestionAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.workflow_agent import WorkflowAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import PipelineError
from app.core.logging_config import get_logger
from app.database import repository
from app.database.connection import SessionLocal
from app.schemas.agent_schema import AgentResult
from app.schemas.decision_schema import DecisionInput, DecisionType
from app.schemas.document_schema import BUSY_STATUSES, DocumentStatus, IngestionInput
from app.schemas.extraction_schema import ExtractionInput, get_document_type
from app.schemas.pipeline_schema import PipelineResult, StepRecord
from app.schemas.validation_schema import ValidationInput
from app.schemas.workflow_schema import WorkflowInput

logger = get_logger("orchestrator")


class PipelineOrchestrator:
    """
    Runs agents sequentially, passes structured outputs between them, tracks status,
    retries retryable failures, and logs every attempt.

    Stages: ingestion -> extraction -> validation -> decision -> workflow.
    """

    def __init__(
        self,
        db: Session,
        *,
        ingestion_agent: Optional[IngestionAgent] = None,
        extraction_agent: Optional[ExtractionAgent] = None,
        validation_agent: Optional[ValidationAgent] = None,
        decision_agent: Optional[DecisionAgent] = None,
        workflow_agent: Optional[WorkflowAgent] = None,
        config: Optional[Settings] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.db = db
        self.cfg = config or default_settings
        self.ingestion = ingestion_agent or IngestionAgent()
        self.extraction = extraction_agent or ExtractionAgent(config=self.cfg)
        self.validation = validation_agent or ValidationAgent(config=self.cfg)
        self.decision = decision_agent or DecisionAgent(config=self.cfg)
        self.workflow = workflow_agent or WorkflowAgent(config=self.cfg)
        self._sleep = sleep

    # ------------------------------------------------------------------ public
    def start(self, document_id: str) -> None:
        """Check the document exists and claim it. Raises PipelineError (404 / 409)."""
        if repository.get_document(self.db, document_id) is None:
            raise PipelineError("Document not found.", code="NOT_FOUND", status_code=404)
        claimed = repository.claim_document(
            self.db, document_id, DocumentStatus.INGESTING.value,
            [s.value for s in BUSY_STATUSES],
        )
        if not claimed:
            raise PipelineError("Document is already being processed.",
                                code="ALREADY_PROCESSING", status_code=409)

    def process_document(self, document_id: str) -> PipelineResult:
        self.start(document_id)
        return self.execute(document_id)

    def execute(self, document_id: str) -> PipelineResult:
        """Run the pipeline for an already-claimed document. Never raises."""
        started = time.perf_counter()
        steps: list[StepRecord] = []
        self._log(document_id, "started", "pipeline started")

        try:
            doc = repository.get_document(self.db, document_id)
            if doc is None:
                raise PipelineError("Document disappeared during processing.", code="NOT_FOUND")
            file_path, document_type, filename = doc.file_path, doc.document_type, doc.original_filename

            # 1. Ingestion --------------------------------------------------
            ing_res, attempts = self._run_stage(
                document_id, self.ingestion,
                IngestionInput(document_id=document_id, file_path=file_path),
                self._summarize_ingestion,
            )
            steps.append(self._step(ing_res, attempts))
            if not ing_res.ok:
                return self._fail(document_id, started, steps, ing_res)
            ingestion_out = ing_res.output
            repository.update_document(self.db, document_id,
                                       status=DocumentStatus.INGESTED.value,
                                       page_count=ingestion_out.page_count)

            # 2. Extraction (OCR step is a pass-through: the VLM reads page images directly)
            repository.update_document(self.db, document_id, status=DocumentStatus.EXTRACTING.value)
            ext_res, attempts = self._run_stage(
                document_id, self.extraction,
                ExtractionInput(document_id=document_id, document_type=document_type,
                                pages=ingestion_out.pages),
                self._summarize_extraction,
            )
            steps.append(self._step(ext_res, attempts))
            if not ext_res.ok:
                return self._fail(document_id, started, steps, ext_res)
            extraction_out = ext_res.output
            extraction_row = repository.save_extraction(self.db, extraction_out)
            repository.update_document(self.db, document_id, status=DocumentStatus.EXTRACTED.value)

            # 3. Validation (cross-document context is gathered here, not inside the agent)
            repository.update_document(self.db, document_id, status=DocumentStatus.VALIDATING.value)
            duplicates = None
            key = get_document_type(document_type).duplicate_key_field
            if key and extraction_out.fields.get(key):
                duplicates = {key: repository.find_documents_with_field_value(
                    self.db, key, extraction_out.fields[key], exclude_document_id=document_id)}

            val_res, attempts = self._run_stage(
                document_id, self.validation,
                ValidationInput(document_id=document_id, document_type=document_type,
                                fields=extraction_out.fields,
                                extraction_parse_ok=extraction_out.parse_ok,
                                duplicates=duplicates),
                self._summarize_validation,
            )
            steps.append(self._step(val_res, attempts))
            if not val_res.ok:
                return self._fail(document_id, started, steps, val_res)
            validation_out = val_res.output
            repository.save_validation(self.db, validation_out, stage="initial")
            repository.update_document(self.db, document_id, status=DocumentStatus.VALIDATED.value)

            # 4. Decision ----------------------------------------------------
            repository.update_document(self.db, document_id, status=DocumentStatus.DECIDING.value)
            dec_res, attempts = self._run_stage(
                document_id, self.decision,
                DecisionInput(document_id=document_id, document_type=document_type,
                              extraction_parse_ok=extraction_out.parse_ok,
                              extraction_missing_fields=extraction_out.missing_fields,
                              extraction_confidence=extraction_out.confidence,
                              validation=validation_out),
                self._summarize_decision,
            )
            steps.append(self._step(dec_res, attempts))
            if not dec_res.ok:
                return self._fail(document_id, started, steps, dec_res)
            decision_out = dec_res.output

            repository.supersede_pending_reviews(self.db, document_id)   # reprocessing replaces old queue entries
            decision_row = repository.save_decision(self.db, decision_out)
            if decision_out.decision == DecisionType.HUMAN_REVIEW:
                repository.create_review(self.db, document_id,
                                         priority=decision_out.review_priority or "normal",
                                         extraction_id=extraction_row.id)
            elif decision_out.is_approved:
                repository.update_document(self.db, document_id, status=DocumentStatus.APPROVED.value)

            # 5. Workflow ----------------------------------------------------
            wf_res, attempts = self._run_stage(
                document_id, self.workflow,
                WorkflowInput(document_id=document_id, document_type=document_type,
                              original_filename=filename, decision=decision_out,
                              fields=extraction_out.fields,
                              normalized_fields=validation_out.normalized_fields,
                              validation_status=validation_out.status.value),
                self._summarize_workflow,
            )
            steps.append(self._step(wf_res, attempts))
            if not wf_res.ok:
                # An approved document keeps its approval; only the follow-up action failed.
                fallback = DocumentStatus.APPROVED if decision_out.is_approved else DocumentStatus.FAILED
                message = f"{wf_res.agent_name} failed [{wf_res.error_code}]: {wf_res.error}"
                return self._finalize(document_id, started, steps, fallback, error=message,
                                      extraction=extraction_out, validation=validation_out,
                                      decision=decision_out)

            workflow_out = wf_res.output
            repository.apply_workflow_result(self.db, decision_row.id, workflow_out)
            return self._finalize(document_id, started, steps, workflow_out.document_status,
                                  extraction=extraction_out, validation=validation_out,
                                  decision=decision_out, workflow=workflow_out)

        except Exception as exc:  # orchestrator-level failure (DB error, bug, ...)
            logger.exception("pipeline crashed for document %s", document_id)
            try:
                self.db.rollback()
                return self._finalize(document_id, started, steps, DocumentStatus.FAILED,
                                      error=f"orchestrator error: {exc}")
            except Exception:
                logger.exception("could not record failure for document %s", document_id)
                return PipelineResult(
                    document_id=document_id, status=DocumentStatus.FAILED.value, success=False,
                    steps=steps, total_duration_ms=self._elapsed_ms(started),
                    error=f"orchestrator error: {exc}",
                )

    # ----------------------------------------------------------------- helpers
    def _run_stage(
        self,
        document_id: str,
        agent: BaseAgent,
        payload: Any,
        summarize: Optional[Callable[[Any], dict]] = None,
    ) -> tuple[AgentResult, int]:
        max_attempts = 1 + self.cfg.pipeline_max_retries
        attempts = 0
        while True:
            attempts += 1
            result = agent.run(payload)
            self._log_attempt(document_id, agent.name, result, attempts, summarize)

            if result.ok or not result.retryable or attempts >= max_attempts:
                return result, attempts

            delay = self.cfg.pipeline_retry_backoff_seconds * (2 ** (attempts - 1))
            logger.warning("%s failed [%s]; retry %d/%d in %.1fs", agent.name, result.error_code,
                           attempts, max_attempts - 1, delay)
            self._sleep(delay)

    def _log_attempt(self, document_id: str, agent_name: str, result: AgentResult, attempt: int,
                     summarize: Optional[Callable[[Any], dict]]) -> None:
        details: dict = {
            "attempt": attempt,
            "error_code": result.error_code,
            "retryable": result.retryable,
            "warnings": result.warnings,
        }
        if result.ok and summarize is not None and result.output is not None:
            details["summary"] = summarize(result.output)
        repository.add_processing_log(
            self.db, document_id, agent_name, result.status.value,
            message=result.error or "ok", duration_ms=result.duration_ms, details=details,
        )

    def _log(self, document_id: str, status: str, message: str, duration_ms: Optional[int] = None) -> None:
        repository.add_processing_log(self.db, document_id, "orchestrator", status,
                                      message=message, duration_ms=duration_ms)

    @staticmethod
    def _step(result: AgentResult, attempts: int) -> StepRecord:
        return StepRecord(
            agent_name=result.agent_name, status=result.status.value, attempts=attempts,
            duration_ms=result.duration_ms, error=result.error, error_code=result.error_code,
            warnings=result.warnings,
        )

    def _fail(self, document_id: str, started: float, steps: list[StepRecord],
              result: AgentResult) -> PipelineResult:
        message = f"{result.agent_name} failed [{result.error_code}]: {result.error}"
        return self._finalize(document_id, started, steps, DocumentStatus.FAILED, error=message)

    def _finalize(self, document_id: str, started: float, steps: list[StepRecord],
                  status: DocumentStatus, error: Optional[str] = None,
                  extraction=None, validation=None, decision=None, workflow=None) -> PipelineResult:
        duration_ms = self._elapsed_ms(started)
        repository.update_document(self.db, document_id, status=status.value,
                                   processing_duration_ms=duration_ms, error_message=error)
        self._log(document_id, "failed" if error else "success",
                  error or f"pipeline finished with status '{status.value}'", duration_ms)
        logger.info("document %s -> %s in %d ms", document_id, status.value, duration_ms)
        return PipelineResult(
            document_id=document_id, status=status.value, success=error is None,
            steps=steps, total_duration_ms=duration_ms, error=error,
            extraction=extraction, validation=validation, decision=decision, workflow=workflow,
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _summarize_ingestion(out) -> dict:
        return {"page_count": out.page_count, "file_type": out.file_type, "warnings": out.warnings}

    @staticmethod
    def _summarize_extraction(out) -> dict:
        return {
            "parse_ok": out.parse_ok, "attempts": out.attempts, "missing_fields": out.missing_fields,
            "generation_ms": out.generation_ms, "confidence": out.confidence,
        }

    @staticmethod
    def _summarize_validation(out) -> dict:
        return {
            "status": out.status.value,
            "errors": [i.rule_id for i in out.errors],
            "warnings": [i.rule_id for i in out.warnings],
        }

    @staticmethod
    def _summarize_decision(out) -> dict:
        return {
            "decision": out.decision.value,
            "reasons": [r.code for r in out.reasons],
            "review_priority": out.review_priority,
        }

    @staticmethod
    def _summarize_workflow(out) -> dict:
        return {
            "workflow_status": out.workflow_status.value,
            "document_status": out.document_status.value,
            "actions": [a.name for a in out.actions],
            "export_path": out.export_path,
        }


def run_pipeline_background(document_id: str) -> None:
    """Entry point for FastAPI background tasks (own DB session, request session is closed)."""
    db = SessionLocal()
    try:
        PipelineOrchestrator(db).execute(document_id)
    except Exception:
        logger.exception("background pipeline failed for %s", document_id)
    finally:
        db.close()