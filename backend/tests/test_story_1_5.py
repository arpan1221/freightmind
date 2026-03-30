"""
Tests for Story 1.5 — Prompt Registry: All Prompt Templates as .txt Files

Verifies:
- AC1: load_prompt reads from .txt files — no inline prompts in agent code
- AC2: Missing prompt file raises FileNotFoundError with the file path
- AC3: All required prompt files exist on disk
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import ast
import subprocess
from pathlib import Path

import pytest

from app.core.prompts import PROMPTS_DIR, load_prompt

REQUIRED_PROMPTS = [
    "analytics_system",
    "analytics_sql_gen",
    "extraction_system",
    "extraction_fields",
    "extraction_normalise",
]


class TestLoadPrompt:
    def test_load_existing_prompt_returns_string(self):
        content = load_prompt("analytics_system")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_load_missing_prompt_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt("nonexistent_prompt_xyz")
        assert "nonexistent_prompt_xyz" in str(exc_info.value)

    @pytest.mark.parametrize("bad_name", ["../etc/passwd", "../../secrets", "foo/bar", "foo\\bar"])
    def test_load_prompt_rejects_path_traversal(self, bad_name):
        with pytest.raises(ValueError, match="Invalid prompt name"):
            load_prompt(bad_name)

    def test_missing_error_includes_file_path(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt("nonexistent_prompt_xyz")
        # Must include the full path for fast debugging
        assert str(PROMPTS_DIR) in str(exc_info.value)

    def test_load_prompt_strips_trailing_whitespace(self, tmp_path, monkeypatch):
        """Verify .strip() is applied so trailing newlines don't reach the LLM."""
        import app.core.prompts as prompts_module

        fake_dir = tmp_path / "prompts"
        fake_dir.mkdir()
        (fake_dir / "whitespace_test.txt").write_text(
            "  hello world  \n\n", encoding="utf-8"
        )
        monkeypatch.setattr(prompts_module, "PROMPTS_DIR", fake_dir)
        result = load_prompt("whitespace_test")
        assert result == "hello world"

    @pytest.mark.parametrize("name", REQUIRED_PROMPTS)
    def test_required_prompt_file_exists(self, name):
        path = PROMPTS_DIR / f"{name}.txt"
        assert path.exists(), f"Required prompt file missing: {path}"

    @pytest.mark.parametrize("name", REQUIRED_PROMPTS)
    def test_required_prompt_returns_non_empty(self, name):
        content = load_prompt(name)
        assert content, f"Prompt '{name}' loaded but is empty after strip"


class TestNoInlinePromptsInAgents:
    """AC1: No inline multi-line string literals used as LLM prompts in agent files."""

    def _get_agent_py_files(self) -> list[Path]:
        agents_dir = Path(__file__).parent.parent / "app" / "agents"
        return agents_dir, list(agents_dir.rglob("*.py"))

    @staticmethod
    def _excluded_node_ids(tree: ast.AST) -> set[int]:
        """Return id() of AST Constant nodes that should not be flagged.

        Excludes:
        - Docstrings: first expression of module/class/function bodies
        - F-string parts: Constant sub-nodes inside JoinedStr (f-string) nodes
        """
        ids: set[int] = set()
        for node in ast.walk(tree):
            # Docstrings
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    ids.add(id(node.body[0].value))
            # F-string constant fragments
            if isinstance(node, ast.JoinedStr):
                for child in ast.walk(node):
                    if isinstance(child, ast.Constant):
                        ids.add(id(child))
        return ids

    def test_no_triple_quoted_strings_in_agents(self):
        """Agent files must not contain multi-line inline prompt strings."""
        agents_dir, py_files = self._get_agent_py_files()
        assert agents_dir.is_dir(), f"Agents directory missing: {agents_dir}"

        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as e:
                violations.append(f"{py_file.name} — SyntaxError (unparseable file): {e}")
                continue

            excluded_ids = self._excluded_node_ids(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) in excluded_ids:
                        continue  # skip docstrings and f-string fragments
                    if "\n" in node.value:
                        violations.append(
                            f"{py_file.name}:{node.lineno} — multi-line inline string found"
                        )

        assert not violations, (
            "Inline prompt strings found in agent files (should be in prompts/):\n"
            + "\n".join(violations)
        )
