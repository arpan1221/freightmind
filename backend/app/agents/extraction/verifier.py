import logging
from typing import Optional, get_args

from app.schemas.common import ConfidenceLevel
from app.schemas.documents import ExtractedField, ExtractedLineItemOut

logger = logging.getLogger(__name__)

_VALID_CONFIDENCE = set(get_args(ConfidenceLevel))

_HEADER_FIELDS = [
    "invoice_number",
    "invoice_date",
    "shipper_name",
    "consignee_name",
    "origin_country",
    "destination_country",
    "shipment_mode",
    "carrier_vendor",
    "total_weight_kg",
    "total_freight_cost_usd",
    "total_insurance_usd",
    "payment_terms",
    "delivery_date",
    # Part 2: trade document fields added to extraction
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
]

_NUMERIC_FIELDS = {"total_weight_kg", "total_freight_cost_usd", "total_insurance_usd", "package_count"}

_ALLOWED_CORRECTION_FIELDS = {
    "invoice_number",
    "invoice_date",
    "shipper_name",
    "consignee_name",
    "origin_country",
    "destination_country",
    "shipment_mode",
    "carrier_vendor",
    "total_weight_kg",
    "total_freight_cost_usd",
    "total_insurance_usd",
    "payment_terms",
    "delivery_date",
    "hs_code",
    "port_of_loading",
    "port_of_discharge",
    "incoterms",
    "description_of_goods",
    # Bill of Lading fields
    "bl_number",
    "vessel_name",
    "container_numbers",
    # Packing List fields
    "package_count",
}

_VALID_SHIPMENT_MODES = {"Air", "Ocean", "Truck", "Air Charter"}


class ExtractionVerifier:
    def verify(self, raw: dict) -> dict:
        """Basic field validation: value present → HIGH, absent → NOT_FOUND.

        Story 3.2 adds mode/country normalisation.
        Story 3.3 adds real per-field confidence scoring.

        Returns {
            "fields": dict[str, ExtractedField],
            "line_items": list[ExtractedLineItemOut],
            "low_confidence_fields": list[str],
        }
        """
        fields: dict[str, ExtractedField] = {}
        low_confidence: list[str] = []

        for name in _HEADER_FIELDS:
            raw_val = raw.get(name)
            value = self._coerce(name, raw_val)
            confidence = "NOT_FOUND" if value is None else "HIGH"
            if value is None:
                low_confidence.append(name)
            fields[name] = ExtractedField(value=value, confidence=confidence)

        line_items = self._parse_line_items(raw.get("line_items") or [])

        return {
            "fields": fields,
            "line_items": line_items,
            "low_confidence_fields": low_confidence,
        }

    def _coerce(self, name: str, value) -> "str | float | None":
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if name in _NUMERIC_FIELDS:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return str(value).strip()

    def _parse_line_items(self, items: list) -> list[ExtractedLineItemOut]:
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            qty = item.get("quantity")
            up = item.get("unit_price")
            tp = item.get("total_price")
            try:
                qty_int = int(float(qty)) if qty is not None else None
            except (TypeError, ValueError):
                qty_int = None
            result.append(
                ExtractedLineItemOut(
                    description=str(item["description"]).strip() if item.get("description") else None,
                    quantity=qty_int,
                    unit_price=float(up) if up is not None else None,
                    total_price=float(tp) if tp is not None else None,
                    confidence="HIGH",
                )
            )
        return result

    def score_confidence(
        self,
        raw_fields: dict[str, dict],
        raw_line_items: list[dict],
    ) -> tuple[dict[str, ExtractedField], list[ExtractedLineItemOut], list[str]]:
        """Parse per-field confidence values from raw LLM extraction output (Story 3.3).

        Each entry in raw_fields must have shape: {"value": <any>, "confidence": <str>}.
        Rules:
        - value is None → confidence forced to NOT_FOUND regardless of the raw confidence key
        - Unknown/invalid confidence string → coerced to LOW (never raises)
        - Confidence comparison is case-insensitive
        - Line items never receive NOT_FOUND — coerced to LOW

        Returns (fields_dict, line_items_list, low_confidence_fields).
        """
        fields: dict[str, ExtractedField] = {}
        low_confidence_fields: list[str] = []

        for field_name, raw in raw_fields.items():
            if not isinstance(raw, dict):
                fields[field_name] = ExtractedField(value=None, confidence="NOT_FOUND")
                low_confidence_fields.append(field_name)
                continue

            raw_value = raw.get("value")
            value = self._coerce(field_name, raw_value)  # P2: numeric coercion + whitespace strip
            raw_conf = raw.get("confidence", "")

            if value is None:
                confidence: ConfidenceLevel = "NOT_FOUND"
            elif isinstance(raw_conf, str) and raw_conf.upper() in _VALID_CONFIDENCE:
                confidence = raw_conf.upper()
            else:
                logger.debug(
                    "score_confidence: unknown confidence %r for field %r — coercing to LOW",
                    raw_conf,
                    field_name,
                )
                confidence = "LOW"

            fields[field_name] = ExtractedField(value=value, confidence=confidence)
            if confidence in ("LOW", "NOT_FOUND"):
                low_confidence_fields.append(field_name)

        line_items: list[ExtractedLineItemOut] = []
        for raw_item in raw_line_items:
            if not isinstance(raw_item, dict):
                continue
            raw_conf = raw_item.get("confidence", "")
            if isinstance(raw_conf, str) and raw_conf.upper() in _VALID_CONFIDENCE:
                confidence = raw_conf.upper()
            else:
                confidence = "LOW"
            # Line items never use NOT_FOUND — coerce to LOW
            if confidence == "NOT_FOUND":
                confidence = "LOW"
            qty = raw_item.get("quantity")
            up = raw_item.get("unit_price")
            tp = raw_item.get("total_price")
            # P1: guard numeric conversions — bad LLM output must not crash the pipeline
            try:
                qty_val = int(qty) if qty is not None else None
            except (TypeError, ValueError):
                qty_val = None
            try:
                up_val = float(up) if up is not None else None
            except (TypeError, ValueError):
                up_val = None
            try:
                tp_val = float(tp) if tp is not None else None
            except (TypeError, ValueError):
                tp_val = None
            line_items.append(
                ExtractedLineItemOut(
                    description=str(raw_item["description"]).strip() if raw_item.get("description") else None,
                    quantity=qty_val,
                    unit_price=up_val,
                    total_price=tp_val,
                    confidence=confidence,
                )
            )

        return fields, line_items, low_confidence_fields

    def validate_corrections(
        self,
        corrections: dict[str, str],
        document: object,
    ) -> tuple[bool, Optional[str]]:
        """Validate correction keys and vocabulary values.

        Returns (True, None) on success; (False, error_message) on failure.
        The document parameter is accepted for future field-level validation
        without requiring an interface change.
        """
        invalid_keys = set(corrections.keys()) - _ALLOWED_CORRECTION_FIELDS
        if invalid_keys:
            msg = f"Invalid correction field(s): {', '.join(sorted(invalid_keys))}"
            logger.warning("ExtractionVerifier rejected corrections: %s", msg)
            return False, msg

        if "shipment_mode" in corrections:
            mode = corrections["shipment_mode"].strip()
            if mode not in _VALID_SHIPMENT_MODES:
                msg = (
                    f"Invalid shipment_mode '{mode}'. "
                    f"Must be one of: {', '.join(sorted(_VALID_SHIPMENT_MODES))}"
                )
                logger.warning("ExtractionVerifier rejected shipment_mode: %s", msg)
                return False, msg

        return True, None
