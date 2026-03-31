import base64
import json
import logging
import re

from app.core.config import settings
from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```[a-z]*\n?|\n?```$", re.MULTILINE)


class ExtractionExecutor:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    async def extract(self, image_bytes: bytes, mime_type: str = "image/png") -> dict:
        """Call the vision model with the image and return the raw parsed JSON dict."""
        img_b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {"role": "system", "content": load_prompt("extraction_system")},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": load_prompt("extraction_fields")},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{img_b64}"},
                    },
                ],
            },
        ]

        def _must_be_json(s: str) -> None:
            cleaned = _FENCE_RE.sub("", s.strip()).strip()
            json.loads(cleaned)

        try:
            raw = await self._client.call(
                model=settings.vision_model,
                messages=messages,
                temperature=0.0,
                validate=_must_be_json,
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("ExtractionExecutor JSON parse failed after retries: %s", e)
            raise ValueError(f"Vision model returned non-JSON response: {e}") from e

        cleaned = _FENCE_RE.sub("", raw.strip()).strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("ExtractionExecutor JSON parse failed: %s", raw[:200])
            raise ValueError(f"Vision model returned non-JSON response: {e}") from e
