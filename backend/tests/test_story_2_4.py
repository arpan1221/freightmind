import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.agents.analytics.planner import AnalyticsPlanner
from app.services.model_client import ModelClient


class TestAnalyticsPlannerPreviousSql:
    def _make_client(self, return_value: str = "refined question") -> ModelClient:
        client = MagicMock(spec=ModelClient)
        client.call = AsyncMock(return_value=return_value)
        return client

    @pytest.mark.asyncio
    async def test_plan_with_previous_sql_includes_it_in_user_message(self):
        client = self._make_client()
        planner = AnalyticsPlanner(client)
        await planner.plan("Filter to Air only", previous_sql="SELECT * FROM shipments")
        call_kwargs = client.call.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        user_message = next(m["content"] for m in messages if m["role"] == "user")
        assert "SELECT * FROM shipments" in user_message
        assert "Filter to Air only" in user_message

    @pytest.mark.asyncio
    async def test_plan_without_previous_sql_sends_question_only(self):
        client = self._make_client()
        planner = AnalyticsPlanner(client)
        await planner.plan("What is total freight cost?", previous_sql=None)
        call_kwargs = client.call.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        user_message = next(m["content"] for m in messages if m["role"] == "user")
        assert user_message == "What is total freight cost?"

    @pytest.mark.asyncio
    async def test_plan_without_previous_sql_no_error(self):
        client = self._make_client("refined")
        planner = AnalyticsPlanner(client)
        result = await planner.plan("Any question")
        assert isinstance(result, str)


class TestPostQueryWithPreviousSql:
    def test_post_query_with_previous_sql_succeeds(self):
        from app.main import app
        client = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner, \
             patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor, \
             patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier, \
             patch("app.api.routes.analytics._generate_answer",
                   new=AsyncMock(return_value="Air shipments cost more")), \
             patch("app.api.routes.analytics._generate_chart_config",
                   new=AsyncMock(return_value=None)), \
             patch("app.api.routes.analytics._generate_follow_ups",
                   new=AsyncMock(return_value=[])):
            MockPlanner.return_value.classify_intent = AsyncMock(
                return_value={"intent": "answerable"}
            )
            MockPlanner.return_value.plan = AsyncMock(return_value="Filter to Air")
            MockExecutor.return_value.generate_sql = AsyncMock(
                return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments WHERE shipment_mode='Air' GROUP BY shipment_mode"
            )
            MockVerifier.return_value.verify = MagicMock(
                return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments WHERE shipment_mode='Air' GROUP BY shipment_mode"
            )
            resp = client.post(
                "/api/query",
                json={
                    "question": "Filter to Air only",
                    "previous_sql": "SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None

    def test_post_query_without_previous_sql_succeeds(self):
        from app.main import app
        client = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner, \
             patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor, \
             patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier, \
             patch("app.api.routes.analytics._generate_answer",
                   new=AsyncMock(return_value="Here is the answer")), \
             patch("app.api.routes.analytics._generate_chart_config",
                   new=AsyncMock(return_value=None)), \
             patch("app.api.routes.analytics._generate_follow_ups",
                   new=AsyncMock(return_value=[])):
            MockPlanner.return_value.classify_intent = AsyncMock(
                return_value={"intent": "answerable"}
            )
            MockPlanner.return_value.plan = AsyncMock(return_value="fresh question")
            MockExecutor.return_value.generate_sql = AsyncMock(
                return_value="SELECT COUNT(*) FROM shipments"
            )
            MockVerifier.return_value.verify = MagicMock(
                return_value="SELECT COUNT(*) FROM shipments"
            )
            resp = client.post(
                "/api/query",
                json={"question": "How many shipments are there?"},
            )
        assert resp.status_code == 200
        assert resp.json()["error"] is None
