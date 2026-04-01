import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.agents.extraction.executor import ExtractionExecutor
from app.agents.extraction.planner import ExtractionPlanner, SUPPORTED_TYPES
from app.agents.extraction.verifier import ExtractionVerifier
from app.core.config import settings
from app.core.database import get_db
from app.models.extracted_document import ExtractedDocument
from app.models.extracted_line_item import ExtractedLineItem
from app.schemas.documents import (
    ConfirmRequest,
    ConfirmResponse,
    ExtractionListResponse,
    ExtractionResponse,
    ExtractedDocumentSummary,
)
from app.services.model_client import ModelClient

router = APIRouter(prefix="/documents")
logger = logging.getLogger(__name__)


@router.post("/extract", response_model=ExtractionResponse)
async def post_extract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ExtractionResponse:
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported media type '{file.content_type}'. "
                "Accepted types: PDF, PNG, JPEG."
            ),
        )

    try:
        file_bytes = await file.read()
    except Exception:
        logger.exception("Failed to read upload for '%s'", file.filename)
        raise HTTPException(
            status_code=400,
            detail="Could not read the uploaded file.",
        ) from None

    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds maximum size of {settings.max_upload_bytes} bytes."
            ),
        )

    try:
        image_bytes, mime_type = ExtractionPlanner.prepare(file_bytes, file.content_type)

        client = ModelClient.for_vision(timeout=settings.vision_timeout)
        executor = ExtractionExecutor(client)
        raw = await executor.extract(image_bytes, mime_type)

        verifier = ExtractionVerifier()
        raw_line_items = raw.get("line_items") or []
        raw_fields = {k: v for k, v in raw.items() if k != "line_items"}
        fields, line_items, low_confidence_fields = verifier.score_confidence(raw_fields, raw_line_items)

        # Aggregate confidence: fraction of header fields with a value present
        present = sum(1 for f in fields.values() if f.value is not None)
        agg_confidence = present / len(fields) if fields else 0.0

        doc = ExtractedDocument(
            source_filename=file.filename or "",
            confirmed_by_user=0,
            extraction_confidence=agg_confidence,
            invoice_number=fields["invoice_number"].value,
            invoice_date=fields["invoice_date"].value,
            shipper_name=fields["shipper_name"].value,
            consignee_name=fields["consignee_name"].value,
            origin_country=fields["origin_country"].value,
            destination_country=fields["destination_country"].value,
            shipment_mode=fields["shipment_mode"].value,
            carrier_vendor=fields["carrier_vendor"].value,
            total_weight_kg=fields["total_weight_kg"].value,
            total_freight_cost_usd=fields["total_freight_cost_usd"].value,
            total_insurance_usd=fields["total_insurance_usd"].value,
            payment_terms=fields["payment_terms"].value,
            delivery_date=fields["delivery_date"].value,
        )
        db.add(doc)
        db.flush()

        for item in line_items:
            db.add(
                ExtractedLineItem(
                    document_id=doc.id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price,
                    confidence=0.9,
                )
            )

        db.commit()
        db.refresh(doc)

        return ExtractionResponse(
            extraction_id=doc.id,
            filename=file.filename or "",
            fields=fields,
            line_items=line_items,
            low_confidence_fields=low_confidence_fields,
        )

    except Exception as e:
        db.rollback()
        logger.exception("Extraction failed for file '%s'", file.filename)
        raise HTTPException(
            status_code=500,
            detail="Extraction failed. Try a different file or a clearer image.",
        ) from e


@router.post("/confirm", response_model=ConfirmResponse)
async def post_confirm(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
) -> ConfirmResponse:
    doc = db.get(ExtractedDocument, body.extraction_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="extraction_id not found")

    if doc.confirmed_by_user == 1:
        raise HTTPException(status_code=409, detail="already_confirmed")

    verifier = ExtractionVerifier()
    corrections = body.corrections or {}
    valid, error_msg = verifier.validate_corrections(corrections, doc)
    if not valid:
        raise HTTPException(status_code=422, detail=error_msg)

    try:
        for key, value in corrections.items():
            setattr(doc, key, value)
        doc.confirmed_by_user = 1
        db.commit()
        db.refresh(doc)
    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed to commit confirmation for extraction_id=%s: %s",
            body.extraction_id,
            exc,
        )
        raise HTTPException(status_code=500, detail="internal_error")

    return ConfirmResponse(stored=True, document_id=doc.id)


@router.delete("/extractions/{extraction_id}", status_code=204)
async def delete_extraction(
    extraction_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Discard an unconfirmed extraction. No-op if already confirmed or not found."""
    doc = db.get(ExtractedDocument, extraction_id)
    if doc is None or doc.confirmed_by_user == 1:
        return
    try:
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/pending", response_model=ExtractionListResponse)
async def get_pending(
    db: Session = Depends(get_db),
) -> ExtractionListResponse:
    """Return unconfirmed extracted documents, newest first."""
    try:
        docs = (
            db.query(ExtractedDocument)
            .filter(ExtractedDocument.confirmed_by_user == 0)
            .order_by(ExtractedDocument.id.desc())
            .all()
        )
        return ExtractionListResponse(
            extractions=[
                ExtractedDocumentSummary(
                    extraction_id=doc.id,
                    filename=doc.source_filename,
                    extracted_at=doc.extracted_at,
                    invoice_number=doc.invoice_number,
                    invoice_date=doc.invoice_date,
                    shipment_mode=doc.shipment_mode,
                    destination_country=doc.destination_country,
                    total_freight_cost_usd=doc.total_freight_cost_usd,
                )
                for doc in docs
            ]
        )
    except Exception as exc:
        logger.error("Failed to list pending extractions: %s", exc)
        raise HTTPException(status_code=500, detail="internal_error")


@router.get("/extractions", response_model=ExtractionListResponse)
async def get_extractions(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Rows to skip (newest-first pagination)"),
) -> ExtractionListResponse:
    """Return confirmed extracted documents, newest first, with optional pagination."""
    try:
        docs = (
            db.query(ExtractedDocument)
            .filter(ExtractedDocument.confirmed_by_user == 1)
            .order_by(ExtractedDocument.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ExtractionListResponse(
            extractions=[
                ExtractedDocumentSummary(
                    extraction_id=doc.id,
                    filename=doc.source_filename,
                    extracted_at=doc.extracted_at,
                    invoice_number=doc.invoice_number,
                    invoice_date=doc.invoice_date,
                    shipment_mode=doc.shipment_mode,
                    destination_country=doc.destination_country,
                    total_freight_cost_usd=doc.total_freight_cost_usd,
                )
                for doc in docs
            ]
        )
    except Exception as exc:
        logger.error("Failed to list extractions: %s", exc)
        raise HTTPException(status_code=500, detail="internal_error")
