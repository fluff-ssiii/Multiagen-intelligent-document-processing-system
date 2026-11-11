from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.extraction_agent import ExtractionAgent
from app.agents.ingestion_agent import IngestionAgent
from app.core.config import Settings
from app.core.exceptions import WorkflowError
from app.database import models  # noqa: F401  (register tables)
from app.database import repository
from app.database.connection import Base
from app.orchestrator.pipeline import PipelineOrchestrator
from app.services.model_service import ModelBackend, ModelResponse
from app.services.storage_service import StorageService


class ScriptedBackend(ModelBackend):
    """Test double: each entry is a response string, a ModelResponse, or an exception to raise.
    Never use it to produce reported metrics."""
    name = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def generate(self, image_paths, prompt, max_new_tokens):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ModelResponse):
            return item
        return ModelResponse(text=item, model_name="scripted")


class FlakyExporter:
    """Test double for ExportService: fails `failures` times, then succeeds."""

    def __init__(self, failures: int, retryable: bool = False):
        self.failures, self.retryable, self.calls = failures, retryable, 0

    def export(self, document_id, record):
        self.calls += 1
        if self.calls <= self.failures:
            raise WorkflowError("disk full", code="EXPORT_FAILED", retryable=self.retryable)
        return f"memory://{document_id}"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture
def cfg(tmp_path):
    return Settings(upload_dir=tmp_path, export_dir=tmp_path / "exports",
                    pipeline_max_retries=1, pipeline_retry_backoff_seconds=0.0)


@pytest.fixture
def flaky_exporter():
    return lambda failures, retryable=False: FlakyExporter(failures, retryable)


def png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def make_pipeline(db, cfg, tmp_path):
    """Returns build(script) -> (orchestrator, upload receipt, backend); creates a new document each call."""
    def build(script):
        ingestion = IngestionAgent(storage=StorageService(tmp_path), config=cfg)
        backend = ScriptedBackend(script)
        orchestrator = PipelineOrchestrator(
            db, ingestion_agent=ingestion,
            extraction_agent=ExtractionAgent(backend=backend, config=cfg),
            config=cfg, sleep=lambda s: None,
        )
        receipt = ingestion.receive("inv.png", png_bytes())
        repository.create_document(db, receipt)
        return orchestrator, receipt, backend
    return build