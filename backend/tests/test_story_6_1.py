"""Story 6.1: docker-compose contract for single-command local startup."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def test_docker_compose_exists_at_repo_root() -> None:
    assert COMPOSE_FILE.is_file(), "docker-compose.yml must exist at repository root"


def test_docker_compose_wires_backend_frontend_for_local_browser() -> None:
    """Browser must call localhost:8000; NEXT_PUBLIC_* is baked at frontend build time."""
    text = COMPOSE_FILE.read_text()
    assert "services:" in text
    assert "backend:" in text
    assert "frontend:" in text
    assert "8000:8000" in text
    assert "3000:3000" in text
    assert "env_file:" in text and ".env" in text
    assert "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" in text
    assert "depends_on:" in text
    assert "build: ./backend" in text
    assert "context: ./frontend" in text
