from io import BytesIO

import fitz
import pytest
from PIL import Image

from app.agents.ingestion_agent import IngestionAgent
from app.core.config import Settings
from app.core.exceptions import IngestionError
from app.schemas.document_schema import IngestionInput
from app.services.storage_service import StorageService


@pytest.fixture
def agent(tmp_path):
    cfg = Settings(upload_dir=tmp_path, max_upload_size_mb=1, max_pages=3)
    return IngestionAgent(storage=StorageService(tmp_path), config=cfg)


def make_png(size=(800, 600)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG")
    return buf.getvalue()


def make_pdf(pages=2) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Invoice page {i + 1}")
    data = doc.tobytes()
    doc.close()
    return data


def test_receive_valid_image(agent):
    receipt = agent.receive("inv.png", make_png())
    assert receipt.file_type == "png" and receipt.page_count == 1


def test_rejects_bad_extension(agent):
    with pytest.raises(IngestionError) as e:
        agent.receive("x.exe", b"abc")
    assert e.value.code == "UNSUPPORTED_TYPE"


def test_rejects_spoofed_content(agent):
    with pytest.raises(IngestionError) as e:
        agent.receive("fake.pdf", make_png())
    assert e.value.code == "CONTENT_MISMATCH"


def test_rejects_empty_and_oversized(agent):
    with pytest.raises(IngestionError):
        agent.receive("a.png", b"")
    with pytest.raises(IngestionError) as e:
        agent.receive("a.png", make_png() + b"\0" * (2 * 1024 * 1024))
    assert e.value.code == "FILE_TOO_LARGE"


def test_rejects_too_many_pages(agent):
    with pytest.raises(IngestionError) as e:
        agent.receive("big.pdf", make_pdf(pages=5))
    assert e.value.code == "TOO_MANY_PAGES"


def test_pdf_to_page_images(agent):
    receipt = agent.receive("inv.pdf", make_pdf(pages=2))
    result = agent.run(IngestionInput(document_id=receipt.document_id, file_path=receipt.stored_path))
    assert result.ok
    assert result.output.page_count == 2
    assert all(p.image_path.endswith(".png") for p in result.output.pages)


def test_missing_file_returns_failed_result(agent):
    result = agent.run(IngestionInput(document_id="nope", file_path="/does/not/exist.png"))
    assert not result.ok and result.error_code == "FILE_NOT_FOUND"