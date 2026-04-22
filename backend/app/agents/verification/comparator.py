"""Comparison layer — completely separate from the extraction layer.

Loads customer rules from a JSON config file and compares extracted field
values against expected values, producing a structured result per field.

Swapping customers = swapping the config file. No agent code changes needed.
Confidence thresholds are read from the config file, not hardcoded here.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).parent.parent.parent.parent / "config" / "customer_rules"

# Maps extraction confidence strings → float 0.0-1.0
_CONFIDENCE_FLOAT: dict[str, float] = {
    "HIGH": 0.9,
    "MEDIUM": 0.6,
    "LOW": 0.3,
    "NOT_FOUND": 0.0,
}


@dataclass
class FieldResult:
    name: str
    extracted: str | None
    expected: str | None
    status: str  # match | mismatch | uncertain | no_rule
    confidence: float
    rule_description: str | None = None
    source_document: str | None = None  # populated by batch pipeline


class DocumentComparator:
    """Compares extracted document fields against a customer rule set.

    Instantiate with a loaded rules config dict (use load_customer_rules() helper).
    Call compare() with the fields dict from ExtractionVerifier.score_confidence().
    """

    def __init__(self, rules_config: dict) -> None:
        self._rules: dict[str, dict] = rules_config.get("rules", {})
        thresholds = rules_config.get("confidence_thresholds", {})
        # Threshold below which a field is marked uncertain regardless of match
        self.uncertain_threshold: float = float(thresholds.get("uncertain_below", 0.6))
        self.customer_id: str = rules_config.get("customer_id", "unknown")
        self.customer_name: str = rules_config.get("customer_name", "Unknown Customer")

    def compare(self, extracted_fields: dict) -> list[FieldResult]:
        """Compare extracted fields against customer rules.

        For each rule defined in the config:
        - If confidence < uncertain_threshold → status = uncertain (even if value matches)
        - If extracted value is None/NOT_FOUND → status = uncertain
        - If no rule defined for a field present in doc → no_rule (not auto-approved)
        - If value matches expected → match
        - If value does not match → mismatch

        Low-confidence extractions are never silently approved.
        """
        results: list[FieldResult] = []

        # Check every field that has a customer rule
        for field_name, rule in self._rules.items():
            extracted_field = extracted_fields.get(field_name)
            expected = rule.get("expected", "")
            match_type = rule.get("match_type", "exact")
            description = rule.get("description")

            if extracted_field is None:
                # Field not in extraction output at all
                results.append(
                    FieldResult(
                        name=field_name,
                        extracted=None,
                        expected=expected,
                        status="uncertain",
                        confidence=0.0,
                        rule_description=description,
                    )
                )
                continue

            raw_value = extracted_field.value
            confidence_str = (
                extracted_field.confidence
                if isinstance(extracted_field.confidence, str)
                else "LOW"
            )
            confidence_float = _CONFIDENCE_FLOAT.get(confidence_str.upper(), 0.0)
            extracted_str = str(raw_value).strip() if raw_value is not None else None

            # Low-confidence extraction → uncertain, even if it appears to match
            if confidence_float < self.uncertain_threshold or extracted_str is None:
                results.append(
                    FieldResult(
                        name=field_name,
                        extracted=extracted_str,
                        expected=expected,
                        status="uncertain",
                        confidence=confidence_float,
                        rule_description=description,
                    )
                )
                continue

            # Compare value against expected
            matches = self._matches(extracted_str, expected, match_type)
            status = "match" if matches else "mismatch"

            results.append(
                FieldResult(
                    name=field_name,
                    extracted=extracted_str,
                    expected=expected,
                    status=status,
                    confidence=confidence_float,
                    rule_description=description,
                )
            )

        # Also surface extraction fields that have no rule (for visibility, not auto-approved).
        # Covers all fields any document type can produce — Commercial Invoice, B/L, Packing List.
        rule_names = set(self._rules.keys())
        trade_fields = {
            # Commercial Invoice + shared
            "hs_code", "incoterms", "port_of_loading", "port_of_discharge",
            "consignee_name", "shipment_mode", "origin_country",
            "destination_country", "invoice_number", "description_of_goods",
            "shipper_name", "carrier_vendor", "total_weight_kg",
            "total_freight_cost_usd", "total_insurance_usd", "payment_terms",
            "invoice_date", "delivery_date",
            # Bill of Lading specific
            "bl_number", "vessel_name", "container_numbers",
            # Packing List specific
            "package_count",
        }
        for field_name in trade_fields - rule_names:
            extracted_field = extracted_fields.get(field_name)
            if extracted_field is None or extracted_field.value is None:
                continue
            confidence_str = (
                extracted_field.confidence
                if isinstance(extracted_field.confidence, str)
                else "LOW"
            )
            results.append(
                FieldResult(
                    name=field_name,
                    extracted=str(extracted_field.value),
                    expected=None,
                    status="no_rule",
                    confidence=_CONFIDENCE_FLOAT.get(confidence_str.upper(), 0.0),
                    rule_description="No rule defined for this field — not auto-approved",
                )
            )

        return results

    def determine_overall_status(self, field_results: list[FieldResult]) -> str:
        """Derive overall shipment status from field-level results.

        Priority: failed > amendment_required > uncertain > approved.
        A single mismatch → amendment_required.
        A single uncertain (with no mismatches) → uncertain.
        All match or no_rule → approved.
        """
        statuses = {r.status for r in field_results}
        if "mismatch" in statuses:
            return "amendment_required"
        if "uncertain" in statuses:
            return "uncertain"
        return "approved"

    @staticmethod
    def _matches(extracted: str, expected: str, match_type: str) -> bool:
        """Case-insensitive field comparison."""
        ext = extracted.strip().lower()
        exp = expected.strip().lower()
        if match_type == "contains":
            return exp in ext or ext in exp
        # Default: exact (case-insensitive)
        return ext == exp


def load_customer_rules(customer_id: str) -> dict:
    """Load customer rules from config file.

    Raises FileNotFoundError if the customer config does not exist.
    The caller is responsible for handling this — missing config is a
    valid failure scenario (not a crash).
    """
    config_path = _RULES_DIR / f"{customer_id}.json"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"No rule config found for customer '{customer_id}'. "
            f"Expected file: {config_path}"
        )
    with config_path.open(encoding="utf-8") as f:
        return json.load(f)
