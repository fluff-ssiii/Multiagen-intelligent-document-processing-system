import pytest
from PIL import Image

from app.agents.extraction_agent import ExtractionAgent
from app.core.config import Settings
from app.schemas.document_schema import PageImage
from app.schemas.extraction_schema import ExtractionInput
from app.services.model_service import ModelBackend, ModelResponse
from app.utils.json_utils import clean_value, extract_json_object


class FakeBackend(ModelBackend):
    """Test double only. Never use it to produce reported metrics."""
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts, self.image_counts = [], []

    def generate(self, image_paths, prompt, max_new_tokens):
        self.prompts.append(prompt)
        self.image_counts.append(len(image_paths))
        return ModelResponse(text=self.responses.pop(0), model_name="fake")


def make_pages(tmp_path, n=1):
    pages = []
    for i in range(1, n + 1):
        path = tmp_path / f"page_{i}.png"
        Image.new("RGB", (100, 100), "white").save(path)
        pages.append(PageImage(page_number=i, image_path=str(path), width=100, height=100,
                               original_width=100, original_height=100, blur_score=100.0,
                               source_type="image"))
    return pages


def run(backend, pages, doc_type="invoice", **cfg):
    agent = ExtractionAgent(backend=backend, config=Settings(**cfg))
    return agent.run(ExtractionInput(document_id="d1", document_type=doc_type, pages=pages))


GOOD = ('{"invoice_number": "PO-1", "date_of_issue": "10/19/2023", "date_due": "11/21/2023", '
        '"client_name": "ACME", "client_address": null, "total_items": 4, "total_amount": "$9,834"}')


def test_clean_json(tmp_path):
    res = run(FakeBackend([GOOD]), make_pages(tmp_path))
    assert res.ok and res.output.parse_ok and res.output.attempts == 1
    assert res.output.fields["invoice_number"] == "PO-1"
    assert res.output.fields["total_items"] == "4"
    assert res.output.missing_fields == ["client_address"]


def test_fenced_json_with_prose(tmp_path):
    text = f"Here you go:\n```json\n{GOOD}\n```\nHope that helps."
    res = run(FakeBackend([text]), make_pages(tmp_path))
    assert res.output.parse_ok and res.output.fields["client_name"] == "ACME"


def test_retry_after_invalid_json(tmp_path):
    backend = FakeBackend(["not json at all", GOOD])
    res = run(backend, make_pages(tmp_path))
    assert res.output.parse_ok and res.output.attempts == 2
    assert backend.prompts[1] != backend.prompts[0]


def test_always_invalid_is_reported_not_raised(tmp_path):
    res = run(FakeBackend(["nope", "still nope"]), make_pages(tmp_path))
    assert res.ok and not res.output.parse_ok
    assert all(v is None for v in res.output.fields.values())
    assert res.output.attempts == 2 and res.output.raw_output == "still nope"


def test_unknown_document_type(tmp_path):
    res = run(FakeBackend([GOOD]), make_pages(tmp_path), doc_type="passport")
    assert not res.ok and res.error_code == "UNKNOWN_DOCUMENT_TYPE"


def test_no_pages():
    res = run(FakeBackend([GOOD]), [])
    assert not res.ok and res.error_code == "NO_PAGES"


def test_page_limit(tmp_path):
    backend = FakeBackend([GOOD])
    res = run(backend, make_pages(tmp_path, 5), extraction_max_pages=2)
    assert backend.image_counts == [2]
    assert any("first 2 of 5" in w for w in res.warnings)


def test_json_helpers():
    assert extract_json_object("blah {\"a\": 1} blah") == {"a": 1}
    assert extract_json_object("[1, 2]") is None
    assert clean_value("null") is None and clean_value(" N/A ") is None
    assert clean_value(4.0) == "4" and clean_value("  x ") == "x"