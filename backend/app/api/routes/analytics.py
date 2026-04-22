import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.analytics.executor import AnalyticsExecutor
from app.agents.analytics.planner import AnalyticsPlanner
from app.agents.analytics.verifier import AnalyticsVerifier
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ModelUnavailableError, RateLimitError
from app.core.prompts import load_prompt
from app.schemas.analytics import (
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    ChartConfig,
)
from app.schemas.common import ErrorResponse
from app.services.model_client import ModelClient
from app.services.stats_service import detect_anomaly

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_ROWS_IN_ANSWER_CONTEXT = 5
_MAX_RESPONSE_ROWS = 200  # hard cap: prevents huge responses if LLM omits LIMIT

# Stable error_type values (Story 5.4 / FR32) — also documented on POST /api/query OpenAPI.
ERROR_TYPE_UNSAFE_SQL = "unsafe_sql"
ERROR_TYPE_SQL_EXECUTION = "sql_execution_error"
ERROR_TYPE_DATABASE_UNAVAILABLE = "database_unavailable"

_MSG_UNSAFE_SQL = (
    "The generated query was not allowed. Only read-only SELECT queries are permitted."
)
_MSG_SQL_EXECUTION = (
    "The generated SQL could not be executed. Try rephrasing your question."
)
_MSG_DATABASE_UNAVAILABLE = (
    "The database could not run this query right now. Try again in a moment."
)
_NULL_COL_RE = re.compile(r"(\w+)\s+IS\s+NOT\s+NULL", re.IGNORECASE)
_SQL_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# ── SQL auto-repair: fix known LLM column-name hallucinations ────────
# When the LLM uses shipments column names on extracted_documents, the query
# fails with an OperationalError.  These regex replacements fix the most
# common mismatches *only* when they appear in extracted_documents context.

# Column rewrites: (wrong_name, correct_name) applied only near extracted_documents refs.
_EXTRACTED_COL_FIXES: list[tuple[re.Pattern[str], str]] = [
    # freight_cost_usd → total_freight_cost_usd  (but not when already prefixed with total_)
    (re.compile(r"(?<!\w)(?:e\.|ed\.|extracted_documents\.)freight_cost_usd\b", re.I),
     lambda m: m.group(0).rsplit(".", 1)[0] + ".total_freight_cost_usd"),
    # weight_kg → total_weight_kg
    (re.compile(r"(?<!\w)(?:e\.|ed\.|extracted_documents\.)weight_kg\b", re.I),
     lambda m: m.group(0).rsplit(".", 1)[0] + ".total_weight_kg"),
    # line_item_insurance_usd → total_insurance_usd
    (re.compile(r"(?<!\w)(?:e\.|ed\.|extracted_documents\.)line_item_insurance_usd\b", re.I),
     lambda m: m.group(0).rsplit(".", 1)[0] + ".total_insurance_usd"),
    # country → destination_country
    (re.compile(r"(?<!\w)(?:e\.|ed\.|extracted_documents\.)country\b", re.I),
     lambda m: m.group(0).rsplit(".", 1)[0] + ".destination_country"),
    # vendor → carrier_vendor
    (re.compile(r"(?<!\w)(?:e\.|ed\.|extracted_documents\.)vendor\b", re.I),
     lambda m: m.group(0).rsplit(".", 1)[0] + ".carrier_vendor"),
]

# Bare (unprefixed) column-name fix when query ONLY touches extracted_documents
_BARE_COL_FIXES: list[tuple[str, str]] = [
    ("freight_cost_usd", "total_freight_cost_usd"),
    ("weight_kg", "total_weight_kg"),
    ("line_item_insurance_usd", "total_insurance_usd"),
]

# strftime returns TEXT; fix integer comparisons like  strftime('%Y',…) = 2014
_STRFTIME_INT_RE = re.compile(
    r"(strftime\s*\([^)]+\))\s*=\s*(\d{4})\b", re.I
)


def _auto_repair_sql(sql: str) -> str:
    """Best-effort fix for known LLM SQL generation mistakes.

    Returns the (possibly rewritten) SQL.  Never raises.
    """
    repaired = sql

    # 1. Fix prefixed column names (e.g. e.freight_cost_usd → e.total_freight_cost_usd)
    if re.search(r"\bextracted_documents\b", repaired, re.I):
        for pattern, repl in _EXTRACTED_COL_FIXES:
            repaired = pattern.sub(repl, repaired)

    # 2. Fix bare column names when extracted_documents is the ONLY table
    if (re.search(r"\bextracted_documents\b", repaired, re.I)
            and not re.search(r"\bshipments\b", repaired, re.I)):
        for wrong, right in _BARE_COL_FIXES:
            # Only replace bare names (not already prefixed with total_)
            repaired = re.sub(
                rf"(?<!\w)(?<!total_){re.escape(wrong)}\b",
                right,
                repaired,
                flags=re.I,
            )

    # 3. Fix strftime integer comparison: = 2014 → = '2014'
    repaired = _STRFTIME_INT_RE.sub(r"\1 = '\2'", repaired)

    if repaired != sql:
        logger.info("SQL auto-repair applied:\n  BEFORE: %s\n  AFTER:  %s", sql, repaired)

    return repaired


@dataclass(frozen=True)
class _RowsBundle:
    """Successful SQL phase: ready for answer generation (streaming or not)."""

    client: ModelClient
    question: str
    safe_sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    null_exclusions: dict[str, int]
    anomaly_context: str | None = None


def _sql_crosses_shipments_and_extracted(sql: str) -> bool:
    """True if generated SQL references both linkage tables (Story 4.2 cross-table path).

    Strips comments first — same idea as `_count_null_exclusions` — so table names in
    ``--`` / ``/* */`` fragments do not alone trigger linkage narrative.
    """
    sql_no_comments = _SQL_BLOCK_COMMENT_RE.sub("", _SQL_LINE_COMMENT_RE.sub("", sql))
    s = sql_no_comments.lower()
    return "shipments" in s and "extracted_documents" in s


# Heuristics for "upload / invoice / extraction" questions when no confirmed rows exist (Story 4.1 AC2).
# Tight patterns avoid false positives (e.g. "confirmed delivery" on shipments).
_DOC_QUESTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(how many|count)\b.*\b(invoice|upload|extraction)s?\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(uploaded?|my)\b.*\b(invoice|invoices|document|documents|file|files)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bextracted\s+document", re.IGNORECASE),
    re.compile(
        r"\b(invoice|invoices)\s+(have|did)\s+i\s+(upload|add|confirm)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(confirmed|confirm)\s+(invoice|upload|extraction|document)s?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(invoice|upload|extraction)\s+data\b", re.IGNORECASE),
    re.compile(r"\bhow\s+many\s+invoices?\b", re.IGNORECASE),
    # "List my extractions" / "show extractions" without saying "invoice"
    re.compile(r"\b(my|our|the)\s+extractions?\b", re.IGNORECASE),
    re.compile(r"\b(list|show)\b.*\bextractions?\b", re.IGNORECASE),
    # Upload-centric phrasing without "invoice" / "document" (Story 4.1 follow-up)
    re.compile(r"\bmy\s+uploads?\b", re.IGNORECASE),
    re.compile(
        r"\b(what|which)\s+(did|have|was)\s+(i|we)\s+upload",
        re.IGNORECASE,
    ),
)


def _question_targets_extracted_documents(question: str) -> bool:
    """True if the analyst is likely asking about uploads or extracted invoice data."""
    return any(p.search(question) for p in _DOC_QUESTION_PATTERNS)


def _count_confirmed_extractions(db: Session) -> int:
    """Count rows the user has confirmed (confirmed_by_user = 1).

    Returns 0 when ``extracted_documents`` is missing (minimal test DB) so shipment-only
    queries still run. Other DB errors propagate.
    """
    try:
        result = db.execute(
            text("SELECT COUNT(*) FROM extracted_documents WHERE confirmed_by_user = 1")
        )
        return int(result.scalar() or 0)
    except OperationalError as exc:
        if "no such table" in str(exc).lower():
            return 0
        raise


def _should_answer_without_confirmed_extractions(db: Session, question: str) -> bool:
    """Analyst-facing 'my data' uses confirmed extractions only — no SQL if none and question needs them."""
    if _count_confirmed_extractions(db) > 0:
        return False
    return _question_targets_extracted_documents(question)


def _no_confirmed_extractions_response() -> AnalyticsQueryResponse:
    """Honest answer when the question needs extracted data but nothing is confirmed yet."""
    return AnalyticsQueryResponse(
        answer=(
            "There are no confirmed uploaded invoices in the database yet. "
            "Open the Documents tab, upload a freight document, review it, and click Confirm "
            "to store it for analytics. You can still ask questions about the historical SCMS "
            "shipments dataset in this chat."
        ),
        sql="",
        columns=[],
        rows=[],
        row_count=0,
        suggested_questions=[
            "What is the average freight cost by shipment mode?",
            "Which countries have the most shipments in the dataset?",
        ],
    )


def _sse_event(event: str, payload: dict[str, Any]) -> bytes:
    """Format one Server-Sent Event frame (event + JSON data line)."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")


async def _run_pipeline_to_rows(
    body: AnalyticsQueryRequest,
    db: Session,
) -> AnalyticsQueryResponse | JSONResponse | _RowsBundle:
    """Shared Planner → Executor → Verifier → DB path; returns rows or an early/error response."""
    client = ModelClient.for_analytics()
    planner = AnalyticsPlanner(client)
    executor = AnalyticsExecutor(client)
    verifier = AnalyticsVerifier()

    # No confirmed extractions + document-themed question: answer before intent (Story 4.1 deferred).
    # Avoids misclassified out_of_scope hiding the empty-state message.
    # If the confirmed-count query fails, defer to the normal pipeline (same as when this lived
    # inside the main try — see test_db_error_returns_query_failed_not_500).
    should_empty_state = False
    try:
        should_empty_state = _should_answer_without_confirmed_extractions(db, body.question)
    except Exception:
        logger.warning(
            "Confirmed-extraction precheck failed; continuing to intent classification",
            exc_info=True,
        )

    if should_empty_state:
        return _no_confirmed_extractions_response()

    # classify_intent has its own try/except so LLM errors here don't become
    # structured SQL error responses.
    try:
        intent = await planner.classify_intent(body.question)
    except (RateLimitError, ModelUnavailableError):
        raise
    except Exception:
        logger.warning("classify_intent raised unexpectedly")
        intent = {
            "intent": "classification_failed",
            "answer": "Unable to classify your question. Please rephrase and try again.",
        }

    # Normalize intent value (guard against model returning wrong case)
    intent_value = intent.get("intent", "").lower()

    if intent_value == "out_of_scope":
        return AnalyticsQueryResponse(
            answer=intent.get(
                "answer", "This question cannot be answered from the available data."
            ),
            sql="",
            columns=[],
            rows=[],
            row_count=0,
        )

    if intent_value == "classification_failed":
        return AnalyticsQueryResponse(
            answer=intent.get(
                "answer",
                "Unable to classify your question. Please rephrase and try again.",
            ),
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error="classification_failed",
            message="Intent classification failed — could not parse model response.",
        )

    try:
        refined_question = await planner.plan(body.question, body.previous_sql)
        sql = await executor.generate_sql(refined_question, body.previous_sql)
        try:
            safe_sql = verifier.verify(sql)
        except ValueError:
            logger.warning("Analytics verifier rejected SQL")
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error=True,
                    error_type=ERROR_TYPE_UNSAFE_SQL,
                    message=_MSG_UNSAFE_SQL,
                    detail={"sql": sql},
                ).model_dump(),
            )

        safe_sql = _auto_repair_sql(safe_sql)

        try:
            result = db.execute(text(safe_sql))
        except OperationalError as exc:
            # SQLite uses OperationalError for bad SQL too; reserve 503 for lock/contention only.
            if "locked" in str(exc).lower():
                logger.warning("Database locked after SQL verification", exc_info=True)
                return JSONResponse(
                    status_code=503,
                    content=ErrorResponse(
                        error=True,
                        error_type=ERROR_TYPE_DATABASE_UNAVAILABLE,
                        message=_MSG_DATABASE_UNAVAILABLE,
                        detail={"sql": safe_sql},
                    ).model_dump(),
                )
            logger.warning("SQL execution failed after verification", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    error=True,
                    error_type=ERROR_TYPE_SQL_EXECUTION,
                    message=_MSG_SQL_EXECUTION,
                    detail={"sql": safe_sql},
                ).model_dump(),
            )
        except SQLAlchemyError:
            logger.warning("SQL execution failed after verification", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    error=True,
                    error_type=ERROR_TYPE_SQL_EXECUTION,
                    message=_MSG_SQL_EXECUTION,
                    detail={"sql": safe_sql},
                ).model_dump(),
            )
        columns = list(result.keys())
        all_rows = [list(row) for row in result.fetchall()]
        row_count = len(all_rows)
        rows = all_rows[
            :_MAX_RESPONSE_ROWS
        ]  # cap response size; row_count reflects DB total

        null_exclusions = _count_null_exclusions(db, safe_sql)

        anomaly_ctx: str | None = None
        try:
            anomaly_ctx = detect_anomaly(db, safe_sql, columns, rows)
        except Exception:
            logger.debug("anomaly detection skipped", exc_info=True)

        return _RowsBundle(
            client=client,
            question=body.question,
            safe_sql=safe_sql,
            columns=columns,
            rows=rows,
            row_count=row_count,
            null_exclusions=null_exclusions,
            anomaly_context=anomaly_ctx,
        )

    except (RateLimitError, ModelUnavailableError):
        raise
    except Exception as e:
        logger.exception("Analytics query failed")
        return AnalyticsQueryResponse(
            answer="",
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error="query_failed",
            message=str(e),
        )


@router.post(
    "/query",
    response_model=AnalyticsQueryResponse,
    responses={
        400: {
            "description": "Generated SQL failed verification (unsafe or disallowed).",
            "model": ErrorResponse,
        },
        422: {
            "description": "Verified SQL failed to execute against the database.",
            "model": ErrorResponse,
        },
    },
)
async def post_query(
    body: AnalyticsQueryRequest,
    db: Session = Depends(get_db),
) -> AnalyticsQueryResponse | JSONResponse:
    phase = await _run_pipeline_to_rows(body, db)
    if isinstance(phase, JSONResponse):
        return phase
    if isinstance(phase, AnalyticsQueryResponse):
        return phase

    rb = phase
    try:
        answer = await _generate_answer(
            rb.client, rb.question, rb.safe_sql, rb.columns, rb.rows,
            rb.null_exclusions, rb.anomaly_context,
        )

        chart_config = await _generate_chart_config(
            rb.client, rb.question, rb.columns, rb.rows
        )

        suggested_questions = await _generate_follow_ups(
            rb.client, rb.question, answer, rb.columns
        )

        return AnalyticsQueryResponse(
            answer=answer,
            sql=rb.safe_sql,
            columns=rb.columns,
            rows=rb.rows,
            row_count=rb.row_count,
            chart_config=chart_config,
            suggested_questions=suggested_questions,
        )

    except (RateLimitError, ModelUnavailableError):
        raise
    except Exception as e:
        logger.exception("Analytics query failed")
        return AnalyticsQueryResponse(
            answer="",
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error="query_failed",
            message=str(e),
        )


_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post(
    "/query/stream",
    response_model=None,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        200: {
            "description": "Server-Sent Events: metadata → delta → complete (or single complete for early exits).",
            "content": {
                "text/event-stream": {},
            },
        },
    },
)
async def post_query_stream(
    body: AnalyticsQueryRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse | JSONResponse:
    """Same pipeline as ``POST /api/query``, but streams the natural-language answer as SSE.

    Events:
    - ``metadata``: ``sql``, ``columns``, ``rows``, ``row_count`` (result ready; answer still streaming).
    - ``delta``: ``t`` — incremental answer text.
    - ``complete``: full :class:`AnalyticsQueryResponse` body (includes chart and follow-ups).
    - ``error``: structured failure during or after streaming (rare).

    Early exits (out of scope, empty state, etc.) emit a single ``complete`` event.
    """
    phase = await _run_pipeline_to_rows(body, db)
    if isinstance(phase, JSONResponse):
        return phase

    if isinstance(phase, AnalyticsQueryResponse):

        async def early_only() -> Any:
            yield _sse_event("complete", phase.model_dump())

        return StreamingResponse(
            early_only(),
            media_type="text/event-stream",
            headers=_STREAM_HEADERS,
        )

    rb = phase

    async def gen() -> Any:
        yield _sse_event(
            "metadata",
            {
                "sql": rb.safe_sql,
                "columns": rb.columns,
                "rows": rb.rows,
                "row_count": rb.row_count,
            },
        )
        messages = _answer_messages(
            rb.question,
            rb.safe_sql,
            rb.columns,
            rb.rows,
            rb.null_exclusions,
            rb.anomaly_context,
        )
        parts: list[str] = []
        try:
            async for delta in rb.client.stream_call(
                model=settings.analytics_model,
                messages=messages,
                temperature=0.0,
            ):
                parts.append(delta)
                yield _sse_event("delta", {"t": delta})
        except (RateLimitError, ModelUnavailableError):
            raise
        except Exception as e:
            logger.exception("Analytics stream failed")
            yield _sse_event(
                "error",
                {"error": "query_failed", "message": str(e)},
            )
            return

        answer = "".join(parts)
        try:
            chart_config = await _generate_chart_config(
                rb.client, rb.question, rb.columns, rb.rows
            )
            suggested_questions = await _generate_follow_ups(
                rb.client, rb.question, answer, rb.columns
            )
        except Exception as e:
            logger.exception("Analytics post-stream enrichment failed")
            yield _sse_event(
                "error",
                {"error": "query_failed", "message": str(e)},
            )
            return

        resp = AnalyticsQueryResponse(
            answer=answer,
            sql=rb.safe_sql,
            columns=rb.columns,
            rows=rb.rows,
            row_count=rb.row_count,
            chart_config=chart_config,
            suggested_questions=suggested_questions,
        )
        yield _sse_event("complete", resp.model_dump())

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )


def _count_null_exclusions(db: Session, sql: str) -> dict[str, int]:
    """Count rows excluded by IS NOT NULL filters in the given SQL.

    Returns {column_name: excluded_count} for columns with excluded_count > 0.
    Only queries the **shipments** table — not extracted_documents (ambiguous shared column
    names; cross-table queries may omit extracted NULL stats). Strips SQL comments first.
    Column names are double-quoted to prevent keyword conflicts.
    """
    sql_no_comments = _SQL_BLOCK_COMMENT_RE.sub("", _SQL_LINE_COMMENT_RE.sub("", sql))
    cols = list(dict.fromkeys(_NULL_COL_RE.findall(sql_no_comments)))
    counts: dict[str, int] = {}
    for col in cols:
        try:
            # Double-quote the column name to handle SQLite keyword clashes
            result = db.execute(
                text(f'SELECT COUNT(*) FROM shipments WHERE "{col}" IS NULL')
            )
            n = result.scalar() or 0
            if n > 0:
                counts[col] = n
        except Exception as e:
            logger.debug("_count_null_exclusions: skipping column %r: %s", col, e)
    return counts


def _answer_messages(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list],
    null_exclusions: dict[str, int],
    anomaly_context: str | None = None,
) -> list[dict[str, str]]:
    """Chat messages for the analytics natural-language answer (shared by sync and stream)."""
    preview_rows = rows[:_MAX_ROWS_IN_ANSWER_CONTEXT]
    null_info = (
        ", ".join(f"{n} records with NULL {col}" for col, n in null_exclusions.items())
        if null_exclusions
        else "none"
    )
    linkage_note = ""
    if _sql_crosses_shipments_and_extracted(sql):
        linkage_note = (
            "\nLinkage note: NULL exclusion counts (if any) are for **shipments** columns only. "
            "Explain how the result combines or compares the historical SCMS **shipments** "
            "dataset with the user's **confirmed** rows in **extracted_documents**."
        )
    context = (
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Columns: {columns}\n"
        f"Rows (first {len(preview_rows)} of {len(rows)}): {preview_rows}\n"
        f"NULL exclusions: {null_info}"
        f"{linkage_note}"
        f"{anomaly_context or ''}"
    )
    return [
        {"role": "system", "content": load_prompt("analytics_answer")},
        {"role": "user", "content": context},
    ]


async def _generate_answer(
    client: ModelClient,
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list],
    null_exclusions: dict[str, int],
    anomaly_context: str | None = None,
) -> str:
    messages = _answer_messages(question, sql, columns, rows, null_exclusions, anomaly_context)
    return await client.call(
        model=settings.analytics_model, messages=messages, temperature=0.0
    )


async def _generate_follow_ups(
    client: ModelClient,
    question: str,
    answer: str,
    columns: list[str],
) -> list[str]:
    context = f"Question: {question}\nAnswer: {answer}\nResult columns: {columns}"
    messages = [
        {"role": "system", "content": load_prompt("analytics_followup")},
        {"role": "user", "content": context},
    ]

    def _must_be_followup_list(s: str) -> None:
        data = json.loads(s.strip())
        if not isinstance(data, list):
            raise ValueError("follow-up response must be a JSON array")

    try:
        raw = await client.call(
            model=settings.analytics_model,
            messages=messages,
            temperature=0.7,
            validate=_must_be_followup_list,
        )
        suggestions = json.loads(raw.strip())
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions[:3] if s is not None and str(s).strip()]
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("_generate_follow_ups JSON parse failed after retries: %s", e)
    return []


async def _generate_chart_config(
    client: ModelClient,
    question: str,
    columns: list[str],
    rows: list[list],
) -> ChartConfig | None:
    """Generate chart configuration for quantitative results.

    Returns a ChartConfig or None. Never raises — all failures return None.
    """
    if not rows or not columns:
        return None

    preview_rows = rows[:5]
    context = (
        f"Question: {question}\n"
        f"Result columns: {columns}\n"
        f"Sample rows (first {len(preview_rows)} of {len(rows)}): {preview_rows}"
    )
    messages = [
        {"role": "system", "content": load_prompt("analytics_chart")},
        {"role": "user", "content": context},
    ]

    def _must_be_chart_json(s: str) -> None:
        cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", s.strip(), flags=re.MULTILINE)
        json.loads(cleaned.strip())

    raw = ""
    try:
        raw = await client.call(
            model=settings.analytics_model,
            messages=messages,
            temperature=0.0,
            validate=_must_be_chart_json,
        )
        cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip(), flags=re.MULTILINE)
        result = json.loads(cleaned.strip())
        if result is None:
            return None
        if isinstance(result, dict) and result.get("type") in (
            "bar", "line", "pie", "scatter", "stacked_bar"
        ):
            chart_type = result["type"]
            x_key = result.get("x_key")
            y_key = result.get("y_key") or ""
            y_keys = result.get("y_keys")

            if not isinstance(x_key, str) or x_key not in columns:
                logger.warning("_generate_chart_config invalid x_key: %s", result)
            elif chart_type == "stacked_bar":
                if isinstance(y_keys, list) and all(k in columns for k in y_keys) and len(y_keys) >= 2:
                    return ChartConfig(type=chart_type, x_key=x_key, y_key=y_keys[0], y_keys=y_keys)
                logger.warning("_generate_chart_config invalid y_keys for stacked_bar: %s", result)
            elif chart_type == "scatter":
                if isinstance(y_key, str) and y_key in columns:
                    return ChartConfig(type=chart_type, x_key=x_key, y_key=y_key)
                logger.warning("_generate_chart_config invalid y_key for scatter: %s", result)
            elif isinstance(y_key, str) and y_key in columns:
                return ChartConfig(type=chart_type, x_key=x_key, y_key=y_key)
        logger.warning("_generate_chart_config invalid structure: %s", result)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_generate_chart_config JSON parse failed: %s", raw[:100])
    except Exception:
        logger.exception("_generate_chart_config unexpected error")
    return None
