"""Story 6.4: synthetic demo invoice assets under backend/data/demo_invoices/."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "backend" / "data" / "demo_invoices"


def _invoice_files() -> list[Path]:
    """Invoice binaries only (exclude README and dotfiles)."""
    if not DEMO_DIR.is_dir():
        return []
    return [
        p
        for p in DEMO_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
        and not p.name.startswith(".")
    ]


def test_demo_invoices_directory_exists() -> None:
    assert DEMO_DIR.is_dir(), f"Expected {DEMO_DIR}"


def test_demo_invoice_count_and_format_mix() -> None:
    files = _invoice_files()
    assert len(files) >= 5, f"Expected at least 5 invoice files, got {len(files)}: {[f.name for f in files]}"

    pdf_n = sum(1 for f in files if f.suffix.lower() == ".pdf")
    raster_n = sum(1 for f in files if f.suffix.lower() in (".png", ".jpg", ".jpeg"))
    assert pdf_n >= 2, "At least 2 PDFs required for AC4"
    assert raster_n >= 1, "At least 1 PNG or JPG required for AC4"


def test_demo_readme_manifest_exists() -> None:
    readme = DEMO_DIR / "README.md"
    assert readme.is_file(), "README.md should document demo files for Story 6.5 handoff"
    text = readme.read_text()
    lower = text.lower()
    assert "demo-01" in lower or "01-" in text, "README should reference demo files"
    assert "linkage" in lower, "README should document linkage scenario for cross-table demos"
    assert "nigeria" in lower and "air" in lower, "README should name linkage invoice mode/country"
