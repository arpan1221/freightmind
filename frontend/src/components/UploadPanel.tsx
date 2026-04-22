"use client";

import { useRef, DragEvent, useEffect, useState } from "react";
import ConfidenceBadge from "@/components/ConfidenceBadge";
import ErrorToast from "@/components/ErrorToast";
import { useExtraction } from "@/hooks/useExtraction";
import api from "@/lib/api";
import type { ExtractionListResponse } from "@/types/api";

const ACCEPTED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const ACCEPTED_EXTENSIONS = ".pdf, .png, .jpg, .jpeg";

interface UploadPanelProps {
  /** Invoked after vision extraction persists a document and line items (e.g. refresh schema counts). */
  onExtractSuccess?: () => void;
}

const FIELD_LABELS: Record<string, string> = {
  // Commercial Invoice
  invoice_number: "Invoice Number",
  invoice_date: "Invoice Date",
  payment_terms: "Payment Terms",
  total_freight_cost_usd: "Freight Cost (USD)",
  total_insurance_usd: "Insurance (USD)",
  // Bill of Lading
  bl_number: "B/L Number",
  vessel_name: "Vessel / Flight",
  container_numbers: "Container Numbers",
  // Shared
  shipper_name: "Shipper",
  consignee_name: "Consignee",
  origin_country: "Origin Country",
  destination_country: "Destination Country",
  shipment_mode: "Shipment Mode",
  carrier_vendor: "Carrier / Vendor",
  total_weight_kg: "Weight (kg)",
  delivery_date: "Delivery Date",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  incoterms: "Incoterms",
  hs_code: "HS Code",
  description_of_goods: "Description of Goods",
  // Packing List
  package_count: "Package Count",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  commercial_invoice: "Commercial Invoice",
  bill_of_lading: "Bill of Lading",
  packing_list: "Packing List",
};

const DOC_TYPE_COLORS: Record<string, string> = {
  commercial_invoice: "bg-blue-50 text-blue-700 border-blue-200",
  bill_of_lading: "bg-violet-50 text-violet-700 border-violet-200",
  packing_list: "bg-teal-50 text-teal-700 border-teal-200",
};

export default function UploadPanel({ onExtractSuccess }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<ExtractionListResponse["extractions"]>([]);

  async function fetchPending() {
    try {
      const res = await api.get<ExtractionListResponse>("/api/documents/pending");
      setPending(res.data.extractions ?? []);
    } catch {
      // non-critical
    }
  }

  useEffect(() => {
    fetchPending();
  }, []);

  async function confirmPending(id: number) {
    try {
      await api.post("/api/documents/confirm", { extraction_id: id });
      await fetchPending();
      onExtractSuccess?.();
    } catch {
      // surface nothing — user can retry
    }
  }

  async function discardPending(id: number) {
    try {
      await api.delete(`/api/documents/extractions/${id}`);
      await fetchPending();
    } catch {
      // surface nothing
    }
  }
  const {
    isExtracting,
    isConfirming,
    extraction,
    editedFields,
    errorToast,
    confirmed,
    extract,
    setEdit,
    confirm,
    cancel,
    reset,
    setError,
    dismissErrorToast,
    onRateLimitComplete,
    extractDisabled,
    confirmDisabled,
  } = useExtraction({ onExtractSuccess });

  const toastEl =
    errorToast != null ? (
      <ErrorToast
        message={errorToast.message}
        retryAfterSeconds={errorToast.retryAfterSeconds}
        onDismiss={dismissErrorToast}
        onCountdownComplete={onRateLimitComplete}
      />
    ) : null;

  function clearInput() {
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleCancel() {
    cancel();
    clearInput();
  }

  function handleReset() {
    reset();
    clearInput();
  }

  function handleFile(file: File) {
    if (ACCEPTED_TYPES.includes(file.type)) {
      extract(file);
    } else {
      setError(`Unsupported file type. Please upload a PDF, PNG, or JPEG.`);
    }
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (extractDisabled) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleFileChange() {
    const file = inputRef.current?.files?.[0];
    if (file) handleFile(file);
  }

  // ── Success state ────────────────────────────────────────────────────────
  if (confirmed) {
    return (
      <>
      <div className="flex flex-col gap-6">
        <div>
          <h2 className="text-slate-900 font-semibold text-base">
            Upload Freight Document
          </h2>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-8 text-center">
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-emerald-500 mx-auto mb-3"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <p className="text-emerald-700 font-medium text-sm">
            Extraction saved successfully
          </p>
          <p className="text-emerald-600 text-xs mt-1">
            The document data has been added to the dataset.
          </p>
          <button
            onClick={handleReset}
            className="mt-4 text-xs text-slate-500 underline hover:text-slate-700"
          >
            Upload another document
          </button>
        </div>
      </div>
      {toastEl}
      </>
    );
  }

  // ── Review state ─────────────────────────────────────────────────────────
  if (extraction) {
    const docType = extraction.document_type ?? "commercial_invoice";
    const docTypeLabel = DOC_TYPE_LABELS[docType] ?? docType;
    const docTypeBadgeClass = DOC_TYPE_COLORS[docType] ?? "bg-slate-50 text-slate-700 border-slate-200";
    return (
      <>
      <div className="flex flex-col gap-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-slate-900 font-semibold text-base">
              Review Extraction
            </h2>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${docTypeBadgeClass}`}>
              {docTypeLabel}
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-0.5">
            {extraction.filename} — verify fields before saving
          </p>
        </div>

        {/* Header fields table */}
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide w-40">
                  Field
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Value
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                  Confidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {Object.entries(extraction.fields).map(([key, field]) => {
                const isLowConf = extraction.low_confidence_fields.includes(key);
                const editedValue = editedFields[key];
                const displayValue =
                  editedValue !== undefined
                    ? editedValue
                    : field.value !== null && field.value !== undefined
                    ? String(field.value)
                    : "";
                return (
                  <tr key={key} className={isLowConf ? "bg-amber-50" : ""}>
                    <td className="px-4 py-2.5 text-slate-600 font-medium whitespace-nowrap">
                      {FIELD_LABELS[key] ?? key}
                    </td>
                    <td className="px-4 py-2.5">
                      <input
                        type="text"
                        value={displayValue}
                        placeholder="—"
                        onChange={(e) => setEdit(key, e.target.value)}
                        className="w-full text-slate-800 bg-transparent border-b border-transparent hover:border-slate-300 focus:border-blue-400 focus:outline-none placeholder-slate-300"
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      <ConfidenceBadge level={field.confidence} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Line items sub-table */}
        {extraction.line_items.length > 0 && (
          <div>
            <h3 className="text-slate-700 font-medium text-sm mb-2">
              Line Items
            </h3>
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      Description
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide w-20">
                      Qty
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                      Unit Price
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                      Total
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                      Confidence
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {extraction.line_items.map((item, i) => (
                    <tr key={i}>
                      <td className="px-4 py-2 text-slate-700">
                        {item.description ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-700">
                        {item.quantity ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-700">
                        {item.unit_price != null
                          ? `$${item.unit_price.toFixed(2)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-slate-700">
                        {item.total_price != null
                          ? `$${item.total_price.toFixed(2)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-2">
                        <ConfidenceBadge level={item.confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Confirm / Cancel */}
        <div className="flex justify-end gap-3">
          <button
            onClick={handleCancel}
            disabled={isConfirming}
            className="px-4 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={confirm}
            disabled={confirmDisabled}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
          >
            {isConfirming ? "Saving…" : "Confirm →"}
          </button>
        </div>
      </div>
      {toastEl}
      </>
    );
  }

  // ── Upload / extracting state ─────────────────────────────────────────────
  return (
    <>
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-slate-900 font-semibold text-base">
          Upload Freight Document
        </h2>
        <p className="text-slate-500 text-sm mt-0.5">
          Drop a PDF or image — Commercial Invoice, Bill of Lading, or Packing List.
          FreightMind auto-detects the document type and extracts all fields for review.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => !extractDisabled && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-16 flex flex-col items-center justify-center text-center transition-all ${
          isExtracting
            ? "border-blue-300 bg-blue-50 cursor-wait"
            : extractDisabled
              ? "border-slate-200 bg-slate-50 cursor-not-allowed opacity-80"
              : "border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50 cursor-pointer"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleFileChange}
          className="hidden"
          disabled={extractDisabled}
        />

        {isExtracting ? (
          <div className="flex flex-col items-center gap-3">
            <svg
              className="animate-spin text-blue-500"
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            <p className="text-slate-600 text-sm font-medium">
              Extracting fields…
            </p>
            <p className="text-slate-400 text-xs">
              This may take up to 30 seconds
            </p>
          </div>
        ) : (
          <>
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mb-4 text-blue-400"
            >
              <polyline points="16 16 12 12 8 16" />
              <line x1="12" y1="12" x2="12" y2="21" />
              <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
            </svg>
            <p className="text-slate-700 font-medium text-sm">
              Drop a freight document here
            </p>
            <p className="text-slate-400 text-sm mt-1">or click to browse</p>
            <p className="text-slate-300 text-xs mt-3 font-medium tracking-wide uppercase">
              PDF · PNG · JPG · JPEG
            </p>
          </>
        )}
      </div>

      {/* Pending invoices — orphaned unconfirmed extractions */}
      {pending.length > 0 && (
        <div>
          <h3 className="text-slate-700 font-medium text-sm mb-2">
            Pending Invoices ({pending.length})
          </h3>
          <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden divide-y divide-amber-100">
            {pending.map((doc) => {
              const dt = doc.document_type ?? "commercial_invoice";
              const dtLabel = DOC_TYPE_LABELS[dt] ?? dt;
              const dtBadge = DOC_TYPE_COLORS[dt] ?? "bg-slate-50 text-slate-700 border-slate-200";
              const ref = doc.bl_number ?? doc.invoice_number;
              return (
              <div key={doc.extraction_id} className="px-4 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-medium text-slate-700 truncate">{doc.filename}</p>
                    <span className={`shrink-0 text-xs font-medium px-1.5 py-0.5 rounded border ${dtBadge}`}>{dtLabel}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {ref ? `${ref} · ` : ""}{doc.shipment_mode ?? "—"} · {doc.destination_country ?? "—"}
                    {doc.total_freight_cost_usd != null ? ` · $${doc.total_freight_cost_usd.toLocaleString()}` : ""}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => discardPending(doc.extraction_id)}
                    className="px-3 py-1 text-xs text-slate-500 bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Discard
                  </button>
                  <button
                    onClick={() => confirmPending(doc.extraction_id)}
                    className="px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    Confirm
                  </button>
                </div>
              </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Placeholder — only shown when no toast and no pending */}
      {!errorToast && pending.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 text-center">
          <p className="text-slate-400 text-sm">
            Extraction results will appear here after upload.
          </p>
          <p className="text-slate-300 text-xs mt-1">
            Per-field confidence scores · Editable review · Confirm to store
          </p>
        </div>
      )}
    </div>
    {toastEl}
    </>
  );
}
