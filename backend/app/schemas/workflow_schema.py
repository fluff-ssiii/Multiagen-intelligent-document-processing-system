from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.decision_schema import DecisionOutput, DecisionType
from app.schemas.document_schema import DocumentStatus


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    REJECTED = "rejected"


class WorkflowAction(BaseModel):
    name: str
    status: str = "done"            # done | skipped
    timestamp: datetime
    detail: Optional[str] = None


class WorkflowInput(BaseModel):
    document_id: str
    document_type: str = "invoice"
    original_filename: Optional[str] = None
    decision: DecisionOutput
    fields: Optional[dict[str, Optional[str]]] = None    # data to store when the decision is an approval
    normalized_fields: Optional[dict[str, Any]] = None
    validation_status: Optional[str] = None
    corrected_fields: list[str] = Field(default_factory=list)


class WorkflowOutput(BaseModel):
    document_id: str
    decision: DecisionType
    workflow_status: WorkflowStatus
    document_status: DocumentStatus
    final_record: Optional[dict[str, Any]] = None
    export_path: Optional[str] = None
    actions: list[WorkflowAction] = Field(default_factory=list)
    completed_at: Optional[datetime] = None                # set for terminal outcomes only