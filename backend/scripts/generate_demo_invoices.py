#!/usr/bin/env python3
"""Realistic synthetic freight invoice generator v2.

Produces documents that genuinely challenge modern vision extraction models:
  - Table-based layouts with headers, line items, and totals (not label:value)
  - Shipping jargon / abbreviations (POL, POD, AWB, B/L, CMR, CBM, FCL)
  - Multi-page invoice — model must aggregate across pages
  - Mixed-currency invoice with USD conversion buried in footer note
  - Simulated scan: low DPI + rotation + JPEG compression
  - Diagonal COPY watermark overlaying invoice content
  - Insurance entirely absent from charges table (NOT_FOUND test)
  - Non-Latin scripts in consignee/shipper fields (Chinese, Arabic, Cyrillic,
    Korean, Myanmar)
  - Stamp overlays (APPROVED, PAID, CUSTOMS CLEARED) at arbitrary angles
  - Correction marks — strikethrough + handwritten revision above
  - Handwritten-style margin annotations

Run from repo root: uv run python backend/scripts/generate_demo_invoices.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "backend" / "data" / "demo_invoices"

W, H = 595, 842   # A4 portrait in points
MARGIN = 50
random.seed(42)   # deterministic output

# ── System font paths for non-Latin scripts (macOS) ──────────────────────────
# Each list is tried in order; the first existing path wins.
_FONT_CANDIDATES = {
    "cjk":     ["/System/Library/Fonts/STHeiti Medium.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Arial Unicode.ttf"],
    "arabic":  ["/System/Library/Fonts/SFArabic.ttf",
                "/System/Library/Fonts/GeezaPro.ttc",
                "/System/Library/Fonts/Arial Unicode.ttf"],
    "cyrillic":["/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Arial Unicode.ttf",
                "/Library/Fonts/Arial Unicode MS.ttf"],
    "korean":  ["/System/Library/Fonts/AppleSDGothicNeo.ttc",
                "/System/Library/Fonts/Arial Unicode.ttf"],
    "myanmar": ["/System/Library/Fonts/NotoSansMyanmar.ttc",
                "/System/Library/Fonts/Arial Unicode.ttf"],
}


def _font_path(script: str) -> str | None:
    for p in _FONT_CANDIDATES.get(script, []):
        if Path(p).exists():
            return p
    return None

# ── Colours ──────────────────────────────────────────────────────────────────

C_BLACK     = (0.05, 0.05, 0.05)
C_DARK      = (0.15, 0.15, 0.20)
C_MID       = (0.45, 0.45, 0.50)
C_LIGHT     = (0.70, 0.70, 0.72)
C_HDR_BG    = (0.22, 0.38, 0.56)   # dark-blue header band
C_STRIPE    = (0.95, 0.96, 0.98)   # alternating table row
C_BORDER    = (0.70, 0.72, 0.75)
C_WARN      = (0.65, 0.10, 0.10)   # red note text
C_WATERMARK = (0.87, 0.87, 0.88)

FONT      = "helv"
FONT_BOLD = "hebo"

# ── Low-level drawing helpers ─────────────────────────────────────────────────

def _text(page: fitz.Page, x: float, y: float, s: str, *,
          fs: float = 9, fn: str = FONT, color: tuple = C_BLACK) -> None:
    page.insert_text(fitz.Point(x, y), s, fontsize=fs, fontname=fn, color=color)


def _textbox(page: fitz.Page, rect: fitz.Rect, s: str, *,
             fs: float = 9, fn: str = FONT, color: tuple = C_BLACK,
             align: int = 0) -> None:
    page.insert_textbox(rect, s, fontsize=fs, fontname=fn, color=color, align=align)


def _rect(page: fitz.Page, rect: fitz.Rect, *,
          fill: tuple | None = None, stroke: tuple | None = None,
          width: float = 0.5) -> None:
    page.draw_rect(rect, color=stroke, fill=fill, width=width)


def _line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float,
          *, color: tuple = C_BORDER, width: float = 0.4) -> None:
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1),
                   color=color, width=width)


# ── Reusable layout components ────────────────────────────────────────────────

def company_header(page: fitz.Page, company: str, address: str,
                   doc_title: str) -> float:
    """Blue band with company name + address line. Returns y below."""
    band = fitz.Rect(MARGIN, 36, W - MARGIN, 66)
    _rect(page, band, fill=C_HDR_BG)
    _textbox(page, band, company, fs=14, fn=FONT_BOLD,
             color=(1, 1, 1), align=1)
    _text(page, MARGIN, 80, address, fs=7.5, color=C_MID)
    _text(page, W - MARGIN - 155, 80, doc_title,
          fs=10, fn=FONT_BOLD, color=C_DARK)
    _line(page, MARGIN, 90, W - MARGIN, 90, color=C_BORDER, width=0.5)
    return 98.0


def info_strip(page: fitz.Page, y: float,
               items: list[tuple[str, str]], cols: int = 4) -> float:
    """Horizontal strip with label/value pairs. Returns y below."""
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


def address_pair(page: fitz.Page, y: float,
                 left_title: str, left_lines: list[str],
                 right_title: str, right_lines: list[str]) -> float:
    """Two side-by-side address boxes. Returns y below."""
    col_w = (W - 2 * MARGIN - 10) / 2
    for xi, title, lines in (
        (MARGIN, left_title, left_lines),
        (MARGIN + col_w + 10, right_title, right_lines),
    ):
        box = fitz.Rect(xi, y, xi + col_w, y + 78)
        _rect(page, box, fill=C_STRIPE, stroke=C_BORDER, width=0.35)
        _text(page, xi + 5, y + 13, title, fs=7.5, fn=FONT_BOLD, color=C_HDR_BG)
        for k, line in enumerate(lines):
            _text(page, xi + 5, y + 25 + k * 11, line, fs=8, color=C_BLACK)
    return y + 86


def section_label(page: fitz.Page, y: float, text: str) -> float:
    """Bold section heading with underline. Returns y below."""
    _text(page, MARGIN, y, text, fs=8.5, fn=FONT_BOLD, color=C_HDR_BG)
    _line(page, MARGIN, y + 3, W - MARGIN, y + 3, color=C_HDR_BG, width=0.5)
    return y + 12


def table(page: fitz.Page, y: float, headers: list[str],
          rows: list[list[str]], col_widths: list[float], *,
          row_h: float = 15, hdr_h: float = 19,
          stripe: bool = True) -> float:
    """Draw a full bordered table. Returns y below."""
    x0 = MARGIN
    x1 = x0 + sum(col_widths)

    # Header
    hdr_rect = fitz.Rect(x0, y, x1, y + hdr_h)
    _rect(page, hdr_rect, fill=C_HDR_BG)
    cx = x0
    for hdr, cw in zip(headers, col_widths):
        cell = fitz.Rect(cx + 2, y + 2, cx + cw - 2, y + hdr_h - 2)
        _textbox(page, cell, hdr, fs=7.5, fn=FONT_BOLD,
                 color=(1, 1, 1), align=1)
        cx += cw

    # Data rows
    yr = y + hdr_h
    for ri, row in enumerate(rows):
        fill = C_STRIPE if (stripe and ri % 2 == 0) else (1, 1, 1)
        _rect(page, fitz.Rect(x0, yr, x1, yr + row_h),
              fill=fill, stroke=C_BORDER, width=0.25)
        cx = x0
        for ci, (cell_val, cw) in enumerate(zip(row, col_widths)):
            align = 2 if ci >= len(col_widths) - 2 else 0
            cell = fitz.Rect(cx + 3, yr + 2, cx + cw - 3, yr + row_h - 2)
            _textbox(page, cell, cell_val, fs=7.5, color=C_BLACK, align=align)
            cx += cw
        yr += row_h

    # Outer border + vertical dividers
    _rect(page, fitz.Rect(x0, y, x1, yr), stroke=C_BORDER, width=0.5)
    cx = x0
    for cw in col_widths[:-1]:
        cx += cw
        _line(page, cx, y, cx, yr, color=C_BORDER, width=0.25)

    return yr + 6


def totals_block(page: fitz.Page, y: float,
                 items: list[tuple[str, str]]) -> float:
    """Right-aligned totals section. Returns y below."""
    lx = W - MARGIN - 210
    vx = W - MARGIN - 75
    for lbl, val in items:
        bold = "TOTAL" in lbl.upper()
        fn = FONT_BOLD if bold else FONT
        fs = 9.5 if bold else 8.5
        col = C_DARK if bold else C_BLACK
        _text(page, lx, y, lbl, fs=fs, fn=fn, color=col)
        _text(page, vx, y, val, fs=fs, fn=fn, color=col)
        y += 13
        if bold:
            _line(page, lx - 4, y - 1, W - MARGIN, y - 1,
                  color=C_BORDER, width=0.4)
    return y + 4


def watermark(page: fitz.Page, text: str = "COPY") -> None:
    """Diagonal light-grey stamp across centre of page."""
    pivot = fitz.Point(W / 2, H / 2)
    mat   = fitz.Matrix(-42)   # ~42° clockwise tilt
    page.insert_text(
        fitz.Point(W / 2 - 55, H / 2 + 20),
        text,
        fontsize=80,
        fontname=FONT_BOLD,
        color=C_WATERMARK,
        morph=(pivot, mat),
    )


def footer_note(page: fitz.Page, y: float, lines: list[str]) -> None:
    _line(page, MARGIN, y, W - MARGIN, y, color=C_BORDER, width=0.3)
    for k, line in enumerate(lines):
        _text(page, MARGIN, y + 10 + k * 11, line, fs=7, color=C_MID)


# ── File I/O ──────────────────────────────────────────────────────────────────

def save_pdf(doc: fitz.Document, name: str) -> Path:
    path = OUT_DIR / name
    # garbage=4: remove unreferenced objects + subset embedded fonts
    # deflate=True: compress streams → dramatically reduces CJK font bloat
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


def rasterise(src: Path, out_name: str, *,
              dpi: int = 144, angle: float = 0.0,
              jpg_quality: int | None = None) -> Path:
    """Render page 0 of *src* PDF to an image file."""
    doc = fitz.open(str(src))
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        if angle != 0.0:
            mat.prerotate(angle)
        pix = doc[0].get_pixmap(matrix=mat)
        out = OUT_DIR / out_name
        if jpg_quality is not None:
            pix.save(str(out), jpg_quality=jpg_quality)
        else:
            pix.save(str(out))
        return out
    finally:
        doc.close()


# ── Invoice generators ────────────────────────────────────────────────────────

def make_01_air_nigeria() -> None:
    """Linkage demo — table layout, company letterhead, line items."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "ACME GLOBAL LOGISTICS LTD",
                       "1400 Harbor Blvd, Newark NJ 07114, USA  |  logistics@acme-demo.invalid",
                       "AIR FREIGHT INVOICE")
    y = info_strip(pg, y, [
        ("INVOICE NO.", "INV-2025-AIR-8841"),
        ("INVOICE DATE", "12 Nov 2025"),
        ("AWB NO.", "176-48291034"),
        ("PAGE", "1 of 1"),
    ])
    y += 5
    y = address_pair(pg, y,
                     "SHIPPER / EXPORTER",
                     ["Acme Medical Supplies Corp (fictional)",
                      "1400 Harbor Blvd, Newark",
                      "NJ 07114, United States",
                      "EORI: US-DEMO-884421"],
                     "CONSIGNEE / IMPORTER",
                     ["Lagos Central Health Depot (fictional)",
                      "14 Apapa Wharf Road",
                      "Lagos, NIGERIA",
                      "VAT: NG-DEMO-00291"])
    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("SHIPMENT MODE", "Air"),
        ("ORIGIN COUNTRY", "United States"),
        ("DESTINATION", "Nigeria"),
        ("CARRIER / AIRLINE", "Demo Air Cargo LLC"),
    ])
    y = info_strip(pg, y, [
        ("GROSS WEIGHT", "450.5 KGS"),
        ("CHARGEABLE WT.", "512.0 KGS"),
        ("DELIVERY DATE", "20 Nov 2025"),
        ("PAYMENT TERMS", "Net 30"),
    ])
    y += 5
    y = section_label(pg, y, "COMMODITY DETAILS")
    y = table(pg, y,
              ["HS CODE", "DESCRIPTION", "QTY", "UNIT",
               "UNIT PRICE (USD)", "LINE TOTAL (USD)"],
              [["3004.90", "Antimalarial tablets 250 mg blister (fictional)", "200", "CTN",
                "48.00", "9,600.00"],
               ["3002.12", "Malaria rapid diagnostic test kits (RDT)", "50", "BOX",
                "96.00", "4,800.00"],
               ["3006.60", "Chemical contraceptives — assorted", "30", "CTN",
                "72.00", "2,160.00"]],
              [55, 190, 35, 35, 95, 85])
    y += 4
    y = section_label(pg, y, "CHARGES SUMMARY")
    y = totals_block(pg, y, [
        ("Goods value (USD)", "16,560.00"),
        ("Air freight charge (USD)", "8,920.00"),
        ("Fuel surcharge (USD)", "445.00"),
        ("Insurance (USD)", "210.00"),
        ("Documentation fee (USD)", "85.00"),
        ("INVOICE TOTAL (USD)", "26,220.00"),
    ])
    footer_note(pg, H - 52, [
        "All charges in US Dollars. Payment due 30 days from invoice date.",
        "SYNTHETIC DEMO — FreightMind PoC. No real transaction represented.",
    ])
    save_pdf(doc, "demo-01-air-nigeria-linkage.pdf")


def make_02_ocean_vietnam() -> None:
    """Multi-page ocean invoice — mode implicit in B/L and FCL."""
    doc = fitz.open()

    # ── Page 1: header + shipment overview ──────────────────────────────────
    p1 = doc.new_page(width=W, height=H)
    y = company_header(p1,
                       "BLUE HARBOR FORWARDING PTE LTD",
                       "18 Tanjong Pagar Road #08-01, Singapore 088065  |  MOM Lic: SG-DEMO-4421",
                       "OCEAN FREIGHT INVOICE")
    y = info_strip(p1, y, [
        ("INVOICE NO.", "BHF-2025-OCN-0421"),
        ("INVOICE DATE", "01 Oct 2025"),
        ("B/L NO.", "BHFSGVN2510041"),
        ("PAGE", "1 of 2"),
    ])
    y += 5
    y = address_pair(p1, y,
                     "SHIPPER",
                     ["Blue Harbor Forwarding Pte Ltd (fictional)",
                      "18 Tanjong Pagar Road, Singapore 088065",
                      "UEN: DEMO-199912345A", ""],
                     "CONSIGNEE",
                     ["Ho Chi Minh City Medical Clinic (fictional)",
                      "147 Nguyen Hue Blvd, Dist. 1",
                      "Ho Chi Minh City, VIETNAM",
                      "Tax Code: VN-DEMO-0012291"])
    y += 4
    y = section_label(p1, y, "BOOKING & VESSEL DETAILS")
    y = info_strip(p1, y, [
        ("VESSEL / VOYAGE", "MV DEMO PACIFIC / V.42W"),
        ("POL (PORT OF LOADING)", "Singapore (SGSIN)"),
        ("POD (PORT OF DISCHARGE)", "Ho Chi Minh City (VNSGN)"),
        ("ETD / ETA", "05 Oct 2025 / 10 Oct 2025"),
    ])
    y = info_strip(p1, y, [
        ("CONTAINER TYPE", "FCL 40' High Cube"),
        ("CONTAINER NO.", "DEMO4219834-7"),
        ("GROSS WEIGHT", "12,000 KGS"),
        ("DELIVERY DATE", "05 Nov 2025"),
    ])
    y = info_strip(p1, y, [
        ("MEASUREMENT (CBM)", "28.4"),
        ("INCOTERMS", "CIF Ho Chi Minh City"),
        ("PAYMENT TERMS", "CAD 45"),
        ("ORIGIN COUNTRY", "Singapore"),
    ])
    y += 5
    y = section_label(p1, y, "CARGO MANIFEST SUMMARY  (charges detail — see page 2)")
    y = table(p1, y,
              ["MARKS & NOS.", "DESCRIPTION OF GOODS", "NO. PKGS", "GW (KGS)", "CBM"],
              [["BHF-SG-001",
                "General merchandise — medical consumables (fictional)",
                "48 PLT", "12,000", "28.4"]],
              [80, 215, 70, 80, 50])
    _text(p1, MARGIN, H - 50, "→  CONTINUED ON PAGE 2 — CHARGES BREAKDOWN",
          fs=8, fn=FONT_BOLD, color=C_HDR_BG)
    footer_note(p1, H - 38, [
        "SYNTHETIC DEMO — FreightMind PoC. Blue Harbor Forwarding Pte Ltd is a fictional entity.",
    ])

    # ── Page 2: charges table + totals ──────────────────────────────────────
    p2 = doc.new_page(width=W, height=H)
    y = company_header(p2,
                       "BLUE HARBOR FORWARDING PTE LTD",
                       "18 Tanjong Pagar Road #08-01, Singapore 088065",
                       "OCEAN FREIGHT INVOICE")
    y = info_strip(p2, y, [
        ("INVOICE NO.", "BHF-2025-OCN-0421"),
        ("B/L NO.", "BHFSGVN2510041"),
        ("ORIGIN COUNTRY", "Singapore"),
        ("PAGE", "2 of 2"),
    ])
    y += 8
    y = section_label(p2, y, "CHARGES BREAKDOWN")
    y = table(p2, y,
              ["CHARGE DESCRIPTION", "CCY", "RATE", "UNIT", "QTY", "AMOUNT (USD)"],
              [["Basic ocean freight", "USD", "850.00", "Per TEU", "2", "1,700.00"],
               ["Bunker adjustment factor (BAF)", "USD", "320.00", "Per TEU", "2", "640.00"],
               ["Port surcharge — origin (PSC)", "USD", "185.00", "Per TEU", "2", "370.00"],
               ["Terminal handling — dest. (THC)", "USD", "210.00", "Per TEU", "2", "420.00"],
               ["Bill of lading fee", "USD", "75.00", "Per B/L", "1", "75.00"],
               ["Inland haulage (Singapore)", "USD", "2,800.00", "Lump sum", "1", "2,800.00"],
               ["Cargo insurance", "USD", "400.00", "Lump sum", "1", "400.00"],
               ["Documentation & customs", "USD", "180.00", "Per shpt", "1", "180.00"],
               ["Container cleaning", "USD", "55.00", "Per unit", "2", "110.00"],
               ["Fuel surcharge (FSC)", "USD", "705.00", "Per TEU", "2", "1,410.00"],
               ["Emergency bunker surcharge (EBS)", "USD", "95.00", "Per TEU", "2", "190.00"],
               ["Telex / cable release fee", "USD", "55.00", "Per B/L", "1", "55.00"]],
              [170, 40, 58, 65, 38, 124],
              row_h=14)
    y += 4
    y = totals_block(p2, y, [
        ("Sub-total freight & surcharges", "USD 8,350.00"),
        ("Sub-total local charges", "USD 3,815.00"),
        ("Insurance", "USD 400.00"),
        ("Documentation", "USD 235.00"),
        ("Goods value (CIF)", "USD 2,600.00"),
        ("INVOICE TOTAL (USD)", "USD 15,400.00"),
    ])
    footer_note(p2, H - 42, [
        "Payment by T/T within 45 days of B/L date.  Bank details on reverse.",
        "SYNTHETIC DEMO — FreightMind PoC. All entities and transaction details are fictional.",
    ])

    save_pdf(doc, "demo-02-ocean-vietnam.pdf")


def make_03_truck_zambia() -> None:
    """Abbreviation-heavy road invoice — mode inferred, freight in ZAR."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "ROADLINK SYNTHETIC SA (PTY) LTD",
                       "12 Jan Smuts Ave, Johannesburg 2001, South Africa  |  IATA Cargo Agent Ref: DEMO-JNB-0041",
                       "ROAD FREIGHT INVOICE / CMR")
    y = info_strip(pg, y, [
        ("INV. REF.", "RLS-2025-0918-ZM"),
        ("DATE ISSUED", "18 Sep 2025"),
        ("CMR NO.", "CMR-JNB-LUN-0918-44"),
        ("PAGE", "1 of 1"),
    ])
    y += 5
    y = address_pair(pg, y,
                     "CONSIGNOR (SHIPPER)",
                     ["RoadLink Synthetic SA (fictional)",
                      "12 Jan Smuts Ave, Johannesburg",
                      "Gauteng 2001, SOUTH AFRICA",
                      "VAT: ZA-DEMO-4881922"],
                     "CONSIGNEE",
                     ["Lusaka Warehouse 7 — MedStore (fictional)",
                      "Plot 18, Heavy Industry Area",
                      "Lusaka, ZAMBIA",
                      "TPIN: ZM-DEMO-1003"])
    y += 4
    y = section_label(pg, y, "CONSIGNMENT DETAILS")
    y = info_strip(pg, y, [
        ("POL", "Johannesburg (ZAJNB)"),
        ("POD", "Lusaka (ZMLUN)"),
        ("VEHICLE REG.", "GP-DEMO-48821"),
        ("VEHICLE TYPE", "34T Flatbed (curtainsider)"),
    ])
    y = info_strip(pg, y, [
        ("GW (KGS)", "2,100"),
        ("CBM", "18.6"),
        ("ETA", "25-Sep-2025"),
        ("INCOTERMS", "DAP Lusaka"),
    ])
    y = info_strip(pg, y, [
        ("TRANSIT BORDER", "Beit Bridge / Chirundu"),
        ("CARNET / MRN", "ZA-DEMO-MRN-2025-0918"),
        ("NO. PACKAGES", "42 PLT"),
        ("PACKING", "Shrink-wrap on pallets"),
    ])
    y += 5
    y = section_label(pg, y, "COMMODITY — HS & DESCRIPTION")
    y = table(pg, y,
              ["HS CODE", "GOODS DESCRIPTION", "PKG", "GW KGS", "CBM",
               "DECLARED VALUE (ZAR)"],
              [["3004.90",
                "Pharmaceutical tablets — assorted (fictional)",
                "28 PLT", "1,540", "12.2", "ZAR 148,000"],
               ["9018.90",
                "Medical diagnostic equipment (fictional)",
                "14 PLT", "560", "6.4", "ZAR 72,500"]],
              [55, 173, 45, 60, 42, 120])
    y += 5
    y = section_label(pg, y, "FREIGHT CHARGES (ZAR) — USD equivalent footnoted below")
    y = table(pg, y,
              ["CHARGE", "RATE (ZAR)", "UNIT", "QTY", "AMOUNT (ZAR)"],
              [["Road freight — JNB to LUN", "ZAR 2,800", "Per ton", "2.1", "ZAR 5,880"],
               ["Fuel levy (15%)", "", "", "", "ZAR 882"],
               ["Cross-border handling", "ZAR 650", "Lump sum", "1", "ZAR 650"],
               ["Carnet processing", "ZAR 320", "Per shpt", "1", "ZAR 320"],
               ["Insurance (0.3% of declared)", "", "", "", "ZAR 661"]],
              [173, 90, 68, 50, 114])
    y += 4
    y = totals_block(pg, y, [
        ("SUB-TOTAL (ZAR)", "ZAR 8,393"),
        ("INVOICE TOTAL (ZAR)", "ZAR 8,393"),
    ])
    # Payment terms + delivery in body (not in footer)
    _text(pg, MARGIN, y + 4, "PAYMENT TERMS:", fs=9, fn=FONT_BOLD, color=C_DARK)
    _text(pg, MARGIN + 115, y + 4, "Due on receipt", fs=9, color=C_BLACK)
    _text(pg, MARGIN, y + 17, "DELIVERY DATE:", fs=9, fn=FONT_BOLD, color=C_DARK)
    _text(pg, MARGIN + 115, y + 17, "25 September 2025", fs=9, color=C_BLACK)

    footer_note(pg, H - 52, [
        "* USD equivalent (indicative): USD 3,100.50 at exchange rate ZAR/USD 2.7080 as of 18-Sep-2025.",
        "CMR = International Road Consignment Note (Convention on the Contract for International Carriage of Goods by Road).",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and figures are fictional.",
    ])
    save_pdf(doc, "demo-03-truck-zambia.pdf")


def make_04_low_confidence() -> None:
    """SGD invoice with USD buried in footer; payment terms in sidebar."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "MISTRAL FREIGHT & FORWARDING PTE LTD",
                       "22 Boon Lay Way #05-75, Singapore 609968  |  freight@mistral-demo.invalid",
                       "FREIGHT INVOICE (SGD)")
    y = info_strip(pg, y, [
        ("INV. NO.", "MFF-SG-2025-0822"),
        ("DATE", "22 Aug 2025"),
        ("SHIPPER REF.", "SHR-KE-UG-0822"),
        ("PAGE", "1 of 1"),
    ])
    y += 5
    y = address_pair(pg, y,
                     "SHIPPER",
                     ["Mistral Freight Test Co (fictional)",
                      "22 Boon Lay Way, Singapore 609968", "", ""],
                     "CONSIGNEE",
                     ["Recipient Placeholder Ltd (fictional)",
                      "Plot 7, Industrial Area",
                      "Kampala, UGANDA", ""])
    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("MODE", "Truck"),
        ("ORIGIN", "Kenya"),
        ("DESTINATION", "Uganda"),
        ("CARRIER", "Carrier Sample Ltd"),
    ])
    y = info_strip(pg, y, [
        ("GW KGS", "888"),
        ("CBM", "6.2"),
        ("ETA / DELIVERY", "01 Sep 2025"),
        ("INCOTERMS", "FCA Nairobi"),
    ])

    # Sidebar box for payment terms — unusual location, hard to find
    sb_x = W - MARGIN - 118
    sb = fitz.Rect(sb_x, y + 6, W - MARGIN, y + 80)
    _rect(pg, sb, fill=(1.0, 0.97, 0.90), stroke=C_BORDER, width=0.5)
    _text(pg, sb_x + 5, y + 18, "PAYMENT TERMS",
          fs=7, fn=FONT_BOLD, color=C_HDR_BG)
    _text(pg, sb_x + 5, y + 30, "Net 60",
          fs=12, fn=FONT_BOLD, color=C_DARK)
    _text(pg, sb_x + 5, y + 43, "Bank transfer only.", fs=7.5, color=C_BLACK)
    _text(pg, sb_x + 5, y + 54, "Ref: INV MFF-SG-2025-0822",
          fs=7, color=C_MID)
    _text(pg, sb_x + 5, y + 65, "Late fee: 1.5%/month", fs=7, color=C_MID)
    _text(pg, sb_x + 5, y + 77, "Due: 21 Oct 2025", fs=7, color=C_MID)

    y += 10
    y = section_label(pg, y, "CHARGES — ALL AMOUNTS IN SINGAPORE DOLLARS (SGD)")
    y = table(pg, y,
              ["DESCRIPTION", "QTY / UNIT", "RATE (SGD)", "AMOUNT (SGD)"],
              [["Road freight — Nairobi to Kampala", "1 shipment",
                "SGD 1,820", "SGD 1,820.00"],
               ["Fuel surcharge (8%)", "", "", "SGD 145.60"],
               ["Cross-border handling fee", "1", "SGD 380", "SGD 380.00"],
               ["Documentation & customs clearance", "1", "SGD 220", "SGD 220.00"],
               ["Cargo insurance (0.35% declared)", "1", "SGD 102", "SGD 102.00"],
               ["Packaging / re-consolidation", "2 PLT", "SGD 65", "SGD 130.00"]],
              [200, 88, 90, 117])
    y += 4
    y = totals_block(pg, y, [
        ("TOTAL DUE (SGD)", "SGD 2,797.60"),
    ])
    footer_note(pg, H - 58, [
        "* Indicative USD equivalent: USD 2,087.76  (exchange rate SGD/USD 1.3400 as at invoice date 22-Aug-2025).",
        "  Total freight cost (USD): approx. USD 2,200.00 inclusive of all charges listed above.",
        "SYNTHETIC DEMO — FreightMind PoC.  All named entities are fictional.",
    ])

    p4 = save_pdf(doc, "demo-04-low-confidence-paymentterms.pdf")
    rasterise(p4, "demo-04-low-confidence-paymentterms.png", dpi=110)
    p4.unlink()


def make_05_air_charter_haiti() -> None:
    """Air Charter + Haiti — scanned copy: rotation + low DPI + JPEG artefacts."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "CHARTER WINGS DEMO CORP",
                       "3200 N Terminal Rd, Miami International Airport, FL 33142, USA",
                       "AIR CHARTER INVOICE")
    y = info_strip(pg, y, [
        ("INV. NO.", "CWD-HAI-2025-0714"),
        ("DATE", "14 Jul 2025"),
        ("CHARTER AWB", "CHT-MIA-PAP-0714-009"),
        ("PAGE", "1 of 1"),
    ])
    y += 5
    y = address_pair(pg, y,
                     "CHARTERER / SHIPPER",
                     ["Charter Demo Shipper Inc. (fictional)",
                      "3200 N Terminal Rd",
                      "Miami, FL 33142, USA",
                      "FAA: DEMO-AIR-0044"],
                     "CONSIGNEE",
                     ["Port-au-Prince Consignee Corp (fictional)",
                      "Aéroport Int'l Toussaint Louverture",
                      "Port-au-Prince, HAITI",
                      "NIF: HT-DEMO-2291"])
    y += 4
    y = section_label(pg, y, "CHARTER FLIGHT DETAILS")
    y = info_strip(pg, y, [
        ("MODE", "Air Charter"),
        ("AIRCRAFT TYPE", "B737-400F (freighter)"),
        ("ORIGIN COUNTRY", "USA"),
        ("DESTINATION COUNTRY", "Haiti"),
    ])
    y = info_strip(pg, y, [
        ("DEPARTURE", "MIA — 14 Jul 2025 22:45 EST"),
        ("ARRIVAL", "PAP — 15 Jul 2025 01:20 EST"),
        ("GW KGS", "120"),
        ("DELIVERY DATE", "16 Jul 2025"),
    ])
    y += 5
    y = section_label(pg, y, "CARGO MANIFEST (SUMMARY)")
    y = table(pg, y,
              ["DESCRIPTION", "PIECES", "GW (KGS)", "DIMS (CM)", "DECLARED VALUE (USD)"],
              [["Emergency medical supplies — assorted (fictional)",
                "8 skids", "120", "120×80×85", "USD 185,000"]],
              [183, 58, 65, 84, 105])
    y += 5
    y = section_label(pg, y, "CHARTER CHARGES")
    y = table(pg, y,
              ["CHARGE DESCRIPTION", "AMOUNT (USD)"],
              [["Charter flight fee (wet lease)", "USD 38,000.00"],
               ["Fuel & oil — actual consumption", "USD 4,200.00"],
               ["Airport handling — MIA", "USD 850.00"],
               ["Airport handling — PAP", "USD 620.00"],
               ["Cargo insurance (0.2% of declared value)", "USD 900.00"],
               ["Customs / documentation fee", "USD 430.00"]],
              [350, 145])
    y += 4
    y = totals_block(pg, y, [
        ("INVOICE TOTAL (USD)", "USD 45,000.00"),
    ])
    _text(pg, MARGIN, y + 6, "PAYMENT TERMS:",
          fs=9, fn=FONT_BOLD, color=C_DARK)
    _text(pg, MARGIN + 120, y + 6,
          "Wire transfer — full payment before aircraft departure.",
          fs=9, color=C_BLACK)
    footer_note(pg, H - 38, [
        "Wire ref: CWD-HAI-0714.  Beneficiary: Charter Wings Demo Corp.  Bank details on file.",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and transaction details are fictional.",
    ])

    # Diagonal COPY watermark (rendered into the clean PDF)
    watermark(pg)

    p5 = save_pdf(doc, "demo-05-air-charter-haiti.pdf")
    # Simulate scan: slight tilt + low DPI + JPEG compression
    rasterise(p5, "demo-05-air-charter-haiti.jpg",
              dpi=96, angle=1.3, jpg_quality=62)
    p5.unlink()


def make_06_no_insurance() -> None:
    """NOT_FOUND insurance — no insurance row anywhere in document."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "EAST AFRICA DEMO AIR SERVICES LTD",
                       "Addis Ababa Bole Int'l Airport, Cargo Terminal 2, Ethiopia  |  IATA: ETH-DEMO-9901",
                       "AIR FREIGHT INVOICE")
    y = info_strip(pg, y, [
        ("INVOICE NO.", "EADAS-2025-AIR-0630"),
        ("DATE", "30 Jun 2025"),
        ("HAWB NO.", "ETH-NBO-2506300017"),
        ("PAGE", "1 of 1"),
    ])
    y += 5
    y = address_pair(pg, y,
                     "SHIPPER",
                     ["Silent Insurance Omit Co (fictional)",
                      "Cargo Terminal 2, Bole Airport",
                      "Addis Ababa, ETHIOPIA",
                      "TIN: ET-DEMO-0044"],
                     "CONSIGNEE",
                     ["Generic Receiver Ltd (fictional)",
                      "Wilson Airport, Langata Road",
                      "Nairobi, KENYA",
                      "PIN: KE-DEMO-A1020Z"])
    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("SHIPMENT MODE", "Air"),
        ("ORIGIN COUNTRY", "Ethiopia"),
        ("DESTINATION", "Kenya"),
        ("CARRIER", "East Africa Demo Air"),
    ])
    y = info_strip(pg, y, [
        ("GW KGS", "333"),
        ("CHARGEABLE WT.", "380 KGS"),
        ("DELIVERY DATE", "08 Jul 2025"),
        ("PAYMENT TERMS", "Net 15"),
    ])
    y += 5
    y = section_label(pg, y, "GOODS DESCRIPTION")
    y = table(pg, y,
              ["HS CODE", "DESCRIPTION", "PKG", "GW KGS", "DECLARED VALUE"],
              [["2106.90",
                "Nutritional supplements — fortified powder (fictional)",
                "18 CTN", "333", "USD 4,200.00"]],
              [55, 200, 50, 65, 125])
    y += 5
    y = section_label(pg, y,
                      "CHARGES — INSURANCE NOT ARRANGED BY CARRIER (see note below)")
    # Deliberately no insurance row — model must return NOT_FOUND
    y = table(pg, y,
              ["CHARGE DESCRIPTION", "RATE", "UNIT", "QTY", "AMOUNT (USD)"],
              [["Air freight — ADD to NBO", "USD 3.20", "Per KGS chrg.", "380", "USD 1,216.00"],
               ["Fuel surcharge (FSC)", "USD 0.48", "Per KGS", "380", "USD 182.40"],
               ["Airport security surcharge", "USD 0.12", "Per KGS", "380", "USD 45.60"],
               ["Origin handling — ADD", "USD 85.00", "Lump sum", "1", "USD 85.00"],
               ["Destination handling — NBO", "USD 95.00", "Lump sum", "1", "USD 95.00"],
               ["Customs documentation", "USD 60.00", "Per AWB", "1", "USD 60.00"],
               ["HAWB issuance fee", "USD 35.00", "Per AWB", "1", "USD 35.00"],
               ["Terminal handling NBO (THC)", "USD 80.00", "Lump sum", "1", "USD 80.00"]],
              [180, 78, 110, 45, 82],
              row_h=14)
    y += 4
    y = totals_block(pg, y, [
        ("Sub-total", "USD 1,799.00"),
        ("INVOICE TOTAL (USD)", "USD 1,800.00"),
    ])
    _text(pg, MARGIN, y + 6,
          "NOTE: Insurance is NOT arranged by the carrier. "
          "Consignee must arrange own cargo insurance.",
          fs=7.5, fn=FONT_BOLD, color=C_WARN)
    footer_note(pg, H - 42, [
        "Payment within 15 days of invoice date by bank transfer.  "
        "Quote HAWB ETH-NBO-2506300017.",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and figures are fictional.",
    ])

    p6 = save_pdf(doc, "demo-06-no-insurance-line.pdf")
    rasterise(p6, "demo-06-no-insurance-line.png", dpi=130)
    p6.unlink()


# ── Advanced helpers (stamps, corrections, unicode text) ─────────────────────

def write_unicode(page: fitz.Page, x: float, y: float, text: str,
                  script: str, *, fs: float = 9.5) -> None:
    """Render non-Latin text at (x, y) using the best available system font."""
    fp = _font_path(script)
    if not fp:
        return
    try:
        font = fitz.Font(fontfile=fp)
        tw   = fitz.TextWriter(page.rect)
        tw.append(fitz.Point(x, y), text, font=font, fontsize=fs)
        tw.write_text(page)
    except Exception:
        pass  # font unavailable or glyphs missing — skip silently


def stamp_overlay(page: fitz.Page, cx: float, cy: float, text: str, *,
                  color: tuple = (0.72, 0.10, 0.10),
                  angle: float = 14,
                  box_w: float = 148, box_h: float = 38) -> None:
    """Draw a rotated rubber-stamp rectangle with bold text inside."""
    a  = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = box_w / 2, box_h / 2

    def _rot(rx: float, ry: float) -> fitz.Point:
        return fitz.Point(cx + rx * ca - ry * sa, cy + rx * sa + ry * ca)

    # Outer border (thick)
    outer = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    opts  = [_rot(rx, ry) for rx, ry in outer]
    page.draw_quad(fitz.Quad(opts[0], opts[1], opts[3], opts[2]),
                   color=color, width=2.8)
    # Inner border (thin double-line effect)
    inner = [(-hw + 5, -hh + 5), (hw - 5, -hh + 5),
             (hw - 5, hh - 5),  (-hw + 5, hh - 5)]
    ipts  = [_rot(rx, ry) for rx, ry in inner]
    page.draw_quad(fitz.Quad(ipts[0], ipts[1], ipts[3], ipts[2]),
                   color=color, width=0.7)
    # Text rotated around centre
    char_w = len(text) * 5.4
    pivot  = fitz.Point(cx, cy)
    page.insert_text(
        fitz.Point(cx - char_w / 2, cy + 6),
        text, fontsize=15, fontname=FONT_BOLD,
        color=color, morph=(pivot, fitz.Matrix(angle)),
    )


def correction_mark(page: fitz.Page, x: float, y: float,
                    old_val: str, new_val: str, *,
                    color: tuple = (0.72, 0.10, 0.10)) -> None:
    """Draw old value with red strikethrough, corrected value above."""
    _text(page, x, y, old_val, fs=9, color=C_BLACK)
    w = fitz.get_text_length(old_val, fontname=FONT, fontsize=9)
    _line(page, x, y - 3, x + w, y - 3, color=color, width=1.6)
    _text(page, x, y - 16, new_val, fs=9, fn=FONT_BOLD, color=color)
    # Caret
    mx = x + w / 2
    page.draw_line(fitz.Point(mx - 4, y - 7),
                   fitz.Point(mx, y - 14), color=color, width=0.7)
    page.draw_line(fitz.Point(mx + 4, y - 7),
                   fitz.Point(mx, y - 14), color=color, width=0.7)


def handwritten_note(page: fitz.Page, x: float, y: float,
                     lines: list[str], *,
                     color: tuple = (0.10, 0.22, 0.65),
                     angle: float = 4) -> None:
    """Simulate a handwritten margin note (oblique font, slight tilt)."""
    for i, line in enumerate(lines):
        yy    = y + i * 14
        pivot = fitz.Point(x, yy)
        page.insert_text(
            fitz.Point(x, yy), line,
            fontsize=8.5, fontname="heit",
            color=color, morph=(pivot, fitz.Matrix(-angle)),
        )


# ── Invoices 07–11 ────────────────────────────────────────────────────────────

def make_07_air_usa_china() -> None:
    """Air, USA → China — Chinese consignee address, green APPROVED stamp."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "ACME PHARMA EXPORTS CORP",
                       "500 Westlake Ave N, Seattle WA 98109, USA  |  FDA Estab.: DEMO-US-2291",
                       "AIR FREIGHT INVOICE")
    y = info_strip(pg, y, [
        ("INVOICE NO.", "APE-2025-CNS-1103"),
        ("INVOICE DATE", "03 Nov 2025"),
        ("AWB NO.", "006-77812943"),
        ("PAGE", "1 of 1"),
    ])
    y += 5

    # Address pair — consignee lines left blank for CJK overdraw
    addr_y  = y
    col_w   = (W - 2 * MARGIN - 10) / 2
    rx      = MARGIN + col_w + 10
    y = address_pair(pg, y,
                     "SHIPPER / EXPORTER",
                     ["Acme Pharma Exports Corp (fictional)",
                      "500 Westlake Ave N, Seattle",
                      "WA 98109, United States",
                      "FDA Estab.: DEMO-US-2291"],
                     "CONSIGNEE / IMPORTER",
                     ["",   # rendered in Chinese below
                      "",   # rendered in Chinese below
                      "Shanghai, CHINA",
                      "统一社会信用代码: 91310000DEMO001X"])
    # Chinese company name + street
    write_unicode(pg, rx + 5, addr_y + 25,
                  "上海医疗器械贸易有限公司 (fictional)", "cjk", fs=9)
    write_unicode(pg, rx + 5, addr_y + 36,
                  "浦东新区张江路1000号  邮编200120", "cjk", fs=8)

    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("SHIPMENT MODE", "Air"),
        ("ORIGIN COUNTRY", "United States"),
        ("DESTINATION", "China"),
        ("CARRIER / AIRLINE", "Pacific Demo Airlines"),
    ])
    y = info_strip(pg, y, [
        ("GROSS WEIGHT", "320.0 KGS"),
        ("CHARGEABLE WT.", "380.0 KGS"),
        ("DELIVERY DATE", "10 Nov 2025"),
        ("PAYMENT TERMS", "Net 45"),
    ])
    y += 5
    y = section_label(pg, y, "COMMODITY DETAILS")
    y = table(pg, y,
              ["HS CODE", "DESCRIPTION", "QTY", "UNIT",
               "UNIT PRICE (USD)", "LINE TOTAL (USD)"],
              [["3004.50", "Ophthalmic pharmaceutical preparation (fictional)",
                "150", "BOX", "60.00", "9,000.00"],
               ["9018.11", "Electro-diagnostic apparatus (fictional)",
                "12", "SET", "350.00", "4,200.00"]],
              [55, 190, 35, 35, 95, 85])
    y += 4
    totals_y = y
    y = section_label(pg, y, "CHARGES SUMMARY")
    y = totals_block(pg, y, [
        ("Goods value (USD)", "13,200.00"),
        ("Air freight charge (USD)", "6,840.00"),
        ("Fuel surcharge (USD)", "342.00"),
        ("Insurance (USD)", "185.00"),
        ("Documentation fee (USD)", "75.00"),
        ("INVOICE TOTAL (USD)", "20,642.00"),
    ])

    # Green APPROVED stamp overlapping the totals section
    stamp_overlay(pg, W - MARGIN - 105, totals_y + 45,
                  "APPROVED", color=(0.08, 0.48, 0.15), angle=14)

    footer_note(pg, H - 42, [
        "All charges in US Dollars.  Payment due 45 days from invoice date.  Wire transfer only.",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities are fictional.",
    ])
    # Rasterise so the 53 MB CJK font is never the final deliverable
    p7 = save_pdf(doc, "demo-07-air-usa-china.pdf")
    rasterise(p7, "demo-07-air-usa-china.png", dpi=130)
    p7.unlink()


def make_08_air_germany_uae() -> None:
    """Air, Germany → UAE — Arabic consignee, EUR invoice, blue PAID stamp."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "RHINELAND CARGO SOLUTIONS GMBH",
                       "Cargo City Süd, Geb. 458, 60549 Frankfurt am Main, Germany  |  VAT: DE-DEMO-291882",
                       "LUFTFRACHT-RECHNUNG / AIR FREIGHT INVOICE")
    y = info_strip(pg, y, [
        ("RECHNUNGS-NR. / INV. NO.", "RCS-DE-2025-0315"),
        ("DATUM / DATE", "15 Mar 2025"),
        ("HAWB NO.", "020-44921038"),
        ("SEITE / PAGE", "1 of 1"),
    ])
    y += 5

    addr_y = y
    col_w  = (W - 2 * MARGIN - 10) / 2
    rx     = MARGIN + col_w + 10
    pay_y  = 0.0   # recorded after payment terms strip

    y = address_pair(pg, y,
                     "ABSENDER / SHIPPER",
                     ["Rhineland Cargo Solutions GmbH (fictional)",
                      "Cargo City Süd, Geb. 458",
                      "60549 Frankfurt am Main, GERMANY",
                      "VAT: DE-DEMO-291882"],
                     "EMPFÄNGER / CONSIGNEE",
                     ["",   # Arabic name
                      "",   # Arabic address
                      "Dubai, UNITED ARAB EMIRATES",
                      "TRN: AE-DEMO-100291884700003"])
    # Arabic consignee name + street
    write_unicode(pg, rx + 5, addr_y + 25,
                  "مستشفى دبي الدولي للرعاية الصحية (fictional)", "arabic", fs=9)
    write_unicode(pg, rx + 5, addr_y + 36,
                  "شارع الشيخ زايد، دبي", "arabic", fs=8.5)

    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("MODE", "Air"),
        ("ORIGIN COUNTRY", "Germany"),
        ("DESTINATION", "United Arab Emirates"),
        ("CARRIER", "Cargo Demo Lufthansa"),
    ])
    pay_y = y
    y = info_strip(pg, y, [
        ("GW KGS", "275.0"),
        ("CHARGEABLE WT.", "310.0 KGS"),
        ("DELIVERY DATE", "22 Mar 2025"),
        ("PAYMENT TERMS", "Net 30"),
    ])
    y += 5
    y = section_label(pg, y, "CHARGES — ALL AMOUNTS IN EUROS (EUR)")
    y = table(pg, y,
              ["CHARGE DESCRIPTION", "RATE (EUR)", "UNIT", "QTY", "AMOUNT (EUR)"],
              [["Air freight — FRA to DXB", "EUR 8.20", "Per KGS chrg.", "310", "EUR 2,542.00"],
               ["Fuel surcharge (FSC)", "EUR 1.40", "Per KGS", "310", "EUR 434.00"],
               ["Security surcharge (SEC)", "EUR 0.28", "Per KGS", "310", "EUR 86.80"],
               ["Origin handling — FRA", "EUR 220.00", "Lump sum", "1", "EUR 220.00"],
               ["Destination handling — DXB", "EUR 195.00", "Lump sum", "1", "EUR 195.00"],
               ["Cargo insurance", "EUR 130.00", "Lump sum", "1", "EUR 130.00"],
               ["Documentation fee", "EUR 65.00", "Per AWB", "1", "EUR 65.00"]],
              [185, 82, 72, 42, 114])
    y += 4
    y = totals_block(pg, y, [
        ("INVOICE TOTAL (EUR)", "EUR 3,672.80"),
    ])

    # Blue PAID stamp overlapping the payment terms strip
    stamp_overlay(pg, MARGIN + 300, pay_y + 15,
                  "PAID", color=(0.10, 0.22, 0.65), angle=-10, box_w=110, box_h=32)

    footer_note(pg, H - 52, [
        "* USD equivalent (indicative): USD 3,966.62  "
        "(exchange rate EUR/USD 1.0800 as at 15-Mar-2025).",
        "  Total freight cost (USD): approx. USD 4,840.00 incl. goods value.",
        "SYNTHETIC DEMO — FreightMind PoC.  All named entities are fictional.",
    ])

    p8 = save_pdf(doc, "demo-08-air-germany-uae.pdf")
    rasterise(p8, "demo-08-air-germany-uae.png", dpi=120)
    p8.unlink()


def make_09_truck_russia_kazakhstan() -> None:
    """Truck, Russia → Kazakhstan — Cyrillic shipper, weight correction, margin note."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "ROSMEDTRANS LLC  /  ООО РОСМЕДТРАНС",
                       "ul. Tverskaya 18, Moscow 125009, Russia  |  ИНН: RU-DEMO-7701002291",
                       "АВТОМОБИЛЬНАЯ НАКЛАДНАЯ / ROAD FREIGHT INVOICE")
    y = info_strip(pg, y, [
        ("INV. / СЧЁТ-ФАКТУРА", "RMT-2025-KAZ-0209"),
        ("ДАТА / DATE", "09 Feb 2025"),
        ("CMR NO.", "CMR-MOW-ALA-0209-17"),
        ("PAGE", "1 of 1"),
    ])
    y += 5

    addr_y = y
    col_w  = (W - 2 * MARGIN - 10) / 2
    y = address_pair(pg, y,
                     "ОТПРАВИТЕЛЬ / SHIPPER",
                     ["",   # Cyrillic name
                      "",   # Cyrillic address
                      "Moscow 125009, RUSSIA",
                      "ИНН: RU-DEMO-7701002291"],
                     "ПОЛУЧАТЕЛЬ / CONSIGNEE",
                     ["Almaty Medical Depot (fictional)",
                      "ul. Alatau 44, Almaty",
                      "050057, KAZAKHSTAN",
                      "БИН: KZ-DEMO-221240007291"])
    # Cyrillic shipper name + address
    write_unicode(pg, MARGIN + 5, addr_y + 25,
                  "ООО «РосМедТранс» (fictional)", "cyrillic", fs=9)
    write_unicode(pg, MARGIN + 5, addr_y + 36,
                  "ул. Тверская, 18, Москва", "cyrillic", fs=8.5)

    y += 4
    y = section_label(pg, y, "ДЕТАЛИ ОТПРАВЛЕНИЯ / CONSIGNMENT DETAILS")
    y = info_strip(pg, y, [
        ("MODE / ВИД ТРАНСПОРТА", "Truck"),
        ("ORIGIN", "Russia"),
        ("DESTINATION", "Kazakhstan"),
        ("VEHICLE / АВТО", "MAN TGX 26.480, GP-DM-4882"),
    ])
    y = info_strip(pg, y, [
        ("CBM", "22.4"),
        ("ETA", "14-Feb-2025"),
        ("INCOTERMS", "DAP Almaty"),
        ("PAYMENT TERMS", "Net 30"),
    ])

    # Weight field with correction mark (original weight was wrong)
    y += 6
    _text(pg, MARGIN, y, "GROSS WEIGHT:", fs=9, fn=FONT_BOLD, color=C_DARK)
    correction_mark(pg, MARGIN + 100, y, "1,240 KGS", "1,318 KGS")
    y += 26

    y = section_label(pg, y, "COMMODITY / ТОВАРНАЯ ПОЗИЦИЯ")
    y = table(pg, y,
              ["HS CODE", "DESCRIPTION / НАИМЕНОВАНИЕ", "PKG", "GW KGS", "DECLARED (USD)"],
              [["3004.90", "Pharmaceutical products — mixed (fictional)", "32 PLT", "1,318", "USD 88,500"],
               ["3822.00", "Diagnostic reagents (fictional)", "10 PLT", "—", "USD 14,200"]],
              [55, 190, 50, 65, 135])
    y += 5
    y = section_label(pg, y, "FREIGHT CHARGES")
    y = table(pg, y,
              ["CHARGE", "RATE", "UNIT", "QTY", "AMOUNT (USD)"],
              [["Road freight — MOW to ALA", "USD 1.60", "Per KGS", "1,318", "USD 2,108.80"],
               ["Fuel surcharge (12%)", "", "", "", "USD 253.06"],
               ["Cross-border handling", "USD 420", "Lump sum", "1", "USD 420.00"],
               ["CMR / documentation", "USD 95", "Per shpt", "1", "USD 95.00"],
               ["Insurance (0.15% declared)", "", "", "", "USD 154.05"],
               ["Phytosanitary certificate", "USD 60", "Per shpt", "1", "USD 60.00"]],
              [175, 80, 70, 52, 118])
    y += 4
    y = totals_block(pg, y, [
        ("Sub-total", "USD 3,090.91"),
        ("INVOICE TOTAL (USD)", "USD 3,091.00"),
    ])

    # Handwritten margin annotation (blue, tilted)
    handwritten_note(pg, W - MARGIN - 130, y + 10, [
        "re-check weight vs",
        "CMR doc — ops team",
        "confirmed 1,318 KGS",
    ])

    footer_note(pg, H - 42, [
        "DELIVERY DATE: 14 February 2025.  "
        "Payment by SWIFT T/T within 30 days.  Quote CMR-MOW-ALA-0209-17.",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and figures are fictional.",
    ])
    save_pdf(doc, "demo-09-truck-russia-kazakhstan.pdf")


def make_10_ocean_japan_korea() -> None:
    """Ocean, Japan → South Korea — Korean consignee, payment terms correction, scanned JPG."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "NIPPON DEMO FORWARDING CO. LTD",
                       "2-1 Kaigan, Minato-ku, Tokyo 105-0022, Japan  |  登録番号: JP-DEMO-T1810291",
                       "OCEAN FREIGHT INVOICE / 海上運賃請求書")
    y = info_strip(pg, y, [
        ("INVOICE NO. / 請求書番号", "NDF-2025-KR-0528"),
        ("DATE / 日付", "28 May 2025"),
        ("B/L NO.", "NDFTKPUS250528001"),
        ("PAGE / ページ", "1 of 1"),
    ])
    y += 5

    addr_y = y
    col_w  = (W - 2 * MARGIN - 10) / 2
    rx     = MARGIN + col_w + 10
    y = address_pair(pg, y,
                     "荷送人 / SHIPPER",
                     ["Nippon Demo Forwarding Co. Ltd (fictional)",
                      "2-1 Kaigan, Minato-ku",
                      "Tokyo 105-0022, JAPAN",
                      "登録番号: JP-DEMO-T1810291"],
                     "荷受人 / CONSIGNEE",
                     ["",   # Korean name
                      "",   # Korean address
                      "Busan, SOUTH KOREA",
                      "사업자등록번호: KR-DEMO-220-81-00291"])
    # Korean consignee name + address
    write_unicode(pg, rx + 5, addr_y + 25,
                  "부산 국제 의료물류 주식회사 (fictional)", "korean", fs=9)
    write_unicode(pg, rx + 5, addr_y + 36,
                  "부산광역시 중구 중앙대로 55", "korean", fs=8.5)

    y += 4
    y = section_label(pg, y, "BOOKING & VESSEL DETAILS / 船積詳細")
    y = info_strip(pg, y, [
        ("VESSEL / VOYAGE", "MV DEMO KOREA / V.18E"),
        ("POL", "Tokyo (JPTYO)"),
        ("POD", "Busan (KRBSN)"),
        ("ETD / ETA", "01 Jun 2025 / 03 Jun 2025"),
    ])
    y = info_strip(pg, y, [
        ("CONTAINER", "LCL  (groupage)"),
        ("GW KGS", "4,280"),
        ("CBM", "18.2"),
        ("DELIVERY DATE", "06 Jun 2025"),
    ])
    y = info_strip(pg, y, [
        ("ORIGIN COUNTRY", "Japan"),
        ("DEST. COUNTRY", "South Korea"),
        ("INCOTERMS", "CFR Busan"),
        ("MODE", "Ocean"),
    ])

    # Payment terms field with correction mark
    y += 10
    _text(pg, MARGIN, y, "PAYMENT TERMS:", fs=9, fn=FONT_BOLD, color=C_DARK)
    correction_mark(pg, MARGIN + 110, y, "Net 30", "Net 45  (revised 28-May)")
    y += 30

    y = section_label(pg, y, "CHARGES")
    y = table(pg, y,
              ["CHARGE DESCRIPTION", "CCY", "RATE", "UNIT", "QTY", "AMOUNT (USD)"],
              [["Basic ocean freight (LCL)", "USD", "42.00", "Per CBM", "18.2", "764.40"],
               ["Origin CFS handling (TYO)", "USD", "85.00", "Per CBM", "18.2", "1,547.00"],
               ["B/L issuance fee", "USD", "55.00", "Per B/L", "1", "55.00"],
               ["Destination CFS (BSN)", "USD", "65.00", "Per CBM", "18.2", "1,183.00"],
               ["Cargo insurance", "USD", "290.00", "Lump sum", "1", "290.00"],
               ["Fuel surcharge (BAF)", "USD", "18.00", "Per CBM", "18.2", "327.60"]],
              [170, 40, 58, 68, 38, 121],
              row_h=14)
    y += 4
    y = totals_block(pg, y, [
        ("INVOICE TOTAL (USD)", "USD 4,167.00"),
    ])
    footer_note(pg, H - 42, [
        "Payment within 45 days of B/L date.  Bank: Demo Bank Tokyo.  Swift: DBTOJPJT.",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and transaction details are fictional.",
    ])

    p10 = save_pdf(doc, "demo-10-ocean-japan-korea.pdf")
    # Scan simulation: low DPI + rotation + JPEG artefacts
    rasterise(p10, "demo-10-ocean-japan-korea.jpg", dpi=94, angle=0.9, jpg_quality=60)
    p10.unlink()


def make_11_truck_thailand_myanmar() -> None:
    """Truck, Thailand → Myanmar — Myanmar consignee, two overlapping stamps."""
    doc = fitz.open()
    pg  = doc.new_page(width=W, height=H)

    y = company_header(pg,
                       "SIAM CROSS-BORDER LOGISTICS CO. LTD",
                       "999/9 Rama IX Rd, Huai Khwang, Bangkok 10310, Thailand  |  TAX ID: TH-DEMO-0105562001291",
                       "ใบกำกับภาษี / ROAD FREIGHT TAX INVOICE")
    y = info_strip(pg, y, [
        ("INV. NO. / เลขที่ใบแจ้งหนี้", "SCL-TH-2025-MM-0411"),
        ("DATE / วันที่", "11 Apr 2025"),
        ("CMR / CONSIGNMENT NOTE", "CMR-BKK-MDY-0411-08"),
        ("PAGE", "1 of 1"),
    ])
    y += 5

    addr_y = y
    col_w  = (W - 2 * MARGIN - 10) / 2
    rx     = MARGIN + col_w + 10
    y = address_pair(pg, y,
                     "ผู้ส่ง / SHIPPER",
                     ["Siam Cross-Border Logistics Co. Ltd (fictional)",
                      "999/9 Rama IX Rd, Huai Khwang",
                      "Bangkok 10310, THAILAND",
                      "TAX: TH-DEMO-0105562001291"],
                     "ผู้รับ / CONSIGNEE",
                     ["",   # Myanmar name
                      "",   # Myanmar address
                      "Mandalay, MYANMAR",
                      "TIN: MM-DEMO-101291884"])
    # Myanmar consignee name + address
    write_unicode(pg, rx + 5, addr_y + 25,
                  "မန္တလေး ကျန်းမာရေး ဝန်ဆောင်မှုများ (fictional)", "myanmar", fs=8.5)
    write_unicode(pg, rx + 5, addr_y + 36,
                  "၈၃ လမ်း၊ မန္တလေးမြို့", "myanmar", fs=8.5)

    y += 4
    y = section_label(pg, y, "CONSIGNMENT DETAILS")
    y = info_strip(pg, y, [
        ("POL / ต้นทาง", "Bangkok (THBKK)"),
        ("POD / ปลายทาง", "Mandalay (MYMDY)"),
        ("VEHICLE REG.", "GBB-DEMO-8842"),
        ("VEHICLE TYPE", "6-Wheel Truck (covered)"),
    ])
    y = info_strip(pg, y, [
        ("GW KGS", "1,950"),
        ("CBM", "14.8"),
        ("ETA", "16-Apr-2025"),
        ("INCOTERMS", "DDP Mandalay"),
    ])
    y = info_strip(pg, y, [
        ("MODE", "Truck"),
        ("BORDER CROSSING", "Mae Sot / Myawaddy"),
        ("PAYMENT TERMS", "Due on receipt"),
        ("DELIVERY DATE", "16 Apr 2025"),
    ])
    y += 5
    y = section_label(pg, y, "COMMODITY")
    y = table(pg, y,
              ["HS CODE", "DESCRIPTION", "PKG", "GW KGS", "CBM", "DECLARED VALUE"],
              [["3004.90", "Essential medicines — assorted (fictional)",
                "40 CTN", "1,580", "11.2", "USD 62,000"],
               ["3922.10", "Medical consumables — sterile (fictional)",
                "18 CTN", "370", "3.6", "USD 9,800"]],
              [55, 175, 45, 60, 42, 118])
    y += 5
    y = section_label(pg, y, "FREIGHT CHARGES (USD)")
    y = table(pg, y,
              ["CHARGE", "RATE (USD)", "UNIT", "QTY", "AMOUNT (USD)"],
              [["Road freight — BKK to MDY", "USD 920", "Per truck", "1", "USD 920.00"],
               ["Fuel surcharge (10%)", "", "", "", "USD 92.00"],
               ["Cross-border handling", "USD 380", "Lump sum", "1", "USD 380.00"],
               ["Myanmar customs clearance", "USD 250", "Lump sum", "1", "USD 250.00"],
               ["Insurance (0.2% declared)", "", "", "", "USD 143.60"],
               ["Documentation / CMR", "USD 75", "Per shpt", "1", "USD 75.00"]],
              [175, 88, 70, 52, 110])
    y += 4
    y = totals_block(pg, y, [
        ("INVOICE TOTAL (USD)", "USD 1,860.60"),
    ])

    # Two overlapping stamps at different angles and colours
    # Green "CUSTOMS CLEARED" stamp
    stamp_overlay(pg, MARGIN + 170, y + 20,
                  "CUSTOMS CLEARED", color=(0.08, 0.48, 0.15),
                  angle=8, box_w=170, box_h=36)
    # Red "ORIGINAL" stamp (partially overlapping)
    stamp_overlay(pg, MARGIN + 310, y + 35,
                  "ORIGINAL", color=(0.72, 0.10, 0.10),
                  angle=-5, box_w=120, box_h=34)

    footer_note(pg, H - 42, [
        "Payment due on receipt.  Wire transfer to Siam Cross-Border Logistics Co. Ltd (fictional).",
        "SYNTHETIC DEMO — FreightMind PoC.  All entities and transaction details are fictional.",
    ])

    p11 = save_pdf(doc, "demo-11-truck-thailand-myanmar.pdf")
    rasterise(p11, "demo-11-truck-thailand-myanmar.png", dpi=125)
    p11.unlink()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    steps = [
        # Batch 1 — table layouts, multi-page, scan artefacts, currency
        (make_01_air_nigeria,       "demo-01-air-nigeria-linkage.pdf"),
        (make_02_ocean_vietnam,     "demo-02-ocean-vietnam.pdf"),
        (make_03_truck_zambia,      "demo-03-truck-zambia.pdf"),
        (make_04_low_confidence,    "demo-04-low-confidence-paymentterms.png"),
        (make_05_air_charter_haiti, "demo-05-air-charter-haiti.jpg"),
        (make_06_no_insurance,      "demo-06-no-insurance-line.png"),
        # Batch 2 — non-Latin scripts, stamps, correction marks
        (make_07_air_usa_china,          "demo-07-air-usa-china.png"),
        (make_08_air_germany_uae,        "demo-08-air-germany-uae.png"),
        (make_09_truck_russia_kazakhstan,"demo-09-truck-russia-kazakhstan.pdf"),
        (make_10_ocean_japan_korea,      "demo-10-ocean-japan-korea.jpg"),
        (make_11_truck_thailand_myanmar, "demo-11-truck-thailand-myanmar.png"),
    ]
    for fn, label in steps:
        fn()
        print(f"  ✓  {label}")
    print(f"\nWrote {len(steps)} demo invoices to {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except OSError as exc:
        raise SystemExit(f"Demo invoice generator I/O failed: {exc}") from exc
