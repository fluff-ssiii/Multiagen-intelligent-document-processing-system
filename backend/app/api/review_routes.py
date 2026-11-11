from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import AgentError
from app.database import repository
from app.database.connection import get_db
from app.schemas.document_schema import (
    DecisionRead,
    DocumentRead,
    ExtractionRead,
    ReviewRead,
    ValidationRead,
)
from app.schemas.extraction_schema import get_document_type
from app.schemas.review_schema import (
    ApproveRequest,
    PendingReviewItem,
    RejectRequest,
    ReviewDetail,
    ReviewResult,
)
from app.services.review_service import ReviewService
from app.utils.response_utils import api_error

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _raise(exc: AgentError):
    raise api_error(exc.status_code, exc.code, exc.message, getattr(exc, "details", None))


@router.get("/pending", response_model=list[PendingReviewItem])
def list_pending(skip: int = 0, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    items = []
    for review in ReviewService(db).pending(skip, limit):
        doc = review.document
        decision = repository.get_latest_decision(db, review.document_id)
        details = (decision.details or {}) if decision else {}
        items.append(PendingReviewItem(
            document_id=doc.id,
            original_filename=doc.original_filename,
            upload_timestamp=doc.upload_timestamp,
            queued_at=review.created_at,
            priority=review.priority,
            summary=decision.decision_reason if decision else None,
            reasons=details.get("reasons", []),
            flagged_fields=details.get("flagged_fields", []),
        ))
    return items


@router.get("/{document_id}", response_model=ReviewDetail)
def get_review(document_id: str, db: Session = Depends(get_db)):
    doc = repository.get_document(db, document_id)
    review = repository.get_latest_review(db, document_id) if doc else None
    if doc is None or review is None:
        raise api_error(404, "NOT_FOUND", "No review found for this document.")
    extraction = repository.get_latest_extraction(db, document_id)
    validation = repository.get_latest_validation(db, document_id)
    decision = repository.get_latest_decision(db, document_id)
    return ReviewDetail(
        document=DocumentRead.model_validate(doc),
        review=ReviewRead.model_validate(review),
        extraction=ExtractionRead.model_validate(extraction) if extraction else None,
        validation=ValidationRead.model_validate(validation) if validation else None,
        decision=DecisionRead.model_validate(decision) if decision else None,
        field_specs=get_document_type(doc.document_type).fields,
        page_urls=[f"/api/documents/{document_id}/pages/{n}" for n in range(1, (doc.page_count or 0) + 1)],
    )


@router.post("/{document_id}/approve", response_model=ReviewResult)
def approve(document_id: str, body: ApproveRequest, db: Session = Depends(get_db)):
    try:
        return ReviewService(db).approve(document_id, body.corrections, body.notes)
    except AgentError as exc:
        _raise(exc)


@router.post("/{document_id}/reject", response_model=ReviewResult)
def reject(document_id: str, body: RejectRequest, db: Session = Depends(get_db)):
    try:
        return ReviewService(db).reject(document_id, body.notes)
    except AgentError as exc:
        _raise(exc)