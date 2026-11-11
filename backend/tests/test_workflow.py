import json
from datetime import datetime, timezone

from app.agents.workflow_agent import WorkflowAgent
from app.schemas.decision_schema import DecisionOutput, DecisionStage, DecisionType
from app.schemas.workflow_schema import WorkflowInput
from app.services.export_service import ExportService

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
FIELDS = {"invoice_number": "PO-1", "client_name": "ACME", "total_amount": "$9834"}


def run(agent, kind, doc_id="d1", fields=FIELDS, corrected=(), priority=None):
    decision = DecisionOutput(document_id=doc_id, decision=kind, stage=DecisionStage.INITIAL,
                              summary="because", review_priority=priority)
    return agent.run(WorkflowInput(
        document_id=doc_id, original_filename="inv.png", decision=decision, fields=fields,
        corrected_fields=list(corrected), validation_status="valid",
        normalized_fields={"total_amount": "9834"}))


def make_agent(tmp_path, exporter=None):
    return WorkflowAgent(exporter=exporter or ExportService(tmp_path / "exports"), clock=lambda: NOW)


def test_auto_approved_is_completed_and_exported(tmp_path):
    res = run(make_agent(tmp_path), DecisionType.AUTO_APPROVED)
    out = res.output
    assert res.ok and out.workflow_status.value == "completed" and out.document_status.value == "completed"
    assert out.final_record["source"] == "automatic" and out.final_record["fields"] == FIELDS
    assert [a.name for a in out.actions] == ["store_final_record", "export_record"]
    assert all(a.timestamp == NOW for a in out.actions) and out.completed_at == NOW
    exported = json.loads((tmp_path / "exports" / "d1.json").read_text(encoding="utf-8"))
    assert exported["fields"] == FIELDS and exported["decision"] == "auto_approved"


def test_provenance_of_reviewed_records(tmp_path):
    agent = make_agent(tmp_path)
    corrected = run(agent, DecisionType.APPROVED_AFTER_CORRECTION, corrected=["invoice_number"]).output
    assert corrected.final_record["source"] == "human_corrected"
    assert corrected.final_record["corrected_fields"] == ["invoice_number"]
    confirmed = run(agent, DecisionType.APPROVED_AFTER_REVIEW, doc_id="d2").output
    assert confirmed.final_record["source"] == "human_confirmed"


def test_human_review_waits_without_exporting(tmp_path):
    out = run(make_agent(tmp_path), DecisionType.HUMAN_REVIEW, priority="high").output
    assert out.workflow_status.value == "awaiting_review" and out.document_status.value == "pending_review"
    assert out.final_record is None and out.completed_at is None
    assert [a.name for a in out.actions] == ["queue_for_review"] and "high" in out.actions[0].detail
    assert not (tmp_path / "exports").exists()


def test_rejected_is_recorded_but_not_exported(tmp_path):
    out = run(make_agent(tmp_path), DecisionType.REJECTED).output
    assert out.workflow_status.value == "rejected" and out.document_status.value == "rejected"
    assert [(a.name, a.status) for a in out.actions] == [("mark_rejected", "done"), ("export_record", "skipped")]
    assert out.completed_at == NOW and not (tmp_path / "exports").exists()


def test_approved_without_data_fails(tmp_path):
    res = run(make_agent(tmp_path), DecisionType.AUTO_APPROVED, fields=None)
    assert not res.ok and res.error_code == "NO_FINAL_DATA"


def test_document_mismatch(tmp_path):
    decision = DecisionOutput(document_id="other", decision=DecisionType.AUTO_APPROVED,
                              stage=DecisionStage.INITIAL, summary="x")
    res = make_agent(tmp_path).run(WorkflowInput(document_id="d1", decision=decision, fields=FIELDS))
    assert not res.ok and res.error_code == "DOCUMENT_MISMATCH"


def test_export_failure_is_retryable(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, so a directory cannot be created below it")
    res = run(make_agent(tmp_path, ExportService(blocker / "exports")), DecisionType.AUTO_APPROVED)
    assert not res.ok and res.error_code == "EXPORT_FAILED" and res.retryable


def test_unsafe_document_id_is_refused(tmp_path):
    res = run(make_agent(tmp_path), DecisionType.AUTO_APPROVED, doc_id="../evil")
    assert not res.ok and res.error_code == "INVALID_DOCUMENT_ID"