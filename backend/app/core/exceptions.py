class AgentError(Exception):
    """Base error for all agents. `retryable` lets the orchestrator decide on retries."""

    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        retryable: bool = False,
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class IngestionError(AgentError):
    def __init__(self, message: str, code: str = "INGESTION_ERROR", status_code: int = 400,
                 retryable: bool = False):
        super().__init__(message, code=code, retryable=retryable, status_code=status_code)

class ExtractionError(AgentError):
    def __init__(self, message: str, code: str = "EXTRACTION_ERROR", status_code: int = 500,
                 retryable: bool = False):
        super().__init__(message, code=code, retryable=retryable, status_code=status_code)

class PipelineError(AgentError):
    def __init__(self, message: str, code: str = "PIPELINE_ERROR", status_code: int = 500):
        super().__init__(message, code=code, retryable=False, status_code=status_code)

class DecisionError(AgentError):
    def __init__(self, message: str, code: str = "DECISION_ERROR", status_code: int = 500):
        super().__init__(message, code=code, retryable=False, status_code=status_code)

class ReviewError(AgentError):
    def __init__(self, message: str, code: str = "REVIEW_ERROR", status_code: int = 400,
                 details: dict | None = None):
        super().__init__(message, code=code, retryable=False, status_code=status_code)
        self.details = details

class WorkflowError(AgentError):
    def __init__(self, message: str, code: str = "WORKFLOW_ERROR", status_code: int = 500,
                 retryable: bool = False):
        super().__init__(message, code=code, retryable=retryable, status_code=status_code)