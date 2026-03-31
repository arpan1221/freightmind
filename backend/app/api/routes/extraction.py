import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.extracted_document import ExtractedDocument
from app.schemas.common import ErrorResponse
from app.schemas.extraction import DeleteExtractionResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete("/extract/{extraction_id}", response_model=DeleteExtractionResponse)
def cancel_extraction(
    extraction_id: int,
    db: Session = Depends(get_db),
) -> DeleteExtractionResponse | JSONResponse:
    doc = db.get(ExtractedDocument, extraction_id)
    if doc is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error_type="not_found",
                message=f"Extraction {extraction_id} not found.",
            ).model_dump(),
        )
    try:
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to delete extraction %d", extraction_id)
        raise
    logger.info("Extraction %d cancelled and deleted.", extraction_id)
    return DeleteExtractionResponse(
        extraction_id=extraction_id,
        deleted=True,
        message="Extraction cancelled and deleted.",
    )
