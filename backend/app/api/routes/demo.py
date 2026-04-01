"""Demo seeding endpoints — for evaluator use only.

POST /api/demo/seed/{scenario}  inserts synthetic rows and refreshes _stats_cache.
GET  /api/demo/scenarios        lists available scenarios and their descriptions.
GET  /api/stats/live            lightweight row-count poll (no column sampling).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.services.data_seeder import AVAILABLE_SCENARIOS, seed_scenario
from app.services.stats_service import compute_and_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats/live")
async def live_stats(db: Session = Depends(get_db)) -> dict:
    """Lightweight row-count endpoint for frontend polling.

    Returns current row counts for the three main tables plus whether live
    seeding is active, so the UI can decide whether to show the live indicator.
    """
    counts: dict[str, int] = {}
    for table in ("shipments", "extracted_documents", "extracted_line_items"):
        try:
            counts[table] = int(
                db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
            )
        except Exception:
            counts[table] = 0
    return {
        **counts,
        "live_seeding_active": settings.live_seeding_interval_seconds > 0,
        "live_seeding_interval_seconds": settings.live_seeding_interval_seconds,
    }


@router.get("/demo/scenarios")
async def list_scenarios() -> dict:
    """List pre-scripted demo scenarios and their descriptions."""
    return {"scenarios": AVAILABLE_SCENARIOS}


@router.post("/demo/seed/{scenario}")
async def seed_demo_scenario(
    scenario: str,
    db: Session = Depends(get_db),
) -> dict:
    """Seed a pre-scripted scenario into the shipments table, then refresh the stats cache.

    **Scenarios**

    | Name | Effect |
    |------|--------|
    | `nigeria_air_surge` | 42 Air shipments to Nigeria → volume crosses IQR fence |
    | `ocean_cost_spike` | 35 Ocean shipments with freight cost ~1.7× the mean |
    | `new_vendor_emergence` | 25 shipments from brand-new vendor FreightCo International |

    After seeding, ask the analytics agent a question touching the affected dimension
    (e.g. "top countries by Air shipments" after `nigeria_air_surge`) to see the
    anomaly detection layer engage.

    **Note:** This endpoint is additive — calling it twice inserts the rows twice.
    """
    if scenario not in AVAILABLE_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_scenario",
                "message": f"Unknown scenario {scenario!r}.",
                "available": list(AVAILABLE_SCENARIOS),
            },
        )
    try:
        rows_inserted = seed_scenario(db, scenario)
        compute_and_store(db)
        return {
            "scenario": scenario,
            "rows_inserted": rows_inserted,
            "stats_refreshed": True,
            "message": (
                f"Scenario '{scenario}' seeded. "
                f"Ask the analytics agent about the affected dimension to trigger anomaly detection."
            ),
        }
    except Exception as exc:
        logger.exception("Demo seed failed for scenario %r", scenario)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
