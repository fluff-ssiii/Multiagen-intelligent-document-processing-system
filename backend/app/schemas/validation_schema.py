from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class CheckOutcome(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


class ValidationStatus(str, Enum):
    VALID = "valid"
    VALID_WITH_WARNINGS = "valid_with_warnings"
    INVALID = "invalid"


class ValidationIssue(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    fields: list[str] = Field(default_factory=list)


class ValidationInput(BaseModel):
    document_id: str
    document_type: str = "invoice"
    fields: dict[str, Optional[str]]
    extraction_parse_ok: bool = True
    # field -> ids of OTHER documents sharing that value. None = lookup not performed.
    duplicates: Optional[dict[str, list[str]]] = None


class ValidationOutput(BaseModel):
    document_id: str
    document_type: str
    status: ValidationStatus
    is_valid: bool                      # True when there are no errors (warnings allowed)
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    checks: dict[str, str] = Field(default_factory=dict)   # rule_id -> CheckOutcome value
    # Dates: ISO string if unambiguous, otherwise a list of ISO candidates.
    # Amounts: plain decimal string. Integers: int.
    normalized_fields: dict[str, Any] = Field(default_factory=dict)
    flagged_fields: list[str] = Field(default_factory=list)