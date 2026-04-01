import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "SCMS_Delivery_History_Dataset.csv"

# Map CSV header names → SQLAlchemy ORM field names.
# Note: source CSV uses "ID" (uppercase) for the primary key column.
COLUMN_MAP = {
    "ID": "id",
    "Project Code": "project_code",
    "PQ #": "pq_number",
    "PO / SO #": "po_so_number",
    "ASN/DN #": "asn_dn_number",
    "Country": "country",
    "Managed By": "managed_by",
    "Fulfill Via": "fulfill_via",
    "Vendor INCO Term": "vendor_inco_term",
    "Shipment Mode": "shipment_mode",
    "PQ First Sent to Client Date": "pq_first_sent_to_client_date",
    "PO Sent to Vendor Date": "po_sent_to_vendor_date",
    "Scheduled Delivery Date": "scheduled_delivery_date",
    "Delivered to Client Date": "delivered_to_client_date",
    "Delivery Recorded Date": "delivery_recorded_date",
    "Product Group": "product_group",
    "Sub Classification": "sub_classification",
    "Vendor": "vendor",
    "Item Description": "item_description",
    "Molecule/Test Type": "molecule_test_type",
    "Brand": "brand",
    "Dosage": "dosage",
    "Dosage Form": "dosage_form",
    "Unit of Measure (Per Pack)": "unit_of_measure_per_pack",
    "Line Item Quantity": "line_item_quantity",
    "Line Item Value": "line_item_value",
    "Pack Price": "pack_price",
    "Unit Price": "unit_price",
    "Manufacturing Site": "manufacturing_site",
    "First Line Designation": "first_line_designation",
    "Weight (Kilograms)": "weight_kg",
    "Freight Cost (USD)": "freight_cost_usd",
    "Line Item Insurance (USD)": "line_item_insurance_usd",
}

DATE_COLS = [
    "PQ First Sent to Client Date",
    "PO Sent to Vendor Date",
    "Scheduled Delivery Date",
    "Delivered to Client Date",
    "Delivery Recorded Date",
]


def load_shipments_from_csv(session: Session, csv_path: Path = CSV_PATH) -> int:
    """Load SCMS shipments from CSV into the `shipments` table.

    Idempotent: returns 0 immediately if the table already contains rows.
    Raises FileNotFoundError if csv_path does not exist.
    Returns the number of rows inserted.
    """
    from app.models.shipment import Shipment  # late import avoids circular at module level

    if session.query(Shipment).count() > 0:
        logger.info("Shipments table already populated — CSV load skipped")
        return 0

    if not csv_path.exists():
        raise FileNotFoundError(f"SCMS CSV not found at: {csv_path.resolve()}")

    logger.info("Loading shipments from %s ...", csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    # Clean numeric sentinel columns BEFORE rename so original CSV headers apply.
    # Non-numeric strings (e.g. "Weight Captured Separately", "See ASN-XXX") → NaN → NULL.
    for col in ["Weight (Kilograms)", "Freight Cost (USD)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse date columns to ISO TEXT before rename.
    # format="mixed" handles the varied date formats in the SCMS CSV (e.g. "3/14/13", "2-Jun-06").
    # strftime on NaT produces literal "NaT" in some pandas versions;
    # guard with .where(parsed.notna(), None) to ensure None instead.
    for col in DATE_COLS:
        parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
        df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)

    # Strip leading/trailing whitespace from all string/object columns before rename.
    # Include both "object" and "str" dtypes to support pandas 2.x and 3.x.
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()

    # Rename CSV headers to ORM column names.
    df = df.rename(columns=COLUMN_MAP)

    # Impute freight_cost_usd for rows where weight_kg is known but freight is NULL.
    # Uses mode-specific average cost-per-kg computed from rows that have both values.
    # Only ~197 rows qualify; the ~3,929 rows missing both columns are left as NULL.
    rates = (
        df[df["freight_cost_usd"].notna() & df["weight_kg"].notna() & (df["weight_kg"] > 0)]
        .assign(_rate=lambda x: x["freight_cost_usd"] / x["weight_kg"])
        .groupby("shipment_mode")["_rate"]
        .mean()
    )
    impute_mask = (
        df["freight_cost_usd"].isna()
        & df["weight_kg"].notna()
        & (df["weight_kg"] > 0)
        & df["shipment_mode"].isin(rates.index)
    )
    df.loc[impute_mask, "freight_cost_usd"] = df.loc[impute_mask].apply(
        lambda row: round(row["weight_kg"] * rates[row["shipment_mode"]], 2), axis=1
    )
    logger.info(
        "Imputed freight_cost_usd for %d rows using mode-avg cost/kg rates: %s",
        int(impute_mask.sum()),
        {mode: round(float(rate), 4) for mode, rate in rates.items()},
    )

    # Convert ALL remaining NaN / NaT to Python None → SQLite NULL.
    # df.where() alone is insufficient in pandas 3.x with mixed dtypes;
    # do an explicit per-value cleanup pass after to_dict() for safety.
    df = df.where(pd.notna(df), None)
    raw_records = df.to_dict(orient="records")

    def _none_if_nan(v: object) -> object:
        """Return None for any NaN/NA/NaT value; leave everything else intact."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    records = [{k: _none_if_nan(v) for k, v in row.items()} for row in raw_records]
    try:
        session.execute(insert(Shipment), records)
        session.commit()
    except Exception:
        session.rollback()
        raise

    logger.info("Loaded %d shipments from CSV", len(records))
    return len(records)
