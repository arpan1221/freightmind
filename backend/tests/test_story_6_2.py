"""Story 6.2 — Backend image listens on Render PORT (not hardcoded 8000 only)."""

from pathlib import Path


def _dockerfile_text() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "Dockerfile").read_text(encoding="utf-8")


def test_dockerfile_cmd_uses_port_env() -> None:
    """CMD must expand PORT so Render health checks reach uvicorn."""
    text = _dockerfile_text()
    assert "PORT" in text, "Dockerfile must reference PORT for Render"
    assert "${PORT:-8000}" in text or "${PORT}" in text, (
        "Dockerfile CMD should use shell form with ${PORT:-8000} (or similar)"
    )
    assert "sh" in text and "-c" in text, (
        "Dockerfile CMD should use sh -c for variable expansion"
    )
    assert "exec uv run uvicorn" in text.replace("\n", " "), (
        "Dockerfile CMD should exec uvicorn so the process receives container signals (SIGTERM)"
    )
