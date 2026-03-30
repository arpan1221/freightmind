"""
Tests for Story 2.3 — Chart configuration generation

Verifies:
- AC1: chart_config returned with valid type/x_key/y_key for quantitative results
- AC3: chart_config is null for non-quantitative or empty results
- Schema: AnalyticsQueryResponse includes chart_config field defaulting to None
- Failure resilience: JSON parse failure and invalid structure both return None
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.analytics import _generate_chart_config
from app.schemas.analytics import AnalyticsQueryResponse, ChartConfig
from app.services.model_client import ModelClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_in_memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE shipments (
                id INTEGER PRIMARY KEY,
                shipment_mode TEXT,
                freight_cost_usd REAL
            )
        """))
        conn.execute(text("""
            INSERT INTO shipments VALUES
                (1, 'Air', 1000.0),
                (2, 'Ocean', 500.0),
                (3, 'Truck', 200.0)
        """))
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, Factory


def _get_test_client_with_db(session_factory):
    from app.main import app
    from app.core.database import get_db

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _make_mock_client_with_chart(chart_json: str) -> MagicMock:
    """Mock pipeline: classify → plan → sql → answer → chart → follow_ups."""
    mock = MagicMock()
    mock.call = AsyncMock(
        side_effect=[
            '{"intent": "answerable"}',
            "What is average freight cost by mode?",
            "SELECT shipment_mode, AVG(freight_cost_usd) AS avg_cost FROM shipments GROUP BY shipment_mode",
            "Air costs the most at $1000.",
            chart_json,
            '["Q1?", "Q2?"]',
        ]
    )
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for _generate_chart_config
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateChartConfig:
    def _make_client(self, return_value: str) -> ModelClient:
        client = MagicMock(spec=ModelClient)
        client.call = AsyncMock(return_value=return_value)
        return client

    @pytest.mark.asyncio
    async def test_returns_chart_config_for_valid_bar_response(self):
        client = self._make_client('{"type": "bar", "x_key": "shipment_mode", "y_key": "avg_cost"}')
        result = await _generate_chart_config(
            client,
            "What is average freight cost by mode?",
            ["shipment_mode", "avg_cost"],
            [["Air", 1000.0], ["Ocean", 500.0]],
        )
        assert result is not None
        assert result.type == "bar"
        assert result.x_key == "shipment_mode"
        assert result.y_key == "avg_cost"

    @pytest.mark.asyncio
    async def test_returns_chart_config_for_line_type(self):
        client = self._make_client('{"type": "line", "x_key": "month", "y_key": "total"}')
        result = await _generate_chart_config(
            client,
            "Show freight cost over time",
            ["month", "total"],
            [["2024-01", 5000.0], ["2024-02", 6000.0]],
        )
        assert result is not None
        assert result.type == "line"

    @pytest.mark.asyncio
    async def test_returns_chart_config_for_pie_type(self):
        client = self._make_client('{"type": "pie", "x_key": "country", "y_key": "count"}')
        result = await _generate_chart_config(
            client,
            "Distribution by country",
            ["country", "count"],
            [["Nigeria", 10], ["Uganda", 5]],
        )
        assert result is not None
        assert result.type == "pie"

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_returns_null(self):
        client = self._make_client("null")
        result = await _generate_chart_config(
            client,
            "List vendor names",
            ["vendor_name"],
            [["Vendor A"], ["Vendor B"]],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_json_parse_failure(self):
        client = self._make_client("not valid json at all")
        result = await _generate_chart_config(
            client,
            "Some question",
            ["col1", "col2"],
            [[1, 2], [3, 4]],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_rows_empty(self):
        client = self._make_client('{"type": "bar", "x_key": "a", "y_key": "b"}')
        result = await _generate_chart_config(
            client,
            "Some question",
            ["a", "b"],
            [],
        )
        assert result is None
        # LLM should not be called when rows is empty
        client.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_columns_empty(self):
        client = self._make_client('{"type": "bar", "x_key": "a", "y_key": "b"}')
        result = await _generate_chart_config(
            client,
            "Some question",
            [],
            [[1, 2]],
        )
        assert result is None
        client.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_type_value(self):
        """type must be 'bar', 'line', or 'pie' — other values return None."""
        client = self._make_client('{"type": "scatter", "x_key": "a", "y_key": "b"}')
        result = await _generate_chart_config(
            client,
            "Some question",
            ["a", "b"],
            [[1, 2]],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_x_key(self):
        client = self._make_client('{"type": "bar", "y_key": "b"}')
        result = await _generate_chart_config(
            client,
            "Some question",
            ["a", "b"],
            [[1, 2]],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_y_key(self):
        client = self._make_client('{"type": "bar", "x_key": "a"}')
        result = await _generate_chart_config(
            client,
            "Some question",
            ["a", "b"],
            [[1, 2]],
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Schema tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsQueryResponseSchema:
    def test_chart_config_defaults_to_none(self):
        resp = AnalyticsQueryResponse(
            answer="test",
            sql="SELECT 1",
            columns=[],
            rows=[],
            row_count=0,
        )
        assert resp.chart_config is None

    def test_chart_config_accepted_as_chart_config_object(self):
        cfg = ChartConfig(type="bar", x_key="mode", y_key="cost")
        resp = AnalyticsQueryResponse(
            answer="test",
            sql="SELECT 1",
            columns=["mode", "cost"],
            rows=[["Air", 1000.0]],
            row_count=1,
            chart_config=cfg,
        )
        assert resp.chart_config is not None
        assert resp.chart_config.type == "bar"

    def test_chart_config_field_present_in_json_output(self):
        resp = AnalyticsQueryResponse(
            answer="test",
            sql="SELECT 1",
            columns=[],
            rows=[],
            row_count=0,
        )
        data = resp.model_dump()
        assert "chart_config" in data


# ─────────────────────────────────────────────────────────────────────────────
# Route integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPostQueryChartConfig:
    def setup_method(self):
        from app.main import app
        app.dependency_overrides.clear()

    def test_post_query_includes_chart_config_when_quantitative(self):
        """AC1: chart_config returned with valid fields for categorical + numeric result."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = _make_mock_client_with_chart(
            '{"type": "bar", "x_key": "shipment_mode", "y_key": "avg_cost"}'
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "What is average freight cost by mode?"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert body["chart_config"] is not None
        assert body["chart_config"]["type"] == "bar"
        assert body["chart_config"]["x_key"] == "shipment_mode"
        assert body["chart_config"]["y_key"] == "avg_cost"

    def test_post_query_chart_config_null_when_llm_returns_null(self):
        """AC3: chart_config is null when LLM determines no chart is appropriate."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = _make_mock_client_with_chart("null")

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "List all vendor names"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert body["chart_config"] is None

    def test_post_query_out_of_scope_has_null_chart_config(self):
        """Out-of-scope response must include chart_config: null."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "out_of_scope", "answer": "I cannot answer that."}'
            ]
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "What is the weather today?"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["chart_config"] is None

    def test_chart_config_key_present_in_all_responses(self):
        """chart_config key must always be present in response JSON."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = _make_mock_client_with_chart("null")

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "count shipments"})

        assert "chart_config" in response.json()
