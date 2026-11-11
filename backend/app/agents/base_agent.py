import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.core.exceptions import AgentError
from app.core.logging_config import get_logger
from app.schemas.agent_schema import AgentResult, AgentStatus

InT = TypeVar("InT")
OutT = TypeVar("OutT")


class BaseAgent(ABC, Generic[InT, OutT]):
    """Common interface: every agent implements process() and is invoked via run()."""

    name: str = "base_agent"

    def __init__(self) -> None:
        self.logger = get_logger(f"agent.{self.name}")
        self.warnings: list[str] = []

    @abstractmethod
    def process(self, payload: InT) -> OutT:
        ...

    def run(self, payload: InT) -> AgentResult[OutT]:
        self.warnings = []
        start = time.perf_counter()
        self.logger.info("started")
        try:
            output = self.process(payload)
            status, error, code, retryable = AgentStatus.SUCCESS, None, None, False
        except AgentError as exc:
            self.logger.error("failed [%s]: %s", exc.code, exc.message)
            output, status, error, code, retryable = None, AgentStatus.FAILED, exc.message, exc.code, exc.retryable
        except Exception as exc:  # unexpected - treat as retryable
            self.logger.exception("unexpected error")
            output, status, error, code, retryable = None, AgentStatus.FAILED, str(exc), "UNEXPECTED_ERROR", True

        duration_ms = int((time.perf_counter() - start) * 1000)
        self.logger.info("finished status=%s duration_ms=%d", status.value, duration_ms)
        return AgentResult(
            agent_name=self.name,
            status=status,
            output=output,
            error=error,
            error_code=code,
            retryable=retryable,
            warnings=list(self.warnings),
            duration_ms=duration_ms,
        )