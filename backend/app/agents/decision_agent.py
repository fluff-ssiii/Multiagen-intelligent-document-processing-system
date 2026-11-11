from typing import Optional

from app.agents.base_agent import BaseAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import DecisionError
from app.schemas.decision_schema import (
    DecisionInput,
    DecisionOutput,
    DecisionReason,
    DecisionStage,
    DecisionType,
)
from app.schemas.extraction_schema import get_document_type

# Warnings that always need a human, even when other warnings are tolerated.
HARD_WARNING_RULES = {"DUPLICATE_DOCUMENT"}


def _rules(issues) -> str:
    return ", ".join(sorted({i.rule_id for i in issues}))


class DecisionAgent(BaseAgent[DecisionInput, DecisionOutput]):
    """
    Responsibility: turn validation results + extraction confidence into a routing decision
    (auto-approve / human review / reject). Pure rules, no I/O; every reason is returned so the
    decision is explainable.
    """

    name = "decision_agent"

    def __init__(self, config: Optional[Settings] = None):
        super().__init__()
        self.cfg = config or default_settings

    def process(self, payload: DecisionInput) -> DecisionOutput:
        if payload.stage == DecisionStage.REVIEWER_REJECTED:
            output = self._build(payload, DecisionType.REJECTED, [
                DecisionReason(code="REVIEWER_REJECTED", detail="A reviewer rejected the document.")])
        elif payload.validation is None:
            raise DecisionError("Validation output is required for this decision stage.",
                                code="MISSING_VALIDATION", status_code=400)
        elif payload.stage == DecisionStage.POST_CORRECTION:
            output = self._post_correction(payload)
        else:
            output = self._initial(payload)
        self.logger.info("document %s: %s", payload.document_id, output.decision.value)
        return output

    # ---------------------------------------------------------------- stages
    def _initial(self, p: DecisionInput) -> DecisionOutput:
        spec = get_document_type(p.document_type)
        v = p.validation
        required = [f.name for f in spec.fields if f.required]

        # Rule 1: almost nothing could be read -> reject (a parse failure is NOT rejected; see below)
        if p.extraction_parse_ok and required:
            missing = [n for n in p.extraction_missing_fields if n in required]
            if len(missing) / len(required) >= self.cfg.decision_reject_missing_ratio:
                return self._build(p, DecisionType.REJECTED, [DecisionReason(
                    code="UNREADABLE_DOCUMENT",
                    detail=f"{len(missing)} of {len(required)} required fields could not be found; "
                           f"the document may be unreadable or not a supported {spec.name}.")])

        reasons: list[DecisionReason] = []

        # Rule 2: extraction failure / validation errors
        if not p.extraction_parse_ok:
            reasons.append(DecisionReason(
                code="EXTRACTION_PARSE_FAILED",
                detail="The model output could not be parsed; fields must be entered manually."))
        elif v.errors:
            reasons.append(DecisionReason(
                code="VALIDATION_ERRORS",
                detail=f"{len(v.errors)} validation error(s): {_rules(v.errors)}"))

        # Rule 3: warnings
        hard = [w for w in v.warnings if w.rule_id in HARD_WARNING_RULES]
        soft = [w for w in v.warnings if w.rule_id not in HARD_WARNING_RULES]
        if hard:
            reasons.append(DecisionReason(
                code="BUSINESS_RULE_WARNING", detail=f"Needs a human check: {_rules(hard)}"))
        if soft and not self.cfg.decision_auto_approve_warnings:
            reasons.append(DecisionReason(
                code="VALIDATION_WARNINGS",
                detail=f"{len(soft)} validation warning(s): {_rules(soft)}"))

        # Rule 4: model confidence
        reasons.extend(self._confidence_reasons(p.extraction_confidence))

        if any(r.blocking for r in reasons):
            priority = "high" if (not p.extraction_parse_ok or v.errors) else "normal"
            return self._build(p, DecisionType.HUMAN_REVIEW, reasons, priority)

        reasons.append(DecisionReason(code="ALL_CHECKS_PASSED", blocking=False,
                                      detail="Validation passed and confidence is acceptable."))
        return self._build(p, DecisionType.AUTO_APPROVED, reasons)

    def _post_correction(self, p: DecisionInput) -> DecisionOutput:
        v = p.validation
        if v.errors:
            return self._build(p, DecisionType.HUMAN_REVIEW, [DecisionReason(
                code="VALIDATION_ERRORS",
                detail=f"Corrected data still has {len(v.errors)} validation error(s): {_rules(v.errors)}")],
                priority="high")
        if p.corrections_count > 0:
            return self._build(p, DecisionType.APPROVED_AFTER_CORRECTION, [DecisionReason(
                code="REVIEWER_APPROVED", blocking=False,
                detail=f"Reviewer approved after correcting {p.corrections_count} field(s).")])
        return self._build(p, DecisionType.APPROVED_AFTER_REVIEW, [DecisionReason(
            code="REVIEWER_APPROVED", blocking=False,
            detail="Reviewer approved the extraction without changes.")])

    def _confidence_reasons(self, confidence: Optional[dict]) -> list[DecisionReason]:
        mean_p = (confidence or {}).get("mean_token_prob")
        min_p = (confidence or {}).get("min_token_prob")
        if mean_p is None and min_p is None:
            return [DecisionReason(code="CONFIDENCE_UNAVAILABLE", blocking=False,
                                   detail="The model backend did not provide confidence signals.")]
        reasons = []
        if mean_p is not None and mean_p < self.cfg.decision_min_mean_token_prob:
            reasons.append(DecisionReason(
                code="LOW_MEAN_CONFIDENCE",
                detail=f"Mean token probability {mean_p:.2f} is below {self.cfg.decision_min_mean_token_prob:.2f}."))
        if min_p is not None and min_p < self.cfg.decision_min_token_prob:
            reasons.append(DecisionReason(
                code="LOW_MIN_CONFIDENCE",
                detail=f"Lowest token probability {min_p:.2f} is below {self.cfg.decision_min_token_prob:.2f}."))
        return reasons

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _build(p: DecisionInput, decision: DecisionType, reasons: list[DecisionReason],
               priority: Optional[str] = None) -> DecisionOutput:
        text = "; ".join(r.detail for r in reasons if r.blocking) or "; ".join(r.detail for r in reasons)
        summary = {
            DecisionType.AUTO_APPROVED: "Approved for automatic processing.",
            DecisionType.HUMAN_REVIEW: f"Sent for human review: {text}",
            DecisionType.REJECTED: f"Rejected: {text}",
        }.get(decision, text)
        return DecisionOutput(
            document_id=p.document_id,
            decision=decision,
            stage=p.stage,
            summary=summary,
            reasons=reasons,
            review_priority=priority if decision == DecisionType.HUMAN_REVIEW else None,
            flagged_fields=p.validation.flagged_fields if p.validation else [],
            corrections_count=p.corrections_count,
        )