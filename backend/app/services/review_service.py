from typing import Optional

from sqlalchemy.orm import Session

from app.agents.decision_agent import DecisionAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.workflow_agent import WorkflowAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import ReviewError
from app.database import repository
from app.database.models import Document, ReviewRecord
from app.schemas.agent_schema import AgentResult
from app.schemas.decision_schema import DecisionInput, DecisionOutput, DecisionStage
from app.schemas.document_schema import DocumentStatus
from app.schemas.extraction_schema import get_document_type
from app.schemas.review_schema import ReviewResult
from app.schemas.validation_schema import ValidationInput, ValidationOutput
from app.schemas.workflow_schema import WorkflowInput
from app.utils.json_utils import clean_value


class ReviewService:
    """Pending queue + reviewer actions. Corrections are re-validated and re-decided before approval,
    then handed to the Workflow Agent."""

    def __init__(self, db: Session, validation_agent: Optional[ValidationAgent] = None,
                 decision_agent: Optional[DecisionAgent] = None,
                 workflow_agent: Optional[WorkflowAgent] = None,
                 config: Optional[Settings] = None):
        self.db = db
        self.cfg = config or default_settings
        self.validation = validation_agent or ValidationAgent(config=self.cfg)
        self.decision = decision_agent or DecisionAgent(config=self.cfg)
        self.workflow = workflow_agent or WorkflowAgent(config=self.cfg)

    # ------------------------------------------------------------------ queue
    def pending(self, skip: int = 0, limit: int = 50) -> list[ReviewRecord]:
        return repository.list_pending_reviews(self.db, skip, limit)

    # ---------------------------------------------------------------- approve
    def approve(self, document_id: str, corrections: dict[str, Optional[str]],
                notes: Optional[str] = None) -> ReviewResult:
        doc, review = self._get_pending(document_id)
        filename, doc_type = doc.original_filename, doc.document_type
        extraction = repository.get_latest_extraction(self.db, document_id)
        if extraction is None:
            raise ReviewError("No extraction exists for this document.", "NO_EXTRACTION", 409)

        spec = get_document_type(doc_type)
        unknown = sorted(set(corrections) - set(spec.field_names))
        if unknown:
            raise ReviewError(f"Unknown field(s): {', '.join(unknown)}", "UNKNOWN_FIELD", 422)

        predicted = dict(extraction.predicted_fields or {})
        cleaned = {k: clean_value(v) for k, v in corrections.items()}        # None / "" clears a field
        final_fields = {name: predicted.get(name) for name in spec.field_names}
        final_fields.update(cleaned)
        effective = {k: v for k, v in cleaned.items() if v != clean_value(predicted.get(k))}

        # Re-evaluate the corrected data before approval
        duplicates = None
        key = spec.duplicate_key_field
        if key and final_fields.get(key):
            duplicates = {key: repository.find_documents_with_field_value(
                self.db, key, final_fields[key], exclude_document_id=document_id)}
        val_res = self.validation.run(ValidationInput(
            document_id=document_id, document_type=doc_type, fields=final_fields,
            extraction_parse_ok=True, duplicates=duplicates))
        self._log_agent(document_id, val_res)
        if not val_res.ok:
            raise ReviewError(f"Re-validation failed: {val_res.error}", "REVALIDATION_FAILED", 500)

        dec_res = self.decision.run(DecisionInput(
            document_id=document_id, document_type=doc_type,
            stage=DecisionStage.POST_CORRECTION, validation=val_res.output,
            corrections_count=len(effective)))
        self._log_agent(document_id, dec_res)
        if not dec_res.ok:
            raise ReviewError(f"Decision failed: {dec_res.error}", "DECISION_FAILED", 500)

        decision = dec_res.output
        if not decision.is_approved:
            raise ReviewError(
                "The corrected data still has validation errors. Fix them or reject the document.",
                "VALIDATION_ERRORS_REMAIN", 422,
                details={"errors": [i.model_dump(mode="json") for i in val_res.output.errors],
                         "warnings": [i.model_dump(mode="json") for i in val_res.output.warnings]})

        claimed = repository.complete_review(
            self.db, review.id, status="approved", human_corrections=effective,
            final_fields=final_fields, notes=notes)
        if not claimed:
            raise ReviewError("This review was already completed.", "ALREADY_REVIEWED", 409)

        repository.save_validation(self.db, val_res.output, stage="post_correction")
        decision_row = repository.save_decision(self.db, decision)
        repository.update_document(self.db, document_id, status=DocumentStatus.APPROVED.value)
        repository.add_processing_log(self.db, document_id, "review_service", "success",
                                      message=f"approved with {len(effective)} correction(s)",
                                      details={"corrected_fields": sorted(effective)})
        return self._run_workflow(document_id, filename, doc_type, decision, decision_row.id,
                                  final_fields, val_res.output, sorted(effective))

    # ----------------------------------------------------------------- reject
    def reject(self, document_id: str, notes: Optional[str] = None) -> ReviewResult:
        doc, review = self._get_pending(document_id)
        filename, doc_type = doc.original_filename, doc.document_type
        dec_res = self.decision.run(DecisionInput(
            document_id=document_id, document_type=doc_type,
            stage=DecisionStage.REVIEWER_REJECTED))
        self._log_agent(document_id, dec_res)
        if not dec_res.ok:
            raise ReviewError(f"Decision failed: {dec_res.error}", "DECISION_FAILED", 500)

        claimed = repository.complete_review(
            self.db, review.id, status="rejected", human_corrections=None,
            final_fields=None, notes=notes)
        if not claimed:
            raise ReviewError("This review was already completed.", "ALREADY_REVIEWED", 409)

        decision_row = repository.save_decision(self.db, dec_res.output)
        repository.update_document(self.db, document_id, status=DocumentStatus.REJECTED.value)
        repository.add_processing_log(self.db, document_id, "review_service", "success",
                                      message="rejected by reviewer")
        return self._run_workflow(document_id, filename, doc_type, dec_res.output, decision_row.id,
                                  None, None, [])

    # ---------------------------------------------------------------- helpers
    def _run_workflow(self, document_id: str, filename: str, doc_type: str, decision: DecisionOutput,
                      decision_row_id: int, fields: Optional[dict], validation: Optional[ValidationOutput],
                      corrected: list[str]) -> ReviewResult:
        result = self.workflow.run(WorkflowInput(
            document_id=document_id, document_type=doc_type, original_filename=filename,
            decision=decision, fields=fields,
            normalized_fields=validation.normalized_fields if validation else None,
            validation_status=validation.status.value if validation else None,
            corrected_fields=corrected))
        self._log_agent(document_id, result)

        if not result.ok:
            # The human decision stands; only the follow-up action failed.
            repository.update_document(
                self.db, document_id,
                error_message=f"workflow_agent failed [{result.error_code}]: {result.error}")
            return ReviewResult(decision=decision, workflow=None, workflow_error=result.error)

        repository.apply_workflow_result(self.db, decision_row_id, result.output)
        repository.update_document(self.db, document_id, error_message=None)
        return ReviewResult(decision=decision, workflow=result.output)

    def _get_pending(self, document_id: str) -> tuple[Document, ReviewRecord]:
        doc = repository.get_document(self.db, document_id)
        if doc is None:
            raise ReviewError("Document not found.", "NOT_FOUND", 404)
        review = repository.get_pending_review(self.db, document_id)
        if review is None:
            raise ReviewError("This document has no pending review.", "NOT_PENDING_REVIEW", 409)
        return doc, review

    def _log_agent(self, document_id: str, result: AgentResult) -> None:
        repository.add_processing_log(
            self.db, document_id, result.agent_name, result.status.value,
            message=result.error or "ok", duration_ms=result.duration_ms,
            details={"stage": "review"})