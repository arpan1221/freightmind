"""Tests for POST /api/query/stream (SSE analytics answer streaming)."""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analytics import AnalyticsQueryResponse


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_stream_early_exit_emits_single_complete(client: TestClient) -> None:
    """Out-of-scope path yields one SSE ``complete`` frame (no metadata/deltas)."""
    early = AnalyticsQueryResponse(
        answer="Cannot answer that.",
        sql="",
        columns=[],
        rows=[],
        row_count=0,
    )
    with patch(
        "app.api.routes.analytics._run_pipeline_to_rows",
        new=AsyncMock(return_value=early),
    ):
        r = client.post("/api/query/stream", json={"question": "What is the CEO's favorite color?"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert "event: complete" in r.text
    assert "Cannot answer that." in r.text


def test_stream_rows_path_emits_metadata_delta_complete(client: TestClient) -> None:
    """Successful SQL phase streams metadata, answer deltas, then complete."""
    from app.api.routes.analytics import _RowsBundle
    from app.services.model_client import ModelClient

    mock_mc = MagicMock(spec=ModelClient)

    async def fake_stream(*_a, **_kw):
        yield "Hi "
        yield "there."

    mock_mc.stream_call = fake_stream

    bundle = _RowsBundle(
        client=mock_mc,
        question="Average cost?",
        safe_sql="SELECT 1",
        columns=["a"],
        rows=[[1]],
        row_count=1,
        null_exclusions={},
    )

    with patch(
        "app.api.routes.analytics._run_pipeline_to_rows",
        new=AsyncMock(return_value=bundle),
    ), patch(
        "app.api.routes.analytics._generate_chart_config",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.api.routes.analytics._generate_follow_ups",
        new=AsyncMock(return_value=["Next?"]),
    ):
        r = client.post("/api/query/stream", json={"question": "Average cost?"})

    assert r.status_code == 200
    body = r.text
    assert "event: metadata" in body
    assert "event: delta" in body
    assert "event: complete" in body
    assert "Hi " in body or "there." in body
    assert '"answer"' in body
