from pydantic import BaseModel
from typing import Optional


class ErrorResponse(BaseModel):
    error: Optional[str] = None
    message: Optional[str] = None
    retry_after: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    model: str
