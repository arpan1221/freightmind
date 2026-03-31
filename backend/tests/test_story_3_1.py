"""
Tests for Story 3.1 — File upload endpoint POST /api/documents/extract

Verifies:
- AC1: PDF → PyMuPDF image → vision model → structured response + DB row (confirmed_by_user=0)
- AC2: PNG/JPEG → vision model directly (no conversion)
- AC3: Unsupported file type → structured error response, no crash
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.agents.extraction.planner import ExtractionPlanner
from app.agents.extraction.executor import ExtractionExecutor
from app.agents.extraction.verifier import ExtractionVerifier
from app.schemas.documents import ExtractedField, ExtractedLineItemOut, ExtractionResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_EXTRACTION_JSON = json.dumps({
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-03-15",
    "shipper_name": "Pharma Co Ltd",
    "consignee_name": "Health Ministry",
    "origin_country": "India",
    "destination_country": "Nigeria",
    "shipment_mode": "Air",
    "carrier_vendor": "DHL",
    "total_weight_kg": 250.5,
    "total_freight_cost_usd": 4500.00,
    "total_insurance_usd": 120.00,
    "payment_terms": "Net 30",
    "delivery_date": "2024-04-01",
    "line_items": [
        {"description": "ARV Tablets", "quantity": 1000, "unit_price": 0.50, "total_price": 500.00}
    ],
})

PARTIAL_EXTRACTION_JSON = json.dumps({
    "invoice_number": "INV-2024-002",
    "invoice_date": None,
    "shipper_name": None,
    "consignee_name": "Health Ministry",
    "origin_country": "India",
    "destination_country": None,
    "shipment_mode": None,
    "carrier_vendor": None,
    "total_weight_kg": None,
    "total_freight_cost_usd": None,
    "total_insurance_usd": None,
    "payment_terms": None,
    "delivery_date": None,
    "line_items": [],
})

# Minimal valid PDF bytes (not a real PDF, but enough for mocked tests)
FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content"
FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png"


# ---------------------------------------------------------------------------
# Task 5: ExtractionExecutor
# ---------------------------------------------------------------------------

class TestExtractionExecutor:
    def _make_client(self, raw: str) -> MagicMock:
        client = MagicMock()
        client.call = AsyncMock(return_value=raw)
        return client

    @pytest.mark.asyncio
    async def test_returns_parsed_dict_on_valid_json(self):
        client = self._make_client(VALID_EXTRACTION_JSON)
        executor = ExtractionExecutor(client)
        result = await executor.extract(FAKE_PNG_BYTES, "image/png")
        assert result["invoice_number"] == "INV-2024-001"
        assert result["destination_country"] == "Nigeria"
        assert len(result["line_items"]) == 1

    @pytest.mark.asyncio
    async def test_strips_code_fences_before_parsing(self):
        fenced = f"```json\n{VALID_EXTRACTION_JSON}\n```"
        client = self._make_client(fenced)
        executor = ExtractionExecutor(client)
        result = await executor.extract(FAKE_PNG_BYTES, "image/png")
        assert result["invoice_number"] == "INV-2024-001"

    @pytest.mark.asyncio
    async def test_raises_value_error_on_non_json_response(self):
        client = self._make_client("I cannot read this invoice.")
        executor = ExtractionExecutor(client)
        with pytest.raises(ValueError, match="non-JSON"):
            await executor.extract(FAKE_PNG_BYTES, "image/png")

    @pytest.mark.asyncio
    async def test_calls_vision_model_with_image_url_content(self):
        client = self._make_client(VALID_EXTRACTION_JSON)
        executor = ExtractionExecutor(client)
        await executor.extract(FAKE_PNG_BYTES, "image/png")
        call_args = client.call.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[1]
        user_msg = messages[-1]
        assert isinstance(user_msg["content"], list)
        image_part = next(p for p in user_msg["content"] if p["type"] == "image_url")
        assert "base64" in image_part["image_url"]["url"]


# ---------------------------------------------------------------------------
# Task 6: ExtractionPlanner
# ---------------------------------------------------------------------------

class TestExtractionPlanner:
    def test_png_passthrough(self):
        img, mime = ExtractionPlanner.prepare(FAKE_PNG_BYTES, "image/png")
        assert img == FAKE_PNG_BYTES
        assert mime == "image/png"

    def test_jpeg_passthrough(self):
        img, mime = ExtractionPlanner.prepare(b"\xff\xd8\xff fake jpeg", "image/jpeg")
        assert mime == "image/jpeg"

    def test_unsupported_type_raises_value_error(self):
        with pytest.raises(ValueError, match="unsupported_file_type"):
            ExtractionPlanner.prepare(b"data", "application/vnd.ms-excel")

    def test_pdf_returns_png_bytes(self):
        """Test PDF conversion using a real minimal PDF via PyMuPDF."""
        import fitz
        # Create a minimal valid PDF in memory
        doc = fitz.open()
        page = doc.new_page()
        doc_bytes = doc.tobytes()
        doc.close()

        img_bytes, mime = ExtractionPlanner.prepare(doc_bytes, "application/pdf")
        assert mime == "image/png"
        assert img_bytes[:4] == b"\x89PNG"  # PNG magic bytes


# ---------------------------------------------------------------------------
# Task 7: ExtractionVerifier
# ---------------------------------------------------------------------------

class TestExtractionVerifier:
    def test_all_fields_present_gives_high_confidence(self):
        raw = json.loads(VALID_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        fields = result["fields"]
        assert fields["invoice_number"].confidence == "HIGH"
        assert fields["invoice_number"].value == "INV-2024-001"
        assert result["low_confidence_fields"] == []

    def test_null_fields_get_not_found_confidence(self):
        raw = json.loads(PARTIAL_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        fields = result["fields"]
        assert fields["invoice_date"].confidence == "NOT_FOUND"
        assert fields["invoice_date"].value is None
        assert "invoice_date" in result["low_confidence_fields"]

    def test_low_confidence_fields_populated_for_nulls(self):
        raw = json.loads(PARTIAL_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        low = result["low_confidence_fields"]
        assert "invoice_date" in low
        assert "destination_country" in low
        assert "invoice_number" not in low  # has a value

    def test_numeric_fields_coerced_to_float(self):
        raw = json.loads(VALID_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        assert isinstance(result["fields"]["total_weight_kg"].value, float)
        assert result["fields"]["total_weight_kg"].value == 250.5

    def test_line_items_parsed(self):
        raw = json.loads(VALID_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        items = result["line_items"]
        assert len(items) == 1
        assert items[0].description == "ARV Tablets"
        assert items[0].quantity == 1000
        assert items[0].confidence == "HIGH"

    def test_empty_line_items(self):
        raw = json.loads(PARTIAL_EXTRACTION_JSON)
        verifier = ExtractionVerifier()
        result = verifier.verify(raw)
        assert result["line_items"] == []


# ---------------------------------------------------------------------------
# Task 8: Route integration tests
# ---------------------------------------------------------------------------

class TestPostExtract:
    def _mock_pipeline(self, raw_json: str = VALID_EXTRACTION_JSON):
        """Patch ExtractionPlanner, ExtractionExecutor, ExtractionVerifier at route level."""
        planner_patch = patch("app.api.routes.documents.ExtractionPlanner")
        executor_patch = patch("app.api.routes.documents.ExtractionExecutor")
        verifier_patch = patch("app.api.routes.documents.ExtractionVerifier")

        mock_planner_cls = planner_patch.start()
        mock_executor_cls = executor_patch.start()
        mock_verifier_cls = verifier_patch.start()

        mock_planner_cls.prepare = MagicMock(return_value=(FAKE_PNG_BYTES, "image/png"))

        # Build new-format raw (nested {"value":..., "confidence":...}) from flat test JSON
        flat = json.loads(raw_json)
        new_format_raw = {
            k: {"value": v, "confidence": "NOT_FOUND" if v is None else "HIGH"}
            for k, v in flat.items()
            if k != "line_items"
        }
        new_format_raw["line_items"] = [
            {**item, "confidence": "HIGH"} for item in (flat.get("line_items") or [])
        ]

        # Compute expected score_confidence output using the real verifier
        real_verifier = ExtractionVerifier()
        raw_fields = {k: v for k, v in new_format_raw.items() if k != "line_items"}
        raw_line_items = new_format_raw.get("line_items") or []
        fields, line_items, low_confidence_fields = real_verifier.score_confidence(raw_fields, raw_line_items)

        mock_executor_instance = mock_executor_cls.return_value
        mock_executor_instance.extract = AsyncMock(return_value=new_format_raw)

        mock_verifier_instance = mock_verifier_cls.return_value
        mock_verifier_instance.score_confidence = MagicMock(return_value=(fields, line_items, low_confidence_fields))

        return planner_patch, executor_patch, verifier_patch

    def test_returns_200_with_extraction_id(self):
        from app.main import app
        from fastapi.testclient import TestClient
        http = TestClient(app)

        pp, ep, vp = self._mock_pipeline()
        try:
            resp = http.post(
                "/api/documents/extract",
                files={"file": ("invoice.pdf", FAKE_PDF_BYTES, "application/pdf")},
            )
        finally:
            pp.stop(); ep.stop(); vp.stop()

        assert resp.status_code == 200
        body = resp.json()
        assert body["extraction_id"] > 0
        assert body["filename"] == "invoice.pdf"
        assert "invoice_number" in body["fields"]
        assert body["error"] is None

    def test_db_row_inserted_with_confirmed_by_user_zero(self):
        from app.main import app
        from fastapi.testclient import TestClient
        from app.core.database import SessionLocal
        from app.models.extracted_document import ExtractedDocument
        http = TestClient(app)

        pp, ep, vp = self._mock_pipeline()
        try:
            resp = http.post(
                "/api/documents/extract",
                files={"file": ("test.png", FAKE_PNG_BYTES, "image/png")},
            )
        finally:
            pp.stop(); ep.stop(); vp.stop()

        assert resp.status_code == 200
        extraction_id = resp.json()["extraction_id"]
        assert extraction_id > 0

        db = SessionLocal()
        try:
            doc = db.get(ExtractedDocument, extraction_id)
            assert doc is not None
            assert doc.confirmed_by_user == 0
            assert doc.source_filename == "test.png"
        finally:
            db.close()

    def test_unsupported_file_type_returns_error(self):
        from app.main import app
        from fastapi.testclient import TestClient
        http = TestClient(app)

        resp = http.post(
            "/api/documents/extract",
            files={"file": ("data.xlsx", b"fake xlsx", "application/vnd.ms-excel")},
        )

        assert resp.status_code == 415
        body = resp.json()
        assert body["error"] is True
        assert body["error_type"] == "http_error"
        assert "unsupported" in body["message"].lower() or "media type" in body["message"].lower()

    def test_jpeg_image_accepted(self):
        from app.main import app
        from fastapi.testclient import TestClient
        http = TestClient(app)

        pp, ep, vp = self._mock_pipeline()
        try:
            resp = http.post(
                "/api/documents/extract",
                files={"file": ("photo.jpg", b"\xff\xd8\xff fake", "image/jpeg")},
            )
        finally:
            pp.stop(); ep.stop(); vp.stop()

        assert resp.status_code == 200
        assert resp.json()["error"] is None

    def test_extraction_failure_returns_error_response(self):
        from app.main import app
        from fastapi.testclient import TestClient
        http = TestClient(app)

        with patch("app.api.routes.documents.ExtractionPlanner") as mock_planner:
            mock_planner.prepare = MagicMock(return_value=(FAKE_PNG_BYTES, "image/png"))
            with patch("app.api.routes.documents.ExtractionExecutor") as mock_exec:
                mock_exec.return_value.extract = AsyncMock(
                    side_effect=ValueError("Vision model returned non-JSON response")
                )
                resp = http.post(
                    "/api/documents/extract",
                    files={"file": ("bad.pdf", FAKE_PDF_BYTES, "application/pdf")},
                )

        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] is True
        assert body["error_type"] == "http_error"
