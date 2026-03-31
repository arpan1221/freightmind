from typing import Any, Literal

from pydantic import BaseModel, Field

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "NOT_FOUND"]


class ErrorResponse(BaseModel):
    """Unified API error envelope (FR29). `error` is always true for error responses.

    Examples of ``error_type``: ``rate_limit``, ``model_unavailable`` (LLM boundary),
    ``unsafe_sql``, ``sql_execution_error`` (analytics SQL — Story 5.4).
    """

    error: bool = Field(default=True, description="Always true for error payloads")
    error_type: str = Field(..., description="Stable machine-readable error category")
    message: str = Field(..., description="Human-readable message safe for clients")
    detail: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured context (e.g. validation field errors)",
    )
    retry_after: int | None = Field(
        default=None,
        description="Seconds to wait before retry (e.g. rate limits)",
    )


class HealthResponse(BaseModel):
    status: str
    database: str
    model: str
