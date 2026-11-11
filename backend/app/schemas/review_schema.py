from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.decision_schema import DecisionOutput
from app.schemas.document_schema import (
    DecisionRead,
    DocumentRead,
    ExtractionRead,
    ReviewRead,
    ValidationRead,
)
from app.schemas.extraction_schema import FieldSpec
from app.schemas.workflow_schema import WorkflowOutput


class ApproveRequest(BaseModel):
    # Only send the fields you want to change; use null or "" to clear a value.
    corrections: dict[str, Optional[str]] = Field(default_factory=dict)
    notes: Optional[str] = None


class RejectRequest(BaseModel):
    notes: Optional[str] = None


class ReviewResult(BaseModel):
    decision: DecisionOutput
    workflow: Optional[WorkflowOutput] = None
    workflow_error: Optional[str] = None     # set when the review was saved but the workflow step failed


class PendingReviewItem(BaseModel):
    document_id: str
    original_filename: str
    upload_timestamp: datetime
    queued_at: datetime
    priority: str
    summary: Optional[str] = None
    reasons: list[dict[str, Any]] = Field(default_factory=list)
    flagged_fields: list[str] = Field(default_factory=list)


class ReviewDetail(BaseModel):
    document: DocumentRead
    review: ReviewRead
    extraction: Optional[ExtractionRead] = None
    validation: Optional[ValidationRead] = None
    decision: Optional[DecisionRead] = None
    field_specs: list[FieldSpec] = Field(default_factory=list)
    page_urls: list[str] = Field(default_factory=list)