"""Demo data seeder — inserts synthetic but statistically plausible shipment rows.

Three pre-scripted scenarios push the dataset into states where the anomaly
detection layer in the analytics agent will naturally surface insights:

  nigeria_air_surge      — Air volume to Nigeria climbs beyond the IQR fence
  ocean_cost_spike       — Ocean freight costs spike well above historical mean
  new_vendor_emergence   — A brand-new vendor appears with significant volume

Seeded rows use dates in 2025–2026 so they're distinguishable from SCMS
historical data (2006–2015) in SQL queries if needed.

Important: the endpoint is additive — calling it twice doubles the rows.
Use for demo purposes only; not idempotent.
"""
import logging
import random
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AIR_VENDORS = [
    "SCMS from RDC",
    "Aurobindo Pharma, Ltd.",
    "Ranbaxy Fine Chemicals Limited",
    "Cipla Limited",
    "Matrix Laboratories Ltd",
]

_OCEAN_VENDORS = [
    "SCMS from RDC",
    "Strides Arcolab Limited",
    "Mylan (formerly Matrix Laboratories Ltd)",
    "Mega Lifesciences Public Company Limited",
]

_PRODUCT_GROUPS = ["ARV", "HRDT", "Malaria", "HIV test"]

_INSERT_SQL = text("""
    INSERT INTO shipments (
        project_code, country, managed_by, fulfill_via, shipment_mode,
        vendor, product_group, line_item_quantity, line_item_value,
        freight_cost_usd, weight_kg, line_item_insurance_usd,
        scheduled_delivery_date, delivered_to_client_date
    ) VALUES (
        :project_code, :country, :managed_by, :fulfill_via, :shipment_mode,
        :vendor, :product_group, :line_item_quantity, :line_item_value,
        :freight_cost_usd, :weight_kg, :line_item_insurance_usd,
        :scheduled_delivery_date, :delivered_to_client_date
    )
""")


def _rng() -> random.Random:
    """Return a fresh seeded RNG so each call produces the same rows."""
    return random.Random(42)


def _rand_date(rng: random.Random, start_year: int = 2025, end_year: int = 2026) -> str:
    start = date(start_year, 1, 1)
    delta = (date(end_year, 12, 31) - start).days
    return (start + timedelta(days=rng.randint(0, delta))).isoformat()


def _insert(db: Session, rows: list[dict]) -> int:
    for row in rows:
        db.execute(_INSERT_SQL, row)
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def _nigeria_air_surge(count: int = 42) -> list[dict]:
    """Air shipments to Nigeria — pushes volume well above the IQR upper fence."""
    rng = _rng()
    rows = []
    for _ in range(count):
        weight = round(rng.uniform(80, 600), 1)
        cost = round(rng.uniform(6_000, 22_000), 2)
        rows.append({
            "project_code": "SCMS",
            "country": "Nigeria",
            "managed_by": "PMO - US",
            "fulfill_via": "Direct Drop Shipment",
            "shipment_mode": "Air",
            "vendor": rng.choice(_AIR_VENDORS),
            "product_group": rng.choice(_PRODUCT_GROUPS),
            "line_item_quantity": rng.randint(100, 5_000),
            "line_item_value": round(rng.uniform(5_000, 80_000), 2),
            "freight_cost_usd": cost,
            "weight_kg": weight,
            "line_item_insurance_usd": round(cost * 0.005, 2),
            "scheduled_delivery_date": _rand_date(rng),
            "delivered_to_client_date": _rand_date(rng),
        })
    return rows


def _ocean_cost_spike(count: int = 35) -> list[dict]:
    """Ocean shipments with freight costs ~1.7× the historical mean (~$18k → ~$30k)."""
    rng = _rng()
    countries = ["South Africa", "Tanzania", "Kenya", "Ethiopia", "Zambia", "Ghana"]
    rows = []
    for _ in range(count):
        weight = round(rng.uniform(1_000, 8_000), 1)
        cost = round(rng.uniform(24_000, 48_000), 2)
        rows.append({
            "project_code": "SCMS",
            "country": rng.choice(countries),
            "managed_by": "PMO - US",
            "fulfill_via": "Direct Drop Shipment",
            "shipment_mode": "Ocean",
            "vendor": rng.choice(_OCEAN_VENDORS),
            "product_group": rng.choice(_PRODUCT_GROUPS),
            "line_item_quantity": rng.randint(5_000, 50_000),
            "line_item_value": round(rng.uniform(20_000, 200_000), 2),
            "freight_cost_usd": cost,
            "weight_kg": weight,
            "line_item_insurance_usd": round(cost * 0.005, 2),
            "scheduled_delivery_date": _rand_date(rng),
            "delivered_to_client_date": _rand_date(rng),
        })
    return rows


def _new_vendor_emergence(count: int = 25) -> list[dict]:
    """Shipments from FreightCo International — absent from the SCMS dataset."""
    rng = _rng()
    modes = ["Air", "Ocean", "Truck"]
    countries = ["Nigeria", "Ghana", "Kenya", "South Africa", "Ethiopia"]
    rows = []
    for _ in range(count):
        mode = rng.choice(modes)
        weight = round(rng.uniform(50, 3_000), 1)
        cost = round(rng.uniform(3_000, 30_000), 2)
        rows.append({
            "project_code": "SCMS",
            "country": rng.choice(countries),
            "managed_by": "PMO - US",
            "fulfill_via": "Direct Drop Shipment",
            "shipment_mode": mode,
            "vendor": "FreightCo International",
            "product_group": rng.choice(_PRODUCT_GROUPS),
            "line_item_quantity": rng.randint(200, 10_000),
            "line_item_value": round(rng.uniform(8_000, 120_000), 2),
            "freight_cost_usd": cost,
            "weight_kg": weight,
            "line_item_insurance_usd": round(cost * 0.005, 2),
            "scheduled_delivery_date": _rand_date(rng),
            "delivered_to_client_date": _rand_date(rng),
        })
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

AVAILABLE_SCENARIOS: dict[str, str] = {
    "nigeria_air_surge": (
        "42 synthetic Air shipments to Nigeria — pushes Air volume above the IQR fence "
        "so the anomaly layer flags it in subsequent queries"
    ),
    "ocean_cost_spike": (
        "35 Ocean shipments with freight costs ~1.7× the historical mean — "
        "triggers freight cost anomaly detection"
    ),
    "new_vendor_emergence": (
        "25 shipments from FreightCo International — a vendor absent from the SCMS "
        "dataset — high vendor-count anomaly signal"
    ),
}

_BUILDERS = {
    "nigeria_air_surge": _nigeria_air_surge,
    "ocean_cost_spike": _ocean_cost_spike,
    "new_vendor_emergence": _new_vendor_emergence,
}


def seed_scenario(db: Session, scenario: str) -> int:
    """Insert rows for the named scenario. Returns row count inserted."""
    if scenario not in _BUILDERS:
        raise ValueError(
            f"Unknown scenario {scenario!r}. "
            f"Available: {list(AVAILABLE_SCENARIOS)}"
        )
    rows = _BUILDERS[scenario]()
    inserted = _insert(db, rows)
    logger.info("Seeded scenario %r: %d rows inserted", scenario, inserted)
    return inserted
