"use client";

import { useCallback, useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import UploadPanel from "@/components/UploadPanel";
import DatasetStatus from "@/components/DatasetStatus";
import ErrorToast from "@/components/ErrorToast";
import api from "@/lib/api";
import {
  getErrorResponseFromUnknown,
  getUserFacingErrorMessage,
  normalizeRetryAfterSeconds,
} from "@/lib/errorResponse";
import type { SchemaInfoResponse } from "@/types/api";

type Tab = "analytics" | "documents";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("analytics");
  const [schema, setSchema] = useState<SchemaInfoResponse | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(true);
  const [schemaErrorToast, setSchemaErrorToast] = useState<{
    message: string;
    retryAfterSeconds: number | null;
  } | null>(null);

  const loadSchema = useCallback((options?: { silent?: boolean }) => {
    const silent = options?.silent === true;
    if (!silent) {
      setIsLoadingSchema(true);
    }
    api
      .get<SchemaInfoResponse>("/api/schema")
      .then((res) => {
        setSchema(res.data);
        setSchemaErrorToast(null);
      })
      .catch((err: unknown) => {
        setSchema(null);
        const structured = getErrorResponseFromUnknown(err);
        if (structured) {
          setSchemaErrorToast({
            message: structured.message,
            retryAfterSeconds: normalizeRetryAfterSeconds(structured.retry_after),
          });
        } else {
          setSchemaErrorToast({
            message: getUserFacingErrorMessage(
              err,
              "Could not load dataset schema."
            ),
            retryAfterSeconds: null,
          });
        }
      })
      .finally(() => {
        if (!silent) {
          setIsLoadingSchema(false);
        }
      });
  }, []);

  useEffect(() => {
    loadSchema();
  }, [loadSchema]);

  const shipmentsCount =
    schema?.tables?.find((t) => t.table_name === "shipments")?.row_count ?? 0;
  const extractedCount =
    schema?.tables?.find((t) => t.table_name === "extracted_documents")
      ?.row_count ?? 0;

  return (
    <main className="flex-1 flex flex-col max-w-5xl mx-auto w-full px-6 py-6">
      {schemaErrorToast && (
        <ErrorToast
          message={schemaErrorToast.message}
          retryAfterSeconds={schemaErrorToast.retryAfterSeconds}
          onDismiss={() => setSchemaErrorToast(null)}
          onCountdownComplete={() => {
            loadSchema();
          }}
          placement="top"
        />
      )}

      <DatasetStatus schema={schema} isLoading={isLoadingSchema} />

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        <button
          type="button"
          onClick={() => setActiveTab("analytics")}
          className={`flex items-center gap-2 px-4 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "analytics"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Analytics
          {!isLoadingSchema && shipmentsCount > 0 && (
            <span className="text-xs bg-blue-50 text-blue-600 rounded-full px-2 py-0.5 font-medium">
              {shipmentsCount.toLocaleString()}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("documents")}
          className={`flex items-center gap-2 px-4 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "documents"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Documents
          {!isLoadingSchema && extractedCount > 0 && (
            <span className="text-xs bg-blue-50 text-blue-600 rounded-full px-2 py-0.5 font-medium">
              {extractedCount}
            </span>
          )}
        </button>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        {activeTab === "analytics" ? (
          <ChatPanel />
        ) : (
          <UploadPanel
            onExtractSuccess={() => loadSchema({ silent: true })}
          />
        )}
      </div>
    </main>
  );
}
