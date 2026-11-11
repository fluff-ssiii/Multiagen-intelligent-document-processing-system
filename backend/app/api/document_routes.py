from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents.ingestion_agent import IngestionAgent
from app.core.config import settings
from app.core.exceptions import AgentError
from app.database import repository
from app.database.connection import get_db
from app.orchestrator.pipeline import PipelineOrchestrator, run_pipeline_background
from app.schemas.document_schema import (
    DecisionRead,
    DocumentRead,
    DocumentResults,
    ExtractionRead,
    ProcessAccepted,
    ProcessingLogRead,
    ReviewRead,
    ValidationRead,
)
from app.schemas.pipeline_schema import PipelineResult
from app.utils.response_utils import api_error

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read(settings.max_upload_size_bytes + 1)
    try:
        receipt = IngestionAgent().receive(file.filename or "document", content)
    except AgentError as exc:
        raise api_error(exc.status_code, exc.code, exc.message)
    return repository.create_document(db, receipt)


@router.get("", response_model=list[DocumentRead])
def list_documents(
    skip: int = 0,
    limit: int = Query(50, le=200),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return repository.list_documents(db, skip=skip, limit=limit, status=status)


@router.post("/{document_id}/process", response_model=Union[ProcessAccepted, PipelineResult],
             status_code=202)
def process_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    response: Response,
    wait: bool = False,
    db: Session = Depends(get_db),
):
    """Start processing. Default: 202 and runs in the background.
    With ?wait=true the pipeline runs synchronously and the full result is returned."""
    orchestrator = PipelineOrchestrator(db)
    try:
        orchestrator.start(document_id)
    except AgentError as exc:
        raise api_error(exc.status_code, exc.code, exc.message)

    if wait:
        response.status_code = 200
        return orchestrator.execute(document_id)

    background_tasks.add_task(run_pipeline_background, document_id)
    return ProcessAccepted(document_id=document_id, status="ingesting")


@router.get("/{document_id}/results", response_model=DocumentResults)
def get_results(document_id: str, db: Session = Depends(get_db)):
    doc = repository.get_document(db, document_id)
    if doc is None:
        raise api_error(404, "NOT_FOUND", "Document not found.")
    extraction = repository.get_latest_extraction(db, document_id)
    validation = repository.get_latest_validation(db, document_id)
    decision = repository.get_latest_decision(db, document_id)
    review = repository.get_latest_review(db, document_id)
    logs = repository.get_processing_logs(db, document_id)
    return DocumentResults(
        document=DocumentRead.model_validate(doc),
        extraction=ExtractionRead.model_validate(extraction) if extraction else None,
        validation=ValidationRead.model_validate(validation) if validation else None,
        decision=DecisionRead.model_validate(decision) if decision else None,
        review=ReviewRead.model_validate(review) if review else None,
        logs=[ProcessingLogRead.model_validate(log) for log in logs],
    )


@router.get("/{document_id}/pages/{page_number}")
def get_page_image(document_id: str, page_number: int, db: Session = Depends(get_db)):
    """Processed page image, so reviewers can compare extracted fields with the document."""
    if repository.get_document(db, document_id) is None or page_number < 1:
        raise api_error(404, "NOT_FOUND", "Page not found.")
    path = Path(settings.upload_dir) / document_id / "pages" / f"page_{page_number:03d}.png"
    if not path.is_file():
        raise api_error(404, "NOT_FOUND", "Page image not found. Has the document been processed?")
    return FileResponse(path, media_type="image/png")


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = repository.get_document(db, document_id)
    if doc is None:
        raise api_error(404, "NOT_FOUND", "Document not found.")
    return doc