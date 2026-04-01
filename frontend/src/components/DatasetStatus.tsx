"use client";

import type { SchemaInfoResponse } from "@/types/api";

interface LiveStats {
  shipments: number;
  extracted_documents: number;
  extracted_line_items: number;
  live_seeding_active: boolean;
}

interface DatasetStatusProps {
  schema: SchemaInfoResponse | null;
  isLoading: boolean;
  liveStats?: LiveStats | null;
  flashedTables?: Set<string>;
}

const TABLE_LABELS: Record<string, string> = {
  shipments: "Shipments",
  extracted_documents: "Extracted Docs",
  extracted_line_items: "Line Items",
};

export default function DatasetStatus({
  schema,
  isLoading,
  liveStats,
  flashedTables = new Set(),
}: DatasetStatusProps) {
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
  const isLiveSeeding = liveStats?.live_seeding_active === true;

  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      {tables.map((t) => {
        const count =
          liveStats && t.table_name in liveStats
            ? liveStats[t.table_name as keyof LiveStats]
            : t.row_count;
        const isShipments = t.table_name === "shipments";
        const isFlashing = flashedTables.has(t.table_name);

        return (
          <div
            key={t.table_name}
            className={`bg-white border rounded-xl p-4 transition-all duration-300 ${
              isFlashing
                ? "border-emerald-400 shadow-sm shadow-emerald-100"
                : "border-slate-200"
            }`}
          >
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
              {TABLE_LABELS[t.table_name] ?? t.table_name}
            </p>
            <p
              className={`text-2xl font-bold tabular-nums transition-colors duration-300 ${
                isFlashing ? "text-emerald-600" : "text-slate-900"
              }`}
            >
              {typeof count === "number" ? count.toLocaleString() : t.row_count.toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
              {isShipments && isLiveSeeding ? (
                <>
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                  </span>
                  Live
                </>
              ) : isShipments && (typeof count === "number" ? count : t.row_count) > 0 ? (
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
