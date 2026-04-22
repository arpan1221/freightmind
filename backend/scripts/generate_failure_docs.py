#!/usr/bin/env python3
"""Generate demo documents for all 5 assignment failure scenarios.

Scenario 1 — HS code obscured
  demo_failure_obscured_hs.pdf
  The HS code cell is painted over with a black rectangle. The vision model
  sees blank pixels → returns NOT_FOUND or LOW confidence → comparator marks
  the field as `uncertain`. Overall status: amendment_required.

Scenario 2 — LLM returns unrecognised field format
  demo_failure_bad_format.pdf
  The HS code cell contains a visually garbled value ("84X7-??-CORRUPT").
  The vision model extracts it as-is and returns LOW confidence (value is
  present but clearly malformed). score_confidence preserves the raw value,
  forces confidence = LOW → comparator marks `uncertain`. Raw value surfaced.

Scenario 3 — Customer config missing a rule (DEMO_CUSTOMER_003.json)
  Use demo_shipment_CI.pdf with customer_id=DEMO_CUSTOMER_003.
  That config has no `hs_code` rule. The comparator returns status=`no_rule`
  for hs_code. Field is NOT auto-approved; it is surfaced in the UI.

Scenario 4 — Corrupted / empty attachment
  demo_failure_corrupted.pdf
  Contains random bytes (not a valid PDF). ExtractionPlanner.prepare() raises
  → pipeline calls _store_failed() immediately. CG is notified, no partial
  result is stored.

Scenario 5 — LLM API timeout
  No document needed. Reproduce by setting VISION_TIMEOUT=0.001 in .env
  (or environment) and uploading any PDF. The ModelClient's httpx.Timeout
  fires on the very first LLM call → retried once → _store_failed() called.
  See instructions printed at the end of this script.

Run from repo root:
  uv run python backend/scripts/generate_failure_docs.py
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

# ── Ensure repo root is on sys.path so PyMuPDF is importable ─────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import fitz  # PyMuPDF  # noqa: E402

OUT_DIR = REPO_ROOT / "backend" / "data" / "demo_invoices"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 595, 842   # A4 portrait
MARGIN = 50

# ── Colour palette (same as other demo generators) ───────────────────────────
C_BLACK     = (0.05, 0.05, 0.05)
C_DARK      = (0.15, 0.15, 0.20)
C_MID       = (0.45, 0.45, 0.50)
C_HDR_BG    = (0.22, 0.38, 0.56)
C_STRIPE    = (0.95, 0.96, 0.98)
C_BORDER    = (0.70, 0.72, 0.75)
C_WARN      = (0.65, 0.10, 0.10)
C_GREEN     = (0.10, 0.50, 0.20)

FONT      = "helv"
FONT_BOLD = "hebo"


# ── Low-level helpers (same as other generators) ─────────────────────────────

def _text(page, x, y, s, *, fs=9, fn=FONT, color=C_BLACK):
    page.insert_text(fitz.Point(x, y), s, fontsize=fs, fontname=fn, color=color)


def _textbox(page, rect, s, *, fs=9, fn=FONT, color=C_BLACK, align=0):
    page.insert_textbox(rect, s, fontsize=fs, fontname=fn, color=color, align=align)


def _rect(page, rect, *, fill=None, stroke=None, width=0.5):
    page.draw_rect(rect, color=stroke, fill=fill, width=width)


def _line(page, x0, y0, x1, y1, *, color=C_BORDER, width=0.4):
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=color, width=width)


def company_header(page, company: str, address: str, doc_title: str) -> float:
    band = fitz.Rect(MARGIN, 36, W - MARGIN, 66)
    _rect(page, band, fill=C_HDR_BG)
    _textbox(page, band, company, fs=14, fn=FONT_BOLD, color=(1, 1, 1), align=1)
    _text(page, MARGIN, 80, address, fs=7.5, color=C_MID)
    _text(page, W - MARGIN - 170, 80, doc_title, fs=10, fn=FONT_BOLD, color=C_DARK)
    _line(page, MARGIN, 90, W - MARGIN, 90, color=C_BORDER, width=0.5)
    return 98.0


def info_strip(page, y: float, items: list[tuple[str, str]], cols: int = 4) -> float:
    col_w = (W - 2 * MARGIN) / cols
    box = fitz.Rect(MARGIN, y, W - MARGIN, y + 30)
    _rect(page, box, fill=(0.98, 0.98, 1.0), stroke=C_BORDER, width=0.3)
    for i, (lbl, val) in enumerate(items):
        x = MARGIN + i * col_w + 5
        _text(page, x, y + 11, lbl, fs=7, color=C_MID)
        _text(page, x, y + 23, val, fs=9, fn=FONT_BOLD, color=C_DARK)
        if i > 0:
            _line(page, MARGIN + i * col_w, y + 4,
                  MARGIN + i * col_w, y + 26, color=C_BORDER, width=0.25)
    return y + 36


def section_label(page, y: float, text: str) -> float:
    _text(page, MARGIN, y, text, fs=8.5, fn=FONT_BOLD, color=C_HDR_BG)
    _line(page, MARGIN, y + 3, W - MARGIN, y + 3, color=C_HDR_BG, width=0.5)
    return y + 12


def table_row(page, y: float, label: str, value: str, *,
              fill=(1, 1, 1), value_color=C_DARK, row_h=20) -> float:
    row = fitz.Rect(MARGIN, y, W - MARGIN, y + row_h)
    _rect(page, row, fill=fill, stroke=C_BORDER, width=0.25)
    _text(page, MARGIN + 6, y + 13, label, fs=8, fn=FONT_BOLD, color=C_MID)
    _text(page, MARGIN + 200, y + 13, value, fs=9, color=value_color)
    return y + row_h


def footer_note(page, y: float, lines: list[str]) -> None:
    _line(page, MARGIN, y, W - MARGIN, y, color=C_BORDER, width=0.3)
    for k, line in enumerate(lines):
        _text(page, MARGIN, y + 10 + k * 11, line, fs=7, color=C_MID)


def scenario_banner(page, y: float, scenario_num: int, title: str, description: str) -> float:
    """Orange callout banner describing which failure scenario this document triggers."""
    box = fitz.Rect(MARGIN, y, W - MARGIN, y + 42)
    _rect(page, box, fill=(1.0, 0.95, 0.87), stroke=(0.80, 0.45, 0.10), width=0.8)
    _text(page, MARGIN + 8, y + 14, f"FAILURE SCENARIO {scenario_num}:", fs=9, fn=FONT_BOLD,
          color=(0.70, 0.30, 0.05))
    _text(page, MARGIN + 8, y + 27, title, fs=9, fn=FONT_BOLD, color=C_DARK)
    _text(page, MARGIN + 8, y + 38, description, fs=7.5, color=C_MID)
    return y + 50


# ── Scenario 1: HS code obscured ─────────────────────────────────────────────

def make_obscured_hs() -> Path:
    """CI where the HS code cell is covered by a solid black rectangle.

    The vision model cannot read the hidden value → returns NOT_FOUND or LOW
    confidence → comparator marks hs_code as `uncertain`. Status: amendment_required.
    """
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    y = company_header(
        pg,
        "SHANGHAI TECH EXPORTS LTD.",
        "88 Pudong Avenue, Pudong New District, Shanghai 200120, P.R. China",
        "COMMERCIAL INVOICE",
    )
    y = info_strip(pg, y, [
        ("INVOICE NO.", "INV-2024-FAIL-001"),
        ("INVOICE DATE", "15 Mar 2024"),
        ("PAYMENT TERMS", "Net 60 days"),
        ("CURRENCY", "USD"),
    ])
    y += 8

    y = scenario_banner(
        pg, y, 1,
        "HS Code Partially Obscured — Expected: field marked uncertain / low confidence",
        "The HS code field below is covered. Vision model returns NOT_FOUND → comparator marks uncertain.",
    )

    y = section_label(pg, y, "SHIPMENT DETAILS")
    fields = [
        ("SHIPMENT MODE", "Ocean"),
        ("INCOTERMS", "CIF"),
        ("PORT OF LOADING", "Shanghai, China"),
        ("PORT OF DISCHARGE", "Rotterdam, Netherlands"),
        ("ORIGIN COUNTRY", "China"),
        ("DELIVERY DATE (ETA)", "20 Apr 2024"),
        ("CONSIGNEE", "GlobalTech Industries Ltd."),
        ("DESCRIPTION OF GOODS", "Portable automatic data-processing machines"),
    ]
    stripe = True
    for lbl, val in fields:
        fill = C_STRIPE if stripe else (1, 1, 1)
        y = table_row(pg, y, lbl, val, fill=fill)
        stripe = not stripe

    # HS CODE row — draw the label only; leave the value area blank so the
    # text layer contains nothing for a vision model to read.
    hs_row_y = y
    row = fitz.Rect(MARGIN, hs_row_y, W - MARGIN, hs_row_y + 20)
    _rect(pg, row, fill=C_STRIPE, stroke=C_BORDER, width=0.25)
    _text(pg, MARGIN + 6, hs_row_y + 13, "HS CODE", fs=8, fn=FONT_BOLD, color=C_MID)
    # Value cell: solid black fill (no text underneath) + white "ILLEGIBLE" label
    value_rect = fitz.Rect(MARGIN + 195, hs_row_y + 2, W - MARGIN - 2, hs_row_y + 18)
    _rect(pg, value_rect, fill=(0.08, 0.08, 0.08))
    _textbox(pg, value_rect, "▓▓▓ ILLEGIBLE ▓▓▓", fs=7, fn=FONT_BOLD,
             color=(0.6, 0.6, 0.6), align=1)
    # Apply a PyMuPDF redaction annotation so the text layer is also wiped clean.
    pg.add_redact_annot(value_rect, fill=(0.08, 0.08, 0.08))
    pg.apply_redactions()
    y = hs_row_y + 20

    y += 8
    footer_note(pg, y, [
        "FAILURE SCENARIO 1 — This document is intentionally modified for FreightMind PoC testing.",
        "Upload with customer_id=DEMO_CUSTOMER_001. Expected result: hs_code → uncertain, overall → amendment_required.",
    ])

    path = OUT_DIR / "demo_failure_obscured_hs.pdf"
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


# ── Scenario 2: Garbled / unrecognised HS code format ────────────────────────

def make_bad_format() -> Path:
    """CI where the HS code cell contains a garbled, non-standard value.

    The vision model extracts the garbled string as-is and assigns LOW
    confidence (value is present but clearly malformed). score_confidence
    preserves the raw value without correction. The comparator sees
    confidence < threshold → marks `uncertain`. Raw value surfaced in UI.
    """
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    y = company_header(
        pg,
        "SHANGHAI TECH EXPORTS LTD.",
        "88 Pudong Avenue, Pudong New District, Shanghai 200120, P.R. China",
        "COMMERCIAL INVOICE",
    )
    y = info_strip(pg, y, [
        ("INVOICE NO.", "INV-2024-FAIL-002"),
        ("INVOICE DATE", "15 Mar 2024"),
        ("PAYMENT TERMS", "Net 60 days"),
        ("CURRENCY", "USD"),
    ])
    y += 8

    y = scenario_banner(
        pg, y, 2,
        "HS Code — Unrecognised Format  →  Raw value preserved, field marked uncertain",
        "Value does not match any valid HS format. LLM returns LOW confidence. Not silently corrected.",
    )

    y = section_label(pg, y, "SHIPMENT DETAILS")
    fields = [
        ("SHIPMENT MODE", "Ocean"),
        ("INCOTERMS", "CIF"),
        ("PORT OF LOADING", "Shanghai, China"),
        ("PORT OF DISCHARGE", "Rotterdam, Netherlands"),
        ("ORIGIN COUNTRY", "China"),
        ("DELIVERY DATE (ETA)", "20 Apr 2024"),
        ("CONSIGNEE", "GlobalTech Industries Ltd."),
        ("DESCRIPTION OF GOODS", "Portable automatic data-processing machines"),
    ]
    stripe = True
    for lbl, val in fields:
        fill = C_STRIPE if stripe else (1, 1, 1)
        y = table_row(pg, y, lbl, val, fill=fill)
        stripe = not stripe

    # HS CODE row with garbled value — visually obvious corruption
    y = table_row(
        pg, y,
        "HS CODE",
        "84X7-??-CORRUPT\u25a0\u25a0",   # garbled: non-numeric, bad separators, box chars
        fill=C_STRIPE,
        value_color=C_WARN,
    )

    # Second annotation line
    _text(pg, MARGIN + 200, y - 6, "(system print error — original stamp unreadable)", fs=7,
          color=C_MID)

    y += 12
    footer_note(pg, y, [
        "FAILURE SCENARIO 2 — This document is intentionally modified for FreightMind PoC testing.",
        "Upload with customer_id=DEMO_CUSTOMER_001. Expected result: hs_code → uncertain (raw value preserved).",
    ])

    path = OUT_DIR / "demo_failure_bad_format.pdf"
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


# ── Scenario 3: Missing rule — use existing CI + DEMO_CUSTOMER_003 ────────────
# No document generation needed: use demo_shipment_CI.pdf with customer_id=DEMO_CUSTOMER_003.
# DEMO_CUSTOMER_003.json omits the hs_code rule entirely → comparator returns no_rule.


# ── Scenario 4: Corrupted / binary attachment ─────────────────────────────────

def make_corrupted_pdf() -> Path:
    """Write random binary bytes with a .pdf extension.

    When submitted, ExtractionPlanner.prepare() tries to parse it with PyMuPDF,
    which raises an exception. The pipeline calls _store_failed() immediately:
    no partial result is stored, CG is notified via the failed record.
    """
    path = OUT_DIR / "demo_failure_corrupted.pdf"
    # Build a byte pattern that looks plausibly file-like but is invalid PDF:
    # 512 bytes of structured garbage (not a valid %PDF- header).
    garbage = b"\x00\xDE\xAD\xBE\xEF" * 10          # binary header noise
    garbage += b"This is NOT a valid PDF file.\n"      # readable marker
    garbage += b"FreightMind Failure Scenario 4\n"    # identifies demo intent
    garbage += b"\xff\xfe" * 220                       # padding with invalid bytes
    path.write_bytes(garbage)
    return path


# ── Scenario 5: LLM API timeout — no document, env-var instructions ──────────
# Reproduce by setting VISION_TIMEOUT=0.001 in .env (or shell) before restarting
# the backend. Upload any valid PDF. The httpx.Timeout fires on the first LLM
# call; ModelClient retries once (fallback model, same tiny timeout) → raises
# ModelUnavailableError → pipeline calls _store_failed().

_SCENARIO_5_INSTRUCTIONS = """
Scenario 5 — LLM API Timeout
─────────────────────────────
1. Add VISION_TIMEOUT=0.001 to backend/.env  (or export it in your shell)
2. Restart the backend:  docker compose restart backend
   (or: uv run uvicorn app.main:app --reload)
3. Upload any PDF via the Verification tab (e.g. demo_shipment_CI.pdf)
4. The ModelClient's httpx.Timeout fires immediately on the first LLM call.
   Primary model fails → fallback model tried → also times out.
   Pipeline calls _store_failed(); the Queue tab shows status=failed.
5. CG-facing message: "Document extraction failed after retry: ...timed out"
6. After the demo: remove VISION_TIMEOUT from .env and restart.
"""


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Output directory: {OUT_DIR}\n")

    p1 = make_obscured_hs()
    print(f"  [Scenario 1] Created: {p1.name}")
    print( "               Upload with customer_id=DEMO_CUSTOMER_001")
    print( "               Expected: hs_code → uncertain, overall → amendment_required\n")

    p2 = make_bad_format()
    print(f"  [Scenario 2] Created: {p2.name}")
    print( "               Upload with customer_id=DEMO_CUSTOMER_001")
    print( "               Expected: hs_code → uncertain (raw garbled value preserved)\n")

    print( "  [Scenario 3] No new document needed.")
    print( "               Upload backend/data/demo_invoices/demo_shipment_CI.pdf")
    print( "               with customer_id=DEMO_CUSTOMER_003")
    print( "               Expected: hs_code → no_rule (no rule defined in config)\n")

    p4 = make_corrupted_pdf()
    print(f"  [Scenario 4] Created: {p4.name}")
    print( "               Upload with any customer_id")
    print( "               Expected: status=failed, 'file may be corrupted' error surfaced\n")

    print( "  [Scenario 5] No document generated — env-var trigger.")
    print(_SCENARIO_5_INSTRUCTIONS)

    print("All failure scenario demo artifacts ready.")
