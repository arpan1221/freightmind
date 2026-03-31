#!/usr/bin/env python3
"""One-off generator for Story 6.4 synthetic freight invoices (PyMuPDF only).

Run from repo root: uv run python backend/scripts/generate_demo_invoices.py
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "backend" / "data" / "demo_invoices"

# A4 portrait points
W, H = 595, 842


def _new_page() -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    return doc, page


def _header(page: fitz.Page, title: str) -> None:
    page.insert_text((72, 56), title, fontsize=16, fontname="helv", color=(0.1, 0.1, 0.2))
    page.insert_text((72, 78), "SYNTHETIC DEMO — FreightMind PoC", fontsize=9, color=(0.4, 0.4, 0.45))


def _block(
    page: fitz.Page,
    y: float,
    label: str,
    value: str,
    *,
    fontsize: float = 10,
    color: tuple[float, float, float] = (0, 0, 0),
) -> float:
    line = f"{label}: {value}"
    page.insert_text((72, y), line, fontsize=fontsize, fontname="helv", color=color)
    return y + 14


def draw_full_invoice(
    page: fitz.Page,
    *,
    invoice_number: str,
    invoice_date: str,
    shipper: str,
    consignee: str,
    origin_country: str,
    destination_country: str,
    shipment_mode: str,
    carrier: str,
    total_weight_kg: str,
    total_freight_usd: str,
    total_insurance_usd: str | None,
    payment_terms: str,
    delivery_date: str,
    payment_terms_style: tuple[float, tuple[float, float, float]] | None = None,
) -> None:
    """Draw header fields. If total_insurance_usd is None, omit insurance line (NOT_FOUND demo)."""
    y = 110.0
    y = _block(page, y, "Invoice Number", invoice_number)
    y = _block(page, y, "Invoice Date", invoice_date)
    y = _block(page, y, "Shipper", shipper)
    y = _block(page, y, "Consignee", consignee)
    y = _block(page, y, "Origin Country", origin_country)
    y = _block(page, y, "Destination Country", destination_country)
    y = _block(page, y, "Shipment Mode", shipment_mode)
    y = _block(page, y, "Carrier / Vendor", carrier)
    y = _block(page, y, "Total Weight (kg)", total_weight_kg)
    y = _block(page, y, "Total Freight Cost (USD)", total_freight_usd)
    if total_insurance_usd is not None:
        y = _block(page, y, "Total Insurance (USD)", total_insurance_usd)
    if payment_terms_style:
        fs, col = payment_terms_style
        page.insert_text((72, y), f"Payment Terms: {payment_terms}", fontsize=fs, fontname="helv", color=col)
        y += 14
    else:
        y = _block(page, y, "Payment Terms", payment_terms)
    y = _block(page, y, "Delivery Date", delivery_date)
    y += 8
    page.insert_text((72, y), "Line items:", fontsize=10, fontname="helv", color=(0, 0, 0))
    y += 14
    page.insert_text(
        (72, y),
        "  Description: Generic freight | Qty: 10 | Unit USD: 120.00 | Line total: 1200.00",
        fontsize=9,
        fontname="helv",
        color=(0, 0, 0),
    )


def save_pdf(doc: fitz.Document, name: str) -> Path:
    path = OUT_DIR / name
    doc.save(path)
    doc.close()
    return path


def page_to_png(src_pdf: Path, out_name: str, dpi: int = 144) -> Path:
    doc = fitz.open(src_pdf)
    try:
        pix = doc[0].get_pixmap(dpi=dpi)
        out = OUT_DIR / out_name
        pix.save(out)
        return out
    finally:
        doc.close()


def page_to_jpg(src_pdf: Path, out_name: str, dpi: int = 144) -> Path:
    doc = fitz.open(src_pdf)
    try:
        pix = doc[0].get_pixmap(dpi=dpi)
        out = OUT_DIR / out_name
        pix.save(out, jpg_quality=85)
        return out
    finally:
        doc.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Linkage demo: Air + Nigeria (SCMS vocabulary after normalisation)
    doc, page = _new_page()
    _header(page, "Freight Invoice — Linkage demo")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-001",
        invoice_date="2025-11-12",
        shipper="Acme Logistics Fictional Ltd",
        consignee="Lagos Health Depot (fictional)",
        origin_country="United States",
        destination_country="Nigeria",
        shipment_mode="Air",
        carrier="Demo Air Cargo LLC",
        total_weight_kg="450.5",
        total_freight_usd="8920.00",
        total_insurance_usd="210.00",
        payment_terms="Net 30",
        delivery_date="2025-11-20",
    )
    save_pdf(doc, "demo-01-air-nigeria-linkage.pdf")

    # 2) Ocean + Vietnam
    doc, page = _new_page()
    _header(page, "Freight Invoice — Ocean")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-002",
        invoice_date="2025-10-01",
        shipper="Blue Harbor Forwarding (fake)",
        consignee="Ho Chi Minh Clinic (fake)",
        origin_country="Singapore",
        destination_country="Vietnam",
        shipment_mode="Ocean",
        carrier="Ocean Lines Demo Co",
        total_weight_kg="12000",
        total_freight_usd="15400.00",
        total_insurance_usd="400.00",
        payment_terms="CAD 45",
        delivery_date="2025-11-05",
    )
    save_pdf(doc, "demo-02-ocean-vietnam.pdf")

    # 3) Truck + Zambia
    doc, page = _new_page()
    _header(page, "Freight Invoice — Truck")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-003",
        invoice_date="2025-09-18",
        shipper="RoadLink Synthetic SA",
        consignee="Lusaka Warehouse 7 (fictional)",
        origin_country="South Africa",
        destination_country="Zambia",
        shipment_mode="Truck",
        carrier="Overland Demo Carriers",
        total_weight_kg="2100",
        total_freight_usd="3100.50",
        total_insurance_usd="95.00",
        payment_terms="Due on receipt",
        delivery_date="2025-09-25",
    )
    save_pdf(doc, "demo-03-truck-zambia.pdf")

    # 4) LOW confidence: tiny, low-contrast payment terms (export to PNG)
    doc, page = _new_page()
    _header(page, "Freight Invoice — Low-confidence field demo")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-004",
        invoice_date="2025-08-22",
        shipper="Mistral Freight Test Co",
        consignee="Recipient Placeholder",
        origin_country="Kenya",
        destination_country="Uganda",
        shipment_mode="Truck",
        carrier="Carrier Sample Ltd",
        total_weight_kg="888",
        total_freight_usd="2200.00",
        total_insurance_usd="50.00",
        payment_terms="Net 60 (see microprint)",
        delivery_date="2025-09-01",
        payment_terms_style=(4.5, (0.82, 0.82, 0.84)),
    )
    p4 = save_pdf(doc, "demo-04-low-confidence-paymentterms.pdf")
    page_to_png(p4, "demo-04-low-confidence-paymentterms.png")

    # 5) Air Charter + Haiti → JPG (dataset has both)
    doc, page = _new_page()
    _header(page, "Freight Invoice — Air Charter")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-005",
        invoice_date="2025-07-14",
        shipper="Charter Demo Shipper",
        consignee="Port-au-Prince Consignee (fictional)",
        origin_country="USA",
        destination_country="Haiti",
        shipment_mode="Air Charter",
        carrier="Charter Wings Demo",
        total_weight_kg="120",
        total_freight_usd="45000.00",
        total_insurance_usd="900.00",
        payment_terms="Wire transfer",
        delivery_date="2025-07-16",
    )
    p5 = save_pdf(doc, "demo-05-air-charter-haiti.pdf")
    page_to_jpg(p5, "demo-05-air-charter-haiti.jpg")

    # 6) NOT_FOUND: omit insurance line entirely → PNG
    doc, page = _new_page()
    _header(page, "Freight Invoice — Missing insurance line")
    draw_full_invoice(
        page,
        invoice_number="SYN-DEMO-006",
        invoice_date="2025-06-30",
        shipper="Silent Insurance Omit Co",
        consignee="Generic Receiver",
        origin_country="Ethiopia",
        destination_country="Kenya",
        shipment_mode="Air",
        carrier="East Africa Demo Air",
        total_weight_kg="333",
        total_freight_usd="1800.00",
        total_insurance_usd=None,
        payment_terms="Net 15",
        delivery_date="2025-07-08",
    )
    p6 = save_pdf(doc, "demo-06-no-insurance-line.pdf")
    page_to_png(p6, "demo-06-no-insurance-line.png")

    # Ship 6 files: 3 PDFs + 2 PNG + 1 JPG; drop raster-only source PDFs.
    for extra in (
        "demo-04-low-confidence-paymentterms.pdf",
        "demo-05-air-charter-haiti.pdf",
        "demo-06-no-insurance-line.pdf",
    ):
        p = OUT_DIR / extra
        if p.exists():
            p.unlink()

    print(f"Wrote demo invoices to {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except OSError as exc:
        raise SystemExit(f"Demo invoice generator I/O failed: {exc}") from exc
