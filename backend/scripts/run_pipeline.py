"""Usage (from backend/):  python -m scripts.run_pipeline path/to/invoice.jpg"""
import json
import sys
from pathlib import Path

from app.agents.ingestion_agent import IngestionAgent
from app.core.logging_config import setup_logging
from app.database import repository
from app.database.connection import SessionLocal, init_db
from app.orchestrator.pipeline import PipelineOrchestrator

setup_logging()
init_db()
path = Path(sys.argv[1])

with SessionLocal() as db:
    receipt = IngestionAgent().receive(path.name, path.read_bytes())
    repository.create_document(db, receipt)
    result = PipelineOrchestrator(db).process_document(receipt.document_id)
    print(json.dumps(result.model_dump(mode="json", exclude={"extraction": {"raw_output"}}), indent=2))