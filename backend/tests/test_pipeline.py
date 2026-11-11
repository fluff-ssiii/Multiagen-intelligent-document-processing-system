import json
from pathlib import Path

import pytest

from app.agents.workflow_agent import WorkflowAgent
from app.core.exceptions import ExtractionError, PipelineError
from app.database import repository
from app.services.model_service import ModelResponse

GOOD = ('{"invoice_number": "PO-1", "date_of_issue": "10/19/2023", "date_due": "11/21/2023", '
        '"client_name": "ACME", "client_address": null, "total_items": 4, "total_amount": "$9834"}')


def test_happy_path_is_completed_and_exported(db, cfg, make_pipeline):
    orch, receipt, _ = make_pipeline([GOOD])
    result = orch.process_document(receipt.document_id)

    assert result.success and result.status == "completed"
    assert [s.agent_name for s in result.steps] == [
        "ingestion_agent", "extraction_agent", "validation_agent", "decision_agent", "workflow_agent"]
    assert result.decision.decision.value == "auto_approved"

    doc = repository.get_document(db, receipt.document_id)
    assert doc.status == "completed" and doc.page_count == 1
    assert doc.processing_duration_ms is not None and doc.error_message is None
    assert repository.get_latest_extraction(db, receipt.document_id).predicted_fields["invoice_number"] == "PO-1"
    assert repository.get_latest_validation(db, receipt.document_id).status == "valid"
    assert repository.get_pending_review(db, receipt.document_id) is None

    row = repository.get_latest_decision(db, receipt.document_id)
    assert row.decision == "auto_approved" and row.workflow_status == "completed"
    assert row.final_data["fields"]["invoice_number"] == "PO-1" and row.final_data["source"] == "automatic"
    assert [a["name"] for a in row.actions] == ["store_final_record", "export_record"]
    assert row.completed_at is not None

    export = Path(cfg.export_dir) / f"{receipt.document_id}.json"
    assert json.loads(export.read_text(encoding="utf-8"))["fields"]["client_name"] == "ACME"

    agents = [log.agent_name for log in repository.get_processing_logs(db, receipt.document_id)]
    assert agents == ["orchestrator", "ingestion_agent", "extraction_agent", "validation_agent",
                      "decision_agent", "workflow_agent", "orchestrator"]


def test_ingestion_failure_stops_pipeline(db, make_pipeline):
    orch, receipt, backend = make_pipeline([GOOD])
    Path(receipt.stored_path).unlink()
    result = orch.process_document(receipt.document_id)

    assert not result.success and result.status == "failed"
    assert len(result.steps) == 1 and result.steps[0].error_code == "FILE_NOT_FOUND"
    assert backend.calls == 0
    assert repository.get_latest_extraction(db, receipt.document_id) is None
    assert "FILE_NOT_FOUND" in repository.get_document(db, receipt.document_id).error_message


def test_retryable_failure_is_retried(db, make_pipeline):
    flaky = ExtractionError("GPU out of memory", code="GPU_OOM", retryable=True)
    orch, receipt, backend = make_pipeline([flaky, GOOD])
    result = orch.process_document(receipt.document_id)

    assert result.success and result.steps[1].attempts == 2 and backend.calls == 2
    logs = repository.get_processing_logs(db, receipt.document_id)
    assert [l.status for l in logs if l.agent_name == "extraction_agent"] == ["failed", "success"]


def test_non_retryable_failure_is_not_retried(db, make_pipeline):
    fatal = ExtractionError("bad model config", code="MODEL_LOAD_FAILED", retryable=False)
    orch, receipt, backend = make_pipeline([fatal, GOOD])
    result = orch.process_document(receipt.document_id)

    assert not result.success and result.steps[1].attempts == 1 and backend.calls == 1
    assert repository.get_document(db, receipt.document_id).status == "failed"


def test_unparseable_output_goes_to_review(db, make_pipeline):
    orch, receipt, _ = make_pipeline(["garbage", "more garbage"])
    result = orch.process_document(receipt.document_id)

    assert result.success and result.status == "pending_review"
    assert result.steps[-1].agent_name == "workflow_agent"
    assert repository.get_latest_extraction(db, receipt.document_id).parse_ok is False
    assert repository.get_latest_validation(db, receipt.document_id).status == "invalid"
    review = repository.get_pending_review(db, receipt.document_id)
    assert review is not None and review.priority == "high"
    row = repository.get_latest_decision(db, receipt.document_id)
    assert row.workflow_status == "awaiting_review" and row.final_data is None
    assert [a["name"] for a in row.actions] == ["queue_for_review"]


def test_duplicate_invoice_number_goes_to_review(db, make_pipeline):
    first, r1, _ = make_pipeline([GOOD])
    assert first.process_document(r1.document_id).status == "completed"
    second, r2, _ = make_pipeline([GOOD])
    result = second.process_document(r2.document_id)

    assert result.status == "pending_review"
    issues = repository.get_latest_validation(db, r2.document_id).issues
    assert any(i["rule_id"] == "DUPLICATE_DOCUMENT" for i in issues)
    reasons = repository.get_latest_decision(db, r2.document_id).details["reasons"]
    assert any(r["code"] == "BUSINESS_RULE_WARNING" for r in reasons)
    assert repository.get_pending_review(db, r2.document_id).priority == "normal"


def test_low_confidence_goes_to_review(db, make_pipeline):
    unsure = ModelResponse(text=GOOD, model_name="scripted", mean_token_prob=0.5, min_token_prob=0.1)
    orch, receipt, _ = make_pipeline([unsure])
    result = orch.process_document(receipt.document_id)

    assert result.status == "pending_review"
    assert {"LOW_MEAN_CONFIDENCE", "LOW_MIN_CONFIDENCE"} <= {r.code for r in result.decision.reasons}


def test_reprocessing_supersedes_the_pending_review(db, make_pipeline):
    orch, receipt, _ = make_pipeline(["garbage", "garbage", GOOD])
    assert orch.process_document(receipt.document_id).status == "pending_review"
    first_review = repository.get_pending_review(db, receipt.document_id)

    assert orch.process_document(receipt.document_id).status == "completed"
    assert repository.get_pending_review(db, receipt.document_id) is None
    db.refresh(first_review)
    assert first_review.status == "superseded"


def test_workflow_failure_keeps_the_approval(db, cfg, make_pipeline, flaky_exporter):
    orch, receipt, _ = make_pipeline([GOOD])
    orch.workflow = WorkflowAgent(exporter=flaky_exporter(failures=5), config=cfg)
    result = orch.process_document(receipt.document_id)

    assert not result.success and result.status == "approved"
    assert "EXPORT_FAILED" in result.error
    doc = repository.get_document(db, receipt.document_id)
    assert doc.status == "approved" and "EXPORT_FAILED" in doc.error_message
    assert repository.get_latest_decision(db, receipt.document_id).workflow_status == "pending"


def test_retryable_workflow_failure_is_retried(db, cfg, make_pipeline, flaky_exporter):
    orch, receipt, _ = make_pipeline([GOOD])
    exporter = flaky_exporter(failures=1, retryable=True)
    orch.workflow = WorkflowAgent(exporter=exporter, config=cfg)
    result = orch.process_document(receipt.document_id)

    assert result.success and result.status == "completed"
    assert result.steps[-1].attempts == 2 and exporter.calls == 2


def test_start_guards(db, make_pipeline):
    orch, receipt, _ = make_pipeline([GOOD])

    with pytest.raises(PipelineError) as e:
        orch.start("does-not-exist")
    assert e.value.code == "NOT_FOUND"

    repository.update_document(db, receipt.document_id, status="extracting")
    with pytest.raises(PipelineError) as e:
        orch.start(receipt.document_id)
    assert e.value.code == "ALREADY_PROCESSING"

    repository.update_document(db, receipt.document_id, status="failed")
    orch.start(receipt.document_id)  # reprocessing a failed document is allowed