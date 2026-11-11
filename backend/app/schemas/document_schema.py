from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DECIDING = "deciding"
    APPROVED = "approved"            # decided (or reviewed) as OK; waiting for the workflow stage
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


BUSY_STATUSES = (
    DocumentStatus.INGESTING,
    DocumentStatus.EXTRACTING,
    DocumentStatus.VALIDATING,
    DocumentStatus.DECIDING,
)


class UploadReceipt(BaseModel):
    document_id: str
    original_filename: str
    stored_path: str
    file_type: str
    file_size_bytes: int
    sha256: str
    page_count: Optional[int] = None


class IngestionInput(BaseModel):
    document_id: str
    file_path: str


class PageImage(BaseModel):
    page_number: int
    image_path: str
    width: int
    height: int
    original_width: int
    original_height: int
    blur_score: float
    exif_rotated: bool = False
    source_type: str


class IngestionOutput(BaseModel):
    document_id: str
    file_type: str
    page_count: int
    pages: list[PageImage]
    warnings: list[str] = Field(default_factory=list)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: Optional[int] = None
    status: str
    upload_timestamp: datetime
    processing_duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class ProcessAccepted(BaseModel):
    document_id: str
    status: str
    message: str = "Processing started. Poll GET /api/documents/{id} for status."


class ExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: Optional[str] = None
    model_name: Optional[str] = None
    predicted_fields: Optional[dict[str, Any]] = None
    confidence: Optional[dict[str, Any]] = None
    parse_ok: bool = True
    generation_ms: Optional[int] = None
    raw_model_output: Optional[str] = None
    created_at: datetime


class ValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str = "initial"
    status: str
    is_valid: bool
    checks: Optional[dict[str, Any]] = None
    issues: Optional[list[dict[str, Any]]] = None
    normalized_fields: Optional[dict[str, Any]] = None
    created_at: datetime


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision: str
    decision_reason: Optional[str] = None
    workflow_status: str
    details: Optional[dict[str, Any]] = None
    final_data: Optional[dict[str, Any]] = None
    actions: Optional[list[dict[str, Any]]] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    priority: str
    human_corrections: Optional[dict[str, Any]] = None
    final_fields: Optional[dict[str, Any]] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class ProcessingLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    status: str
    message: Optional[str] = None
    duration_ms: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime


class DocumentResults(BaseModel):
    document: DocumentRead
    extraction: Optional[ExtractionRead] = None
    validation: Optional[ValidationRead] = None
    decision: Optional[DecisionRead] = None
    review: Optional[ReviewRead] = None
    logs: list[ProcessingLogRead] = Field(default_factory=list)