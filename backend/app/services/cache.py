import hashlib
import json
from pathlib import Path


def make_cache_key(model: str, messages: list, temperature: float) -> str:
    """Return a deterministic SHA-256 hex digest for the given LLM call parameters.

    sort_keys=True ensures key is stable regardless of dict insertion order (NFR13).
    """
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached_response(key: str, cache_dir: str) -> dict | None:
    """Return parsed JSON dict from cache file, or None if not found or unreadable.

    Uses EAFP instead of exists()+read to avoid TOCTOU race condition.
    Returns None on missing file or malformed JSON — caller falls back to live API.
    """
    path = Path(cache_dir) / f"{key}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def write_cached_response(key: str, response: dict, cache_dir: str) -> None:
    """Atomically write response dict to a JSON cache file.

    Uses write-to-temp-then-rename to avoid partial writes corrupting the cache.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    final_path = cache_path / f"{key}.json"
    tmp_path = cache_path / f"{key}.json.tmp"
    tmp_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    tmp_path.rename(final_path)
