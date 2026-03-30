from typing import Literal

from pydantic import BaseModel, Field


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie"]
    x_key: str
    y_key: str


class AnalyticsQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    previous_sql: str | None = None


class AnalyticsQueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    chart_config: ChartConfig | None = None
    error: str | None = None
    message: str | None = None
    suggested_questions: list[str] = []
