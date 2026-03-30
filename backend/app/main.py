import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.csv_loader import CSV_PATH, load_shipments_from_csv
from app.core.database import SessionLocal, init_db
# Import models before init_db() so Base.metadata registers all tables
import app.models.shipment  # noqa: F401
import app.models.extracted_document  # noqa: F401
import app.models.extracted_line_item  # noqa: F401
from app.schemas.common import ErrorResponse
from app.api.routes import analytics, system

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()  # Story 1.2: idempotent table + index creation
        db = SessionLocal()
        try:
            load_shipments_from_csv(db, CSV_PATH)  # Story 1.3: seed on cold start
        finally:
            db.close()
    except FileNotFoundError:
        logger.error("CSV file missing at startup — check backend/data/ directory")
        raise
    except Exception as exc:
        logger.error("Startup sequence failed: %s", exc)
        raise
    yield


app = FastAPI(title="FreightMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            retry_after=None,
        ).model_dump(),
    )


app.include_router(system.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
