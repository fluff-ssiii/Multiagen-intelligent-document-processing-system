from datetime import datetime, timezone
from typing import Callable, Optional

from app.agents.base_agent import BaseAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import WorkflowError
from app.schemas.decision_schema import DecisionType
from app.schemas.document_schema import DocumentStatus
from app.schemas.workflow_schema import (
    WorkflowAction,
    WorkflowInput,
    WorkflowOutput,
    WorkflowStatus,
)
from app.services.export_service import ExportService

SOURCE_BY_DECISION = {
    DecisionType.AUTO_APPROVED: "automatic",
    DecisionType.APPROVED_AFTER_CORRECTION: "human_corrected",
    DecisionType.APPROVED_AFTER_REVIEW: "human_confirmed",
}


class WorkflowAgent(BaseAgent[WorkflowInput, WorkflowOutput]):
    """
    Responsibility: carry out the Decision Agent's outcome - build the final record for approved
    documents, export it, and describe every action taken with a timestamp (audit trail).
    It never touches the database; the caller persists the returned output.
    """

    name = "workflow_agent"

    def __init__(
        self,
        exporter: Optional[ExportService] = None,
        config: Optional[Settings] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        super().__init__()
        self.cfg = config or default_settings
        self._exporter = exporter
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def exporter(self) -> ExportService:
        if self._exporter is None:
            self._exporter = ExportService(self.cfg.export_dir)
        return self._exporter

    def process(self, payload: WorkflowInput) -> WorkflowOutput:
        decision = payload.decision
        if decision.document_id != payload.document_id:
            raise WorkflowError("The decision belongs to a different document.",
                                code="DOCUMENT_MISMATCH", status_code=400)

        if decision.is_approved:
            output = self._complete(payload)
        elif decision.decision == DecisionType.HUMAN_REVIEW:
            output = self._await_review(payload)
        elif decision.decision == DecisionType.REJECTED:
            output = self._reject(payload)
        else:
            raise WorkflowError(f"Unsupported decision '{decision.decision}'.",
                                code="UNSUPPORTED_DECISION", status_code=400)

        self.logger.info("document %s: %s -> %s", payload.document_id,
                         decision.decision.value, output.document_status.value)
        return output

    # ---------------------------------------------------------------- outcomes
    def _complete(self, p: WorkflowInput) -> WorkflowOutput:
        if not p.fields:
            raise WorkflowError("No data was supplied for an approved document.",
                                code="NO_FINAL_DATA", status_code=400)
        now = self._clock()
        record = {
            "document_id": p.document_id,
            "document_type": p.document_type,
            "original_filename": p.original_filename,
            "fields": dict(p.fields),
            "normalized_fields": p.normalized_fields,
            "source": SOURCE_BY_DECISION[p.decision.decision],
            "corrected_fields": list(p.corrected_fields),
            "validation_status": p.validation_status,
            "decision": p.decision.decision.value,
            "completed_at": now.isoformat(),
        }
        actions = [self._action("store_final_record", now,
                                f"Final record prepared (source: {record['source']}).")]
        path = self.exporter.export(p.document_id, record)
        actions.append(self._action("export_record", self._clock(), f"Exported to {path}"))
        return WorkflowOutput(
            document_id=p.document_id, decision=p.decision.decision,
            workflow_status=WorkflowStatus.COMPLETED, document_status=DocumentStatus.COMPLETED,
            final_record=record, export_path=path, actions=actions, completed_at=self._clock(),
        )

    def _await_review(self, p: WorkflowInput) -> WorkflowOutput:
        priority = p.decision.review_priority or "normal"
        return WorkflowOutput(
            document_id=p.document_id, decision=p.decision.decision,
            workflow_status=WorkflowStatus.AWAITING_REVIEW, document_status=DocumentStatus.PENDING_REVIEW,
            actions=[self._action("queue_for_review", self._clock(),
                                  f"Waiting in the review queue (priority: {priority}).")],
        )

    def _reject(self, p: WorkflowInput) -> WorkflowOutput:
        now = self._clock()
        return WorkflowOutput(
            document_id=p.document_id, decision=p.decision.decision,
            workflow_status=WorkflowStatus.REJECTED, document_status=DocumentStatus.REJECTED,
            actions=[
                self._action("mark_rejected", now, p.decision.summary),
                self._action("export_record", now, "Rejected documents are not exported.", status="skipped"),
            ],
            completed_at=now,
        )

    @staticmethod
    def _action(name: str, when: datetime, detail: str, status: str = "done") -> WorkflowAction:
        return WorkflowAction(name=name, status=status, timestamp=when, detail=detail)