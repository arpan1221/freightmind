import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, SessionLocal, get_db
from app.schemas.common import HealthResponse
from app.schemas.schema_info import ColumnInfo, SchemaInfoResponse, TableInfo

router = APIRouter()
logger = logging.getLogger(__name__)

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_MODEL_CHECK_TIMEOUT = 3.0  # seconds — hard cap so health never blocks


async def _check_model() -> str:
    try:
        async with httpx.AsyncClient(timeout=_MODEL_CHECK_TIMEOUT) as client:
            resp = await client.get(
                _OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            return "reachable" if resp.is_success else "unreachable"
    except Exception:
        logger.warning("Health check: model unreachable")
        return "unreachable"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    # DB check — create session inline so any failure (including session creation)
    # is caught here; Depends(get_db) would propagate exceptions before this try/except.
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            database = "connected"
        finally:
            db.close()
    except Exception:
        logger.warning("Health check: DB unreachable")
        database = "error"

    # Model check — async HTTP with hard timeout
    model = await _check_model()

    status = "ok" if database == "connected" and model == "reachable" else "degraded"
    return HealthResponse(status=status, database=database, model=model)


@router.get("/schema", response_model=SchemaInfoResponse)
async def get_schema(db: Session = Depends(get_db)) -> SchemaInfoResponse:
    """Return all table names, row counts, column names, and up to 3 sample values per column."""
    tables = []
    for table_name, table in Base.metadata.tables.items():
        try:
            row_count = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0
        except Exception:
            row_count = 0

        columns = []
        for col in table.columns:
            try:
                result = db.execute(
                    text(
                        f'SELECT DISTINCT "{col.name}" FROM "{table_name}"'
                        f' WHERE "{col.name}" IS NOT NULL LIMIT 3'
                    )
                )
                sample_values = [row[0] for row in result.fetchall()]
            except Exception:
                sample_values = []
            columns.append(ColumnInfo(column_name=col.name, sample_values=sample_values))

        tables.append(TableInfo(table_name=table_name, row_count=row_count, columns=columns))

    return SchemaInfoResponse(tables=tables)
