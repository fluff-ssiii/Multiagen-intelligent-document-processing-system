from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.validation_schema import ValidationOutput


class DecisionType(str, Enum):
    AUTO_APPROVED = "auto_approved"
    HUMAN_REVIEW = "human_review"
    REJECTED = "rejected"
    APPROVED_AFTER_CORRECTION = "approved_after_correction"   # reviewer changed at least one field
    APPROVED_AFTER_REVIEW = "approved_after_review"           # reviewer approved without changes


class DecisionStage(str, Enum):
    INITIAL = "initial"
    POST_CORRECTION = "post_correction"
    REVIEWER_REJECTED = "reviewer_rejected"


class DecisionReason(BaseModel):
    code: str
    detail: str
    blocking: bool = True      # False = informational, does not affect the outcome


class DecisionInput(BaseModel):
    document_id: str
    document_type: str = "invoice"
    stage: DecisionStage = DecisionStage.INITIAL
    extraction_parse_ok: bool = True
    extraction_missing_fields: list[str] = Field(default_factory=list)
    extraction_confidence: Optional[dict[str, Optional[float]]] = None
    validation: Optional[ValidationOutput] = None
    corrections_count: int = 0


class DecisionOutput(BaseModel):
    document_id: str
    decision: DecisionType
    stage: DecisionStage
    summary: str
    reasons: list[DecisionReason] = Field(default_factory=list)
    review_priority: Optional[str] = None      # "high" | "normal"; only for human_review
    flagged_fields: list[str] = Field(default_factory=list)
    corrections_count: int = 0

    @property
    def is_approved(self) -> bool:
        return self.decision in (DecisionType.AUTO_APPROVED,
                                 DecisionType.APPROVED_AFTER_CORRECTION,
                                 DecisionType.APPROVED_AFTER_REVIEW)