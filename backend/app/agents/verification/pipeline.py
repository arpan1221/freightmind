"""Verification pipeline: Trigger → Extract → Compare → Flag → Draft.

This is the orchestrator for the SU → CG document verification workflow.
It reuses the Part 1 extraction agent and wires it into the comparison,
flagging, and draft generation layers introduced in Part 2.

Failure handling (all five scenarios from the assignment spec):
1. HS code obscured → extraction returns LOW confidence → comparator marks uncertain
2. LLM returns unrecognised format → score_confidence coerces to LOW → uncertain
3. Customer config missing a rule → comparator marks field as no_rule
4. No attachment / corrupted → _store_failed() called immediately, no partial result
5. LLM API fails → ModelClient retries once; if still failing → _store_failed()
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.agents.extraction.executor import ExtractionExecutor
from app.agents.extraction.planner import ExtractionPlanner, SUPPORTED_TYPES
from app.agents.extraction.verifier import ExtractionVerifier
from app.agents.verification.comparator import DocumentComparator, FieldResult, load_customer_rules
from app.agents.verification.drafter import VerificationDrafter
from app.core.config import settings
from app.models.verification_result import VerificationField, VerificationResult
from app.schemas.verification import FieldVerificationResult, VerificationResultResponse
from app.services.model_client import ModelClient

logger = logging.getLogger(__name__)


async def run_verification(
    file_bytes: bytes,
    content_type: str,
    filename: str,
    customer_id: str,
    db: Session,
) -> VerificationResultResponse:
    """Run the full SU → CG verification pipeline.

    Always returns a VerificationResultResponse — failures are stored as
    status=failed records so CG is always notified. Never crashes silently.
    """
    shipment_id = f"SH-{uuid.uuid4().hex[:8].upper()}"
    received_at = datetime.now(timezone.utc).isoformat()

    # ── Failure scenario 4: no attachment or corrupted file ──────────────────
    if not file_bytes:
        logger.warning("Verification aborted: empty file bytes for shipment %s", shipment_id)
        return _store_failed(
            db, shipment_id, received_at, customer_id,
            "Document has no content — attachment may be missing or corrupted. "
            "CG notified. No partial result stored.",
        )

    # ── Failure scenario 4b: infer content type from extension if browser omits it ──
    if not content_type or content_type not in SUPPORTED_TYPES:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        _EXT_MAP = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        content_type = _EXT_MAP.get(ext, content_type or "")

    if content_type not in SUPPORTED_TYPES:
        logger.warning("Unsupported file type '%s' for shipment %s", content_type, shipment_id)
        return _store_failed(
            db, shipment_id, received_at, customer_id,
            f"Unsupported document type '{content_type}'. "
            "Accepted formats: PDF, PNG, JPEG. Please resubmit.",
        )

    # ── Prepare image (PDF → PNG, pass-through for images) ───────────────────
    try:
        image_bytes, mime_type = ExtractionPlanner.prepare(file_bytes, content_type)
    except Exception as e:
        logger.warning("Document preparation failed for shipment %s: %s", shipment_id, e)
        return _store_failed(
            db, shipment_id, received_at, customer_id,
            f"Document could not be prepared for processing: {e}. "
            "The file may be corrupted or password-protected.",
        )

    # ── Load customer rules (failure scenario 3: config missing) ─────────────
    try:
        rules_config = load_customer_rules(customer_id)
    except FileNotFoundError as e:
        logger.warning("Customer rules missing for '%s': %s", customer_id, e)
        return _store_failed(
            db, shipment_id, received_at, customer_id,
            f"No rule configuration found for customer '{customer_id}'. "
            "Cannot perform verification without customer rules.",
        )
    except Exception as e:
        logger.warning("Failed to load customer rules for '%s': %s", customer_id, e)
        return _store_failed(db, shipment_id, received_at, customer_id, str(e))

    # ── Extract fields using Part 1 vision agent ──────────────────────────────
    vision_client = ModelClient.for_vision(timeout=settings.vision_timeout)
    executor = ExtractionExecutor(vision_client)

    try:
        raw = await executor.extract(image_bytes, mime_type)
    except Exception as e:
        # ── Failure scenario 5: LLM API fails/times out ──────────────────────
        # ModelClient already retried internally. We store failed record.
        logger.error("Extraction failed for shipment %s after retries: %s", shipment_id, e)
        return _store_failed(
            db, shipment_id, received_at, customer_id,
            f"Document extraction failed after retry: {e}. "
            "CG has been notified. Please resubmit when the service recovers.",
        )

    # ── Parse extracted fields with per-field confidence ─────────────────────
    verifier = ExtractionVerifier()
    raw_line_items = raw.get("line_items") or []
    raw_fields = {k: v for k, v in raw.items() if k != "line_items"}

    # score_confidence handles failure scenario 2:
    # LLM returns unrecognised format → confidence coerced to LOW → comparator marks uncertain
    fields, _, _ = verifier.score_confidence(raw_fields, raw_line_items)

    # ── Compare against customer rules ────────────────────────────────────────
    comparator = DocumentComparator(rules_config)
    field_results: list[FieldResult] = comparator.compare(fields)

    # ── Determine overall status ──────────────────────────────────────────────
    overall_status = comparator.determine_overall_status(field_results)

    # ── Generate draft reply ──────────────────────────────────────────────────
    text_client = ModelClient.for_analytics()
    drafter = VerificationDrafter(client=text_client)
    try:
        draft_reply = await drafter.generate(field_results, overall_status, rules_config)
    except Exception as e:
        logger.warning("Draft generation failed, using template: %s", e)
        draft_reply = _fallback_draft(overall_status)

    # ── Persist to same data store as Part 1 ─────────────────────────────────
    result_orm = VerificationResult(
        shipment_id=shipment_id,
        received_at=received_at,
        customer_id=customer_id,
        customer_name=rules_config.get("customer_name"),
        overall_status=overall_status,
        draft_reply=draft_reply,
    )
    db.add(result_orm)
    db.flush()

    for fr in field_results:
        db.add(
            VerificationField(
                verification_id=result_orm.id,
                name=fr.name,
                extracted=fr.extracted,
                expected=fr.expected,
                status=fr.status,
                confidence=fr.confidence,
                rule_description=fr.rule_description,
                source_document=fr.source_document,
            )
        )

    db.commit()
    db.refresh(result_orm)

    return _build_response(result_orm, field_results, rules_config)


async def run_verification_stream(
    file_bytes: bytes,
    content_type: str,
    filename: str,
    customer_id: str,
    db: Session,
) -> AsyncGenerator[dict, None]:
    """Stream the verification pipeline as SSE events.

    Yields stage, field, complete, or error dicts. The caller wraps each
    in 'data: {json}\\n\\n' for the SSE wire format.

    Stages:
      1 — Receive & Validate
      2 — Extract Fields (slow: vision LLM call)
      3 — Compare Rules (fast: each field yielded individually with delay)
      4 — Generate Draft (LLM call)
      complete — full result + DB record ID
      error — structured failure (also stored as failed record in DB)
    """
    shipment_id = f"SH-{uuid.uuid4().hex[:8].upper()}"
    received_at = datetime.now(timezone.utc).isoformat()

    yield {"type": "stage", "step": 1, "message": "Document received — validating format"}
    await asyncio.sleep(0)

    if not file_bytes:
        msg = "Document has no content — attachment may be missing or corrupted."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    if not content_type or content_type not in SUPPORTED_TYPES:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        _EXT_MAP = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        content_type = _EXT_MAP.get(ext, content_type or "")

    if content_type not in SUPPORTED_TYPES:
        msg = f"Unsupported document type '{content_type}'. Accepted: PDF, PNG, JPEG."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    try:
        rules_config = load_customer_rules(customer_id)
    except FileNotFoundError:
        msg = f"No rule configuration found for customer '{customer_id}'."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return
    except Exception as e:
        _store_failed(db, shipment_id, received_at, customer_id, str(e))
        yield {"type": "error", "message": str(e)}
        return

    try:
        image_bytes, mime_type = ExtractionPlanner.prepare(file_bytes, content_type)
    except Exception as e:
        msg = f"Document preparation failed: {e}"
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    yield {"type": "stage", "step": 2, "message": "Extracting fields with vision model…"}
    await asyncio.sleep(0)

    vision_client = ModelClient.for_vision(timeout=settings.vision_timeout)
    executor = ExtractionExecutor(vision_client)
    try:
        raw = await executor.extract(image_bytes, mime_type)
    except Exception as e:
        msg = f"Extraction failed after retry: {e}"
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    verifier = ExtractionVerifier()
    raw_line_items = raw.get("line_items") or []
    raw_fields = {k: v for k, v in raw.items() if k != "line_items"}
    fields, _, _ = verifier.score_confidence(raw_fields, raw_line_items)

    yield {"type": "stage", "step": 3, "message": "Comparing extracted fields against customer rules…"}
    await asyncio.sleep(0)

    comparator = DocumentComparator(rules_config)
    field_results: list[FieldResult] = comparator.compare(fields)

    # Yield each field result individually so the UI table builds up live.
    # The 120 ms pause per field lets the event loop flush each chunk to the client.
    for fr in field_results:
        yield {
            "type": "field",
            "name": fr.name,
            "extracted": fr.extracted,
            "expected": fr.expected,
            "status": fr.status,
            "confidence": fr.confidence,
            "rule_description": fr.rule_description,
            "source_document": fr.source_document,
        }
        await asyncio.sleep(0.12)

    overall_status = comparator.determine_overall_status(field_results)

    yield {"type": "stage", "step": 4, "message": "Generating draft reply…"}
    await asyncio.sleep(0)

    text_client = ModelClient.for_analytics()
    drafter = VerificationDrafter(client=text_client)
    try:
        draft_reply = await drafter.generate(field_results, overall_status, rules_config)
    except Exception as e:
        logger.warning("Draft generation failed, using template: %s", e)
        draft_reply = _fallback_draft(overall_status)

    result_orm = VerificationResult(
        shipment_id=shipment_id,
        received_at=received_at,
        customer_id=customer_id,
        customer_name=rules_config.get("customer_name"),
        overall_status=overall_status,
        draft_reply=draft_reply,
    )
    db.add(result_orm)
    db.flush()

    for fr in field_results:
        db.add(
            VerificationField(
                verification_id=result_orm.id,
                name=fr.name,
                extracted=fr.extracted,
                expected=fr.expected,
                status=fr.status,
                confidence=fr.confidence,
                rule_description=fr.rule_description,
                source_document=fr.source_document,
            )
        )

    db.commit()
    db.refresh(result_orm)

    yield {
        "type": "complete",
        "verification_id": result_orm.id,
        "shipment_id": shipment_id,
        "received_at": received_at,
        "customer_id": customer_id,
        "customer_name": rules_config.get("customer_name"),
        "overall_status": overall_status,
        "draft_reply": draft_reply,
    }


def _store_failed(
    db: Session,
    shipment_id: str,
    received_at: str,
    customer_id: str,
    error_message: str,
) -> VerificationResultResponse:
    """Store a failed verification record and return a structured response.

    No partial results are stored — the record only captures the failure.
    CG is always notified via the error field in the response.
    """
    # Clear any dirty pending state left by a partial pipeline run.
    # Without this, db.add() below may fail on a session with unflushed errors.
    try:
        db.rollback()
    except Exception:
        pass

    customer_name = None
    try:
        cfg = load_customer_rules(customer_id)
        customer_name = cfg.get("customer_name")
    except Exception:
        pass

    result_orm = VerificationResult(
        shipment_id=shipment_id,
        received_at=received_at,
        customer_id=customer_id,
        customer_name=customer_name,
        overall_status="failed",
        draft_reply=(
            "Dear Shipping Unit,\n\n"
            "We were unable to process your submitted document. "
            f"Reason: {error_message}\n\n"
            "Please resubmit or contact support.\n\n"
            "Regards,\nCargo Control Group"
        ),
        error_message=error_message,
    )
    try:
        db.add(result_orm)
        db.commit()
        db.refresh(result_orm)
        verification_id = result_orm.id
    except Exception as e:
        db.rollback()
        logger.error("Failed to store failed verification record: %s", e)
        verification_id = -1

    return VerificationResultResponse(
        verification_id=verification_id,
        shipment_id=shipment_id,
        received_at=received_at,
        customer_id=customer_id,
        customer_name=customer_name,
        overall_status="failed",
        fields=[],
        draft_reply=result_orm.draft_reply,
        error=error_message,
    )


def _build_response(
    result_orm: VerificationResult,
    field_results: list[FieldResult],
    rules_config: dict,
) -> VerificationResultResponse:
    return VerificationResultResponse(
        verification_id=result_orm.id,
        shipment_id=result_orm.shipment_id,
        received_at=result_orm.received_at,
        customer_id=result_orm.customer_id,
        customer_name=rules_config.get("customer_name"),
        overall_status=result_orm.overall_status,
        fields=[
            FieldVerificationResult(
                name=fr.name,
                extracted=fr.extracted,
                expected=fr.expected,
                status=fr.status,
                confidence=fr.confidence,
                rule_description=fr.rule_description,
                source_document=fr.source_document,
            )
            for fr in field_results
        ],
        draft_reply=result_orm.draft_reply or "",
    )


def _fallback_draft(overall_status: str) -> str:
    if overall_status == "approved":
        return (
            "Dear Shipping Unit,\n\n"
            "All submitted documents have been reviewed and verified. "
            "The shipment is cleared for processing.\n\n"
            "Regards,\nCargo Control Group"
        )
    return (
        "Dear Shipping Unit,\n\n"
        "We have reviewed your submitted documents and found discrepancies "
        "that require correction. Please review the verification results and "
        "resubmit corrected documents.\n\n"
        "Regards,\nCargo Control Group"
    )


# ── Batch verification pipeline ───────────────────────────────────────────────

_DOC_TYPE_LABEL = {
    "commercial_invoice": "Commercial Invoice",
    "bill_of_lading": "Bill of Lading",
    "packing_list": "Packing List",
}


async def run_batch_verification_stream(
    files: list[tuple[bytes, str, str]],  # (file_bytes, content_type, filename)
    customer_id: str,
    db,
):
    shipment_id = f"SH-{uuid.uuid4().hex[:8].upper()}"
    received_at = datetime.now(timezone.utc).isoformat()

    yield {"type": "stage", "step": 1, "message": f"Received {len(files)} document(s) — validating"}
    await asyncio.sleep(0)

    if not files:
        msg = "No documents received."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    # Load customer rules first
    try:
        rules_config = load_customer_rules(customer_id)
    except FileNotFoundError:
        msg = f"No rule configuration found for customer '{customer_id}'."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return
    except Exception as e:
        _store_failed(db, shipment_id, received_at, customer_id, str(e))
        yield {"type": "error", "message": str(e)}
        return

    vision_client = ModelClient.for_vision(timeout=settings.vision_timeout)
    executor = ExtractionExecutor(vision_client)
    verifier = ExtractionVerifier()

    # ── Step 2: Extract each document ────────────────────────────────────────
    extracted_per_doc: list[tuple[str, str, dict]] = []  # (doc_type, label, fields_dict)

    for idx, (file_bytes, content_type, filename) in enumerate(files):
        doc_label = f"Document {idx + 1} ({filename})"
        yield {
            "type": "stage",
            "step": 2,
            "message": f"Extracting {doc_label}…",
        }
        await asyncio.sleep(0)

        if not file_bytes:
            yield {"type": "warning", "message": f"{doc_label}: empty — skipped"}
            continue

        # Infer content type from extension if missing
        ct = content_type
        if not ct or ct not in SUPPORTED_TYPES:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            _EXT_MAP = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
            ct = _EXT_MAP.get(ext, ct or "")

        if ct not in SUPPORTED_TYPES:
            yield {"type": "warning", "message": f"{doc_label}: unsupported type '{ct}' — skipped"}
            continue

        try:
            image_bytes, mime_type = ExtractionPlanner.prepare(file_bytes, ct)
        except Exception as e:
            yield {"type": "warning", "message": f"{doc_label}: preparation failed ({e}) — skipped"}
            continue

        try:
            # Auto-detect document type
            doc_type = await executor.detect_document_type(image_bytes, mime_type)
            yield {
                "type": "doc_detected",
                "filename": filename,
                "document_type": doc_type,
                "label": _DOC_TYPE_LABEL.get(doc_type, doc_type),
            }
            raw = await executor.extract(image_bytes, mime_type, document_type=doc_type)
        except Exception as e:
            logger.error("Extraction failed for %s: %s", filename, e)
            yield {"type": "warning", "message": f"{doc_label}: extraction failed ({e}) — skipped"}
            continue

        raw_line_items = raw.get("line_items") or []
        raw_fields = {k: v for k, v in raw.items() if k != "line_items"}
        fields, _, _ = verifier.score_confidence(raw_fields, raw_line_items)
        doc_label_pretty = _DOC_TYPE_LABEL.get(doc_type, doc_type)
        extracted_per_doc.append((doc_type, doc_label_pretty, fields))

        # Yield field preview events immediately so the UI populates during extraction,
        # not only after all documents are processed. Comparison will re-yield these
        # with their final status; the frontend deduplicates by field name (last-write wins).
        _CONF_MAP = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3, "NOT_FOUND": 0.0}
        for fname, efield in fields.items():
            conf_str = efield.confidence if isinstance(efield.confidence, str) else "LOW"
            yield {
                "type": "field",
                "name": fname,
                "extracted": str(efield.value) if efield.value is not None else None,
                "expected": None,
                "status": "no_rule",
                "confidence": _CONF_MAP.get(conf_str.upper(), 0.0),
                "rule_description": None,
                "source_document": doc_label_pretty,
            }
            await asyncio.sleep(0.1)

    if not extracted_per_doc:
        msg = "All documents failed extraction — cannot verify."
        _store_failed(db, shipment_id, received_at, customer_id, msg)
        yield {"type": "error", "message": msg}
        return

    # ── Step 3: Merge fields (last-write wins for primary, track sources) ────
    yield {"type": "stage", "step": 3, "message": "Merging fields and checking cross-document consistency…"}
    await asyncio.sleep(0)

    # merged_fields: field_name → ExtractedField (highest confidence wins)
    # source_map: field_name → label of doc that provided the winning value
    # all_values: field_name → list of (label, value, confidence_str) for cross-check
    merged_fields: dict = {}
    source_map: dict[str, str] = {}
    all_values: dict[str, list[tuple[str, str | None, str]]] = {}

    for doc_type, label, fields in extracted_per_doc:
        for fname, efield in fields.items():
            if fname not in all_values:
                all_values[fname] = []
            all_values[fname].append((label, efield.value, efield.confidence))

            # Keep the highest-confidence extraction for comparison
            if fname not in merged_fields:
                merged_fields[fname] = efield
                source_map[fname] = label
            else:
                from app.agents.verification.comparator import _CONFIDENCE_FLOAT
                existing_conf = _CONFIDENCE_FLOAT.get(
                    merged_fields[fname].confidence.upper()
                    if isinstance(merged_fields[fname].confidence, str) else "LOW", 0.0
                )
                new_conf = _CONFIDENCE_FLOAT.get(
                    efield.confidence.upper()
                    if isinstance(efield.confidence, str) else "LOW", 0.0
                )
                if new_conf > existing_conf:
                    merged_fields[fname] = efield
                    source_map[fname] = label

    # Cross-document consistency check: flag shared fields with differing values
    cross_check_issues: list[dict] = []
    _SHARED_FIELDS = {
        "port_of_loading", "port_of_discharge", "shipment_mode",
        "origin_country", "destination_country", "incoterms", "hs_code",
    }
    for fname in _SHARED_FIELDS:
        entries = all_values.get(fname, [])
        if len(entries) < 2:
            continue
        values = {(v or "").strip().lower() for _, v, _ in entries if v}
        if len(values) > 1:
            sources = "; ".join(f"{lbl}={val!r}" for lbl, val, _ in entries if val)
            issue = {
                "type": "cross_check",
                "field": fname,
                "conflict": sources,
                "message": f"Cross-document inconsistency on '{fname}': {sources}",
            }
            cross_check_issues.append(issue)
            yield issue
            await asyncio.sleep(0)

    # ── Step 4: Compare against customer rules ────────────────────────────────
    yield {"type": "stage", "step": 4, "message": "Comparing extracted fields against customer rules…"}
    await asyncio.sleep(0)

    comparator = DocumentComparator(rules_config)
    field_results: list[FieldResult] = comparator.compare(merged_fields)

    # Attach source_document to each FieldResult
    for fr in field_results:
        fr.source_document = source_map.get(fr.name)

    for fr in field_results:
        yield {
            "type": "field",
            "name": fr.name,
            "extracted": fr.extracted,
            "expected": fr.expected,
            "status": fr.status,
            "confidence": fr.confidence,
            "rule_description": fr.rule_description,
            "source_document": fr.source_document,
        }
        await asyncio.sleep(0.12)

    # Escalate to amendment_required if any cross-doc conflicts exist (they can mask rule matches)
    overall_status = comparator.determine_overall_status(field_results)
    if cross_check_issues and overall_status == "approved":
        overall_status = "amendment_required"

    # ── Step 5: Generate draft ─────────────────────────────────────────────────
    yield {"type": "stage", "step": 5, "message": "Generating draft reply…"}
    await asyncio.sleep(0)

    # Augment drafter prompt with cross-check issues if present
    text_client = ModelClient.for_analytics()
    drafter = VerificationDrafter(client=text_client)

    # Inject cross-doc conflicts as synthetic mismatch entries for the drafter
    augmented_results = list(field_results)
    for issue in cross_check_issues:
        augmented_results.append(FieldResult(
            name=issue["field"],
            extracted=issue["conflict"],
            expected="Consistent value across all documents",
            status="mismatch",
            confidence=0.0,
            rule_description="Cross-document inconsistency detected",
            source_document="Multiple documents",
        ))

    try:
        draft_reply = await drafter.generate(augmented_results, overall_status, rules_config)
    except Exception as e:
        logger.warning("Draft generation failed, using template: %s", e)
        draft_reply = _fallback_draft(overall_status)

    # ── Persist ────────────────────────────────────────────────────────────────
    doc_summary = ", ".join(label for _, label, _ in extracted_per_doc)
    result_orm = VerificationResult(
        shipment_id=shipment_id,
        received_at=received_at,
        customer_id=customer_id,
        customer_name=rules_config.get("customer_name"),
        overall_status=overall_status,
        draft_reply=draft_reply,
    )
    db.add(result_orm)
    db.flush()

    for fr in field_results:
        db.add(
            VerificationField(
                verification_id=result_orm.id,
                name=fr.name,
                extracted=fr.extracted,
                expected=fr.expected,
                status=fr.status,
                confidence=fr.confidence,
                rule_description=fr.rule_description,
                source_document=fr.source_document,
            )
        )

    db.commit()
    db.refresh(result_orm)

    yield {
        "type": "complete",
        "verification_id": result_orm.id,
        "shipment_id": shipment_id,
        "received_at": received_at,
        "customer_id": customer_id,
        "customer_name": rules_config.get("customer_name"),
        "overall_status": overall_status,
        "draft_reply": draft_reply,
        "documents_processed": [
            {"doc_type": dt, "label": lbl} for dt, lbl, _ in extracted_per_doc
        ],
        "cross_check_issues": len(cross_check_issues),
    }
