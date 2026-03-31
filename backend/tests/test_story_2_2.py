"""
Tests for Story 2.2 — Out-of-Scope Detection, NULL Surfacing, and Follow-Up Suggestions

Verifies:
- AC1: Out-of-scope questions return an explanation, no fabricated SQL result
- AC2: NULL exclusions are counted and surfaced in the answer
- AC3: Successful queries include suggested_questions array (2-3 questions)
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.analytics.planner import AnalyticsPlanner
from app.api.routes.analytics import _count_null_exclusions, _generate_follow_ups
from app.schemas.analytics import AnalyticsQueryResponse


# ---------------------------------------------------------------------------
# Task 1: Schema field
# ---------------------------------------------------------------------------

class TestAnalyticsQueryResponseSchema:
    def test_has_suggested_questions_field(self):
        r = AnalyticsQueryResponse(
            answer="answer", sql="", columns=[], rows=[], row_count=0
        )
        assert hasattr(r, "suggested_questions")
        assert r.suggested_questions == []

    def test_suggested_questions_accepts_list_of_strings(self):
        r = AnalyticsQueryResponse(
            answer="answer", sql="SELECT 1", columns=["col"],
            rows=[["val"]], row_count=1,
            suggested_questions=["Q1?", "Q2?"],
        )
        assert r.suggested_questions == ["Q1?", "Q2?"]

    def test_existing_fields_unchanged(self):
        r = AnalyticsQueryResponse(
            answer="a", sql="s", columns=["c"], rows=[["v"]],
            row_count=1, error="e", message="m",
        )
        assert r.answer == "a"
        assert r.sql == "s"
        assert r.error == "e"
        assert r.message == "m"


# ---------------------------------------------------------------------------
# Task 3: classify_intent
# ---------------------------------------------------------------------------

class TestClassifyIntent:
    def _make_planner(self, mock_response: str) -> AnalyticsPlanner:
        client = MagicMock()
        client.call = AsyncMock(return_value=mock_response)
        return AnalyticsPlanner(client)

    @pytest.mark.asyncio
    async def test_out_of_scope_returns_correct_intent(self):
        raw = '{"intent": "out_of_scope", "answer": "Carbon footprint data is not available in this dataset."}'
        planner = self._make_planner(raw)
        result = await planner.classify_intent("What is the carbon footprint?")
        assert result["intent"] == "out_of_scope"
        assert "answer" in result
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_answerable_returns_correct_intent(self):
        planner = self._make_planner('{"intent": "answerable"}')
        result = await planner.classify_intent("What is the average freight cost?")
        assert result["intent"] == "answerable"

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_classification_failed(self):
        planner = self._make_planner("I cannot determine this.")
        result = await planner.classify_intent("What is the average freight cost?")
        assert result["intent"] == "classification_failed"
        assert "answer" in result

    @pytest.mark.asyncio
    async def test_whitespace_stripped_before_json_parse(self):
        raw = '  \n{"intent": "answerable"}\n  '
        planner = self._make_planner(raw)
        result = await planner.classify_intent("Show freight cost by country")
        assert result["intent"] == "answerable"

    @pytest.mark.asyncio
    async def test_classify_intent_uses_temperature_zero(self):
        client = MagicMock()
        client.call = AsyncMock(return_value='{"intent": "answerable"}')
        planner = AnalyticsPlanner(client)
        await planner.classify_intent("test question")
        call_kwargs = client.call.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.0 or call_kwargs.args[2] == 0.0


# ---------------------------------------------------------------------------
# Task 4: _count_null_exclusions
# ---------------------------------------------------------------------------

class TestCountNullExclusions:
    def test_no_is_not_null_returns_empty(self):
        db = MagicMock()
        result = _count_null_exclusions(db, "SELECT COUNT(*) FROM shipments")
        assert result == {}
        db.execute.assert_not_called()

    def test_detects_is_not_null_and_counts(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 245
        db.execute.return_value = mock_result
        sql = "SELECT AVG(freight_cost_usd) FROM shipments WHERE freight_cost_usd IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert counts == {"freight_cost_usd": 245}

    def test_zero_count_excluded_from_result(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute.return_value = mock_result
        sql = "SELECT AVG(weight_kg) FROM shipments WHERE weight_kg IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert counts == {}

    def test_multiple_columns_all_with_nulls(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        db.execute.return_value = mock_result
        sql = "SELECT * FROM shipments WHERE freight_cost_usd IS NOT NULL AND weight_kg IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert "freight_cost_usd" in counts
        assert "weight_kg" in counts

    def test_duplicate_column_deduplicated(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        db.execute.return_value = mock_result
        sql = "SELECT x FROM shipments WHERE freight_cost_usd IS NOT NULL GROUP BY freight_cost_usd IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        # freight_cost_usd appears twice but should only be counted once
        assert db.execute.call_count == 1

    def test_db_exception_swallowed_gracefully(self):
        db = MagicMock()
        db.execute.side_effect = Exception("DB error")
        sql = "SELECT AVG(freight_cost_usd) FROM shipments WHERE freight_cost_usd IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert counts == {}

    def test_case_insensitive_detection(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        db.execute.return_value = mock_result
        sql = "SELECT * FROM shipments WHERE weight_kg is not null"
        counts = _count_null_exclusions(db, sql)
        assert "weight_kg" in counts


# ---------------------------------------------------------------------------
# Task 6: _generate_follow_ups
# ---------------------------------------------------------------------------

class TestGenerateFollowUps:
    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self):
        client = MagicMock()
        raw = '["How does this vary by country?", "What about Air shipments only?", "Show top 5 vendors."]'
        client.call = AsyncMock(return_value=raw)
        result = await _generate_follow_ups(client, "question", "answer", ["col1"])
        assert isinstance(result, list)
        assert len(result) <= 3
        assert all(isinstance(s, str) for s in result)

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_empty_list(self):
        client = MagicMock()
        client.call = AsyncMock(return_value="I cannot generate suggestions.")
        result = await _generate_follow_ups(client, "q", "a", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_caps_at_three_items(self):
        client = MagicMock()
        raw = '["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"]'
        client.call = AsyncMock(return_value=raw)
        result = await _generate_follow_ups(client, "q", "a", ["c"])
        assert len(result) <= 3

    @pytest.mark.asyncio
    async def test_non_list_json_returns_empty_list(self):
        client = MagicMock()
        client.call = AsyncMock(return_value='{"key": "value"}')
        result = await _generate_follow_ups(client, "q", "a", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_items_coerced_to_str(self):
        client = MagicMock()
        raw = '[1, 2, 3]'
        client.call = AsyncMock(return_value=raw)
        result = await _generate_follow_ups(client, "q", "a", [])
        assert all(isinstance(s, str) for s in result)


# ---------------------------------------------------------------------------
# Task 7: Route integration — out-of-scope early return
# ---------------------------------------------------------------------------

class TestRouteOutOfScope:
    def test_out_of_scope_returns_answer_no_sql(self):
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner:
            instance = MockPlanner.return_value
            instance.classify_intent = AsyncMock(
                return_value={
                    "intent": "out_of_scope",
                    "answer": "Carbon footprint data is not in the dataset.",
                }
            )
            resp = http.post("/api/query", json={"question": "What is the carbon footprint?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["sql"] == ""
        assert body["columns"] == []
        assert body["rows"] == []
        assert len(body["answer"]) > 0
        assert body["row_count"] == 0
        assert body["suggested_questions"] == []

    def test_successful_response_includes_suggested_questions_field(self):
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        with (
            patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner,
            patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor,
            patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier,
            patch("app.api.routes.analytics._generate_follow_ups", new=AsyncMock(return_value=["Q1?", "Q2?"])),
            patch("app.api.routes.analytics._generate_answer", new=AsyncMock(return_value="Average is $500.")),
        ):
            planner_instance = MockPlanner.return_value
            planner_instance.classify_intent = AsyncMock(return_value={"intent": "answerable"})
            planner_instance.plan = AsyncMock(return_value="What is the average freight cost?")

            executor_instance = MockExecutor.return_value
            executor_instance.generate_sql = AsyncMock(
                return_value="SELECT AVG(freight_cost_usd) FROM shipments"
            )

            verifier_instance = MockVerifier.return_value
            verifier_instance.verify = MagicMock(
                return_value="SELECT AVG(freight_cost_usd) FROM shipments"
            )

            resp = http.post("/api/query", json={"question": "Average freight cost?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "suggested_questions" in body
        assert isinstance(body["suggested_questions"], list)


# ---------------------------------------------------------------------------
# [P6] Error paths must return suggested_questions=[]
# ---------------------------------------------------------------------------

class TestRouteErrorPaths:
    def test_unsafe_sql_returns_error_envelope_not_analytics_body(self):
        """Unsafe SQL returns ErrorResponse (Story 5.4), not AnalyticsQueryResponse with suggested_questions."""
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        with (
            patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner,
            patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor,
            patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier,
        ):
            planner_instance = MockPlanner.return_value
            planner_instance.classify_intent = AsyncMock(return_value={"intent": "answerable"})
            planner_instance.plan = AsyncMock(return_value="drop table")

            executor_instance = MockExecutor.return_value
            executor_instance.generate_sql = AsyncMock(return_value="DROP TABLE shipments")

            verifier_instance = MockVerifier.return_value
            verifier_instance.verify = MagicMock(side_effect=ValueError("Unsafe SQL: DROP"))

            resp = http.post("/api/query", json={"question": "drop table"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] is True
        assert body["error_type"] == "unsafe_sql"
        assert body["detail"]["sql"] == "DROP TABLE shipments"
        assert "suggested_questions" not in body

    def test_query_failed_suggested_questions_empty(self):
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        with (
            patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner,
        ):
            planner_instance = MockPlanner.return_value
            planner_instance.classify_intent = AsyncMock(return_value={"intent": "answerable"})
            planner_instance.plan = AsyncMock(side_effect=Exception("LLM failure"))

            resp = http.post("/api/query", json={"question": "what?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] == "query_failed"
        assert body["suggested_questions"] == []

    def test_unknown_intent_triggers_out_of_scope_early_return(self):
        """[D1] Fail-closed: any intent value other than 'answerable' triggers early return."""
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner:
            planner_instance = MockPlanner.return_value
            planner_instance.classify_intent = AsyncMock(
                return_value={"intent": "partially_answerable", "answer": "Partial data available."}
            )
            resp = http.post("/api/query", json={"question": "some question"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["sql"] == ""
        assert body["suggested_questions"] == []


# ---------------------------------------------------------------------------
# [P7] Route wiring: _count_null_exclusions called when SQL has IS NOT NULL
# ---------------------------------------------------------------------------

class TestNullExclusionsRouteWiring:
    def test_count_null_exclusions_called_for_is_not_null_sql(self):
        from app.main import app
        from fastapi.testclient import TestClient

        http = TestClient(app)
        safe_sql = "SELECT AVG(freight_cost_usd) FROM shipments WHERE freight_cost_usd IS NOT NULL"
        with (
            patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner,
            patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor,
            patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier,
            patch("app.api.routes.analytics._count_null_exclusions", return_value={"freight_cost_usd": 10}) as mock_null,
            patch("app.api.routes.analytics._generate_answer", new=AsyncMock(return_value="avg is $500.")),
            patch("app.api.routes.analytics._generate_follow_ups", new=AsyncMock(return_value=[])),
            patch("app.api.routes.analytics._generate_chart_config", new=AsyncMock(return_value=None)),
        ):
            planner_instance = MockPlanner.return_value
            planner_instance.classify_intent = AsyncMock(return_value={"intent": "answerable"})
            planner_instance.plan = AsyncMock(return_value="avg freight cost")

            executor_instance = MockExecutor.return_value
            executor_instance.generate_sql = AsyncMock(return_value=safe_sql)

            verifier_instance = MockVerifier.return_value
            verifier_instance.verify = MagicMock(return_value=safe_sql)

            resp = http.post("/api/query", json={"question": "avg freight cost?"})

        assert resp.status_code == 200
        mock_null.assert_called_once()
