from pydantic import BaseModel


class FieldVerificationResult(BaseModel):
    name: str
    extracted: str | None
    expected: str | None
    status: str  # match | mismatch | uncertain | no_rule
    confidence: float
    rule_description: str | None = None
    source_document: str | None = None  # "Commercial Invoice" | "Bill of Lading" | "Packing List"


class VerificationResultResponse(BaseModel):
    verification_id: int
    shipment_id: str
    received_at: str
    customer_id: str
    customer_name: str | None = None
    overall_status: str  # approved | amendment_required | uncertain | failed
    fields: list[FieldVerificationResult]
    draft_reply: str
    error: str | None = None


class VerificationSummary(BaseModel):
    verification_id: int
    shipment_id: str
    received_at: str
    customer_id: str
    customer_name: str | None = None
    overall_status: str
    created_at: str | None = None
    field_count: int = 0
    mismatch_count: int = 0


class VerificationQueueResponse(BaseModel):
    verifications: list[VerificationSummary]
