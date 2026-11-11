"""Usage (from backend/):  python -m scripts.try_extraction path/to/invoice.jpg"""
import json
import sys
from pathlib import Path

from app.agents.extraction_agent import ExtractionAgent
from app.agents.ingestion_agent import IngestionAgent
from app.core.logging_config import setup_logging
from app.schemas.document_schema import IngestionInput
from app.schemas.extraction_schema import ExtractionInput

setup_logging()
path = Path(sys.argv[1])

ingestion = IngestionAgent()
receipt = ingestion.receive(path.name, path.read_bytes())
ing = ingestion.run(IngestionInput(document_id=receipt.document_id, file_path=receipt.stored_path))
assert ing.ok, ing.error

ext = ExtractionAgent().run(ExtractionInput(document_id=receipt.document_id, pages=ing.output.pages))
print(json.dumps(ext.model_dump(mode="json"), indent=2))