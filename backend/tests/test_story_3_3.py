"""
Tests for Story 3.3 — Confidence Scoring Per Field

Verifies:
- AC1: Each field and line item has a confidence of HIGH, MEDIUM, LOW, or NOT_FOUND
- AC2: Missing/null field → value=null, confidence=NOT_FOUND
- AC3: LOW or NOT_FOUND fields appear in low_confidence_fields list
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from typing import get_args

from app.schemas.common import ConfidenceLevel
from app.schemas.documents import ExtractedField, ExtractionResponse
from app.agents.extraction.verifier import ExtractionVerifier


# ─────────────────────────────────────────────────────────────────────────────
# ConfidenceLevel type (AC1)
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceLevel:
    def test_all_four_values_exist(self):
        args = get_args(ConfidenceLevel)
        assert "HIGH" in args
        assert "MEDIUM" in args
        assert "LOW" in args
        assert "NOT_FOUND" in args

    def test_all_values_are_strings(self):
        assert all(isinstance(v, str) for v in get_args(ConfidenceLevel))

    def test_serialises_as_plain_string(self):
        fv = ExtractedField(value="Air", confidence="HIGH")
        data = fv.model_dump()
        assert data["confidence"] == "HIGH"
        assert isinstance(data["confidence"], str)

    def test_accepts_valid_confidence_string(self):
        fv = ExtractedField(value="test", confidence="HIGH")
        assert fv.confidence == "HIGH"


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionResponse defaults (AC3)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionResponseDefaults:
    def test_low_confidence_fields_defaults_to_empty(self):
        resp = ExtractionResponse(
            extraction_id=1,
            filename="test.pdf",
            fields={"invoice_number": ExtractedField(value="INV-001", confidence="HIGH")},
            line_items=[],
        )
        assert resp.low_confidence_fields == []
        assert resp.error is None


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionVerifier.score_confidence (AC1, AC2, AC3)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionVerifierScoreConfidence:
    def setup_method(self):
        self.verifier = ExtractionVerifier()

    def test_high_confidence_mapped_correctly(self):
        raw = {"invoice_number": {"value": "INV-001", "confidence": "HIGH"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["invoice_number"].confidence == "HIGH"
        assert "invoice_number" not in low

    def test_medium_confidence_mapped_correctly(self):
        raw = {"payment_terms": {"value": "NET30", "confidence": "MEDIUM"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["payment_terms"].confidence == "MEDIUM"
        assert "payment_terms" not in low

    def test_low_confidence_appears_in_low_confidence_fields(self):
        raw = {"total_insurance_usd": {"value": 150.0, "confidence": "LOW"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["total_insurance_usd"].confidence == "LOW"
        assert "total_insurance_usd" in low

    def test_null_value_forces_not_found_regardless_of_confidence(self):
        """AC2: null value → NOT_FOUND, even if LLM said HIGH."""
        raw = {"shipper_name": {"value": None, "confidence": "HIGH"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["shipper_name"].confidence == "NOT_FOUND"
        assert fields["shipper_name"].value is None
        assert "shipper_name" in low

    def test_not_found_confidence_appears_in_low_confidence_fields(self):
        raw = {"carrier_vendor": {"value": None, "confidence": "NOT_FOUND"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["carrier_vendor"].confidence == "NOT_FOUND"
        assert "carrier_vendor" in low

    def test_invalid_confidence_string_coerced_to_low(self):
        raw = {"invoice_date": {"value": "2024-01-15", "confidence": "UNSURE"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["invoice_date"].confidence == "LOW"
        assert "invoice_date" in low

    def test_confidence_comparison_case_insensitive(self):
        raw = {"destination_country": {"value": "Nigeria", "confidence": "high"}}
        fields, _, _ = self.verifier.score_confidence(raw, [])
        assert fields["destination_country"].confidence == "HIGH"

    def test_mixed_case_medium(self):
        raw = {"shipment_mode": {"value": "Air", "confidence": "Medium"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["shipment_mode"].confidence == "MEDIUM"
        assert "shipment_mode" not in low

    def test_high_medium_not_in_low_confidence_fields(self):
        raw = {
            "invoice_number": {"value": "INV-001", "confidence": "HIGH"},
            "payment_terms": {"value": "NET30", "confidence": "MEDIUM"},
        }
        _, _, low = self.verifier.score_confidence(raw, [])
        assert low == []

    def test_empty_input_returns_empty_outputs(self):
        fields, line_items, low = self.verifier.score_confidence({}, [])
        assert fields == {}
        assert line_items == []
        assert low == []

    def test_line_item_not_found_coerced_to_low(self):
        """Line items never receive NOT_FOUND — coerced to LOW."""
        raw_items = [
            {
                "description": "ARV tablets",
                "quantity": 100,
                "unit_price": 5.0,
                "total_price": 500.0,
                "confidence": "NOT_FOUND",
            }
        ]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].confidence == "LOW"

    def test_line_item_with_null_fields_coerced_to_low(self):
        """Line items with LOW confidence and null fields stay LOW."""
        raw_items = [
            {
                "description": None,
                "quantity": None,
                "unit_price": None,
                "total_price": None,
                "confidence": "LOW",
            }
        ]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].confidence == "LOW"

    def test_line_item_fields_populated_correctly(self):
        raw_items = [
            {
                "description": "ARV tablets",
                "quantity": 50,
                "unit_price": 10.0,
                "total_price": 500.0,
                "confidence": "HIGH",
            }
        ]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].description == "ARV tablets"
        assert line_items[0].quantity == 50
        assert line_items[0].unit_price == pytest.approx(10.0)
        assert line_items[0].confidence == "HIGH"

    def test_multiple_low_and_not_found_all_in_list(self):
        """AC3: all LOW and NOT_FOUND fields appear in low_confidence_fields."""
        raw = {
            "invoice_number": {"value": "INV-001", "confidence": "HIGH"},
            "invoice_date": {"value": None, "confidence": "NOT_FOUND"},
            "shipper_name": {"value": "Pharma Co", "confidence": "LOW"},
            "consignee_name": {"value": "Ministry", "confidence": "MEDIUM"},
        }
        _, _, low = self.verifier.score_confidence(raw, [])
        assert "invoice_date" in low
        assert "shipper_name" in low
        assert "invoice_number" not in low
        assert "consignee_name" not in low
        assert len(low) == 2
