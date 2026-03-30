import json
import logging
import re

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.analytics.executor import AnalyticsExecutor
from app.agents.analytics.planner import AnalyticsPlanner
from app.agents.analytics.verifier import AnalyticsVerifier
from app.core.config import settings
from app.core.database import get_db
from app.core.prompts import load_prompt
from app.schemas.analytics import AnalyticsQueryRequest, AnalyticsQueryResponse, ChartConfig
from app.services.model_client import ModelClient

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_ROWS_IN_ANSWER_CONTEXT = 5
_MAX_RESPONSE_ROWS = 200  # hard cap: prevents huge responses if LLM omits LIMIT
_NULL_COL_RE = re.compile(r"(\w+)\s+IS\s+NOT\s+NULL", re.IGNORECASE)
_SQL_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


@router.post("/query", response_model=AnalyticsQueryResponse)
async def post_query(
    body: AnalyticsQueryRequest,
    db: Session = Depends(get_db),
) -> AnalyticsQueryResponse:
    client = ModelClient()
    planner = AnalyticsPlanner(client)
    executor = AnalyticsExecutor(client)
    verifier = AnalyticsVerifier()

    # classify_intent has its own try/except so LLM errors here don't become
    # "unsafe_sql" responses via the outer ValueError handler.
    try:
        intent = await planner.classify_intent(body.question)
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
                "answer", "Unable to classify your question. Please rephrase and try again."
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
        safe_sql = verifier.verify(sql)

        result = db.execute(text(safe_sql))
        columns = list(result.keys())
        all_rows = [list(row) for row in result.fetchall()]
        row_count = len(all_rows)
        rows = all_rows[:_MAX_RESPONSE_ROWS]  # cap response size; row_count reflects DB total

        null_exclusions = _count_null_exclusions(db, safe_sql)

        answer = await _generate_answer(
            client, body.question, safe_sql, columns, rows, null_exclusions
        )

        chart_config = await _generate_chart_config(client, body.question, columns, rows)

        suggested_questions = await _generate_follow_ups(
            client, body.question, answer, columns
        )

        return AnalyticsQueryResponse(
            answer=answer,
            sql=safe_sql,
            columns=columns,
            rows=rows,
            row_count=row_count,
            chart_config=chart_config,
            suggested_questions=suggested_questions,
        )

    except ValueError as e:
        logger.warning("Analytics verifier rejected SQL", extra={"error": str(e)})
        return AnalyticsQueryResponse(
            answer="",
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error="unsafe_sql",
            message=str(e),
        )
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


def _count_null_exclusions(db: Session, sql: str) -> dict[str, int]:
    """Count rows excluded by IS NOT NULL filters in the given SQL.

    Returns {column_name: excluded_count} for columns with excluded_count > 0.
    Only queries the shipments table. Strips SQL comments first to avoid false positives.
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


async def _generate_answer(
    client: ModelClient,
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list],
    null_exclusions: dict[str, int],
) -> str:
    preview_rows = rows[:_MAX_ROWS_IN_ANSWER_CONTEXT]
    null_info = (
        ", ".join(f"{n} records with NULL {col}" for col, n in null_exclusions.items())
        if null_exclusions
        else "none"
    )
    context = (
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Columns: {columns}\n"
        f"Rows (first {len(preview_rows)} of {len(rows)}): {preview_rows}\n"
        f"NULL exclusions: {null_info}"
    )
    messages = [
        {"role": "system", "content": load_prompt("analytics_answer")},
        {"role": "user", "content": context},
    ]
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
    raw = await client.call(
        model=settings.analytics_model, messages=messages, temperature=0.7
    )
    try:
        suggestions = json.loads(raw.strip())
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions[:3] if s is not None and str(s).strip()]
    except (json.JSONDecodeError, ValueError):
        logger.warning("_generate_follow_ups JSON parse failed: %s", raw[:100])
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
    raw = ""
    try:
        raw = await client.call(
            model=settings.analytics_model, messages=messages, temperature=0.0
        )
        cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip(), flags=re.MULTILINE)
        result = json.loads(cleaned.strip())
        if result is None:
            return None
        if (
            isinstance(result, dict)
            and result.get("type") in ("bar", "line", "pie")
            and isinstance(result.get("x_key"), str)
            and isinstance(result.get("y_key"), str)
            and result["x_key"] in columns
            and result["y_key"] in columns
        ):
            return ChartConfig(
                type=result["type"], x_key=result["x_key"], y_key=result["y_key"]
            )
        logger.warning("_generate_chart_config invalid structure: %s", result)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_generate_chart_config JSON parse failed: %s", raw[:100])
    except Exception:
        logger.exception("_generate_chart_config unexpected error")
    return None
