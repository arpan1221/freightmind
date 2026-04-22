import base64
import json
import logging
import re

from app.core.config import settings
from app.core.prompts import load_prompt
from app.services.model_client import ModelClient

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```[a-z]*\n?|\n?```$", re.MULTILINE)

DOCUMENT_TYPES = ("commercial_invoice", "bill_of_lading", "packing_list")

_FIELDS_PROMPT_MAP = {
    "commercial_invoice": "extraction_fields",
    "bill_of_lading": "extraction_fields_bol",
    "packing_list": "extraction_fields_packing_list",
}


class ExtractionExecutor:
    def __init__(self, client: ModelClient) -> None:
        self._client = client

    async def detect_document_type(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Classify the document type using the vision model.

        Returns one of: "commercial_invoice", "bill_of_lading", "packing_list".
        Falls back to "commercial_invoice" on any parse failure.
        """
        img_b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {"role": "system", "content": load_prompt("extraction_type_detect")},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What type of freight document is this?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{img_b64}"},
                    },
                ],
            },
        ]

        def _must_be_type_json(s: str) -> None:
            cleaned = _FENCE_RE.sub("", s.strip()).strip()
            data = json.loads(cleaned)
            if data.get("document_type") not in DOCUMENT_TYPES:
                raise ValueError(f"unknown document_type: {data.get('document_type')}")

        try:
            raw = await self._client.call(
                model=settings.vision_model,
                messages=messages,
                temperature=0.0,
                validate=_must_be_type_json,
            )
            cleaned = _FENCE_RE.sub("", raw.strip()).strip()
            result = json.loads(cleaned)
            doc_type = result.get("document_type", "commercial_invoice")
            if doc_type not in DOCUMENT_TYPES:
                return "commercial_invoice"
            logger.info("Document type detected: %s", doc_type)
            return doc_type
        except Exception as e:
            logger.warning("detect_document_type failed, defaulting to commercial_invoice: %s", e)
            return "commercial_invoice"

    async def extract(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        document_type: str = "commercial_invoice",
    ) -> dict:
        """Call the vision model with the image and return the raw parsed JSON dict."""
        fields_prompt_name = _FIELDS_PROMPT_MAP.get(document_type, "extraction_fields")
        img_b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {"role": "system", "content": load_prompt("extraction_system")},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": load_prompt(fields_prompt_name)},
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
