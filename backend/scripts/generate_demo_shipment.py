#!/usr/bin/env python3
"""Synthetic 3-document freight shipment generator.

Produces a matched set:
  - demo_shipment_CI.pdf  — Commercial Invoice (all rules pass)
  - demo_shipment_BL.pdf  — Bill of Lading (port_of_loading = Ningbo, triggers mismatch)
  - demo_shipment_PL.pdf  — Packing List

All three documents reference the same shipment:
  GlobalTech Industries Ltd. / INV-2024-GT-0042 / CIF Shanghai→Rotterdam
  Vessel: EVER GLORY / Container: CSNU3456789

The B/L deliberately lists Ningbo as the port of loading instead of Shanghai,
which trips the customer rule for DEMO_CUSTOMER_001 and produces
overall_status = amendment_required in the batch verification pipeline.

Run from repo root:
  uv run python backend/scripts/generate_demo_shipment.py
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "backend" / "data" / "demo_invoices"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 595, 842   # A4 portrait in points
MARGIN = 50

# ── Colours (same palette as generate_demo_invoices.py) ──────────────────────
C_BLACK     = (0.05, 0.05, 0.05)
C_DARK      = (0.15, 0.15, 0.20)
C_MID       = (0.45, 0.45, 0.50)
C_LIGHT     = (0.70, 0.70, 0.72)
C_HDR_BG    = (0.22, 0.38, 0.56)
C_STRIPE    = (0.95, 0.96, 0.98)
C_BORDER    = (0.70, 0.72, 0.75)
C_WARN      = (0.65, 0.10, 0.10)
C_WATERMARK = (0.87, 0.87, 0.88)
C_GREEN     = (0.10, 0.50, 0.20)

FONT      = "helv"
FONT_BOLD = "hebo"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _text(page, x, y, s, *, fs=9, fn=FONT, color=C_BLACK):
    page.insert_text(fitz.Point(x, y), s, fontsize=fs, fontname=fn, color=color)


def _textbox(page, rect, s, *, fs=9, fn=FONT, color=C_BLACK, align=0):
    page.insert_textbox(rect, s, fontsize=fs, fontname=fn, color=color, align=align)


def _rect(page, rect, *, fill=None, stroke=None, width=0.5):
    page.draw_rect(rect, color=stroke, fill=fill, width=width)


def _line(page, x0, y0, x1, y1, *, color=C_BORDER, width=0.4):
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=color, width=width)


# ── Reusable layout components ────────────────────────────────────────────────

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


def address_pair(page, y: float,
                 left_title: str, left_lines: list[str],
                 right_title: str, right_lines: list[str]) -> float:
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


def section_label(page, y: float, text: str) -> float:
    _text(page, MARGIN, y, text, fs=8.5, fn=FONT_BOLD, color=C_HDR_BG)
    _line(page, MARGIN, y + 3, W - MARGIN, y + 3, color=C_HDR_BG, width=0.5)
    return y + 12


def table(page, y: float, headers: list[str],
          rows: list[list[str]], col_widths: list[float], *,
          row_h: float = 15, hdr_h: float = 19,
          stripe: bool = True) -> float:
    x0 = MARGIN
    x1 = x0 + sum(col_widths)
    hdr_rect = fitz.Rect(x0, y, x1, y + hdr_h)
    _rect(page, hdr_rect, fill=C_HDR_BG)
    cx = x0
    for hdr, cw in zip(headers, col_widths):
        cell = fitz.Rect(cx + 2, y + 2, cx + cw - 2, y + hdr_h - 2)
        _textbox(page, cell, hdr, fs=7.5, fn=FONT_BOLD, color=(1, 1, 1), align=1)
        cx += cw
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
    _rect(page, fitz.Rect(x0, y, x1, yr), stroke=C_BORDER, width=0.5)
    cx = x0
    for cw in col_widths[:-1]:
        cx += cw
        _line(page, cx, y, cx, yr, color=C_BORDER, width=0.25)
    return yr + 6


def totals_block(page, y: float, items: list[tuple[str, str]]) -> float:
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
            _line(page, lx - 4, y - 1, W - MARGIN, y - 1, color=C_BORDER, width=0.4)
    return y + 4


def footer_note(page, y: float, lines: list[str]) -> None:
    _line(page, MARGIN, y, W - MARGIN, y, color=C_BORDER, width=0.3)
    for k, line in enumerate(lines):
        _text(page, MARGIN, y + 10 + k * 11, line, fs=7, color=C_MID)


def compliance_badge(page, y: float, label: str, value: str, color=C_GREEN) -> float:
    """Small highlighted key/value for compliance-relevant fields."""
    box = fitz.Rect(MARGIN, y, MARGIN + 220, y + 18)
    _rect(page, box, fill=(0.93, 0.98, 0.93), stroke=(0.65, 0.85, 0.65), width=0.4)
    _text(page, MARGIN + 5, y + 12, f"{label}:", fs=7.5, fn=FONT_BOLD, color=color)
    _text(page, MARGIN + 80, y + 12, value, fs=7.5, color=C_DARK)
    return y + 24


# ── Document generators ───────────────────────────────────────────────────────

def make_commercial_invoice() -> Path:
    """Commercial Invoice — all fields match DEMO_CUSTOMER_001 rules."""
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    y = company_header(
        pg,
        "SHANGHAI TECH EXPORTS LTD.",
        "88 Pudong Avenue, Pudong New District, Shanghai 200120, P.R. China  |  trade@ste-demo.invalid",
        "COMMERCIAL INVOICE",
    )
    y = info_strip(pg, y, [
        ("INVOICE NO.", "INV-2024-GT-0042"),
        ("INVOICE DATE", "15 Mar 2024"),
        ("PAYMENT TERMS", "Net 60 days"),
        ("CURRENCY", "USD"),
    ])
    y += 5
    y = address_pair(
        pg, y,
        "SHIPPER / EXPORTER",
        ["Shanghai Tech Exports Ltd. (demo)",
         "88 Pudong Avenue, Pudong New District",
         "Shanghai 200120, P.R. CHINA",
         "EORI: CN-DEMO-STE-20241"],
        "CONSIGNEE / IMPORTER",
        ["GlobalTech Industries Ltd.",
         "Prinses Beatrixlaan 20",
         "2595 AK The Hague, NETHERLANDS",
         "VAT: NL-DEMO-GT-88421"],
    )
    y += 4
    y = section_label(pg, y, "SHIPMENT DETAILS")
    y = info_strip(pg, y, [
        ("SHIPMENT MODE", "Ocean"),
        ("INCOTERMS", "CIF"),
        ("PORT OF LOADING", "Shanghai, China"),
        ("PORT OF DISCHARGE", "Rotterdam, Netherlands"),
    ], cols=4)
    y += 4
    y = info_strip(pg, y, [
        ("HS CODE", "8471.30.00"),
        ("ORIGIN COUNTRY", "China"),
        ("DELIVERY DATE (ETA)", "20 Apr 2024"),
        ("VESSEL / VOYAGE", "EVER GLORY / EG-2024-12W"),
    ], cols=4)
    y += 8

    y = section_label(pg, y, "LINE ITEMS")
    y = table(
        pg, y,
        ["#", "DESCRIPTION OF GOODS", "HS CODE", "QTY", "UNIT PRICE (USD)", "TOTAL (USD)"],
        [
            ["1", "Laptop Computer, 15\" (Core i7, 16GB RAM)", "8471.30.00", "200", "580.00", "116,000.00"],
            ["2", "Laptop Docking Station", "8471.30.00", "200", "45.00", "9,000.00"],
            ["3", "USB-C Power Adapter 65W", "8504.40.95", "200", "18.50", "3,700.00"],
            ["4", "Carrying Case (Nylon)", "4202.12.20", "200", "12.00", "2,400.00"],
        ],
        [20, 185, 80, 40, 100, 70],
    )
    y += 4

    y = totals_block(pg, y, [
        ("Sub-Total:",      "USD 131,100.00"),
        ("Freight (CIF):",  "USD   4,320.00"),
        ("Insurance:",      "USD     420.00"),
        ("TOTAL INVOICE:",  "USD 135,840.00"),
    ])
    y += 10

    y = section_label(pg, y, "COMPLIANCE NOTES")
    for label, value in [
        ("Country of Origin", "China"),
        ("HS Classification", "8471.30.00 — Portable automatic data processing machines"),
        ("Incoterms 2020", "CIF — Cost, Insurance and Freight (Port of Rotterdam)"),
        ("Trade Agreement", "Contract GT-CN-2024 | Customs Agreement CA-2024-GT"),
    ]:
        _text(pg, MARGIN + 5, y, f"  \u2022  {label}: {value}", fs=8, color=C_DARK)
        y += 12

    footer_note(pg, y + 10, [
        "This is a demo document generated for FreightMind PoC testing.",
        "Invoice issued by: Shanghai Tech Exports Ltd. | Authorised signatory: Wang Lei, Export Manager",
        "Bank: Demo Bank of China | Account: DEMO-STE-001 | SWIFT: BKCHCNBJ",
    ])

    path = OUT_DIR / "demo_shipment_CI.pdf"
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


def make_bill_of_lading() -> Path:
    """Bill of Lading — port_of_loading = Ningbo (deliberate mismatch vs. Shanghai rule)."""
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    y = company_header(
        pg,
        "EVERGREEN MARINE CORPORATION",
        "166 Minsheng E. Rd., Taipei 105, Taiwan  |  cargo@evergreen-demo.invalid",
        "BILL OF LADING",
    )
    y = info_strip(pg, y, [
        ("B/L NUMBER", "BL-2024-GT-00512"),
        ("B/L DATE", "16 Mar 2024"),
        ("BOOKING REF.", "EVG-BK-20241603"),
        ("VOYAGE NO.", "EG-2024-12W"),
    ])
    y += 5
    y = address_pair(
        pg, y,
        "SHIPPER",
        ["Shanghai Tech Exports Ltd. (demo)",
         "88 Pudong Avenue",
         "Shanghai 200120, CHINA",
         "Tel: +86 21 DEMO-0001"],
        "CONSIGNEE",
        ["GlobalTech Industries Ltd.",
         "Prinses Beatrixlaan 20",
         "2595 AK The Hague, NETHERLANDS",
         "Tel: +31 70 DEMO-0002"],
    )
    y += 4

    y = section_label(pg, y, "VESSEL & ROUTING")
    y = info_strip(pg, y, [
        ("VESSEL NAME", "EVER GLORY"),
        ("SHIPMENT MODE", "Ocean"),
        ("PORT OF LOADING", "Ningbo, China"),     # ← INTENTIONAL MISMATCH
        ("PORT OF DISCHARGE", "Rotterdam, Netherlands"),
    ], cols=4)
    y += 4

    # Warning callout to make the mismatch visible in demo
    warn_box = fitz.Rect(MARGIN, y, W - MARGIN, y + 22)
    _rect(pg, warn_box, fill=(1.0, 0.95, 0.92), stroke=C_WARN, width=0.6)
    _text(pg, MARGIN + 8, y + 9, "NOTE:", fs=8, fn=FONT_BOLD, color=C_WARN)
    _text(pg, MARGIN + 50, y + 9,
          "Port of Loading recorded as Ningbo per terminal manifest TMF-2024-0342.",
          fs=8, color=C_DARK)
    _text(pg, MARGIN + 8, y + 18, "(Commercial Invoice specifies Shanghai — requires amendment)",
          fs=7, color=C_WARN)
    y += 28

    y = info_strip(pg, y, [
        ("INCOTERMS", "CIF"),
        ("ORIGIN COUNTRY", "China"),
        ("ETA ROTTERDAM", "20 Apr 2024"),
        ("CONTAINER NO.", "CSNU3456789"),
    ], cols=4)
    y += 8

    y = section_label(pg, y, "CONTAINER & CARGO DETAILS")
    y = table(
        pg, y,
        ["CONTAINER NO.", "TYPE", "SEAL NO.", "DESCRIPTION OF GOODS", "GROSS WEIGHT (KG)", "CBM"],
        [
            ["CSNU3456789", "20'GP", "SL-882441", "Laptop Computers & Accessories", "3,240.00", "18.6"],
        ],
        [90, 45, 70, 155, 95, 40],
    )
    y += 4

    y = section_label(pg, y, "CARGO MARKS & NUMBERS")
    y = info_strip(pg, y, [
        ("TOTAL PACKAGES", "200 Cartons"),
        ("TOTAL WEIGHT", "3,240.00 KG"),
        ("TOTAL VOLUME", "18.6 CBM"),
        ("FREIGHT TERMS", "PREPAID"),
    ], cols=4)
    y += 8

    y = section_label(pg, y, "HS CLASSIFICATION")
    y = info_strip(pg, y, [
        ("PRIMARY HS CODE", "8471.30.00"),
        ("GOODS DESCRIPTION", "Portable automatic data-processing machines"),
        ("DANGEROUS GOODS", "No"),
        ("TEMPERATURE", "Ambient"),
    ], cols=4)
    y += 12

    _text(pg, MARGIN, y, "FREIGHT & CHARGES", fs=8.5, fn=FONT_BOLD, color=C_HDR_BG)
    y += 14
    y = table(
        pg, y,
        ["CHARGE TYPE", "CURRENCY", "PREPAID", "COLLECT"],
        [
            ["Ocean Freight", "USD", "4,320.00", "—"],
            ["B/L Fee", "USD", "85.00", "—"],
            ["Terminal Handling", "USD", "240.00", "—"],
        ],
        [180, 80, 100, 135],
    )

    footer_note(pg, y + 10, [
        "This Bill of Lading is issued in 3 (three) originals. One original duly endorsed must be",
        "surrendered to the carrier in exchange for the goods. This is a demo document for FreightMind PoC.",
        "Carrier: Evergreen Marine Corporation | Signed: Y. Chen, Documentation Supervisor",
    ])

    path = OUT_DIR / "demo_shipment_BL.pdf"
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


def make_packing_list() -> Path:
    """Packing List — consistent with Commercial Invoice."""
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    y = company_header(
        pg,
        "SHANGHAI TECH EXPORTS LTD.",
        "88 Pudong Avenue, Pudong New District, Shanghai 200120, P.R. China  |  trade@ste-demo.invalid",
        "PACKING LIST",
    )
    y = info_strip(pg, y, [
        ("REF. INVOICE NO.", "INV-2024-GT-0042"),
        ("PACKING DATE", "15 Mar 2024"),
        ("DESTINATION", "Rotterdam, Netherlands"),
        ("CONTAINER NO.", "CSNU3456789"),
    ])
    y += 5
    y = address_pair(
        pg, y,
        "SHIPPER",
        ["Shanghai Tech Exports Ltd. (demo)",
         "88 Pudong Avenue, Pudong",
         "Shanghai 200120, CHINA"],
        "CONSIGNEE",
        ["GlobalTech Industries Ltd.",
         "Prinses Beatrixlaan 20",
         "2595 AK The Hague, NETHERLANDS"],
    )
    y += 4
    y = section_label(pg, y, "SHIPMENT SUMMARY")
    y = info_strip(pg, y, [
        ("SHIPMENT MODE", "Ocean"),
        ("PORT OF LOADING", "Shanghai, China"),
        ("PORT OF DISCHARGE", "Rotterdam, Netherlands"),
        ("INCOTERMS", "CIF"),
    ], cols=4)
    y += 4
    y = info_strip(pg, y, [
        ("ORIGIN COUNTRY", "China"),
        ("HS CODE", "8471.30.00"),
        ("DELIVERY DATE", "20 Apr 2024"),
        ("TOTAL PACKAGES", "200 Cartons"),
    ], cols=4)
    y += 8

    y = section_label(pg, y, "PACKING DETAILS")
    y = table(
        pg, y,
        ["CARTON NO.", "DESCRIPTION", "HS CODE", "QTY / CTN", "CARTONS", "NW (KG)", "GW (KG)", "DIMS (CM)"],
        [
            ["001-100", "Laptop Computer 15\"", "8471.30.00", "2 pcs", "100", "7.2", "8.0", "50x36x12"],
            ["101-150", "Laptop Docking Station", "8471.30.00", "4 pcs", "50", "3.0", "3.4", "30x20x15"],
            ["151-175", "USB-C Adapter 65W", "8504.40.95", "8 pcs", "25", "1.6", "1.8", "25x18x8"],
            ["176-200", "Carrying Case (Nylon)", "4202.12.20", "8 pcs", "25", "2.0", "2.2", "45x35x5"],
        ],
        [60, 130, 75, 65, 55, 55, 55],
    )
    y += 4

    y = totals_block(pg, y, [
        ("Total Cartons:",           "200"),
        ("Total Net Weight:",        "1,380.00 KG"),
        ("Total Gross Weight:",      "1,480.00 KG"),
        ("Cargo TOTAL Gross Weight:","3,240.00 KG (incl. pallets)"),
        ("Total Volume:",            "18.6 CBM"),
    ])
    y += 10

    y = section_label(pg, y, "MARKS & NUMBERS")
    marks = [
        "SHIPPER'S MARKS: STE-GT-2024-42",
        "CARTON MARKS: GLOBALTECH IND. / ROTTERDAM / MADE IN CHINA",
        "HAZMAT: NO DANGEROUS GOODS",
        "TEMP REQUIREMENTS: AMBIENT / KEEP DRY",
    ]
    for m in marks:
        _text(pg, MARGIN + 5, y, f"  \u2022  {m}", fs=8, color=C_DARK)
        y += 12

    footer_note(pg, y + 10, [
        "This packing list was prepared by the shipper and is accurate to the best of our knowledge.",
        "This is a demo document generated for FreightMind PoC testing.",
        "Prepared by: Li Mei, Logistics Coordinator | Date: 15 Mar 2024",
    ])

    path = OUT_DIR / "demo_shipment_PL.pdf"
    doc.save(str(path), garbage=4, deflate=True, clean=True)
    doc.close()
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Output directory: {OUT_DIR}")

    ci = make_commercial_invoice()
    print(f"  Created: {ci.name}")

    bl = make_bill_of_lading()
    print(f"  Created: {bl.name}  (port_of_loading = Ningbo — intentional mismatch)")

    pl = make_packing_list()
    print(f"  Created: {pl.name}")

    print("\nAll 3 documents generated successfully.")
    print("Upload all three via the Verification tab to demo the batch flow.")
    print("Expected result: amendment_required (B/L port_of_loading mismatch)")
