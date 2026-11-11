from typing import Optional

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.models import (
    Document,
    ExtractedData,
    ProcessingLog,
    ReviewRecord,
    ValidationResult,
    WorkflowRecord,
)
from app.schemas.decision_schema import DecisionOutput, DecisionType
from app.schemas.document_schema import UploadReceipt
from app.schemas.extraction_schema import ExtractionOutput
from app.schemas.validation_schema import ValidationOutput
from app.schemas.workflow_schema import WorkflowOutput


# ---- documents
def create_document(db: Session, receipt: UploadReceipt) -> Document:
    doc = Document(
        id=receipt.document_id,
        original_filename=receipt.original_filename,
        file_path=receipt.stored_path,
        file_type=receipt.file_type,
        file_size_bytes=receipt.file_size_bytes,
        sha256=receipt.sha256,
        page_count=receipt.page_count,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: str) -> Optional[Document]:
    return db.get(Document, document_id)


def list_documents(db: Session, skip: int = 0, limit: int = 50, status: Optional[str] = None) -> list[Document]:
    stmt = select(Document).order_by(Document.upload_timestamp.desc()).offset(skip).limit(limit)
    if status:
        stmt = stmt.where(Document.status == status)
    return list(db.scalars(stmt))


def update_document(db: Session, document_id: str, **fields) -> Optional[Document]:
    doc = db.get(Document, document_id)
    if doc is None:
        return None
    for key, value in fields.items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


def claim_document(db: Session, document_id: str, new_status: str, busy_statuses: list[str]) -> bool:
    """Atomically move a document into `new_status` unless it is already being processed."""
    stmt = (
        update(Document)
        .where(Document.id == document_id, Document.status.not_in(busy_statuses))
        .values(status=new_status, error_message=None, processing_duration_ms=None)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1


# ---- processing logs
def add_processing_log(
    db: Session, document_id: str, agent_name: str, status: str,
    message: Optional[str] = None, duration_ms: Optional[int] = None, details: Optional[dict] = None,
) -> ProcessingLog:
    log = ProcessingLog(document_id=document_id, agent_name=agent_name, status=status,
                        message=message, duration_ms=duration_ms, details=details)
    db.add(log)
    db.commit()
    return log


def get_processing_logs(db: Session, document_id: str) -> list[ProcessingLog]:
    stmt = select(ProcessingLog).where(ProcessingLog.document_id == document_id).order_by(ProcessingLog.id)
    return list(db.scalars(stmt))


# ---- extraction
def save_extraction(db: Session, output: ExtractionOutput) -> ExtractedData:
    row = ExtractedData(
        document_id=output.document_id,
        document_type=output.document_type,
        model_name=output.extractor_name,
        predicted_fields=output.fields,
        confidence=output.confidence,
        raw_model_output=output.raw_output,
        parse_ok=output.parse_ok,
        generation_ms=output.generation_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_extraction(db: Session, document_id: str) -> Optional[ExtractedData]:
    stmt = (select(ExtractedData).where(ExtractedData.document_id == document_id)
            .order_by(ExtractedData.id.desc()).limit(1))
    return db.scalars(stmt).first()


# ---- validation
def save_validation(db: Session, output: ValidationOutput, stage: str = "initial") -> ValidationResult:
    row = ValidationResult(
        document_id=output.document_id,
        stage=stage,
        status=output.status.value,
        is_valid=output.is_valid,
        checks=output.checks,
        issues=[i.model_dump(mode="json") for i in [*output.errors, *output.warnings]],
        normalized_fields=output.normalized_fields,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_validation(db: Session, document_id: str) -> Optional[ValidationResult]:
    stmt = (select(ValidationResult).where(ValidationResult.document_id == document_id)
            .order_by(ValidationResult.id.desc()).limit(1))
    return db.scalars(stmt).first()


def find_documents_with_field_value(db: Session, field: str, value: str,
                                    exclude_document_id: str) -> list[str]:
    """Other documents whose latest extraction has `field == value`."""
    latest_ids = select(func.max(ExtractedData.id)).group_by(ExtractedData.document_id)
    stmt = (
        select(ExtractedData.document_id)
        .where(
            ExtractedData.id.in_(latest_ids),
            ExtractedData.document_id != exclude_document_id,
            ExtractedData.predicted_fields[field].as_string() == value,
        )
    )
    return list(db.scalars(stmt))


# ---- decisions + workflow outcome (both live in workflow_records)
def save_decision(db: Session, output: DecisionOutput) -> WorkflowRecord:
    row = WorkflowRecord(
        document_id=output.document_id,
        decision=output.decision.value,
        decision_reason=output.summary,
        workflow_status="pending",      # the workflow stage sets the real outcome
        details=output.model_dump(mode="json", exclude={"document_id", "summary"}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_decision(db: Session, document_id: str) -> Optional[WorkflowRecord]:
    stmt = (select(WorkflowRecord).where(WorkflowRecord.document_id == document_id)
            .order_by(WorkflowRecord.id.desc()).limit(1))
    return db.scalars(stmt).first()


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    return None if value is None else value.astimezone(timezone.utc).replace(tzinfo=None)


def apply_workflow_result(db: Session, workflow_record_id: int, output: WorkflowOutput) -> None:
    """Store the workflow outcome and the document's new status in ONE commit."""
    row = db.get(WorkflowRecord, workflow_record_id)
    if row is None:
        raise LookupError(f"workflow record {workflow_record_id} not found")
    row.workflow_status = output.workflow_status.value
    row.final_data = output.final_record
    row.actions = [a.model_dump(mode="json") for a in output.actions]
    row.completed_at = _naive_utc(output.completed_at)
    doc = db.get(Document, row.document_id)
    doc.status = output.document_status.value
    db.commit()


# ---- reviews
def supersede_pending_reviews(db: Session, document_id: str) -> int:
    stmt = (update(ReviewRecord)
            .where(ReviewRecord.document_id == document_id, ReviewRecord.status == "pending")
            .values(status="superseded", reviewed_at=func.now()))
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def create_review(db: Session, document_id: str, priority: str,
                  extraction_id: Optional[int] = None) -> ReviewRecord:
    row = ReviewRecord(document_id=document_id, status="pending", priority=priority,
                       extraction_id=extraction_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_pending_review(db: Session, document_id: str) -> Optional[ReviewRecord]:
    stmt = (select(ReviewRecord)
            .where(ReviewRecord.document_id == document_id, ReviewRecord.status == "pending")
            .order_by(ReviewRecord.id.desc()).limit(1))
    return db.scalars(stmt).first()


def get_latest_review(db: Session, document_id: str) -> Optional[ReviewRecord]:
    stmt = (select(ReviewRecord).where(ReviewRecord.document_id == document_id)
            .order_by(ReviewRecord.id.desc()).limit(1))
    return db.scalars(stmt).first()


def list_pending_reviews(db: Session, skip: int = 0, limit: int = 50) -> list[ReviewRecord]:
    """High priority first, then oldest first."""
    priority_order = case((ReviewRecord.priority == "high", 0), else_=1)
    stmt = (select(ReviewRecord).where(ReviewRecord.status == "pending")
            .order_by(priority_order, ReviewRecord.created_at, ReviewRecord.id)
            .offset(skip).limit(limit))
    return list(db.scalars(stmt))


def complete_review(
    db: Session, review_id: int, *, status: str, human_corrections: Optional[dict],
    final_fields: Optional[dict], notes: Optional[str],
) -> bool:
    """Atomically close a pending review. Returns False if it was no longer pending."""
    stmt = (
        update(ReviewRecord)
        .where(ReviewRecord.id == review_id, ReviewRecord.status == "pending")
        .values(status=status, human_corrections=human_corrections, final_fields=final_fields,
                reviewer_notes=notes, reviewed_at=func.now())
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1