from datetime import date

import pytest

from app.agents.decision_agent import DecisionAgent
from app.agents.validation_agent import ValidationAgent
from app.core.config import Settings
from app.schemas.decision_schema import DecisionInput, DecisionStage, DecisionType
from app.schemas.validation_schema import ValidationInput

GOOD = {
    "invoice_number": "PO-629227", "date_of_issue": "10/19/2023", "date_due": "11/21/2023",
    "client_name": "East Cliff Supply Co. Ltd.", "client_address": None,
    "total_items": "4", "total_amount": "$1,700",
}
ALL_REQUIRED = ["invoice_number", "date_of_issue", "date_due", "client_name", "total_items", "total_amount"]


def validate(fields, **kwargs):
    agent = ValidationAgent(config=Settings(), today=date(2026, 11, 10))
    res = agent.run(ValidationInput(document_id="d1", fields=fields, **kwargs))
    assert res.ok
    return res.output


def decide(validation, *, parse_ok=True, missing=None, confidence=None,
           stage=DecisionStage.INITIAL, corrections=0, **cfg):
    agent = DecisionAgent(config=Settings(**cfg))
    res = agent.run(DecisionInput(
        document_id="d1", stage=stage, extraction_parse_ok=parse_ok,
        extraction_missing_fields=missing or [], extraction_confidence=confidence,
        validation=validation, corrections_count=corrections))
    assert res.ok, res.error
    return res.output


def codes(out):
    return {r.code for r in out.reasons}


def test_clean_document_is_auto_approved():
    out = decide(validate(GOOD))
    assert out.decision == DecisionType.AUTO_APPROVED and out.review_priority is None
    assert "ALL_CHECKS_PASSED" in codes(out) and "CONFIDENCE_UNAVAILABLE" in codes(out)


def test_validation_errors_go_to_review_with_high_priority():
    out = decide(validate({**GOOD, "invoice_number": None}), missing=["invoice_number"])
    assert out.decision == DecisionType.HUMAN_REVIEW and out.review_priority == "high"
    assert "VALIDATION_ERRORS" in codes(out) and out.flagged_fields == ["invoice_number"]


AMBIGUOUS = {**GOOD, "date_of_issue": "12/10/2023", "date_due": "07/11/2023"}


def test_warnings_go_to_review_unless_tolerated():
    out = decide(validate(AMBIGUOUS))
    assert out.decision == DecisionType.HUMAN_REVIEW and out.review_priority == "normal"
    assert decide(validate(AMBIGUOUS), decision_auto_approve_warnings=True).decision == DecisionType.AUTO_APPROVED


def test_duplicate_always_needs_review():
    v = validate(GOOD, duplicates={"invoice_number": ["other"]})
    out = decide(v, decision_auto_approve_warnings=True)
    assert out.decision == DecisionType.HUMAN_REVIEW and "BUSINESS_RULE_WARNING" in codes(out)


def test_confidence_thresholds():
    v = validate(GOOD)
    good = {"mean_token_prob": 0.95, "min_token_prob": 0.60}
    assert decide(v, confidence=good).decision == DecisionType.AUTO_APPROVED
    low_mean = decide(v, confidence={"mean_token_prob": 0.5, "min_token_prob": 0.6})
    assert low_mean.decision == DecisionType.HUMAN_REVIEW and "LOW_MEAN_CONFIDENCE" in codes(low_mean)
    low_min = decide(v, confidence={"mean_token_prob": 0.95, "min_token_prob": 0.05})
    assert "LOW_MIN_CONFIDENCE" in codes(low_min)
    off = decide(v, confidence={"mean_token_prob": 0.1, "min_token_prob": 0.01},
                 decision_min_mean_token_prob=0, decision_min_token_prob=0)
    assert off.decision == DecisionType.AUTO_APPROVED


def test_parse_failure_is_reviewed_not_rejected():
    v = validate({k: None for k in GOOD}, extraction_parse_ok=False)
    out = decide(v, parse_ok=False, missing=ALL_REQUIRED + ["client_address"])
    assert out.decision == DecisionType.HUMAN_REVIEW and out.review_priority == "high"
    assert codes(out) >= {"EXTRACTION_PARSE_FAILED"} and "VALIDATION_ERRORS" not in codes(out)


def test_unreadable_document_is_rejected():
    fields = {k: None for k in GOOD}
    fields["client_name"] = "ACME"
    missing = [f for f in ALL_REQUIRED if f != "client_name"]          # 5 of 6 required missing
    out = decide(validate(fields), missing=missing)
    assert out.decision == DecisionType.REJECTED and "UNREADABLE_DOCUMENT" in codes(out)
    # 4 of 6 missing is below the 0.75 threshold -> review instead
    out = decide(validate(fields), missing=missing[:4])
    assert out.decision == DecisionType.HUMAN_REVIEW


def test_post_correction_outcomes():
    ok = validate(AMBIGUOUS)                                            # warnings only
    assert decide(ok, stage=DecisionStage.POST_CORRECTION, corrections=2).decision == \
        DecisionType.APPROVED_AFTER_CORRECTION
    assert decide(ok, stage=DecisionStage.POST_CORRECTION, corrections=0).decision == \
        DecisionType.APPROVED_AFTER_REVIEW
    bad = validate({**GOOD, "invoice_number": None})
    out = decide(bad, stage=DecisionStage.POST_CORRECTION, corrections=1)
    assert out.decision == DecisionType.HUMAN_REVIEW and not out.is_approved


def test_reviewer_rejection():
    out = decide(None, stage=DecisionStage.REVIEWER_REJECTED)
    assert out.decision == DecisionType.REJECTED and "REVIEWER_REJECTED" in codes(out)


def test_missing_validation_fails_cleanly():
    res = DecisionAgent(config=Settings()).run(DecisionInput(document_id="d1"))
    assert not res.ok and res.error_code == "MISSING_VALIDATION"