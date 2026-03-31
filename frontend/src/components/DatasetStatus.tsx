"use client";

import type { SchemaInfoResponse } from "@/types/api";

interface DatasetStatusProps {
  schema: SchemaInfoResponse | null;
  isLoading: boolean;
}

const TABLE_LABELS: Record<string, string> = {
  shipments: "Shipments",
  extracted_documents: "Extracted Docs",
  extracted_line_items: "Line Items",
};

export default function DatasetStatus({ schema, isLoading }: DatasetStatusProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="bg-white border border-slate-200 rounded-xl p-4 animate-pulse"
          >
            <div className="h-3 bg-slate-100 rounded w-24 mb-3" />
            <div className="h-7 bg-slate-100 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (!schema) {
    return null;
  }

  const tables = schema.tables ?? [];

  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      {tables.map((t) => {
        const isLive = t.table_name === "shipments" && t.row_count > 0;
        return (
          <div
            key={t.table_name}
            className="bg-white border border-slate-200 rounded-xl p-4"
          >
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
              {TABLE_LABELS[t.table_name] ?? t.table_name}
            </p>
            <p className="text-2xl font-bold text-slate-900">
              {t.row_count.toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
              {isLive ? (
                <>
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  Live
                </>
              ) : (
                "records"
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
