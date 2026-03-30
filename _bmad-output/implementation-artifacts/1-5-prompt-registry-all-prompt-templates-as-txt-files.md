# Story 1.5: Prompt Registry — All Prompt Templates as .txt Files

Status: done

## Story

As a developer,
I want all LLM prompt templates stored as `.txt` files in `backend/app/prompts/`,
So that prompts can be updated without touching business logic code.

## Acceptance Criteria

1. **Given** the backend starts,
   **When** any agent loads a prompt template,
   **Then** it reads from a `.txt` file in `app/prompts/` — no inline f-string prompt exists in agent code (FR40)

2. **Given** a `.txt` prompt file is missing at startup,
   **When** any agent attempts to load it,
   **Then** a clear `FileNotFoundError` is raised with the missing file path (fail-fast)

3. **Given** the prompt files exist on disk,
   **When** a developer inspects `app/prompts/`,
   **Then** they find all required files (see Task 1 for authoritative list)

## Tasks / Subtasks

- [x] Task 1: Create stub prompt `.txt` files (AC: 3)
  - [x] Create `backend/app/prompts/analytics_system.txt` — stub content: `# Analytics agent system prompt\n[TODO: full prompt for Epic 2]`
  - [x] Create `backend/app/prompts/analytics_sql_gen.txt` — stub content: `# SQL generation instruction + schema context\n[TODO: full prompt for Epic 2]`
  - [x] Create `backend/app/prompts/extraction_system.txt` — stub content: `# Extraction agent system prompt\n[TODO: full prompt for Epic 3]`
  - [x] Create `backend/app/prompts/extraction_fields.txt` — stub content: `# 14-field extraction instructions\n[TODO: full prompt for Epic 3]`
  - [x] Create `backend/app/prompts/extraction_normalise.txt` — stub content: `# Mode/country vocabulary for normalisation\n[TODO: full prompt for Epic 3]`
  - [x] Remove `.gitkeep` from `backend/app/prompts/` after creating the real files

- [x] Task 2: Create `load_prompt` loader utility (AC: 1, 2)
  - [x] Create `backend/app/core/prompts.py`
  - [x] Implement `load_prompt(name: str) -> str` — reads `{PROMPTS_DIR}/{name}.txt`
  - [x] `PROMPTS_DIR` = `Path(__file__).parent.parent / "prompts"` (resolved relative to `core/prompts.py`)
  - [x] If file not found: raise `FileNotFoundError(f"Prompt file not found: {path}")` — no fallback, no silent empty string
  - [x] Strip trailing whitespace on return (`.strip()`) to prevent accidental trailing newlines reaching the LLM

- [x] Task 3: Write tests (AC: 1, 2, 3)
  - [x] Create `backend/tests/test_story_1_5.py`
  - [x] Test: `load_prompt("analytics_system")` returns non-empty string
  - [x] Test: `load_prompt("nonexistent_prompt")` raises `FileNotFoundError` containing the file path
  - [x] Test: All five required prompt files exist on disk (parametrize over the file list)
  - [x] Test: No inline prompt strings in any agent file (use `ast.walk` or grep via `subprocess` to scan `app/agents/`)

## Dev Notes

### Loader utility — `app/core/prompts.py`

```python
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .txt extension).

    Raises FileNotFoundError if the file does not exist — fail-fast.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
```

**Key constraints:**
- No caching inside `load_prompt` — prompts are loaded per agent invocation so live edits take effect without restart.
- All callers use the name without extension: `load_prompt("analytics_system")`, not `load_prompt("analytics_system.txt")`.

### File naming (from architecture — authoritative)

Architecture specifies `{agent}_{purpose}.txt` naming. The five required files are:

| File | Purpose |
|------|---------|
| `analytics_system.txt` | Analytics agent system prompt |
| `analytics_sql_gen.txt` | SQL generation instruction + schema context |
| `extraction_system.txt` | Extraction agent system prompt |
| `extraction_fields.txt` | 14-field list + extraction instructions |
| `extraction_normalise.txt` | Mode/country vocabulary for normalisation |

> **Note:** The epics AC mentions `analytics_planner.txt`, `analytics_executor.txt`, etc. — but the architecture is authoritative here. Use the architecture naming (`{agent}_{purpose}`), which is more descriptive of content than of the code file that consumes it. Agents in `analytics/planner.py`, `analytics/executor.py`, and `analytics/verifier.py` will each call `load_prompt()` with the relevant purpose-named file.

### Stub content format

Stubs are intentionally minimal — just a comment header and a `[TODO]` placeholder. Agents that call `load_prompt()` in future stories (Epic 2/3) will find non-empty strings. The stub format prevents LLM calls from accidentally proceeding with empty prompts.

### Existing directory

`backend/app/prompts/.gitkeep` already exists (scaffolded in Story 1.1). Remove `.gitkeep` once the `.txt` files are in place — git will track the real files instead.

### Architecture enforcement

Architecture red flag: "Prompt strings hardcoded in agent files (should be in `prompts/`)". No agent file may contain multi-line string literals used as LLM prompts. The `load_prompt` utility is the single access point — all agents import from `app.core.prompts`.

### Project structure

- New file: `backend/app/core/prompts.py`
- New files (5x): `backend/app/prompts/*.txt`
- No changes to `main.py`, `database.py`, or any route

### Testing pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from pathlib import Path
from app.core.prompts import load_prompt, PROMPTS_DIR

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

    def test_missing_error_includes_file_path(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt("nonexistent_prompt_xyz")
        # Must include the full path for fast debugging
        assert str(PROMPTS_DIR) in str(exc_info.value)

    @pytest.mark.parametrize("name", REQUIRED_PROMPTS)
    def test_required_prompt_file_exists(self, name):
        path = PROMPTS_DIR / f"{name}.txt"
        assert path.exists(), f"Required prompt file missing: {path}"

    @pytest.mark.parametrize("name", REQUIRED_PROMPTS)
    def test_required_prompt_returns_non_empty(self, name):
        content = load_prompt(name)
        assert content  # non-empty after strip
```

### Previous story learnings

From Story 1.4:
- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must appear at the top of every test file **before** importing app modules (Settings eagerly validates env on import).
- `httpx` is a runtime dependency — confirm any new utility does NOT introduce undeclared dependencies.
- This story has zero runtime dependencies beyond the Python standard library (`pathlib` is stdlib).

From Story 1.1:
- Test file naming convention: `backend/tests/test_story_1_5.py`
- All test classes use `class Test<Feature>:` pattern (no standalone functions).

### References

- [Source: architecture.md — Prompt Registry section, line 55]: "Prompt Registry — all LLM prompt templates in `backend/prompts/`; both agents reference this directory; zero inline strings in business logic (FR40)"
- [Source: architecture.md — Naming Conventions table, line 330]: `{agent}_{purpose}.txt` in `prompts/`
- [Source: architecture.md — Enforcement Guidelines, line 561]: Red flag: "Prompt strings hardcoded in agent files (should be in `prompts/`)"
- [Source: architecture.md — File tree, lines 621–626]: Authoritative list of five required prompt files
- [Source: epics.md — Story 1.5, line 301]: AC text; note naming discrepancy resolved in favour of architecture

### Review Findings

- [x] [Review][Patch] Vacuous pass: `test_no_triple_quoted_strings_in_agents` — `_get_agent_py_files` returns empty list when `agents/` dir is absent or has no `.py` files; test passes with zero files inspected. Add `assert agents_dir.is_dir(), f"Agents directory missing: {agents_dir}"` before the loop. [backend/tests/test_story_1_5.py:56-58]
- [x] [Review][Patch] Silent skip: `SyntaxError` in agent file scan silently `continue`s — a broken agent file is invisible to the no-inline-prompt test. Append the file path to `violations` instead of continuing. [backend/tests/test_story_1_5.py:63-64]
- [x] [Review][Patch] Docstring false-positives + f-string fragments: `test_no_triple_quoted_strings_in_agents` flags any multi-line `ast.Constant` string — this false-positives on docstrings and constant parts inside f-strings. Now excludes docstring nodes and all `ast.Constant` children of `ast.JoinedStr`. [backend/tests/test_story_1_5.py:62-67]
- [x] [Review][Patch] `path.exists()` → `path.is_file()` in `load_prompt`: if a directory is ever named `{name}.txt`, `exists()` returns `True` and `read_text()` raises `IsADirectoryError` instead of the expected `FileNotFoundError`. [backend/app/core/prompts.py:12]
- [x] [Review][Patch] Path traversal: `load_prompt(name)` constructs the path with no validation — a caller passing `"../../../etc/passwd"` would escape `PROMPTS_DIR`. Add `if "/" in name or "\\" in name or ".." in name: raise ValueError(f"Invalid prompt name: {name}")`. [backend/app/core/prompts.py:11]
- [x] [Review][Patch] Missing POSIX trailing newline in all 5 `.txt` stub files (git shows `\ No newline at end of file` for each). Add a trailing newline to each file. [backend/app/prompts/*.txt]
- [x] [Review][Defer] No `PROMPTS_DIR` existence check at import time — in an unusual deployment layout where the `prompts/` directory is absent, callers get a `FileNotFoundError` pointing at the file rather than the directory. Acceptable for current uv-run deploy model. [backend/app/core/prompts.py:3] — deferred, pre-existing
- [x] [Review][Defer] `PermissionError` from `path.read_text()` propagates unhandled with no additional context. Not a concern for a dev/POC service but worth noting for production hardening. [backend/app/core/prompts.py:14] — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Created 5 stub prompt `.txt` files in `backend/app/prompts/` with minimal comment header + `[TODO]` placeholder; non-empty so `load_prompt` callers are safe
- Removed `.gitkeep` — real files now tracked by git
- Created `backend/app/core/prompts.py` with `PROMPTS_DIR` constant and `load_prompt(name)` — pathlib-based, fail-fast `FileNotFoundError`, `.strip()` on return
- Zero new runtime dependencies — only stdlib `pathlib`
- 15 new tests in `test_story_1_5.py`; all 63 tests pass (15 new + 48 regression)

### File List

- `backend/app/core/prompts.py` — new: `load_prompt` utility + `PROMPTS_DIR` constant
- `backend/app/prompts/analytics_system.txt` — new: stub analytics system prompt
- `backend/app/prompts/analytics_sql_gen.txt` — new: stub SQL generation prompt
- `backend/app/prompts/extraction_system.txt` — new: stub extraction system prompt
- `backend/app/prompts/extraction_fields.txt` — new: stub extraction fields prompt
- `backend/app/prompts/extraction_normalise.txt` — new: stub normalisation vocabulary prompt
- `backend/app/prompts/.gitkeep` — deleted: replaced by real prompt files
- `backend/tests/test_story_1_5.py` — new: 15 tests covering all ACs

## Change Log

- 2026-03-30: Implemented Story 1.5 — prompt registry with 5 stub `.txt` files, `load_prompt` loader utility, and 15 tests. 63/63 passing.
