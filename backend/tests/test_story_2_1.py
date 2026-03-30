"""
Tests for Story 2.1 — Analytics pipeline: POST /api/query (Planner → Executor → Verifier)

Verifies:
- AC1: POST /api/query returns HTTP 200 with answer, sql, columns, rows, row_count
- AC2: Verifier rejects DROP/DELETE/UPDATE/INSERT/ALTER; route returns error="unsafe_sql" (never executes)
- AC3: DB execution uses session.execute(text(...)) — not ORM
- AC4: No raw user input is present in the executed SQL string (NFR7)
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.agents.analytics.verifier import AnalyticsVerifier
from app.agents.analytics.executor import AnalyticsExecutor


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_in_memory_db():
    """Return a (engine, SessionFactory) backed by in-memory SQLite with shipments table.

    StaticPool ensures all connections share the same in-memory DB instance, so
    tables created during setup are visible to sessions yielded by the factory.
    """
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
                freight_cost_usd REAL,
                country TEXT,
                product_group TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO shipments VALUES
                (1, 'Air', 1000.0, 'Nigeria', 'ARV'),
                (2, 'Ocean', 500.0, 'Uganda', 'HRDT'),
                (3, 'Truck', 200.0, 'Kenya', 'ARV')
        """))
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, Factory


def _get_test_client_with_db(session_factory):
    """Return a TestClient with get_db overridden to use the given session factory."""
    from app.main import app
    from app.core.database import get_db

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Verifier unit tests (AC2)
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsVerifier:
    def test_safe_select_passes(self):
        v = AnalyticsVerifier()
        sql = "SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode"
        assert v.verify(sql) == sql

    @pytest.mark.parametrize("keyword", ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"])
    def test_unsafe_keyword_raises(self, keyword):
        v = AnalyticsVerifier()
        with pytest.raises(ValueError, match="Unsafe SQL"):
            v.verify(f"{keyword} TABLE shipments")

    @pytest.mark.parametrize("keyword", ["drop", "delete", "update", "insert", "alter"])
    def test_unsafe_keyword_case_insensitive(self, keyword):
        v = AnalyticsVerifier()
        with pytest.raises(ValueError):
            v.verify(f"{keyword} TABLE shipments")

    def test_returns_sql_unchanged_when_safe(self):
        v = AnalyticsVerifier()
        sql = "SELECT COUNT(*) FROM shipments"
        assert v.verify(sql) is sql


# ─────────────────────────────────────────────────────────────────────────────
# Executor unit tests — fence stripping (AC1)
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsExecutorFenceStripping:
    def test_strips_sql_code_fence(self):
        raw = "```sql\nSELECT 1\n```"
        assert AnalyticsExecutor._strip_fences(raw) == "SELECT 1"

    def test_strips_plain_code_fence(self):
        raw = "```\nSELECT 1\n```"
        assert AnalyticsExecutor._strip_fences(raw) == "SELECT 1"

    def test_no_fence_returned_stripped(self):
        raw = "  SELECT 1  "
        assert AnalyticsExecutor._strip_fences(raw) == "SELECT 1"

    def test_multiline_sql_in_fence(self):
        raw = "```sql\nSELECT shipment_mode,\n  AVG(freight_cost_usd)\nFROM shipments\nGROUP BY 1\n```"
        result = AnalyticsExecutor._strip_fences(raw)
        assert "SELECT" in result
        assert "```" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Route integration tests (AC1, AC2, AC3, AC4)
# ─────────────────────────────────────────────────────────────────────────────

class TestPostQueryRoute:
    def setup_method(self):
        """Reset dependency overrides between tests."""
        from app.main import app
        app.dependency_overrides.clear()

    def _make_mock_client(self, planner_response: str, sql_response: str, answer_response: str):
        """Return a ModelClient mock with sequenced call() responses.

        Call order (Story 2.3 pipeline):
          0. classify_intent      → '{"intent": "answerable"}'
          1. plan                 → planner_response
          2. generate_sql         → sql_response
          3. _generate_answer     → answer_response
          4. _generate_chart_config → 'null'
          5. _generate_follow_ups → '["Q1?", "Q2?"]'
        """
        mock = MagicMock()
        mock.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                planner_response,
                sql_response,
                answer_response,
                'null',
                '["Q1?", "Q2?"]',
            ]
        )
        return mock

    def test_post_query_returns_200_with_correct_shape(self):
        """AC1: POST /api/query returns HTTP 200 with answer, sql, columns, rows, row_count."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        safe_sql = "SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode"
        mock_client = self._make_mock_client(
            planner_response="What is the average freight cost per shipment mode?",
            sql_response=safe_sql,
            answer_response="The average freight cost varies by mode: Air $1000, Ocean $500, Truck $200.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "What is average freight cost per mode?"})

        assert response.status_code == 200
        body = response.json()
        assert "answer" in body
        assert "sql" in body
        assert "columns" in body
        assert "rows" in body
        assert "row_count" in body
        assert body["error"] is None
        assert body["row_count"] == len(body["rows"])

    def test_post_query_columns_and_rows_match_sql_result(self):
        """AC3: uses session.execute(text(...)) and returns actual DB results."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        safe_sql = "SELECT shipment_mode, freight_cost_usd FROM shipments ORDER BY id"
        mock_client = self._make_mock_client(
            planner_response="List shipment modes and costs",
            sql_response=safe_sql,
            answer_response="There are 3 shipments: Air at $1000, Ocean at $500, Truck at $200.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "list all modes and costs"})

        assert response.status_code == 200
        body = response.json()
        assert body["columns"] == ["shipment_mode", "freight_cost_usd"]
        assert body["row_count"] == 3
        assert ["Air", 1000.0] in body["rows"]

    def test_unsafe_sql_returns_error_not_executed(self):
        """AC2: Verifier rejects DROP/DELETE/etc. Returns error='unsafe_sql', sql never executed."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        mock_client.call = AsyncMock(side_effect=[
            '{"intent": "answerable"}',  # classify_intent
            "drop all data",             # planner
            "DROP TABLE shipments",      # executor
        ])

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "drop all data"})

        assert response.status_code == 200
        body = response.json()
        assert body["error"] == "unsafe_sql"
        assert body["sql"] == ""
        assert body["rows"] == []
        assert body["row_count"] == 0

    @pytest.mark.parametrize("keyword", ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"])
    def test_each_unsafe_keyword_blocked(self, keyword):
        """AC2: Each blocked keyword returns unsafe_sql error."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        mock_client.call = AsyncMock(side_effect=[
            '{"intent": "answerable"}',   # classify_intent
            "bad question",               # planner
            f"{keyword} TABLE shipments", # executor
        ])

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "bad question"})

        assert response.status_code == 200
        assert response.json()["error"] == "unsafe_sql"

    def test_question_not_in_executed_sql(self):
        """AC4: NFR7 guard — raw user input (question text) must not appear in the executed SQL."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        unique_question = "UniqueMarkerXYZ123 average freight cost"
        safe_sql = "SELECT AVG(freight_cost_usd) FROM shipments WHERE freight_cost_usd IS NOT NULL"

        mock_client = self._make_mock_client(
            planner_response="What is average freight cost?",
            sql_response=safe_sql,
            answer_response="Average freight cost is $566.67.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": unique_question})

        assert response.status_code == 200
        body = response.json()
        # The unique marker from the question must NOT appear in the executed SQL
        assert "UniqueMarkerXYZ123" not in body["sql"]

    def test_db_execute_uses_text_wrapper(self):
        """AC3: Verify db.execute is called with sqlalchemy text() — not raw string or ORM."""
        _, factory = _make_in_memory_db()

        from app.main import app
        from app.core.database import get_db

        captured_args = []

        def override_get_db():
            db = factory()
            original_execute = db.execute

            def capturing_execute(stmt, *args, **kwargs):
                captured_args.append(stmt)
                return original_execute(stmt, *args, **kwargs)

            db.execute = capturing_execute
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        safe_sql = "SELECT COUNT(*) AS cnt FROM shipments"
        mock_client = self._make_mock_client(
            planner_response="count all shipments",
            sql_response=safe_sql,
            answer_response="There are 3 shipments.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "how many shipments?"})

        assert response.status_code == 200
        # At least one execute call should have been made
        assert len(captured_args) >= 1
        # The execute arg should be a SQLAlchemy text clause, not a raw string
        from sqlalchemy.sql.elements import TextClause
        assert any(isinstance(arg, TextClause) for arg in captured_args)

    def test_db_error_returns_query_failed_not_500(self):
        """Route must return HTTP 200 with error='query_failed' even if DB raises."""
        from app.main import app
        from app.core.database import get_db

        def broken_get_db():
            db = MagicMock()
            db.execute.side_effect = Exception("DB connection lost")
            yield db

        app.dependency_overrides[get_db] = broken_get_db
        client = TestClient(app)

        safe_sql = "SELECT COUNT(*) FROM shipments"
        mock_client = self._make_mock_client(
            planner_response="count shipments",
            sql_response=safe_sql,
            answer_response="",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "how many?"})

        assert response.status_code == 200
        body = response.json()
        assert body["error"] == "query_failed"

    def test_response_has_no_envelope_wrapper(self):
        """Response must be direct AnalyticsQueryResponse — no 'data' or 'result' wrapper."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        safe_sql = "SELECT COUNT(*) AS cnt FROM shipments"
        mock_client = self._make_mock_client(
            planner_response="count",
            sql_response=safe_sql,
            answer_response="3 shipments.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "count"})

        body = response.json()
        # Top-level keys must be direct fields, not wrapped
        assert "data" not in body
        assert "result" not in body
        assert "answer" in body

    def test_previous_sql_passed_to_executor(self):
        """P8: previous_sql is forwarded to the executor (follow-up query context)."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        safe_sql = "SELECT COUNT(*) AS cnt FROM shipments"
        mock_client = self._make_mock_client(
            planner_response="count shipments",
            sql_response=safe_sql,
            answer_response="3 shipments total.",
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={
                    "question": "how many?",
                    "previous_sql": "SELECT * FROM shipments LIMIT 5",
                },
            )

        assert response.status_code == 200
        assert response.json()["error"] is None

    def test_previous_sql_not_in_executed_sql(self):
        """P8/NFR7: previous_sql content must not appear verbatim in the executed SQL."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        safe_sql = "SELECT COUNT(*) AS cnt FROM shipments"
        mock_client = self._make_mock_client(
            planner_response="refined question",
            sql_response=safe_sql,
            answer_response="3 shipments.",
        )

        injection_attempt = "SELECT * FROM shipments; DROP TABLE shipments"

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "count", "previous_sql": injection_attempt},
            )

        assert response.status_code == 200
        body = response.json()
        # The injection text must NOT appear in the executed SQL — only LLM-generated SQL runs
        assert "DROP" not in body["sql"]
        assert injection_attempt not in body["sql"]

    def test_empty_question_rejected(self):
        """P7: empty question fails Pydantic validation with 422."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        response = client.post("/api/query", json={"question": ""})
        assert response.status_code == 422

    def test_classification_failed_returns_error(self):
        """D1: classify_intent parse failure returns error='classification_failed', not 500."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        # Simulate classify_intent returning non-JSON (triggers classification_failed path)
        mock_client.call = AsyncMock(return_value="this is not json")

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "what is the cost?"})

        assert response.status_code == 200
        body = response.json()
        assert body["error"] == "classification_failed"
