"""HTTP helpers for typed API errors (Epic 5)."""

from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse


def llm_parse_error_response(
    message: str,
    detail: dict[str, object] | None = None,
    *,
    status_code: int = 422,
) -> JSONResponse:
    """Return a JSON response for LLM output that failed schema validation (FR29)."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error_type="llm_parse_error",
            message=message,
            detail=detail,
        ).model_dump(),
    )
