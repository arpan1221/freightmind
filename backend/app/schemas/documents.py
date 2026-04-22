from typing import Union

from pydantic import BaseModel

from app.schemas.common import ConfidenceLevel


class ExtractedField(BaseModel):
    value: Union[str, float, None]
    confidence: ConfidenceLevel = "HIGH"


class ExtractedLineItemOut(BaseModel):
    description: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    total_price: float | None = None
    confidence: ConfidenceLevel = "HIGH"


class ExtractionResponse(BaseModel):
    extraction_id: int
    filename: str
    document_type: str = "commercial_invoice"
    fields: dict[str, ExtractedField]
    line_items: list[ExtractedLineItemOut]
    low_confidence_fields: list[str] = []
    error: str | None = None
    message: str | None = None


class ConfirmRequest(BaseModel):
    extraction_id: int
    corrections: dict[str, str] | None = None


class ConfirmResponse(BaseModel):
    stored: bool
    document_id: int


class ExtractedDocumentSummary(BaseModel):
    extraction_id: int
    filename: str
    document_type: str = "commercial_invoice"
    extracted_at: str | None = None
    invoice_number: str | None = None
    bl_number: str | None = None
    invoice_date: str | None = None
    shipment_mode: str | None = None
    destination_country: str | None = None
    total_freight_cost_usd: float | None = None


class ExtractionListResponse(BaseModel):
    extractions: list[ExtractedDocumentSummary]
