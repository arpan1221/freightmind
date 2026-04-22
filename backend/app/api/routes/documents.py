import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.agents.extraction.executor import ExtractionExecutor, DOCUMENT_TYPES
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
    document_type: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ExtractionResponse:
    """Extract fields from a freight document.

    Accepts an optional ``document_type`` form field:
    ``commercial_invoice`` | ``bill_of_lading`` | ``packing_list``.
    When omitted the vision model auto-detects the document type.
    """
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported media type '{file.content_type}'. "
                "Accepted types: PDF, PNG, JPEG."
            ),
        )

    if document_type is not None and document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid document_type '{document_type}'. "
                f"Accepted: {', '.join(DOCUMENT_TYPES)}."
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

        # Auto-detect document type when not specified by caller
        resolved_type = document_type
        if resolved_type is None:
            resolved_type = await executor.detect_document_type(image_bytes, mime_type)

        raw = await executor.extract(image_bytes, mime_type, document_type=resolved_type)

        verifier = ExtractionVerifier()
        raw_line_items = raw.get("line_items") or []
        raw_fields = {k: v for k, v in raw.items() if k != "line_items"}
        fields, line_items, low_confidence_fields = verifier.score_confidence(raw_fields, raw_line_items)

        # Aggregate confidence: fraction of header fields with a value present
        present = sum(1 for f in fields.values() if f.value is not None)
        agg_confidence = present / len(fields) if fields else 0.0

        def _fv(name: str):
            """Safely get field value — returns None if field not present."""
            return fields[name].value if name in fields else None

        doc = ExtractedDocument(
            source_filename=file.filename or "",
            confirmed_by_user=0,
            extraction_confidence=agg_confidence,
            document_type=resolved_type,
            # Commercial Invoice fields
            invoice_number=_fv("invoice_number"),
            invoice_date=_fv("invoice_date"),
            payment_terms=_fv("payment_terms"),
            total_freight_cost_usd=_fv("total_freight_cost_usd"),
            total_insurance_usd=_fv("total_insurance_usd"),
            # Shared fields (present across doc types)
            shipper_name=_fv("shipper_name"),
            consignee_name=_fv("consignee_name"),
            origin_country=_fv("origin_country"),
            destination_country=_fv("destination_country"),
            shipment_mode=_fv("shipment_mode"),
            carrier_vendor=_fv("carrier_vendor"),
            total_weight_kg=_fv("total_weight_kg"),
            delivery_date=_fv("delivery_date"),
            hs_code=_fv("hs_code"),
            port_of_loading=_fv("port_of_loading"),
            port_of_discharge=_fv("port_of_discharge"),
            incoterms=_fv("incoterms"),
            description_of_goods=_fv("description_of_goods"),
            # Bill of Lading specific
            bl_number=_fv("bl_number"),
            vessel_name=_fv("vessel_name"),
            container_numbers=_fv("container_numbers"),
            # Packing List specific
            package_count=int(_fv("package_count")) if _fv("package_count") is not None else None,
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
            document_type=resolved_type,
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
            extractions=[_doc_to_summary(doc) for doc in docs]
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
            extractions=[_doc_to_summary(doc) for doc in docs]
        )
    except Exception as exc:
        logger.error("Failed to list extractions: %s", exc)
        raise HTTPException(status_code=500, detail="internal_error")


def _doc_to_summary(doc: ExtractedDocument) -> ExtractedDocumentSummary:
    return ExtractedDocumentSummary(
        extraction_id=doc.id,
        filename=doc.source_filename,
        document_type=getattr(doc, "document_type", "commercial_invoice") or "commercial_invoice",
        extracted_at=doc.extracted_at,
        invoice_number=doc.invoice_number,
        bl_number=getattr(doc, "bl_number", None),
        invoice_date=doc.invoice_date,
        shipment_mode=doc.shipment_mode,
        destination_country=doc.destination_country,
        total_freight_cost_usd=doc.total_freight_cost_usd,
    )
