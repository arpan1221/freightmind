import re

from app.core.config import settings
from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

_CODE_FENCE_RE = re.compile(r"```(?:sql)?\s*([\s\S]*?)```", re.IGNORECASE)


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
            user_content = f"Previous SQL:\n{previous_sql}\n\nNew question:\n{question}"
        messages = [
            {"role": "system", "content": sql_prompt},
            {"role": "user", "content": user_content},
        ]
        raw = await self._client.call(
            model=settings.analytics_model, messages=messages, temperature=0.0
        )
        return self._strip_fences(raw)

    @staticmethod
    def _strip_fences(text: str) -> str:
        m = _CODE_FENCE_RE.search(text)
        if m:
            return m.group(1).strip()
        return text.strip()
