"""Statistical foundation for the analytics judgment layer.

Maintains a ``_stats_cache`` table in SQLite with pre-computed IQR fences for
key shipment dimensions. The anomaly detector reads from this cache after each
SQL execution and enriches the answer prompt when a result crosses a fence.
"""
import logging
import re
import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table bootstrap
# ---------------------------------------------------------------------------

_CREATE_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS _stats_cache (
    dimension        TEXT PRIMARY KEY,
    label            TEXT NOT NULL,
    n                INTEGER NOT NULL,
    mean             REAL NOT NULL,
    stddev           REAL NOT NULL,
    p25              REAL NOT NULL,
    p75              REAL NOT NULL,
    iqr_fence_low    REAL NOT NULL,
    iqr_fence_high   REAL NOT NULL,
    refreshed_at     TEXT NOT NULL
)
"""


def create_stats_table() -> None:
    """Ensure _stats_cache exists.  Called once at app startup."""
    with engine.begin() as conn:
        conn.execute(text(_CREATE_STATS_TABLE))
    logger.info("_stats_cache table ensured")


# ---------------------------------------------------------------------------
# Dimensions to compute
# ---------------------------------------------------------------------------

# Each entry: (dimension_key, human_label, sql_to_fetch_scalar_values)
_DIMENSIONS: list[tuple[str, str, str]] = [
    (
        "count_per_country_all",
        "shipment count per country (all modes)",
        "SELECT COUNT(*) FROM shipments GROUP BY country",
    ),
    (
        "count_per_country_air",
        "Air shipment count per country",
        "SELECT COUNT(*) FROM shipments WHERE shipment_mode = 'Air' GROUP BY country",
    ),
    (
        "count_per_country_ocean",
        "Ocean shipment count per country",
        "SELECT COUNT(*) FROM shipments WHERE shipment_mode = 'Ocean' GROUP BY country",
    ),
    (
        "count_per_country_truck",
        "Truck shipment count per country",
        "SELECT COUNT(*) FROM shipments WHERE shipment_mode = 'Truck' GROUP BY country",
    ),
    (
        "freight_cost_usd_all",
        "freight cost USD (all modes)",
        "SELECT freight_cost_usd FROM shipments WHERE freight_cost_usd IS NOT NULL",
    ),
    (
        "freight_cost_usd_air",
        "Air freight cost USD",
        "SELECT freight_cost_usd FROM shipments "
        "WHERE shipment_mode = 'Air' AND freight_cost_usd IS NOT NULL",
    ),
    (
        "freight_cost_usd_ocean",
        "Ocean freight cost USD",
        "SELECT freight_cost_usd FROM shipments "
        "WHERE shipment_mode = 'Ocean' AND freight_cost_usd IS NOT NULL",
    ),
    (
        "freight_cost_usd_truck",
        "Truck freight cost USD",
        "SELECT freight_cost_usd FROM shipments "
        "WHERE shipment_mode = 'Truck' AND freight_cost_usd IS NOT NULL",
    ),
    (
        "weight_kg_all",
        "shipment weight kg (all modes)",
        "SELECT weight_kg FROM shipments WHERE weight_kg IS NOT NULL",
    ),
    (
        "weight_kg_air",
        "Air shipment weight kg",
        "SELECT weight_kg FROM shipments "
        "WHERE shipment_mode = 'Air' AND weight_kg IS NOT NULL",
    ),
    (
        "count_per_vendor_all",
        "shipment count per vendor (all modes)",
        "SELECT COUNT(*) FROM shipments GROUP BY vendor",
    ),
]


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

def _compute_stats(values: list[float]) -> Optional[dict]:
    """Return IQR-based stats for a list of values, or None if too few."""
    n = len(values)
    if n < 4:
        return None
    values = sorted(values)
    mean = statistics.mean(values)
    stddev = statistics.stdev(values) if n > 1 else 0.0
    p25 = values[n // 4]
    p75 = values[(3 * n) // 4]
    iqr = p75 - p25
    return {
        "n": n,
        "mean": mean,
        "stddev": stddev,
        "p25": p25,
        "p75": p75,
        "iqr_fence_low": p25 - 1.5 * iqr,
        "iqr_fence_high": p75 + 1.5 * iqr,
    }


def compute_and_store(db: Session) -> None:
    """Refresh _stats_cache for all configured dimensions."""
    now = datetime.now(timezone.utc).isoformat()
    stored = 0
    for dimension, label, sql in _DIMENSIONS:
        try:
            rows = db.execute(text(sql)).fetchall()
            values = [float(r[0]) for r in rows if r[0] is not None]
            stats = _compute_stats(values)
            if not stats:
                logger.debug("compute_and_store: too few values for %r (%d)", dimension, len(values))
                continue
            db.execute(
                text("""
                    INSERT INTO _stats_cache
                        (dimension, label, n, mean, stddev, p25, p75,
                         iqr_fence_low, iqr_fence_high, refreshed_at)
                    VALUES
                        (:dimension, :label, :n, :mean, :stddev, :p25, :p75,
                         :iqr_fence_low, :iqr_fence_high, :refreshed_at)
                    ON CONFLICT(dimension) DO UPDATE SET
                        label          = excluded.label,
                        n              = excluded.n,
                        mean           = excluded.mean,
                        stddev         = excluded.stddev,
                        p25            = excluded.p25,
                        p75            = excluded.p75,
                        iqr_fence_low  = excluded.iqr_fence_low,
                        iqr_fence_high = excluded.iqr_fence_high,
                        refreshed_at   = excluded.refreshed_at
                """),
                {"dimension": dimension, "label": label, **stats, "refreshed_at": now},
            )
            stored += 1
        except Exception:
            logger.warning("compute_and_store: failed for %r", dimension, exc_info=True)
    db.commit()
    logger.info("_stats_cache refreshed: %d/%d dimensions stored", stored, len(_DIMENSIONS))


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

_MODE_RE = re.compile(r"shipment_mode\s*=\s*'([^']+)'", re.IGNORECASE)
_GROUP_BY_COUNTRY_RE = re.compile(r"GROUP\s+BY\s+\S*country\b", re.IGNORECASE)
_FILTER_COUNTRY_RE = re.compile(r"\bcountry\s*=\s*'[^']+'", re.IGNORECASE)
_GROUP_BY_VENDOR_RE = re.compile(r"GROUP\s+BY\s+\S*vendor\b", re.IGNORECASE)

# Columns that carry labels, not metrics
_LABEL_COLS = frozenset(
    {
        "country", "vendor", "shipment_mode", "mode", "product_group",
        "sub_classification", "brand", "managed_by", "fulfill_via",
        "vendor_inco_term", "first_line_designation", "project_code",
    }
)


def _pick_dimension(sql: str, columns: list[str]) -> Optional[str]:
    """Map a query's SQL + column list to a _stats_cache dimension key, or None."""
    sql_up = sql.upper()

    # Detect shipment mode filter
    m = _MODE_RE.search(sql)
    raw_mode = m.group(1).strip().lower() if m else "all"
    if raw_mode == "air charter":
        raw_mode = "air"  # merge Air Charter into Air for stat purposes
    mode = raw_mode if raw_mode in ("air", "ocean", "truck") else "all"

    cols_lower = [c.lower() for c in columns]

    # Detect metric type from column names + SQL keywords
    has_freight = any("freight" in c or "cost" in c for c in cols_lower) or \
                  "FREIGHT_COST" in sql_up
    has_weight = any("weight" in c for c in cols_lower)
    has_count = (
        any(c in ("count", "cnt", "num", "total", "shipments", "n") or c.startswith("count")
            for c in cols_lower)
        or "COUNT(" in sql_up
    )

    by_country = bool(_GROUP_BY_COUNTRY_RE.search(sql)) or bool(_FILTER_COUNTRY_RE.search(sql))
    by_vendor = bool(_GROUP_BY_VENDOR_RE.search(sql))

    if has_count and by_country:
        return f"count_per_country_{mode}"
    if has_count and by_vendor:
        return "count_per_vendor_all"
    if has_freight:
        return f"freight_cost_usd_{mode}"
    if has_weight:
        return f"weight_kg_{mode}"

    return None


def detect_anomaly(
    db: Session,
    sql: str,
    columns: list[str],
    rows: list[list],
) -> Optional[str]:
    """Return an anomaly context string to inject into the LLM answer prompt, or None.

    Fires only when the primary numeric result exceeds the IQR upper fence stored in
    _stats_cache for the inferred dimension.  Silent on any error so it never breaks
    the main analytics pipeline.
    """
    if not rows or not columns:
        return None

    dimension = _pick_dimension(sql, columns)
    if not dimension:
        return None

    try:
        stat = db.execute(
            text(
                "SELECT label, mean, iqr_fence_high, iqr_fence_low, p25, p75 "
                "FROM _stats_cache WHERE dimension = :d"
            ),
            {"d": dimension},
        ).fetchone()
    except OperationalError:
        # _stats_cache doesn't exist yet (e.g. first cold start)
        return None
    except Exception:
        logger.debug("detect_anomaly: stats lookup failed for %r", dimension, exc_info=True)
        return None

    if not stat:
        return None

    label, mean, fence_high, fence_low, p25, p75 = stat

    # Find numeric column indices (skip label columns)
    cols_lower = [c.lower() for c in columns]
    numeric_idxs = [
        i for i, c in enumerate(cols_lower) if c not in _LABEL_COLS
    ]
    if not numeric_idxs:
        return None

    metric_idx = numeric_idxs[0]

    try:
        numeric_vals = [float(row[metric_idx]) for row in rows if row[metric_idx] is not None]
    except (TypeError, ValueError):
        return None

    if not numeric_vals:
        return None

    max_val = max(numeric_vals)

    if max_val <= fence_high:
        return None

    # Find which label entity produced the max value (for context)
    entity_label = ""
    label_idxs = [i for i, c in enumerate(cols_lower) if c in _LABEL_COLS]
    if label_idxs:
        for row in rows:
            try:
                if float(row[metric_idx]) == max_val:
                    entity_label = f" for **{row[label_idxs[0]]}**"
                    break
            except (TypeError, ValueError):
                continue

    ratio = max_val / mean if mean > 0 else 1.0
    typical = f"{p25:,.0f}–{p75:,.0f}"

    return (
        f"\n\nSTATISTICAL ANOMALY DETECTED:\n"
        f"The result contains a value that is statistically unusual "
        f"based on historical patterns in this dataset ({label}).\n"
        f"  • Observed value{entity_label}: {max_val:,.0f}\n"
        f"  • Typical range (IQR): {typical}\n"
        f"  • Upper boundary: {fence_high:,.0f}\n"
        f"  • This value is {ratio:.1f}× the historical mean ({mean:,.0f})\n\n"
        f"When presenting your answer, add 1–2 sentences noting this statistical anomaly "
        f"and one specific freight-logistics hypothesis that might explain it "
        f"(e.g. modal dependency, supply chain pressure, policy shift). "
        f"Do not add a follow-up question — those are surfaced separately as suggestion chips. "
        f"Keep the anomaly note concise and do not let it overshadow the main answer."
    )
