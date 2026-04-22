#!/usr/bin/env python3
"""Generate synthetic trade document PDFs for Part 2 demo.

Creates CI, Bill of Lading, and Packing List for both demo customers:
  DEMO_CUSTOMER_001 — GlobalTech Industries (Shanghai → Rotterdam, Ocean, CIF)
  DEMO_CUSTOMER_002 — MedSupply Asia Pte Ltd (Chennai → Singapore, Air, DAP)

All files are saved to demo/ (single location for testing).

Run from the repo root:
    python scripts/create_sample_invoices.py
"""

import sys
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    print("PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "demo"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Shared draw helpers ────────────────────────────────────────────────────────

NAVY  = (0.12, 0.24, 0.45)
STEEL = (0.22, 0.36, 0.58)
LIGHT = (0.97, 0.98, 1.0)
PALE  = (0.85, 0.88, 0.95)
GRAY  = (0.5, 0.5, 0.6)
WHITE = (1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0)


def _page_helpers(page: fitz.Page):
    def text(x, y, s, size=9, bold=False, color=BLACK):
        page.insert_text((x, y), str(s), fontsize=size,
                         fontname="hebo" if bold else "helv", color=color)

    def line(x0, y0, x1, y1, width=0.5, color=(0.7, 0.7, 0.7)):
        page.draw_line((x0, y0), (x1, y1), color=color, width=width)

    def rect(x0, y0, x1, y1, fill=None, stroke=PALE, width=0.5):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1),
                       color=stroke, fill=fill, width=width)

    return text, line, rect


# ── Commercial Invoice ─────────────────────────────────────────────────────────

def _draw_ci(doc: fitz.Document, d: dict) -> None:
    page = doc.new_page(width=595, height=842)
    T, L, R = _page_helpers(page)

    # Header
    R(30, 30, 565, 95, fill=NAVY, stroke=NAVY)
    T(40, 55, "COMMERCIAL INVOICE", size=16, bold=True, color=WHITE)
    T(40, 73, d["shipper_name"], size=9, color=(0.8, 0.9, 1.0))
    T(40, 85, d["shipper_address"], size=8, color=(0.7, 0.8, 0.9))
    T(430, 55, "Invoice No:", size=8, bold=True, color=WHITE)
    T(492, 55, d["invoice_number"], size=8, color=WHITE)
    T(430, 67, "Date:", size=8, bold=True, color=WHITE)
    T(492, 67, d["invoice_date"], size=8, color=WHITE)

    # Shipper / Consignee boxes
    y = 110
    R(30, y, 280, y + 85, fill=LIGHT, stroke=PALE)
    T(38, y + 14, "SHIPPER / EXPORTER", size=7, bold=True, color=GRAY)
    T(38, y + 27, d["shipper_name"], size=9, bold=True)
    T(38, y + 40, d.get("shipper_line2", ""), size=8)
    T(38, y + 52, d.get("shipper_line3", ""), size=8)
    T(38, y + 64, d.get("shipper_phone", ""), size=8)

    R(290, y, 565, y + 85, fill=LIGHT, stroke=PALE)
    T(298, y + 14, "CONSIGNEE / BUYER", size=7, bold=True, color=GRAY)
    T(298, y + 27, d["consignee_name"], size=9, bold=True)
    T(298, y + 40, d["consignee_addr1"], size=8)
    T(298, y + 52, d["consignee_addr2"], size=8)
    T(298, y + 64, d.get("consignee_vat", ""), size=8)

    # Shipment details
    y = 210
    T(30, y, "SHIPMENT DETAILS", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    cols = [
        ("Port of Loading",   d["port_of_loading"]),
        ("Port of Discharge", d["port_of_discharge"]),
        ("Shipment Mode",     d["shipment_mode"]),
        ("Incoterms",         d["incoterms"]),
        ("Payment Terms",     d.get("payment_terms", "Net 30 Days")),
        ("Delivery Date",     d["delivery_date"]),
    ]
    for i, (label, val) in enumerate(cols):
        cx = 30 + (i % 3) * 180
        cy = y + 16 + (i // 3) * 28
        T(cx, cy, label, size=7, color=GRAY)
        T(cx, cy + 13, val, size=9, bold=True)

    # Goods
    y = 300
    T(30, y, "DESCRIPTION OF GOODS", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    y += 14
    T(30, y, "HS / HTS Code:", size=8, bold=True)
    T(130, y, d["hs_code"], size=9, bold=True, color=(0.1, 0.3, 0.6))
    T(30, y + 12, f"Country of Origin: {d.get('origin_country', '')}", size=8)

    y += 30
    R(30, y, 565, y + 18, fill=STEEL, stroke=STEEL)
    T(38, y + 12, "Description", size=8, bold=True, color=WHITE)
    T(280, y + 12, "Qty", size=8, bold=True, color=WHITE)
    T(330, y + 12, "Unit Price (USD)", size=8, bold=True, color=WHITE)
    T(460, y + 12, "Total (USD)", size=8, bold=True, color=WHITE)

    row_colors = [WHITE, LIGHT]
    for idx, item in enumerate(d["line_items"]):
        ry = y + 18 + idx * 22
        R(30, ry, 565, ry + 22, fill=row_colors[idx % 2], stroke=(0.88, 0.88, 0.92))
        T(38, ry + 14, item["description"], size=8)
        T(280, ry + 14, str(item["qty"]), size=8)
        T(330, ry + 14, f"${item['unit_price']:,.2f}", size=8)
        T(460, ry + 14, f"${item['total']:,.2f}", size=8)

    tr_y = y + 18 + len(d["line_items"]) * 22
    L(30, tr_y, 565, tr_y)
    tr_y += 12
    grand = sum(i["total"] for i in d["line_items"])
    ins = round(grand * 0.005, 2)
    frt = d.get("freight_usd", 3200)
    T(30, tr_y, f"Gross Weight: {d['gross_weight_kg']:,} kg", size=8)
    T(380, tr_y, "Subtotal:", size=8, bold=True);  T(460, tr_y, f"${grand:,.2f}", size=8)
    tr_y += 15
    T(380, tr_y, "Freight:", size=8);  T(460, tr_y, f"${frt:,.2f}", size=8)
    tr_y += 15
    T(380, tr_y, "Insurance:", size=8);  T(460, tr_y, f"${ins:,.2f}", size=8)
    tr_y += 15
    R(380, tr_y - 2, 565, tr_y + 16, fill=NAVY, stroke=NAVY)
    T(384, tr_y + 10, "TOTAL INVOICE VALUE:", size=8, bold=True, color=WHITE)
    T(468, tr_y + 10, f"${grand + frt + ins:,.2f}", size=9, bold=True, color=WHITE)

    # Footer
    fy = 790
    L(30, fy - 10, 565, fy - 10)
    T(30, fy, f"Authorized Signatory: {d['shipper_name']}", size=7, color=GRAY)
    T(30, fy + 11, "I/We declare that the information in this invoice is true and correct.", size=7, color=GRAY)
    T(430, fy, "Page 1 of 1", size=7, color=(0.7, 0.7, 0.7))


# ── Bill of Lading ─────────────────────────────────────────────────────────────

def _draw_bl(doc: fitz.Document, d: dict) -> None:
    page = doc.new_page(width=595, height=842)
    T, L, R = _page_helpers(page)

    doc_title = d.get("doc_title", "BILL OF LADING")
    R(30, 30, 565, 95, fill=NAVY, stroke=NAVY)
    T(40, 55, doc_title, size=16, bold=True, color=WHITE)
    T(40, 73, d.get("carrier", "Ocean Carrier"), size=9, color=(0.8, 0.9, 1.0))
    T(430, 44, "B/L Number:", size=8, bold=True, color=WHITE)
    T(492, 44, d["bl_number"], size=8, color=WHITE)
    T(430, 56, "Date Issued:", size=8, bold=True, color=WHITE)
    T(492, 56, d["issue_date"], size=8, color=WHITE)
    T(430, 68, "Invoice No:", size=8, bold=True, color=WHITE)
    T(492, 68, d.get("invoice_ref", ""), size=8, color=WHITE)
    T(430, 80, "Shipment Mode:", size=8, bold=True, color=WHITE)
    T(510, 80, d.get("shipment_mode", ""), size=8, color=WHITE)

    # Shipper / Consignee
    y = 110
    R(30, y, 280, y + 85, fill=LIGHT, stroke=PALE)
    T(38, y + 14, "SHIPPER", size=7, bold=True, color=GRAY)
    T(38, y + 27, d["shipper_name"], size=9, bold=True)
    T(38, y + 40, d.get("shipper_line2", ""), size=8)
    T(38, y + 52, d.get("shipper_line3", ""), size=8)

    R(290, y, 565, y + 85, fill=LIGHT, stroke=PALE)
    T(298, y + 14, "CONSIGNEE", size=7, bold=True, color=GRAY)
    T(298, y + 27, d["consignee_name"], size=9, bold=True)
    T(298, y + 40, d["consignee_addr1"], size=8)
    T(298, y + 52, d["consignee_addr2"], size=8)

    # Transport details
    y = 210
    T(30, y, "TRANSPORT DETAILS", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    tfields = [
        ("Port of Loading / Origin",    d["port_of_loading"]),
        ("Port of Discharge / Dest.",   d["port_of_discharge"]),
        ("Mode of Transport",           d["shipment_mode"]),
        ("Incoterms",                   d["incoterms"]),
        (d.get("vessel_label", "Vessel / Flight"), d["vessel_name"]),
        ("Estimated Delivery",          d["delivery_date"]),
    ]
    for i, (label, val) in enumerate(tfields):
        cx = 30 + (i % 3) * 180
        cy = y + 16 + (i // 3) * 28
        T(cx, cy, label, size=7, color=GRAY)
        T(cx, cy + 13, val, size=9, bold=True)

    # Container / AWB details
    y = 308
    T(30, y, "CONTAINER / CARGO REFERENCE", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    T(30, y + 18, d.get("container_label", "Container No:"), size=8, bold=True)
    T(160, y + 18, d["container_numbers"], size=9, bold=True, color=(0.1, 0.3, 0.6))
    T(30, y + 34, "HS Code:", size=8, bold=True)
    T(160, y + 34, d["hs_code"], size=9, bold=True, color=(0.1, 0.3, 0.6))
    T(30, y + 50, "Total Gross Weight:", size=8, bold=True)
    T(160, y + 50, f"{d['total_weight_kg']:,} kg", size=9, bold=True)

    # Cargo description
    y = 390
    T(30, y, "DESCRIPTION OF GOODS", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    R(30, y + 10, 565, y + 28, fill=STEEL, stroke=STEEL)
    T(38, y + 23, "Marks & Numbers", size=8, bold=True, color=WHITE)
    T(200, y + 23, "Description of Packages and Goods", size=8, bold=True, color=WHITE)
    T(450, y + 23, "Gross Weight", size=8, bold=True, color=WHITE)

    for idx, cargo in enumerate(d["cargo"]):
        ry = y + 38 + idx * 22
        R(30, ry, 565, ry + 22, fill=LIGHT if idx % 2 else WHITE, stroke=(0.88, 0.88, 0.92))
        T(38, ry + 14, cargo["marks"], size=8)
        T(200, ry + 14, cargo["description"], size=8)
        T(450, ry + 14, cargo["weight"], size=8)

    # Signature block
    sig_y = 700
    L(30, sig_y, 565, sig_y)
    R(30, sig_y + 10, 280, sig_y + 80, fill=LIGHT, stroke=PALE)
    T(38, sig_y + 24, "SHIPPER'S DECLARATION", size=7, bold=True, color=GRAY)
    T(38, sig_y + 38, "Signed for and on behalf of", size=8)
    T(38, sig_y + 52, d["shipper_name"], size=9, bold=True)

    R(290, sig_y + 10, 565, sig_y + 80, fill=LIGHT, stroke=PALE)
    T(298, sig_y + 24, "CARRIER AUTHENTICATION", size=7, bold=True, color=GRAY)
    T(298, sig_y + 38, "As agent for the carrier", size=8)
    T(298, sig_y + 52, d.get("carrier", "FreightLine Global Ltd."), size=9, bold=True)

    T(30, 810, f"Original · {doc_title} · {d['bl_number']}", size=7, color=GRAY)
    T(430, 810, "Page 1 of 1", size=7, color=(0.7, 0.7, 0.7))


# ── Packing List ───────────────────────────────────────────────────────────────

def _draw_pl(doc: fitz.Document, d: dict) -> None:
    page = doc.new_page(width=595, height=842)
    T, L, R = _page_helpers(page)

    R(30, 30, 565, 88, fill=NAVY, stroke=NAVY)
    T(40, 55, "PACKING LIST", size=16, bold=True, color=WHITE)
    T(40, 73, d["shipper_name"], size=9, color=(0.8, 0.9, 1.0))
    T(430, 55, "Ref Invoice:", size=8, bold=True, color=WHITE)
    T(492, 55, d["invoice_ref"], size=8, color=WHITE)
    T(430, 67, "Date:", size=8, bold=True, color=WHITE)
    T(492, 67, d["date"], size=8, color=WHITE)

    # Shipper / Consignee
    y = 100
    R(30, y, 280, y + 80, fill=LIGHT, stroke=PALE)
    T(38, y + 14, "SHIPPER", size=7, bold=True, color=GRAY)
    T(38, y + 27, d["shipper_name"], size=9, bold=True)
    T(38, y + 40, d.get("shipper_line2", ""), size=8)
    T(38, y + 52, d.get("shipper_line3", ""), size=8)

    R(290, y, 565, y + 80, fill=LIGHT, stroke=PALE)
    T(298, y + 14, "CONSIGNEE", size=7, bold=True, color=GRAY)
    T(298, y + 27, d["consignee_name"], size=9, bold=True)
    T(298, y + 40, d["consignee_addr1"], size=8)
    T(298, y + 52, d["consignee_addr2"], size=8)

    # Routing
    y = 195
    T(30, y, "ROUTING & REFERENCE", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    rfields = [
        ("Port of Loading",   d["port_of_loading"]),
        ("Port of Discharge", d["port_of_discharge"]),
        ("Shipment Mode",     d["shipment_mode"]),
        ("HS Code",           d["hs_code"]),
        ("Incoterms",         d["incoterms"]),
        ("Total Packages",    str(d["total_packages"])),
    ]
    for i, (label, val) in enumerate(rfields):
        cx = 30 + (i % 3) * 180
        cy = y + 16 + (i // 3) * 28
        T(cx, cy, label, size=7, color=GRAY)
        T(cx, cy + 13, val, size=9, bold=True)

    # Packing table
    y = 300
    T(30, y, "PACKAGE DETAIL", size=8, bold=True, color=(0.3, 0.3, 0.4))
    L(30, y + 4, 565, y + 4)
    y += 10

    R(30, y, 565, y + 18, fill=STEEL, stroke=STEEL)
    cols = [("Pkg #", 38), ("Description of Goods", 80), ("Qty", 290),
            ("Net Wt (kg)", 340), ("Gross Wt (kg)", 410), ("Dimensions (cm)", 470)]
    for label, x in cols:
        T(x, y + 12, label, size=7, bold=True, color=WHITE)

    for idx, pkg in enumerate(d["packages"]):
        ry = y + 18 + idx * 22
        R(30, ry, 565, ry + 22, fill=LIGHT if idx % 2 else WHITE, stroke=(0.88, 0.88, 0.92))
        T(38, ry + 14, str(pkg["pkg_no"]), size=8)
        T(80, ry + 14, pkg["description"], size=8)
        T(290, ry + 14, str(pkg["qty"]), size=8)
        T(340, ry + 14, str(pkg["net_kg"]), size=8)
        T(410, ry + 14, str(pkg["gross_kg"]), size=8)
        T(470, ry + 14, pkg["dims"], size=8)

    # Totals
    tot_y = y + 18 + len(d["packages"]) * 22 + 8
    L(30, tot_y, 565, tot_y)
    tot_y += 12
    total_net   = sum(p["net_kg"]   for p in d["packages"])
    total_gross = sum(p["gross_kg"] for p in d["packages"])
    T(30, tot_y, f"Total Packages: {d['total_packages']}", size=8, bold=True)
    T(300, tot_y, f"Total Net Weight: {total_net:,} kg", size=8, bold=True)
    T(430, tot_y, f"Total Gross Weight: {total_gross:,} kg", size=8, bold=True)

    # Footer
    T(30, 810, "This packing list is a true and accurate account of the goods described above.", size=7, color=GRAY)
    T(430, 810, "Page 1 of 1", size=7, color=(0.7, 0.7, 0.7))


# ── DEMO_CUSTOMER_001 — GlobalTech Industries ─────────────────────────────────
# Shanghai → Rotterdam · Ocean · CIF · HS 8471.30.00

_GT_SHIPPER = {
    "shipper_name": "Shanghai TechExport Co., Ltd.",
    "shipper_address": "No. 88 Pudong Avenue, Shanghai 200120, China",
    "shipper_line2": "No. 88 Pudong Avenue",
    "shipper_line3": "Shanghai 200120, China",
    "shipper_phone": "Tel: +86 21 5555 0100",
}
_GT_CONSIGNEE = {
    "consignee_name": "GlobalTech Industries Ltd.",
    "consignee_addr1": "Stationsplein 45, 3013 AK Rotterdam",
    "consignee_addr2": "Netherlands",
    "consignee_vat": "VAT: NL123456789B01",
}
_GT_ROUTE = {
    "port_of_loading": "Port of Shanghai, China",
    "port_of_discharge": "Port of Rotterdam, Netherlands",
    "shipment_mode": "Ocean",
    "incoterms": "CIF",
    "origin_country": "China",
    "hs_code": "8471.30.00",
    "gross_weight_kg": 2450,
    "total_weight_kg": 2450,
}
_GT_ITEMS = [
    {"description": "Laptop Computers Model X15 (Intel Core i7)", "qty": 200, "unit_price": 850.00, "total": 170000.00},
    {"description": "USB-C Docking Stations",                     "qty": 200, "unit_price":  42.50, "total":   8500.00},
    {"description": "Power Adapters 65W Universal",               "qty": 400, "unit_price":   5.75, "total":   2300.00},
    {"description": "Laptop Carry Cases",                         "qty": 200, "unit_price":  12.00, "total":   2400.00},
]


def create_globaltech_ci_approved() -> Path:
    data = {**_GT_SHIPPER, **_GT_CONSIGNEE, **_GT_ROUTE,
            "invoice_number": "INV-2024-SH-7842",
            "invoice_date": "15 March 2024",
            "delivery_date": "30 April 2024",
            "freight_usd": 3200,
            "line_items": _GT_ITEMS}
    doc = fitz.open()
    _draw_ci(doc, data)
    out = OUTPUT_DIR / "globaltech_CI_approved.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_globaltech_ci_amendment() -> Path:
    """HS code wrong + Incoterms wrong → amendment_required."""
    data = {**_GT_SHIPPER, **_GT_CONSIGNEE, **_GT_ROUTE,
            "hs_code": "8471.40.00",     # ← WRONG
            "incoterms": "FOB",          # ← WRONG
            "invoice_number": "INV-2024-SH-7843",
            "invoice_date": "18 March 2024",
            "delivery_date": "05 May 2024",
            "gross_weight_kg": 1820,
            "freight_usd": 2800,
            "line_items": [
                {"description": "Desktop Workstations Model DX200", "qty": 50, "unit_price": 1200.00, "total": 60000.00},
                {"description": "Mechanical Keyboards",             "qty": 50, "unit_price":   68.00, "total":  3400.00},
                {"description": "Monitor 27-inch 4K",               "qty": 50, "unit_price":  320.00, "total": 16000.00},
            ]}
    doc = fitz.open()
    _draw_ci(doc, data)
    out = OUTPUT_DIR / "globaltech_CI_amendment.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_globaltech_bl() -> Path:
    data = {
        **_GT_SHIPPER, **_GT_CONSIGNEE, **_GT_ROUTE,
        "bl_number": "SHRTM2024003842",
        "invoice_ref": "INV-2024-SH-7842",
        "issue_date": "16 March 2024",
        "delivery_date": "30 April 2024",
        "carrier": "FreightLine Global Ltd.",
        "vessel_name": "CSCL Globe V.024E",
        "container_numbers": "TCKU3456789 / MSCU8821043",
        "vessel_label": "Vessel / Voyage",
        "container_label": "Container No(s):",
        "cargo": [
            {"marks": "GT/SHA/2024/01", "description": "Laptop Computers + Accessories — 200 cartons", "weight": "1 840 kg"},
            {"marks": "GT/SHA/2024/02", "description": "Docking Stations + Power Adapters — 120 cartons", "weight":   "610 kg"},
        ],
    }
    doc = fitz.open()
    _draw_bl(doc, data)
    out = OUTPUT_DIR / "globaltech_BL.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_globaltech_pl() -> Path:
    data = {
        **_GT_SHIPPER, **_GT_CONSIGNEE, **_GT_ROUTE,
        "invoice_ref": "INV-2024-SH-7842",
        "date": "15 March 2024",
        "total_packages": 320,
        "packages": [
            {"pkg_no": "1–200",  "description": "Laptop Computers Model X15",   "qty": 200, "net_kg": 1400, "gross_kg": 1560, "dims": "40×30×8"},
            {"pkg_no": "201–280","description": "USB-C Docking Stations",        "qty":  80, "net_kg":  240, "gross_kg":  280, "dims": "25×20×8"},
            {"pkg_no": "281–320","description": "Power Adapters + Carry Cases", "qty":  40, "net_kg":  120, "gross_kg":  145, "dims": "30×20×15"},
        ],
    }
    doc = fitz.open()
    _draw_pl(doc, data)
    out = OUTPUT_DIR / "globaltech_PL.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


# ── DEMO_CUSTOMER_002 — MedSupply Asia Pte Ltd ────────────────────────────────
# Chennai → Singapore · Air · DAP · HS 3004.90.99

_MS_SHIPPER = {
    "shipper_name": "BioPharm India Exports Pvt. Ltd.",
    "shipper_address": "Plot 14, SIPCOT Industrial Estate, Chennai 600058, India",
    "shipper_line2": "Plot 14, SIPCOT Industrial Estate",
    "shipper_line3": "Chennai 600058, India",
    "shipper_phone": "Tel: +91 44 2234 7890",
}
_MS_CONSIGNEE = {
    "consignee_name": "MedSupply Asia Pte Ltd",
    "consignee_addr1": "30 Toh Guan Road East #05-01",
    "consignee_addr2": "Singapore 608840",
    "consignee_vat": "UEN: 202312345K",
}
_MS_ROUTE = {
    "port_of_loading": "Chennai International Airport, India",
    "port_of_discharge": "Singapore Changi Airport, Singapore",
    "shipment_mode": "Air",
    "incoterms": "DAP",
    "origin_country": "India",
    "hs_code": "3004.90.99",
    "gross_weight_kg": 185,
    "total_weight_kg": 185,
}
_MS_ITEMS = [
    {"description": "Pharmaceutical Prep. — Amoxicillin 500mg Capsules",  "qty": 50000, "unit_price": 0.18, "total":  9000.00},
    {"description": "Pharmaceutical Prep. — Metformin 850mg Tablets",     "qty": 30000, "unit_price": 0.12, "total":  3600.00},
    {"description": "Cold-Chain Insulated Packaging Units",               "qty":   120, "unit_price": 8.50, "total":  1020.00},
]


def create_medsupply_ci_approved() -> Path:
    data = {**_MS_SHIPPER, **_MS_CONSIGNEE, **_MS_ROUTE,
            "invoice_number": "MS-2024-CH-0192",
            "invoice_date": "20 March 2024",
            "delivery_date": "28 March 2024",
            "freight_usd": 4200,
            "line_items": _MS_ITEMS}
    doc = fitz.open()
    _draw_ci(doc, data)
    out = OUTPUT_DIR / "medsupply_CI_approved.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_medsupply_ci_amendment() -> Path:
    """Wrong HS code + wrong Incoterms → amendment_required."""
    data = {**_MS_SHIPPER, **_MS_CONSIGNEE, **_MS_ROUTE,
            "hs_code": "3004.20.00",    # ← WRONG
            "incoterms": "CIF",         # ← WRONG
            "invoice_number": "MS-2024-CH-0193",
            "invoice_date": "22 March 2024",
            "delivery_date": "31 March 2024",
            "gross_weight_kg": 142,
            "freight_usd": 3600,
            "line_items": [
                {"description": "Pharmaceutical Prep. — Ciprofloxacin 500mg Tablets", "qty": 40000, "unit_price": 0.22, "total":  8800.00},
                {"description": "Cold-Chain Packaging Units",                          "qty":    80, "unit_price": 8.50, "total":   680.00},
            ]}
    doc = fitz.open()
    _draw_ci(doc, data)
    out = OUTPUT_DIR / "medsupply_CI_amendment.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_medsupply_awb() -> Path:
    """Air Waybill — equivalent of B/L for air freight."""
    data = {
        **_MS_SHIPPER, **_MS_CONSIGNEE, **_MS_ROUTE,
        "bl_number": "AWB-526-87654321",
        "invoice_ref": "MS-2024-CH-0192",
        "issue_date": "20 March 2024",
        "delivery_date": "28 March 2024",
        "carrier": "Air India Cargo / IndiGo Freighter",
        "vessel_name": "6E-9102 (Chennai → Singapore)",
        "container_numbers": "AWB 526-87654321",
        "doc_title": "AIR WAYBILL",
        "vessel_label": "Flight / Service",
        "container_label": "AWB Number:",
        "cargo": [
            {"marks": "MS/CHN/2024/01", "description": "Pharmaceutical Capsules & Tablets — temp. controlled", "weight": "142 kg"},
            {"marks": "MS/CHN/2024/02", "description": "Cold-Chain Insulated Packaging — 120 units",           "weight":  "43 kg"},
        ],
    }
    doc = fitz.open()
    _draw_bl(doc, data)
    out = OUTPUT_DIR / "medsupply_AWB.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


def create_medsupply_pl() -> Path:
    data = {
        **_MS_SHIPPER, **_MS_CONSIGNEE, **_MS_ROUTE,
        "invoice_ref": "MS-2024-CH-0192",
        "date": "20 March 2024",
        "total_packages": 58,
        "packages": [
            {"pkg_no": "1–40",  "description": "Amoxicillin 500mg Capsules (temp. controlled)", "qty": 50000, "net_kg":  90, "gross_kg": 105, "dims": "45×35×30"},
            {"pkg_no": "41–50", "description": "Metformin 850mg Tablets",                        "qty": 30000, "net_kg":  52, "gross_kg":  62, "dims": "40×30×25"},
            {"pkg_no": "51–58", "description": "Cold-Chain Insulated Packaging Units",            "qty":   120, "net_kg":  43, "gross_kg":  48, "dims": "50×40×35"},
        ],
    }
    doc = fitz.open()
    _draw_pl(doc, data)
    out = OUTPUT_DIR / "medsupply_PL.pdf"
    doc.save(str(out)); doc.close()
    print(f"Created: {out}"); return out


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating trade document PDFs...\n")

    print("── GlobalTech Industries (DEMO_CUSTOMER_001) ──")
    create_globaltech_ci_approved()
    create_globaltech_ci_amendment()
    create_globaltech_bl()
    create_globaltech_pl()

    print("\n── MedSupply Asia Pte Ltd (DEMO_CUSTOMER_002) ──")
    create_medsupply_ci_approved()
    create_medsupply_ci_amendment()
    create_medsupply_awb()
    create_medsupply_pl()

    print("\nAll files saved to demo/")
    print("\n── Test scenarios ──────────────────────────────────────────────────────────")
    print("Single doc:")
    print("  globaltech_CI_approved.pdf   → DEMO_CUSTOMER_001 → approved")
    print("  globaltech_CI_amendment.pdf  → DEMO_CUSTOMER_001 → amendment_required")
    print("  medsupply_CI_approved.pdf    → DEMO_CUSTOMER_002 → approved")
    print("  medsupply_CI_amendment.pdf   → DEMO_CUSTOMER_002 → amendment_required")
    print()
    print("Batch (upload all three together):")
    print("  globaltech_CI_approved.pdf + globaltech_BL.pdf + globaltech_PL.pdf → DEMO_CUSTOMER_001 → approved")
    print("  medsupply_CI_approved.pdf  + medsupply_AWB.pdf + medsupply_PL.pdf  → DEMO_CUSTOMER_002 → approved")
    print()
    print("Wrong customer (shows config swappability):")
    print("  globaltech_CI_approved.pdf   → DEMO_CUSTOMER_002 → all fields mismatch")
