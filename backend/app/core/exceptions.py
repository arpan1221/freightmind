"""Application-specific exceptions surfaced to HTTP clients (Epic 5)."""


class RateLimitError(Exception):
    """OpenRouter returned HTTP 429; include seconds until retry is reasonable."""

    def __init__(
        self,
        retry_after: int,
        message: str = "Rate limit exceeded. Please wait before retrying.",
    ) -> None:
        self.retry_after = retry_after
        self.message = message
        super().__init__(message)


class ModelUnavailableError(Exception):
    """Transport failure, timeout, or non-429 provider error for the LLM call."""

    def __init__(
        self,
        message: str = "The language model is temporarily unavailable. Please try again.",
    ) -> None:
        self.message = message
        super().__init__(message)
