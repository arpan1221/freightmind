"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { SchemaInfoResponse } from "@/types/api";

export default function DatasetStatus() {
  const [schema, setSchema] = useState<SchemaInfoResponse | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(true);

  useEffect(() => {
    api
      .get<SchemaInfoResponse>("/api/schema")
      .then((res) => setSchema(res.data))
      .catch(() => setSchema(null))
      .finally(() => setIsLoadingSchema(false));
  }, []);

  if (isLoadingSchema) {
    return <p className="text-sm text-gray-400">Loading dataset…</p>;
  }

  if (!schema) {
    return <p className="text-sm text-gray-400">Schema unavailable</p>;
  }

  return (
    <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-3 p-2 bg-gray-50 rounded border border-gray-200">
      {schema.tables.map((t) => (
        <span key={t.table_name}>
          <strong>{t.table_name}</strong>: {t.row_count.toLocaleString()} rows
        </span>
      ))}
    </div>
  );
}
