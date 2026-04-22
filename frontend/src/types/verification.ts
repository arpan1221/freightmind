export type VerificationStatus = "approved" | "amendment_required" | "uncertain" | "failed";
export type FieldStatus = "match" | "mismatch" | "uncertain" | "no_rule";

export interface FieldVerificationResult {
  name: string;
  extracted: string | null;
  expected: string | null;
  status: FieldStatus;
  confidence: number;
  rule_description: string | null;
  source_document: string | null;
}

export interface VerificationResultResponse {
  verification_id: number;
  shipment_id: string;
  received_at: string;
  customer_id: string;
  customer_name: string | null;
  overall_status: VerificationStatus;
  fields: FieldVerificationResult[];
  draft_reply: string;
  error: string | null;
}

export interface VerificationSummary {
  verification_id: number;
  shipment_id: string;
  received_at: string;
  customer_id: string;
  customer_name: string | null;
  overall_status: VerificationStatus;
  created_at: string | null;
  field_count: number;
  mismatch_count: number;
}

export interface VerificationQueueResponse {
  verifications: VerificationSummary[];
}

// ── Streaming event types (SSE from POST /api/verify/submit/stream) ──────────

export interface StageEvent {
  type: "stage";
  step: number;
  message: string;
}

export interface FieldStreamEvent extends FieldVerificationResult {
  type: "field";
}

export interface DocDetectedEvent {
  type: "doc_detected";
  filename: string;
  document_type: string;
  label: string;
}

export interface CrossCheckEvent {
  type: "cross_check";
  field: string;
  conflict: string;
  message: string;
}

export interface CompleteEvent {
  type: "complete";
  verification_id: number;
  shipment_id: string;
  received_at: string;
  customer_id: string;
  customer_name: string | null;
  overall_status: VerificationStatus;
  draft_reply: string;
  documents_processed?: { doc_type: string; label: string }[];
  cross_check_issues?: number;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export interface WarningEvent {
  type: "warning";
  message: string;
}

export type StreamEvent =
  | StageEvent
  | FieldStreamEvent
  | DocDetectedEvent
  | CrossCheckEvent
  | CompleteEvent
  | ErrorEvent
  | WarningEvent;
