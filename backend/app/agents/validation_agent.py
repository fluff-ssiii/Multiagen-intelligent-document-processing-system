import json
import re
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.core.config import Settings, settings as default_settings
from app.schemas.extraction_schema import DocumentTypeSpec, get_document_type
from app.schemas.validation_schema import (
    CheckOutcome,
    Severity,
    ValidationInput,
    ValidationIssue,
    ValidationOutput,
    ValidationStatus,
)
from app.utils.parsing_utils import parse_amount, parse_date_candidates, parse_integer

_PLACEHOLDER = re.compile(
    r"\b(not\s+(provided|available|specified|shown|visible|found|present|mentioned)"
    r"|unknown|n/?a|none|null|undefined|illegible|unreadable|redacted|placeholder)\b",
    re.IGNORECASE,
)
MAX_TEXT_LENGTH = 200


class ValidationAgent(BaseAgent[ValidationInput, ValidationOutput]):
    """
    Responsibility: check extracted fields for completeness, format, internal consistency and
    suspicious values. It never changes extracted values; it only reports and normalises.
    """

    name = "validation_agent"

    def __init__(self, config: Optional[Settings] = None, today: Optional[date] = None):
        super().__init__()
        self.cfg = config or default_settings
        self._today = today

    def process(self, payload: ValidationInput) -> ValidationOutput:
        spec = get_document_type(payload.document_type)
        run = _ValidationRun(spec, payload, self.cfg, self._today or date.today())
        output = run.execute()
        self.logger.info("document %s: %s (%d errors, %d warnings)", payload.document_id,
                         output.status.value, len(output.errors), len(output.warnings))
        return output


class _ValidationRun:
    """Holds the state of one validation so the agent itself stays stateless."""

    def __init__(self, spec: DocumentTypeSpec, payload: ValidationInput, cfg: Settings, today: date):
        self.spec, self.payload, self.today = spec, payload, today
        self.fields = payload.fields
        self.tol = Decimal(str(cfg.validation_amount_tolerance))
        self.min_year = cfg.validation_min_year
        self.max_future = timedelta(days=cfg.validation_max_future_days)

        self.issues: list[ValidationIssue] = []
        self.checks: dict[str, CheckOutcome] = {}
        self.normalized: dict[str, Any] = {}
        self.dates: dict[str, set[date]] = {}
        self.amounts: dict[str, Decimal] = {}
        self.checked: Counter = Counter()

    # ---------------------------------------------------------------- plumbing
    def add(self, rule_id: str, severity: Severity, message: str, fields=()) -> None:
        self.issues.append(ValidationIssue(rule_id=rule_id, severity=severity,
                                           message=message, fields=list(fields)))

    def settle(self, rule_id: str, skipped: bool = False) -> None:
        if skipped:
            self.checks[rule_id] = CheckOutcome.SKIPPED
            return
        related = [i for i in self.issues if i.rule_id == rule_id]
        if any(i.severity == Severity.ERROR for i in related):
            self.checks[rule_id] = CheckOutcome.FAILED
        elif related:
            self.checks[rule_id] = CheckOutcome.WARNING
        else:
            self.checks[rule_id] = CheckOutcome.PASSED

    # ------------------------------------------------------------------ driver
    def execute(self) -> ValidationOutput:
        if not self.payload.extraction_parse_ok:
            self.add("EXTRACTION_PARSE_FAILED", Severity.ERROR,
                     "The model output could not be parsed, so no reliable fields are available.")
            self.settle("EXTRACTION_PARSE_FAILED")
            return self.build()
        self.settle("EXTRACTION_PARSE_FAILED")

        self.check_required()
        self.check_formats()
        self.check_date_ranges()
        self.check_date_order()
        self.check_amount_sums()
        self.check_line_items()
        self.check_suspicious()
        self.check_duplicates()
        return self.build()

    def build(self) -> ValidationOutput:
        errors = [i for i in self.issues if i.severity == Severity.ERROR]
        warnings = [i for i in self.issues if i.severity == Severity.WARNING]
        if errors:
            status = ValidationStatus.INVALID
        elif warnings:
            status = ValidationStatus.VALID_WITH_WARNINGS
        else:
            status = ValidationStatus.VALID
        return ValidationOutput(
            document_id=self.payload.document_id,
            document_type=self.payload.document_type,
            status=status,
            is_valid=not errors,
            errors=errors,
            warnings=warnings,
            checks={rule: outcome.value for rule, outcome in self.checks.items()},
            normalized_fields=self.normalized,
            flagged_fields=sorted({f for issue in self.issues for f in issue.fields}),
        )

    # ------------------------------------------------------------------ checks
    def check_required(self) -> None:
        for spec_field in self.spec.fields:
            if spec_field.required and self.fields.get(spec_field.name) is None:
                self.add("REQUIRED_FIELDS", Severity.ERROR,
                         f"Required field '{spec_field.name}' is missing.", [spec_field.name])
        self.settle("REQUIRED_FIELDS")

    def check_formats(self) -> None:
        for f in self.spec.fields:
            value = self.fields.get(f.name)
            if value is None:
                continue

            if f.dtype == "date":
                self.checked["date"] += 1
                candidates = parse_date_candidates(value)
                if not candidates:
                    self.add("DATE_FORMAT", Severity.ERROR,
                             f"'{f.name}' value '{value}' is not a recognised date.", [f.name])
                    continue
                self.dates[f.name] = candidates
                iso = sorted(d.isoformat() for d in candidates)
                self.normalized[f.name] = iso[0] if len(iso) == 1 else iso

            elif f.dtype == "amount":
                self.checked["amount"] += 1
                amount = parse_amount(value)
                if amount is None:
                    self.add("AMOUNT_FORMAT", Severity.ERROR,
                             f"'{f.name}' value '{value}' is not a valid amount.", [f.name])
                    continue
                self.amounts[f.name] = amount
                self.normalized[f.name] = format(amount, "f")
                if amount < 0:
                    self.add("AMOUNT_SIGN", Severity.WARNING,
                             f"'{f.name}' is negative ({amount}).", [f.name])
                elif amount == 0:
                    self.add("AMOUNT_SIGN", Severity.WARNING, f"'{f.name}' is zero.", [f.name])

            elif f.dtype == "integer":
                self.checked["integer"] += 1
                number = parse_integer(value)
                if number is None:
                    self.add("INTEGER_FORMAT", Severity.ERROR,
                             f"'{f.name}' value '{value}' is not a whole number.", [f.name])
                    continue
                self.normalized[f.name] = number
                if number <= 0:
                    self.add("INTEGER_RANGE", Severity.WARNING,
                             f"'{f.name}' is not positive ({number}).", [f.name])

            elif f.dtype == "string":
                self.normalized[f.name] = value.strip()

        self.settle("DATE_FORMAT", skipped=self.checked["date"] == 0)
        self.settle("AMOUNT_FORMAT", skipped=self.checked["amount"] == 0)
        self.settle("AMOUNT_SIGN", skipped=self.checked["amount"] == 0)
        self.settle("INTEGER_FORMAT", skipped=self.checked["integer"] == 0)
        self.settle("INTEGER_RANGE", skipped=self.checked["integer"] == 0)

    def check_date_ranges(self) -> None:
        for name, candidates in self.dates.items():
            low, high = date(self.min_year, 1, 1), self.today + self.max_future
            if all(d < low or d > high for d in candidates):
                shown = ", ".join(sorted(d.isoformat() for d in candidates))
                self.add("DATE_RANGE", Severity.WARNING,
                         f"'{name}' ({shown}) is outside the plausible range "
                         f"{low.isoformat()} to {high.isoformat()}.", [name])
        self.settle("DATE_RANGE", skipped=not self.dates)

    def check_date_order(self) -> None:
        evaluated = False
        for rule in self.spec.date_order_rules:
            earlier, later = self.dates.get(rule.earlier), self.dates.get(rule.later)
            if not earlier or not later:
                continue
            evaluated = True
            pairs = [(e, l) for e in earlier for l in later]
            ok = [p for p in pairs if p[1] >= p[0]]
            names = [rule.earlier, rule.later]
            if not ok:
                self.add("DATE_ORDER", Severity.ERROR,
                         f"'{rule.later}' is earlier than '{rule.earlier}' under every date interpretation.",
                         names)
            elif len(ok) < len(pairs):
                self.add("DATE_ORDER", Severity.WARNING,
                         f"Order of '{rule.earlier}' and '{rule.later}' depends on whether the dates "
                         "are read day/month or month/day.", names)
        self.settle("DATE_ORDER", skipped=not evaluated)

    def check_amount_sums(self) -> None:
        for rule in self.spec.amount_sum_rules:
            needed = [*rule.add, *rule.subtract, rule.equals]
            if not all(n in self.amounts for n in needed):
                self.settle(rule.rule_id, skipped=True)
                continue
            expected = sum((self.amounts[n] for n in rule.add), Decimal(0)) \
                - sum((self.amounts[n] for n in rule.subtract), Decimal(0))
            actual = self.amounts[rule.equals]
            if abs(expected - actual) > self.tol:
                expr = " + ".join(rule.add) + "".join(f" - {n}" for n in rule.subtract)
                self.add(rule.rule_id, Severity.ERROR,
                         f"{expr} = {expected}, but '{rule.equals}' is {actual}.", needed)
            self.settle(rule.rule_id)

    def check_line_items(self) -> None:
        rule = self.spec.line_items_rule
        if rule is None:
            return
        raw = self.fields.get(rule.field)
        if raw is None:
            self.settle(rule.rule_id, skipped=True)
            return
        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                raise ValueError("not a list")
        except ValueError:
            self.add(rule.rule_id, Severity.ERROR,
                     f"'{rule.field}' could not be read as a list of line items.", [rule.field])
            self.settle(rule.rule_id)
            return

        bad_rows, amounts = [], []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            qty = parse_amount(item.get(rule.quantity_key))
            price = parse_amount(item.get(rule.unit_price_key))
            amount = parse_amount(item.get(rule.amount_key))
            if amount is not None:
                amounts.append(amount)
            if qty is not None and price is not None and amount is not None \
                    and abs(qty * price - amount) > self.tol:
                bad_rows.append(index)
        if bad_rows:
            shown = ", ".join(map(str, bad_rows[:5])) + ("..." if len(bad_rows) > 5 else "")
            self.add(rule.rule_id, Severity.ERROR,
                     f"Quantity x unit price does not equal amount on line(s): {shown}.", [rule.field])
        if rule.sum_equals and rule.sum_equals in self.amounts and amounts \
                and len(amounts) == len(items):
            total = sum(amounts, Decimal(0))
            if abs(total - self.amounts[rule.sum_equals]) > self.tol:
                self.add(rule.rule_id, Severity.ERROR,
                         f"Line amounts sum to {total}, but '{rule.sum_equals}' is "
                         f"{self.amounts[rule.sum_equals]}.", [rule.field, rule.sum_equals])
        self.settle(rule.rule_id)

    def check_suspicious(self) -> None:
        for f in self.spec.fields:
            value = self.fields.get(f.name)
            if value is None or f.dtype != "string":
                continue
            self.checked["string"] += 1
            text = value.strip()
            if _PLACEHOLDER.search(text):
                self.add("SUSPICIOUS_VALUE", Severity.WARNING,
                         f"'{f.name}' looks like placeholder text: '{text[:60]}'.", [f.name])
            elif len(text) > MAX_TEXT_LENGTH:
                self.add("SUSPICIOUS_VALUE", Severity.WARNING,
                         f"'{f.name}' is unusually long ({len(text)} characters).", [f.name])
            elif f.name.endswith("_number") and (len(text) < 3 or len(set(text.lower())) == 1):
                self.add("SUSPICIOUS_VALUE", Severity.WARNING,
                         f"'{f.name}' value '{text}' does not look like a real identifier.", [f.name])
        self.settle("SUSPICIOUS_VALUE", skipped=self.checked["string"] == 0)

    def check_duplicates(self) -> None:
        key = self.spec.duplicate_key_field
        duplicates = self.payload.duplicates
        if not key or duplicates is None or self.fields.get(key) is None:
            self.settle("DUPLICATE_DOCUMENT", skipped=True)
            return
        others = duplicates.get(key, [])
        if others:
            shown = ", ".join(others[:3]) + ("..." if len(others) > 3 else "")
            self.add("DUPLICATE_DOCUMENT", Severity.WARNING,
                     f"'{key}' value '{self.fields[key]}' also appears in {len(others)} other "
                     f"document(s): {shown}.", [key])
        self.settle("DUPLICATE_DOCUMENT")