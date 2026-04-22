"""Verification routes — SU → CG document verification workflow (Part 2).

POST /verify/submit   — trigger: file arrives, agent runs full pipeline
GET  /verify/result/{id} — retrieve a stored verification result
GET  /verify/queue       — list recent verifications (newest first)
"""

import json as _json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.verification.pipeline import run_verification, run_verification_stream, run_batch_verification_stream
from app.core.config import settings
from app.core.database import get_db
from app.models.verification_result import VerificationField, VerificationResult
from app.schemas.verification import (
    FieldVerificationResult,
    VerificationQueueResponse,
    VerificationResultResponse,
    VerificationSummary,
)

router = APIRouter(prefix="/verify")
logger = logging.getLogger(__name__)


@router.post("/submit", response_model=VerificationResultResponse)
async def submit_document(
    file: UploadFile = File(...),
    customer_id: str = Form(default="DEMO_CUSTOMER_001"),
    db: Session = Depends(get_db),
) -> VerificationResultResponse:
    """Trigger the verification pipeline.

    Simulates an SU email arriving with an attached trade document.
    A folder watcher or email integration would call this same endpoint.
    See README for trigger mechanism documentation.

    Returns the full verification result immediately (synchronous pipeline).
    Failed documents are persisted and returned — no crashes, no silent approvals.
    """
    try:
        file_bytes = await file.read()
    except Exception:
        logger.exception("Failed to read upload for verification")
        raise HTTPException(status_code=400, detail="Could not read the uploaded file.")

    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_upload_bytes} bytes.",
        )

    try:
        result = await run_verification(
            file_bytes=file_bytes,
            content_type=file.content_type or "",
            filename=file.filename or "",
            customer_id=customer_id,
            db=db,
        )
        return result
    except Exception:
        logger.exception("Verification pipeline raised unhandled error")
        raise HTTPException(
            status_code=500,
            detail="Verification failed unexpectedly. CG has been notified.",
        )


@router.post("/submit/stream")
async def submit_document_stream(
    file: UploadFile = File(...),
    customer_id: str = Form(default="DEMO_CUSTOMER_001"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streaming verification — yields SSE events as each pipeline stage completes.

    The UI connects with fetch() and reads the response body as a stream.
    Each event is: data: {json}\\n\\n

    Event types: stage | field | complete | error
    """
    try:
        file_bytes = await file.read()
    except Exception:
        logger.exception("Failed to read upload for streaming verification")
        raise HTTPException(status_code=400, detail="Could not read the uploaded file.")

    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.max_upload_bytes} bytes.",
        )

    async def event_generator():
        try:
            async for event in run_verification_stream(
                file_bytes=file_bytes,
                content_type=file.content_type or "",
                filename=file.filename or "",
                customer_id=customer_id,
                db=db,
            ):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("Unhandled error in streaming verification")
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/result/{verification_id}", response_model=VerificationResultResponse)
def get_result(
    verification_id: int,
    db: Session = Depends(get_db),
) -> VerificationResultResponse:
    """Retrieve a stored verification result by ID."""
    result = db.get(VerificationResult, verification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Verification result not found.")

    return VerificationResultResponse(
        verification_id=result.id,
        shipment_id=result.shipment_id,
        received_at=result.received_at,
        customer_id=result.customer_id,
        customer_name=result.customer_name,
        overall_status=result.overall_status,
        fields=[
            FieldVerificationResult(
                name=f.name,
                extracted=f.extracted,
                expected=f.expected,
                status=f.status,
                confidence=f.confidence,
                rule_description=f.rule_description,
                source_document=getattr(f, "source_document", None),
            )
            for f in result.fields
        ],
        draft_reply=result.draft_reply or "",
        error=result.error_message,
    )


@router.get("/queue", response_model=VerificationQueueResponse)
def get_queue(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> VerificationQueueResponse:
    """List recent verification results, newest first."""
    try:
        results = (
            db.query(VerificationResult)
            .order_by(VerificationResult.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.error("Failed to list verification queue: %s", exc)
        raise HTTPException(status_code=500, detail="internal_error")

    summaries: list[VerificationSummary] = []
    for r in results:
        mismatch_count = (
            db.query(VerificationField)
            .filter(
                VerificationField.verification_id == r.id,
                VerificationField.status.in_(["mismatch", "uncertain"]),
            )
            .count()
        )
        field_count = (
            db.query(VerificationField)
            .filter(VerificationField.verification_id == r.id)
            .count()
        )
        summaries.append(
            VerificationSummary(
                verification_id=r.id,
                shipment_id=r.shipment_id,
                received_at=r.received_at,
                customer_id=r.customer_id,
                customer_name=r.customer_name,
                overall_status=r.overall_status,
                created_at=r.created_at,
                field_count=field_count,
                mismatch_count=mismatch_count,
            )
        )

    return VerificationQueueResponse(verifications=summaries)


@router.post("/submit-batch/stream")
async def submit_batch_stream(
    files: list[UploadFile] = File(...),
    customer_id: str = Form(default="DEMO_CUSTOMER_001"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Batch streaming verification — accepts up to 3 trade documents.

    Auto-detects each document type (CI / B/L / PL), extracts fields,
    cross-checks shared fields, then runs a single comparator + drafter pass.

    Event types: stage | doc_detected | cross_check | field | complete | error | warning
    """
    loaded: list[tuple[bytes, str, str]] = []
    for f in files[:3]:  # cap at 3 documents
        try:
            data = await f.read()
        except Exception:
            logger.exception("Failed to read batch upload '%s'", f.filename)
            continue
        if len(data) > settings.max_upload_bytes:
            logger.warning("Batch file '%s' exceeds size limit — skipped", f.filename)
            continue
        loaded.append((data, f.content_type or "", f.filename or ""))

    async def event_generator():
        try:
            async for event in run_batch_verification_stream(
                files=loaded,
                customer_id=customer_id,
                db=db,
            ):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("Unhandled error in batch streaming verification")
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
