// Analytics

export interface AnalyticsQueryRequest {
  question: string;
  previous_sql?: string | null;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie";
  x_key: string;
  y_key: string;
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
  extraction_id: string;
  fields: Record<string, ExtractedField>;
  line_items: ExtractedLineItem[];
  error: string | null;
}

export interface ConfirmRequest {
  extraction_id: string;
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

export interface ErrorResponse {
  error: string | null;
  message: string | null;
  retry_after: number | null;
}
