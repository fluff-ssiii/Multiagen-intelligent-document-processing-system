from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class AgentResult(BaseModel, Generic[T]):
    """Uniform envelope returned by every agent."""

    agent_name: str
    status: AgentStatus
    output: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    retryable: bool = False
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == AgentStatus.SUCCESS