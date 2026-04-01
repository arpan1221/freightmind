// Analytics

export interface AnalyticsQueryRequest {
  question: string;
  previous_sql?: string | null;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie" | "scatter" | "stacked_bar";
  x_key: string;
  y_key: string;
  y_keys?: string[] | null;
}

export interface AnalyticsQueryResponse {
  answer: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  chart_config: ChartConfig | null;
  suggested_questions: string[];
  error: string | null;
  message: string | null;
}

// Extraction

export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW" | "NOT_FOUND";

export interface ExtractedField {
  value: string | null;
  confidence: ConfidenceLevel;
}

export interface ExtractedLineItem {
  description: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  confidence: ConfidenceLevel;
}

export interface ExtractionResponse {
  extraction_id: number;
  filename: string;
  fields: Record<string, ExtractedField>;
  line_items: ExtractedLineItem[];
  low_confidence_fields: string[];
  error: string | null;
  message: string | null;
}

export interface ExtractedDocumentSummary {
  extraction_id: number;
  filename: string;
  extracted_at: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  shipment_mode: string | null;
  destination_country: string | null;
  total_freight_cost_usd: number | null;
}

export interface ExtractionListResponse {
  extractions: ExtractedDocumentSummary[];
}

export interface ConfirmRequest {
  extraction_id: number;
  corrections?: Record<string, string>;
}

export interface ConfirmResponse {
  stored: boolean;
  document_id: number;
}

// Schema

export interface ColumnInfo {
  column_name: string;
  sample_values: unknown[];
}

export interface TableInfo {
  table_name: string;
  row_count: number;
  columns: ColumnInfo[];
}

export interface SchemaInfoResponse {
  tables: TableInfo[];
}

// Common

/** Matches backend `ErrorResponse`; analytics may set `detail.sql` for rejected/failed SQL (Story 5.4). */
export interface ErrorResponse {
  error: boolean;
  error_type: string;
  message: string;
  detail?: Record<string, unknown> | null;
  retry_after?: number | null;
}
