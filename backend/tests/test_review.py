import json
from pathlib import Path

import pytest

from app.agents.workflow_agent import WorkflowAgent
from app.core.exceptions import ReviewError
from app.database import repository
from app.schemas.decision_schema import DecisionType
from app.services.review_service import ReviewService

GOOD = ('{"invoice_number": "PO-1", "date_of_issue": "10/19/2023", "date_due": "11/21/2023", '
        '"client_name": "ACME", "client_address": null, "total_items": 4, "total_amount": "$9834"}')
MISSING_NUMBER = GOOD.replace('"invoice_number": "PO-1"', '"invoice_number": null')
AMBIGUOUS_DATES = GOOD.replace('"10/19/2023"', '"12/10/2023"').replace('"11/21/2023"', '"07/11/2023"')


def test_queue_and_approve_with_correction(db, cfg, make_pipeline):
    orch, receipt, _ = make_pipeline([MISSING_NUMBER])
    orch.process_document(receipt.document_id)
    service = ReviewService(db, config=cfg)

    assert [r.document_id for r in service.pending()] == [receipt.document_id]
    result = service.approve(receipt.document_id, {"invoice_number": "PO-77"}, notes="checked image")

    assert result.decision.decision == DecisionType.APPROVED_AFTER_CORRECTION
    assert result.workflow.document_status.value == "completed" and result.workflow_error is None
    assert repository.get_document(db, receipt.document_id).status == "completed"

    review = repository.get_latest_review(db, receipt.document_id)
    assert review.status == "approved" and review.reviewer_notes == "checked image"
    assert review.human_corrections == {"invoice_number": "PO-77"}
    assert review.final_fields["invoice_number"] == "PO-77" and review.final_fields["client_name"] == "ACME"
    validation = repository.get_latest_validation(db, receipt.document_id)
    assert validation.stage == "post_correction" and validation.is_valid

    row = repository.get_latest_decision(db, receipt.document_id)
    assert row.decision == "approved_after_correction" and row.workflow_status == "completed"
    assert row.final_data["source"] == "human_corrected"
    assert row.final_data["corrected_fields"] == ["invoice_number"]
    assert row.final_data["fields"]["invoice_number"] == "PO-77"
    export = Path(cfg.export_dir) / f"{receipt.document_id}.json"
    assert json.loads(export.read_text(encoding="utf-8"))["fields"]["invoice_number"] == "PO-77"
    assert service.pending() == []


def test_approval_is_blocked_while_errors_remain(db, cfg, make_pipeline):
    orch, receipt, _ = make_pipeline([MISSING_NUMBER])
    orch.process_document(receipt.document_id)

    with pytest.raises(ReviewError) as e:
        ReviewService(db, config=cfg).approve(
            receipt.document_id, {"invoice_number": "PO-77", "date_due": "01/01/2020"})
    assert e.value.code == "VALIDATION_ERRORS_REMAIN" and e.value.status_code == 422
    assert any(i["rule_id"] == "DATE_ORDER" for i in e.value.details["errors"])
    assert repository.get_pending_review(db, receipt.document_id) is not None
    assert repository.get_document(db, receipt.document_id).status == "pending_review"
    assert repository.get_latest_decision(db, receipt.document_id).decision == "human_review"


def test_approve_without_changes(db, cfg, make_pipeline):
    orch, receipt, _ = make_pipeline([AMBIGUOUS_DATES])
    assert orch.process_document(receipt.document_id).status == "pending_review"

    result = ReviewService(db, config=cfg).approve(receipt.document_id, {})
    assert result.decision.decision == DecisionType.APPROVED_AFTER_REVIEW
    assert repository.get_latest_review(db, receipt.document_id).human_corrections == {}
    assert repository.get_latest_decision(db, receipt.document_id).final_data["source"] == "human_confirmed"


def test_unknown_field_and_wrong_state(db, cfg, make_pipeline):
    service = ReviewService(db, config=cfg)
    orch, receipt, _ = make_pipeline([MISSING_NUMBER])
    orch.process_document(receipt.document_id)

    with pytest.raises(ReviewError) as e:
        service.approve(receipt.document_id, {"colour": "red"})
    assert e.value.code == "UNKNOWN_FIELD"

    with pytest.raises(ReviewError) as e:
        service.approve("does-not-exist", {})
    assert e.value.code == "NOT_FOUND"

    orch2, receipt2, _ = make_pipeline([GOOD])           # auto-approved, never queued
    orch2.process_document(receipt2.document_id)
    with pytest.raises(ReviewError) as e:
        service.approve(receipt2.document_id, {})
    assert e.value.code == "NOT_PENDING_REVIEW" and e.value.status_code == 409


def test_reject(db, cfg, make_pipeline):
    orch, receipt, _ = make_pipeline([MISSING_NUMBER])
    orch.process_document(receipt.document_id)
    service = ReviewService(db, config=cfg)

    result = service.reject(receipt.document_id, notes="not an invoice")
    assert result.decision.decision == DecisionType.REJECTED
    assert result.workflow.document_status.value == "rejected"
    assert repository.get_document(db, receipt.document_id).status == "rejected"
    assert repository.get_latest_review(db, receipt.document_id).status == "rejected"
    row = repository.get_latest_decision(db, receipt.document_id)
    assert row.workflow_status == "rejected" and row.final_data is None
    assert [a["name"] for a in row.actions] == ["mark_rejected", "export_record"]
    with pytest.raises(ReviewError) as e:
        service.approve(receipt.document_id, {})
    assert e.value.code == "NOT_PENDING_REVIEW"


def test_workflow_failure_after_approval_is_reported_not_raised(db, cfg, make_pipeline, flaky_exporter):
    orch, receipt, _ = make_pipeline([MISSING_NUMBER])
    orch.process_document(receipt.document_id)
    service = ReviewService(db, config=cfg,
                            workflow_agent=WorkflowAgent(exporter=flaky_exporter(failures=5), config=cfg))

    result = service.approve(receipt.document_id, {"invoice_number": "PO-77"})
    assert result.workflow is None and "disk full" in result.workflow_error
    assert result.decision.decision == DecisionType.APPROVED_AFTER_CORRECTION   # the human decision stands
    doc = repository.get_document(db, receipt.document_id)
    assert doc.status == "approved" and "EXPORT_FAILED" in doc.error_message
    assert repository.get_latest_review(db, receipt.document_id).status == "approved"