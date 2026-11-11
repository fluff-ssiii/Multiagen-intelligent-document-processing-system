from datetime import date
from decimal import Decimal

import pytest

from app.agents.validation_agent import ValidationAgent
from app.core.config import Settings
from app.schemas.extraction_schema import (
    DOCUMENT_TYPES, AmountSumRule, DocumentTypeSpec, FieldSpec, LineItemsRule,
)
from app.schemas.validation_schema import ValidationInput
from app.utils.parsing_utils import parse_amount, parse_date_candidates, parse_integer

GOOD = {
    "invoice_number": "PO-629227", "date_of_issue": "10/19/2023", "date_due": "11/21/2023",
    "client_name": "East Cliff Supply Co. Ltd.", "client_address": None,
    "total_items": "4", "total_amount": "$1,700",
}


def validate(fields, doc_type="invoice", **kwargs):
    agent = ValidationAgent(config=Settings(), today=date(2026, 11, 10))
    res = agent.run(ValidationInput(document_id="d1", document_type=doc_type, fields=fields, **kwargs))
    assert res.ok, res.error
    return res.output


def rules(issues):
    return {i.rule_id for i in issues}


def test_valid_document_and_normalisation():
    out = validate(GOOD)
    assert out.status.value == "valid" and out.is_valid
    assert out.normalized_fields["total_amount"] == "1700"
    assert out.normalized_fields["total_items"] == 4
    assert out.normalized_fields["date_of_issue"] == "2023-10-19"


def test_missing_required_field_is_error_but_optional_is_not():
    out = validate({**GOOD, "invoice_number": None})
    assert out.status.value == "invalid" and "REQUIRED_FIELDS" in rules(out.errors)
    assert out.flagged_fields == ["invoice_number"]
    assert validate({**GOOD, "client_address": None}).is_valid


def test_bad_formats():
    out = validate({**GOOD, "date_of_issue": "31/31/2023", "total_amount": "lots", "total_items": "four"})
    assert {"DATE_FORMAT", "AMOUNT_FORMAT", "INTEGER_FORMAT"} <= rules(out.errors)


def test_due_before_issue_is_error():
    out = validate({**GOOD, "date_of_issue": "11/21/2023", "date_due": "10/19/2023"})
    assert "DATE_ORDER" in rules(out.errors)


def test_order_depending_on_interpretation_is_warning():
    # dataset-style pair: only one of four day/month readings puts due after issue
    out = validate({**GOOD, "date_of_issue": "12/10/2023", "date_due": "07/11/2023"})
    assert out.is_valid and "DATE_ORDER" in rules(out.warnings)
    assert out.status.value == "valid_with_warnings"
    assert isinstance(out.normalized_fields["date_of_issue"], list)


def test_date_range_warning():
    out = validate({**GOOD, "date_of_issue": "01/01/1850", "date_due": "02/01/1850"})
    assert "DATE_RANGE" in rules(out.warnings)


def test_placeholder_text_warning():
    out = validate({**GOOD, "client_address": "The client's address is not provided in the image."})
    assert "SUSPICIOUS_VALUE" in rules(out.warnings) and out.is_valid


def test_duplicates():
    assert validate(GOOD, duplicates=None).checks["DUPLICATE_DOCUMENT"] == "skipped"
    assert validate(GOOD, duplicates={"invoice_number": []}).checks["DUPLICATE_DOCUMENT"] == "passed"
    out = validate(GOOD, duplicates={"invoice_number": ["abc"]})
    assert "DUPLICATE_DOCUMENT" in rules(out.warnings) and out.is_valid


def test_parse_failure_short_circuits():
    out = validate({k: None for k in GOOD}, extraction_parse_ok=False)
    assert out.status.value == "invalid" and rules(out.errors) == {"EXTRACTION_PARSE_FAILED"}


# ---- rules that need richer specs (dormant for the dataset-based invoice spec)
@pytest.fixture
def full_spec(monkeypatch):
    spec = DocumentTypeSpec(
        name="invoice_full", description="invoice",
        fields=[FieldSpec(name="subtotal", description="Subtotal", dtype="amount"),
            FieldSpec(name="tax_amount", description="Tax", dtype="amount"),
            FieldSpec(name="total_amount", description="Total", dtype="amount"),
            FieldSpec(name="line_items", description="Line items as JSON", dtype="json"),],
        amount_sum_rules=[AmountSumRule(add=["subtotal", "tax_amount"], equals="total_amount")],
        line_items_rule=LineItemsRule(sum_equals="subtotal"),
    )
    monkeypatch.setitem(DOCUMENT_TYPES, "invoice_full", spec)


def test_totals_consistency(full_spec):
    ok = validate({"subtotal": "100.00", "tax_amount": "18.00", "total_amount": "118.00",
                   "line_items": None}, "invoice_full")
    assert ok.checks["TOTALS_CONSISTENCY"] == "passed"
    bad = validate({"subtotal": "100.00", "tax_amount": "18.00", "total_amount": "120.00",
                    "line_items": None}, "invoice_full")
    assert "TOTALS_CONSISTENCY" in rules(bad.errors)


def test_line_items(full_spec):
    items = '[{"quantity": 2, "unit_price": "10.00", "amount": "20.00"}, ' \
            '{"quantity": 3, "unit_price": "5.00", "amount": "16.00"}]'
    out = validate({"subtotal": "36.00", "tax_amount": "0", "total_amount": "36.00", "line_items": items},
                   "invoice_full")
    assert "LINE_ITEMS_CONSISTENCY" in rules(out.errors)   # 3 x 5 != 16


def test_rules_skipped_when_fields_absent():
    out = validate(GOOD)
    assert "TOTALS_CONSISTENCY" not in out.checks


def test_parsers():
    assert parse_amount("$9,834") == Decimal("9834")
    assert parse_amount("9.834,50") == Decimal("9834.50")
    assert parse_amount("USD 1,200.50") == Decimal("1200.50")
    assert parse_amount("(100)") == Decimal("-100")
    assert parse_amount("abc") is None and parse_amount("12 apples") is None
    assert parse_integer("4.0") == 4 and parse_integer("1,234") == 1234 and parse_integer("4.5") is None
    assert parse_date_candidates("10/19/2023") == {date(2023, 10, 19)}
    assert len(parse_date_candidates("10/11/2023")) == 2
    assert parse_date_candidates("19th October 2023") == {date(2023, 10, 19)}
    assert parse_date_candidates("31/31/2023") == set()