from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.decision_schema import DecisionOutput
from app.schemas.extraction_schema import ExtractionOutput
from app.schemas.validation_schema import ValidationOutput
from app.schemas.workflow_schema import WorkflowOutput


class StepRecord(BaseModel):
    agent_name: str
    status: str                 # success | failed
    attempts: int = 1
    duration_ms: int = 0        # duration of the final attempt
    error: Optional[str] = None
    error_code: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    document_id: str
    status: str                 # final document status
    success: bool
    steps: list[StepRecord] = Field(default_factory=list)
    total_duration_ms: int = 0  # wall time, including retries and backoff
    error: Optional[str] = None
    extraction: Optional[ExtractionOutput] = None
    validation: Optional[ValidationOutput] = None
    decision: Optional[DecisionOutput] = None
    workflow: Optional[WorkflowOutput] = None