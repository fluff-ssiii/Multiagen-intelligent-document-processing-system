from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(16))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    document_type: Mapped[str] = mapped_column(String(32), default="invoice")
    upload_timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processing_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    ground_truth: Mapped[Optional[dict]] = mapped_column(JSON)  # dataset annotations, kept for evaluation

    extracted_data: Mapped[list["ExtractedData"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    validation_results: Mapped[list["ValidationResult"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    workflow_records: Mapped[list["WorkflowRecord"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    review_records: Mapped[list["ReviewRecord"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(32))
    model_name: Mapped[Optional[str]] = mapped_column(String(255))
    predicted_fields: Mapped[Optional[dict]] = mapped_column(JSON)
    confidence: Mapped[Optional[dict]] = mapped_column(JSON)
    raw_model_output: Mapped[Optional[str]] = mapped_column(Text)
    parse_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    generation_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="extracted_data")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(24), default="initial")   # initial | post_correction
    status: Mapped[str] = mapped_column(String(24))      # valid | valid_with_warnings | invalid
    is_valid: Mapped[bool] = mapped_column(Boolean)
    checks: Mapped[Optional[dict]] = mapped_column(JSON)
    issues: Mapped[Optional[list]] = mapped_column(JSON)
    normalized_fields: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="validation_results")


class WorkflowRecord(Base):
    """One row per decision (history is kept). The Workflow Agent fills in the outcome."""
    __tablename__ = "workflow_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    decision_reason: Mapped[Optional[str]] = mapped_column(Text)
    workflow_status: Mapped[str] = mapped_column(String(32))   # pending | awaiting_review | completed | rejected
    details: Mapped[Optional[dict]] = mapped_column(JSON)       # decision reasons etc.
    final_data: Mapped[Optional[dict]] = mapped_column(JSON)    # approved record with provenance
    actions: Mapped[Optional[list]] = mapped_column(JSON)       # timestamped workflow actions (audit)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="workflow_records")


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|approved|rejected|superseded
    priority: Mapped[str] = mapped_column(String(8), default="normal")               # high | normal
    extraction_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)        # extraction row under review
    human_corrections: Mapped[Optional[dict]] = mapped_column(JSON)                  # only fields that changed
    final_fields: Mapped[Optional[dict]] = mapped_column(JSON)                       # corrected full record
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    document: Mapped[Document] = relationship(back_populates="review_records")


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="processing_logs")