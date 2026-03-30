import json
import logging

from app.core.config import settings
from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

logger = logging.getLogger(__name__)


class AnalyticsPlanner:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    async def plan(self, question: str, previous_sql: str | None = None) -> str:
        """Return a clean version of the question (intent classification is Story 2.2 scope)."""
        system_prompt = load_prompt("analytics_system")
        user_content = question
        if previous_sql:
            user_content = f"Previous SQL:\n{previous_sql}\n\nNew question:\n{question}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        return await self._client.call(
            model=settings.analytics_model, messages=messages, temperature=0.0
        )

    async def classify_intent(self, question: str) -> dict:
        """Classify question as answerable or out_of_scope.

        Returns {"intent": "answerable"} or {"intent": "out_of_scope", "answer": "..."}.
        Returns {"intent": "classification_failed", "answer": "..."} on any JSON parse failure.
        """
        planner_prompt = load_prompt("analytics_planner")
        messages = [
            {"role": "system", "content": planner_prompt},
            {"role": "user", "content": question},
        ]
        raw = await self._client.call(
            model=settings.analytics_model, messages=messages, temperature=0.0
        )
        try:
            return json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            logger.warning("classify_intent JSON parse failed: %s", raw[:100])
            return {
                "intent": "classification_failed",
                "answer": "Unable to classify your question. Please rephrase and try again.",
            }
