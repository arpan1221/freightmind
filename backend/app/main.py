import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import cors_allow_origins_list, settings
from app.core.csv_loader import CSV_PATH, load_shipments_from_csv
from app.core.exceptions import ModelUnavailableError, RateLimitError
from app.core.database import SessionLocal, init_db
# Import models before init_db() so Base.metadata registers all tables
import app.models.shipment  # noqa: F401
import app.models.extracted_document  # noqa: F401
import app.models.extracted_line_item  # noqa: F401
from app.schemas.common import ErrorResponse
from app.api.routes import analytics, documents, extraction, system
from app.api.routes import demo as demo_routes
from app.services.stats_service import compute_and_store, create_stats_table

logger = logging.getLogger(__name__)


async def _live_seed_loop(interval: int) -> None:
    """Background task: drip synthetic rows into shipments at a fixed interval.

    Rotates through the three demo scenarios so each wake-up adds a different
    type of data. After each insert, stats are refreshed so anomaly detection
    reflects the new distribution immediately.
    """
    from app.services.data_seeder import AVAILABLE_SCENARIOS, seed_scenario
    from app.services.stats_service import compute_and_store as _refresh

    scenarios = list(AVAILABLE_SCENARIOS.keys())
    idx = 0
    logger.info("Live seeding enabled — interval %ds, scenarios: %s", interval, scenarios)
    while True:
        await asyncio.sleep(interval)
        scenario = scenarios[idx % len(scenarios)]
        idx += 1
        try:
            db = SessionLocal()
            try:
                inserted = seed_scenario(db, scenario)
                _refresh(db)
                logger.info("Live seed: %s — %d rows inserted", scenario, inserted)
            finally:
                db.close()
        except Exception:
            logger.warning("Live seed iteration failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()  # Story 1.2: idempotent table + index creation
        create_stats_table()  # ensure _stats_cache exists before CSV load
        db = SessionLocal()
        try:
            load_shipments_from_csv(db, CSV_PATH)  # Story 1.3: seed on cold start
            compute_and_store(db)  # build statistical baseline from loaded data
        finally:
            db.close()
    except FileNotFoundError:
        logger.error("CSV file missing at startup — check backend/data/ directory")
        raise
    except Exception as exc:
        logger.error("Startup sequence failed: %s", exc)
        raise

    task = None
    if settings.live_seeding_interval_seconds > 0:
        task = asyncio.create_task(
            _live_seed_loop(settings.live_seeding_interval_seconds)
        )

    yield

    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FreightMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins_list(settings),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_type="http_error",
            message=msg,
            detail={"status_code": exc.status_code},
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_type="validation_error",
            message="Request validation failed",
            detail={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error_type="rate_limit",
            message=exc.message,
            retry_after=exc.retry_after,
        ).model_dump(),
    )


@app.exception_handler(ModelUnavailableError)
async def model_unavailable_error_handler(
    request: Request, exc: ModelUnavailableError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(
            error_type="model_unavailable",
            message=exc.message,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_type="internal_error",
            message="An unexpected error occurred. Please try again later.",
        ).model_dump(),
    )


app.include_router(system.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(extraction.router, prefix="/api")
app.include_router(demo_routes.router, prefix="/api")
