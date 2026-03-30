from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .txt extension).

    Raises ValueError for invalid names, FileNotFoundError if the file does not exist.
    """
    if any(c in name for c in ("/", "\\", "..")):
        raise ValueError(f"Invalid prompt name: {name!r}")
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
