"""Parse ``Retry-After`` header values (RFC 7231) to integer seconds."""

from __future__ import annotations

import email.utils
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_AFTER_SEC = 60
_MAX_RETRY_AFTER_SEC = 86400


def retry_after_seconds_from_response(response: httpx.Response | None) -> int:
    """Return seconds to wait; prefers numeric ``Retry-After``, else HTTP-date, else default."""
    if response is None:
        logger.warning(
            "429 response missing HTTP response object; using default retry_after=%s",
            _DEFAULT_RETRY_AFTER_SEC,
        )
        return _DEFAULT_RETRY_AFTER_SEC
    raw = response.headers.get("retry-after")
    if not raw:
        logger.warning(
            "429 without Retry-After header; using default retry_after=%s",
            _DEFAULT_RETRY_AFTER_SEC,
        )
        return _DEFAULT_RETRY_AFTER_SEC
    raw_stripped = raw.strip()
    if raw_stripped.isdigit():
        return min(int(raw_stripped), _MAX_RETRY_AFTER_SEC)
    try:
        dt = email.utils.parsedate_to_datetime(raw_stripped)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(1, min(int((dt - now).total_seconds()), _MAX_RETRY_AFTER_SEC))
    except Exception:
        logger.warning(
            "Could not parse Retry-After %r; using default %s",
            raw,
            _DEFAULT_RETRY_AFTER_SEC,
        )
        return _DEFAULT_RETRY_AFTER_SEC
