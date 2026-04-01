import re

from app.core.config import settings
from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

_CODE_FENCE_RE = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)

# Column name corrections for extracted_documents — the model frequently uses
# shipments column names when querying extracted_documents.
# Only applied within extracted_documents context (alias "ed" or table name present).
_ED_COLUMN_FIXES = {
    "freight_cost_usd": "total_freight_cost_usd",
    "weight_kg": "total_weight_kg",
    "insurance_usd": "total_insurance_usd",
    "line_item_insurance_usd": "total_insurance_usd",
}

# Matches ed.freight_cost_usd or extracted_documents.freight_cost_usd patterns
_ED_COL_RE = re.compile(
    r"\b(ed\d?|extracted_documents)\.(freight_cost_usd|weight_kg|insurance_usd|line_item_insurance_usd)\b",
    re.IGNORECASE,
)

# Matches spurious IS NOT NULL guards on cost/weight columns inside COUNT-only queries.
# These are stripped when the SQL has no AVG() or SUM() — the model adds them incorrectly.
_NULL_GUARD_RE = re.compile(
    r"\s+AND\s+(?:freight_cost_usd|weight_kg)\s+IS\s+NOT\s+NULL",
    re.IGNORECASE,
)

# Rewrites EXTRACT(YEAR FROM col) → strftime('%Y', col), etc. — SQLite has no EXTRACT().
_EXTRACT_RE = re.compile(
    r"\bEXTRACT\s*\(\s*(YEAR|MONTH|DAY)\s+FROM\s+(\w+)\s*\)",
    re.IGNORECASE,
)
_EXTRACT_FMT = {"year": "%Y", "month": "%m", "day": "%d"}


class AnalyticsExecutor:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    async def generate_sql(self, question: str, previous_sql: str | None = None) -> str:
        """Generate a SQLite SELECT query from the natural language question.

        The question is passed as a user message — it is NEVER interpolated into SQL.
        """
        sql_prompt = load_prompt("analytics_sql_gen")
        user_content = question
        if previous_sql:
            user_content = (
                f"Previous SQL (for column/table reference only — do NOT copy its structure):\n"
                f"{previous_sql}\n\nNew question:\n{question}"
            )
        messages = [
            {"role": "system", "content": sql_prompt},
            {"role": "user", "content": user_content},
        ]
        raw = await self._client.call(
            model=settings.analytics_model, messages=messages, temperature=0.0
        )
        sql = self._strip_fences(raw)
        sql = self._remove_spurious_null_guards(sql)
        sql = self._rewrite_extract(sql)
        return self._fix_ed_column_names(sql)

    @staticmethod
    def _strip_fences(text: str) -> str:
        m = _CODE_FENCE_RE.search(text)
        if m:
            return m.group(1).strip()
        return text.strip()

    @staticmethod
    def _rewrite_extract(sql: str) -> str:
        """Rewrite EXTRACT(YEAR/MONTH/DAY FROM col) → strftime('%Y/%m/%d', col).

        SQLite has no EXTRACT() function. The model occasionally generates it despite
        prompt instructions. This catches and silently corrects those cases.
        """
        def _replace(m: re.Match) -> str:
            part = m.group(1).lower()
            col = m.group(2)
            fmt = _EXTRACT_FMT.get(part, "%Y")
            return f"strftime('{fmt}', {col})"

        return _EXTRACT_RE.sub(_replace, sql)

    @staticmethod
    def _fix_ed_column_names(sql: str) -> str:
        """Rewrite wrong column names when used with extracted_documents aliases.

        The model frequently uses shipments column names (freight_cost_usd, weight_kg)
        when querying extracted_documents. This rewrites ed.freight_cost_usd →
        ed.total_freight_cost_usd, etc.
        """
        def _replace(m: re.Match) -> str:
            alias = m.group(1)
            wrong_col = m.group(2).lower()
            correct_col = _ED_COLUMN_FIXES.get(wrong_col, wrong_col)
            return f"{alias}.{correct_col}"

        return _ED_COL_RE.sub(_replace, sql)

    @staticmethod
    def _remove_spurious_null_guards(sql: str) -> str:
        """Strip freight_cost_usd/weight_kg IS NOT NULL from COUNT-only queries.

        The model frequently adds these guards even when the query only uses COUNT(*).
        They are only valid when AVG() or SUM() is applied to those columns.
        """
        sql_upper = sql.upper()
        has_aggregate = bool(re.search(r"\b(AVG|SUM)\s*\(", sql_upper))
        if has_aggregate:
            return sql
        return _NULL_GUARD_RE.sub("", sql)
