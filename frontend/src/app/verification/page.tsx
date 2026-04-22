"use client";

import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "@/lib/getApiBaseUrl";
import type {
  FieldVerificationResult,
  FieldStatus,
  VerificationStatus,
  StreamEvent,
  CompleteEvent,
  CrossCheckEvent,
  DocDetectedEvent,
  VerificationSummary,
} from "@/types/verification";

// ── Customer registry ─────────────────────────────────────────────────────────

const CUSTOMERS = [
  {
    id: "DEMO_CUSTOMER_001",
    name: "GlobalTech Industries",
    rulesPreview: "HS 8471.30.00 · CIF · Shanghai → Rotterdam · Ocean · China",
    ruleCount: 8,
  },
  {
    id: "DEMO_CUSTOMER_002",
    name: "MedSupply Asia Pte Ltd",
    rulesPreview: "HS 3004.90.99 · DAP · Chennai → Singapore · Air · India",
    ruleCount: 8,
  },
  {
    id: "DEMO_CUSTOMER_003",
    name: "EuroParts Distribution GmbH",
    rulesPreview: "CIF · Shanghai → Rotterdam · Ocean · China  [no HS rule — demo scenario 3]",
    ruleCount: 6,
  },
];

// ── Pipeline step definitions ─────────────────────────────────────────────────

const SINGLE_STEPS = [
  { id: 1, label: "Receive" },
  { id: 2, label: "Extract" },
  { id: 3, label: "Compare" },
  { id: 4, label: "Draft" },
];

const BATCH_STEPS = [
  { id: 1, label: "Receive" },
  { id: 2, label: "Extract" },
  { id: 3, label: "Merge" },
  { id: 4, label: "Compare" },
  { id: 5, label: "Draft" },
];

type StepStatus = "pending" | "active" | "done";

interface Step {
  id: number;
  label: string;
  status: StepStatus;
}

function initialSteps(batch: boolean): Step[] {
  return (batch ? BATCH_STEPS : SINGLE_STEPS).map((s) => ({
    ...s,
    status: "pending" as StepStatus,
  }));
}

// ── Batch doc slot config ─────────────────────────────────────────────────────

const BATCH_SLOTS = [
  { key: "ci",  label: "Commercial Invoice", color: "blue",   hint: "CI" },
  { key: "bl",  label: "Bill of Lading",     color: "violet", hint: "B/L" },
  { key: "pl",  label: "Packing List",       color: "teal",   hint: "PL" },
] as const;

type BatchKey = "ci" | "bl" | "pl";

const SLOT_COLORS: Record<string, { border: string; ring: string; badge: string; dot: string }> = {
  blue:   { border: "border-blue-200",   ring: "ring-blue-300",   badge: "bg-blue-50 text-blue-700 border-blue-200",   dot: "bg-blue-500" },
  violet: { border: "border-violet-200", ring: "ring-violet-300", badge: "bg-violet-50 text-violet-700 border-violet-200", dot: "bg-violet-500" },
  teal:   { border: "border-teal-200",   ring: "ring-teal-300",   badge: "bg-teal-50 text-teal-700 border-teal-200",   dot: "bg-teal-500" },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function PipelineBar({ steps, message }: { steps: Step[]; message: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center gap-0">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5 w-20">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 ${
                  step.status === "done"
                    ? "bg-emerald-500 shadow-sm shadow-emerald-200"
                    : step.status === "active"
                    ? "bg-blue-600 shadow-md shadow-blue-200 ring-4 ring-blue-50"
                    : "bg-slate-100"
                }`}
              >
                {step.status === "done" ? (
                  <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : step.status === "active" ? (
                  <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <span className="text-xs font-medium text-slate-400">{step.id}</span>
                )}
              </div>
              <span
                className={`text-xs font-medium ${
                  step.status === "done"
                    ? "text-emerald-600"
                    : step.status === "active"
                    ? "text-blue-600"
                    : "text-slate-400"
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`h-px w-8 mb-5 mx-1 transition-colors duration-500 ${
                  step.status === "done" ? "bg-emerald-300" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>
      {message && (
        <p className="text-center text-xs text-slate-400 h-4">{message}</p>
      )}
    </div>
  );
}

function StatusBanner({ status }: { status: VerificationStatus }) {
  const cfg: Record<VerificationStatus, { label: string; sub: string; wrap: string; pill: string; icon: React.ReactNode }> = {
    approved: {
      label: "Documents Approved",
      sub: "All fields verified against customer rules",
      wrap: "bg-emerald-50 border-emerald-200",
      pill: "bg-emerald-500",
      icon: (
        <svg className="w-6 h-6 text-white" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
      ),
    },
    amendment_required: {
      label: "Amendment Required",
      sub: "Discrepancies found — review flagged fields below",
      wrap: "bg-red-50 border-red-200",
      pill: "bg-red-500",
      icon: (
        <svg className="w-6 h-6 text-white" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
      ),
    },
    uncertain: {
      label: "Manual Review Required",
      sub: "Low-confidence extractions — CG must review before sending",
      wrap: "bg-amber-50 border-amber-200",
      pill: "bg-amber-500",
      icon: (
        <svg className="w-6 h-6 text-white" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      ),
    },
    failed: {
      label: "Processing Failed",
      sub: "CG has been notified — check the error detail below",
      wrap: "bg-slate-50 border-slate-200",
      pill: "bg-slate-400",
      icon: (
        <svg className="w-6 h-6 text-white" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      ),
    },
  };
  const c = cfg[status];
  return (
    <div className={`flex items-center gap-4 px-5 py-4 rounded-xl border ${c.wrap}`}>
      <div className={`w-10 h-10 rounded-full ${c.pill} flex items-center justify-center flex-shrink-0`}>
        {c.icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-900">{c.label}</p>
        <p className="text-xs text-slate-500 mt-0.5">{c.sub}</p>
      </div>
    </div>
  );
}

function ConfidenceIndicator({ value }: { value: number }) {
  // Confidence is a discrete categorical value from the extraction layer:
  // HIGH=0.9, MEDIUM=0.6, LOW=0.3, NOT_FOUND=0.0 — show the label, not a synthetic %
  const cfg =
    value >= 0.85
      ? { label: "HIGH",      bar: "bg-emerald-400", text: "text-emerald-700", pct: 100 }
      : value >= 0.5
      ? { label: "MEDIUM",    bar: "bg-amber-400",   text: "text-amber-700",   pct:  66 }
      : value > 0
      ? { label: "LOW",       bar: "bg-red-400",     text: "text-red-600",     pct:  33 }
      : { label: "NOT FOUND", bar: "bg-slate-300",   text: "text-slate-400",   pct:   0 };

  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${cfg.bar}`} style={{ width: `${cfg.pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${cfg.text}`}>{cfg.label}</span>
    </div>
  );
}

function StatusPill({ status }: { status: FieldStatus }) {
  const cfg: Record<FieldStatus, { label: string; cls: string }> = {
    match:    { label: "Match",    cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    mismatch: { label: "Mismatch", cls: "bg-red-50    text-red-700    border-red-200" },
    uncertain:{ label: "Uncertain",cls: "bg-amber-50  text-amber-700  border-amber-200" },
    no_rule:  { label: "No Rule",  cls: "bg-slate-50  text-slate-500  border-slate-200" },
  };
  const c = cfg[status];
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${c.cls}`}>
      {status === "match" && <span>✓</span>}
      {status === "mismatch" && <span>✗</span>}
      {status === "uncertain" && <span>⚠</span>}
      {c.label}
    </span>
  );
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null;
  const colorMap: Record<string, string> = {
    "Commercial Invoice": "bg-blue-50 text-blue-600 border-blue-100",
    "Bill of Lading": "bg-violet-50 text-violet-600 border-violet-100",
    "Packing List": "bg-teal-50 text-teal-600 border-teal-100",
    "Multiple documents": "bg-orange-50 text-orange-600 border-orange-100",
  };
  const cls = colorMap[source] ?? "bg-slate-50 text-slate-500 border-slate-100";
  const short: Record<string, string> = {
    "Commercial Invoice": "CI",
    "Bill of Lading": "B/L",
    "Packing List": "PL",
    "Multiple documents": "Multi",
  };
  return (
    <span className={`inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cls}`} title={source}>
      {short[source] ?? source}
    </span>
  );
}

function FieldRow({
  field,
  isExpanded,
  onToggle,
  animateIn,
  showSource,
}: {
  field: FieldVerificationResult;
  isExpanded: boolean;
  onToggle: () => void;
  animateIn: boolean;
  showSource: boolean;
}) {
  const isClickable =
    field.status === "mismatch" ||
    field.status === "uncertain" ||
    field.status === "no_rule";

  const leftAccent =
    field.status === "mismatch"
      ? "border-l-4 border-l-red-400"
      : field.status === "uncertain"
      ? "border-l-4 border-l-amber-400"
      : field.status === "no_rule"
      ? "border-l-4 border-l-slate-300"
      : "border-l-4 border-l-transparent";

  const rowBg =
    field.status === "mismatch"
      ? "bg-red-50/30"
      : field.status === "uncertain"
      ? "bg-amber-50/30"
      : "";

  const colSpanDetail = showSource ? 6 : 5;

  return (
    <>
      <tr
        className={`border-b border-slate-100 transition-colors ${leftAccent} ${rowBg} ${animateIn ? "field-enter" : ""} ${isClickable ? "cursor-pointer hover:bg-slate-50" : ""}`}
        onClick={isClickable ? onToggle : undefined}
        title={isClickable ? "Click to expand discrepancy detail" : undefined}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {isClickable && (
              <svg
                className={`w-3 h-3 text-slate-300 flex-shrink-0 transition-transform duration-150 ${isExpanded ? "rotate-90" : ""}`}
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            )}
            {!isClickable && <div className="w-3" />}
            <span className="text-sm font-mono text-slate-700">{field.name}</span>
          </div>
        </td>
        <td className="px-4 py-3 max-w-[150px]">
          {field.extracted != null ? (
            <span className="text-sm text-slate-800 block truncate" title={field.extracted}>
              {field.extracted}
            </span>
          ) : (
            <span className="text-xs italic text-slate-400">not found</span>
          )}
        </td>
        <td className="px-4 py-3 max-w-[150px]">
          {field.expected != null ? (
            <span className="text-sm text-slate-500 block truncate" title={field.expected}>
              {field.expected}
            </span>
          ) : (
            <span className="text-xs italic text-slate-400">—</span>
          )}
        </td>
        <td className="px-4 py-3">
          <StatusPill status={field.status} />
        </td>
        <td className="px-4 py-3">
          <ConfidenceIndicator value={field.confidence} />
        </td>
        {showSource && (
          <td className="px-4 py-3">
            <SourceBadge source={field.source_document} />
          </td>
        )}
      </tr>

      {isExpanded && (
        <tr className="bg-slate-50/80 border-b border-slate-200">
          <td colSpan={colSpanDetail} className="px-6 py-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                  Discrepancy Detail
                </p>
                {field.source_document && (
                  <span className="text-[10px] text-slate-400">
                    · from <span className="font-medium text-slate-500">{field.source_document}</span>
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white border border-slate-200 rounded-lg p-3">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1.5">Extracted from document</p>
                  <p className="font-mono text-sm text-slate-800">
                    {field.extracted ?? <span className="text-slate-400 italic">not found</span>}
                  </p>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1.5">Expected per customer rule</p>
                  <p className="font-mono text-sm text-slate-800">
                    {field.expected ?? <span className="text-slate-400 italic">no rule defined</span>}
                  </p>
                </div>
              </div>
              {field.rule_description && (
                <div className="flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5">
                  <svg className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <p className="text-xs text-blue-800">{field.rule_description}</p>
                </div>
              )}
              {field.confidence < 0.6 && (
                <div className="flex items-start gap-2 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5">
                  <svg className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <p className="text-xs text-amber-800">
                    Extraction confidence: <span className="font-semibold">{field.confidence > 0 ? "LOW" : "NOT FOUND"}</span> — below the HIGH threshold required for auto-approval. Flagged as uncertain regardless of value match.
                  </p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type PageState = "idle" | "streaming" | "complete";
type TabMode = "submit" | "queue";

const STATUS_QUEUE_COLORS: Record<string, string> = {
  approved:           "bg-emerald-50 text-emerald-700 border-emerald-200",
  amendment_required: "bg-red-50 text-red-700 border-red-200",
  uncertain:          "bg-amber-50 text-amber-700 border-amber-200",
  failed:             "bg-slate-50 text-slate-500 border-slate-200",
};
const STATUS_QUEUE_LABELS: Record<string, string> = {
  approved:           "Approved",
  amendment_required: "Amendment Required",
  uncertain:          "Uncertain",
  failed:             "Failed",
};

function QueuePanel({ onOpen }: { onOpen: (id: number) => void }) {
  const [items, setItems] = useState<VerificationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/verify/queue?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.verifications ?? []);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-slate-400">
        <svg className="w-5 h-5 animate-spin mr-2 text-slate-300" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading queue…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
        <p className="text-sm text-slate-400 mb-1">No verifications yet</p>
        <p className="text-xs text-slate-300">
          Drop files into{" "}
          <code className="font-mono bg-slate-100 px-1 rounded">backend/data/incoming/DEMO_CUSTOMER_001/</code>
          {" "}or submit via the Upload tab
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-slate-400">
          {items.length} result{items.length !== 1 ? "s" : ""} · auto-refreshes every 5 s
        </p>
        <button onClick={load} className="text-xs text-blue-500 hover:text-blue-700">Refresh now</button>
      </div>
      {items.map((item) => {
        const statusCls = STATUS_QUEUE_COLORS[item.overall_status] ?? "bg-slate-50 text-slate-500 border-slate-200";
        const statusLabel = STATUS_QUEUE_LABELS[item.overall_status] ?? item.overall_status;
        return (
          <button
            key={item.verification_id}
            className="w-full bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 flex items-center gap-4 hover:bg-slate-50 hover:border-blue-200 transition-all text-left group"
            onClick={() => onOpen(item.verification_id)}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-mono text-slate-400">{item.shipment_id}</span>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${statusCls}`}>
                  {statusLabel}
                </span>
                {item.mismatch_count > 0 && (
                  <span className="text-[10px] text-red-500 font-medium">
                    {item.mismatch_count} issue{item.mismatch_count > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <p className="text-sm font-medium text-slate-700 truncate">{item.customer_name ?? item.customer_id}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-slate-400">{new Date(item.received_at).toLocaleString()}</p>
              <p className="text-[10px] text-slate-300 mt-0.5">{item.field_count} fields checked</p>
            </div>
            <svg className="w-4 h-4 text-slate-200 group-hover:text-blue-400 flex-shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        );
      })}
    </div>
  );
}

export default function VerificationPage() {
  const [tab, setTab] = useState<TabMode>("submit");
  const [pageState, setPageState] = useState<PageState>("idle");
  const [batchMode, setBatchMode] = useState(false);
  const [steps, setSteps] = useState<Step[]>(initialSteps(false));
  const [stageMsg, setStageMsg] = useState("");
  // Map keyed by field name — later events (comparison results) overwrite earlier previews (extraction phase)
  const [liveFieldsMap, setLiveFieldsMap] = useState<Map<string, FieldVerificationResult>>(new Map());
  const [latestField, setLatestField] = useState<string | null>(null);
  const [crossCheckIssues, setCrossCheckIssues] = useState<CrossCheckEvent[]>([]);
  const [detectedDocs, setDetectedDocs] = useState<DocDetectedEvent[]>([]);
  const [result, setResult] = useState<CompleteEvent | null>(null);
  const [draftText, setDraftText] = useState("");
  const [draftSent, setDraftSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState(CUSTOMERS[0].id);
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
  const [uploadedFilename, setUploadedFilename] = useState("");

  // Single mode file ref
  const fileRef = useRef<HTMLInputElement>(null);

  // Batch mode: one ref per slot
  const batchRefs = {
    ci: useRef<HTMLInputElement>(null),
    bl: useRef<HTMLInputElement>(null),
    pl: useRef<HTMLInputElement>(null),
  };
  const [batchFilenames, setBatchFilenames] = useState<Record<BatchKey, string>>({ ci: "", bl: "", pl: "" });

  const selectedCustomer = CUSTOMERS.find((c) => c.id === customerId)!;

  // ── Stream event handler ──────────────────────────────────────────────────

  function applyEvent(event: StreamEvent) {
    switch (event.type) {
      case "stage":
        setStageMsg(event.message);
        setSteps((prev) =>
          prev.map((s) => {
            if (s.id < event.step) return { ...s, status: "done" };
            if (s.id === event.step) return { ...s, status: "active" };
            return { ...s, status: "pending" };
          })
        );
        break;

      case "doc_detected":
        setDetectedDocs((prev) => [...prev, event]);
        break;

      case "cross_check":
        setCrossCheckIssues((prev) => [...prev, event]);
        break;

      case "field":
        setLiveFieldsMap((prev) => {
          const next = new Map(prev);
          next.set(event.name, {
            name: event.name,
            extracted: event.extracted,
            expected: event.expected,
            status: event.status,
            confidence: event.confidence,
            rule_description: event.rule_description,
            source_document: event.source_document ?? null,
          });
          return next;
        });
        setLatestField(event.name);
        break;

      case "complete":
        setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })));
        setStageMsg("");
        setResult(event);
        setDraftText(event.draft_reply);
        setPageState("complete");
        break;

      case "error":
        setError(event.message);
        setPageState("idle");
        break;

      case "warning":
        // non-fatal; could surface in UI but we skip for now
        break;
    }
  }

  // ── Stream reader helper ──────────────────────────────────────────────────

  async function consumeStream(response: Response) {
    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;
        try {
          applyEvent(JSON.parse(json) as StreamEvent);
        } catch {
          // malformed — skip
        }
      }
    }
  }

  // ── Single-doc submit ─────────────────────────────────────────────────────

  async function handleSingleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    resetState(file.name);

    const body = new FormData();
    body.append("file", file);
    body.append("customer_id", customerId);

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/verify/submit/stream`, { method: "POST", body });
      await consumeStream(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed — please try again.");
      setPageState("idle");
    }
  }

  // ── Batch submit ──────────────────────────────────────────────────────────

  async function handleBatchSubmit(e: React.FormEvent) {
    e.preventDefault();

    const files = BATCH_SLOTS
      .map((s) => batchRefs[s.key].current?.files?.[0])
      .filter((f): f is File => f !== null && f !== undefined);

    if (files.length === 0) return;

    const names = files.map((f) => f.name).join(", ");
    resetState(names);

    const body = new FormData();
    for (const f of files) body.append("files", f);
    body.append("customer_id", customerId);

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/verify/submit-batch/stream`, { method: "POST", body });
      await consumeStream(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Batch verification failed — please try again.");
      setPageState("idle");
    }
  }

  function resetState(filename: string) {
    setError(null);
    setLiveFieldsMap(new Map());
    setLatestField(null);
    setResult(null);
    setDraftSent(false);
    setExpandedFields(new Set());
    setCrossCheckIssues([]);
    setDetectedDocs([]);
    setSteps(initialSteps(batchMode));
    setStageMsg("Connecting…");
    setUploadedFilename(filename);
    setPageState("streaming");
  }

  function toggleField(name: string) {
    setExpandedFields((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function handleReset() {
    setPageState("idle");
    setResult(null);
    setError(null);
    setDraftText("");
    setDraftSent(false);
    setLiveFieldsMap(new Map());
    setLatestField(null);
    setExpandedFields(new Set());
    setCrossCheckIssues([]);
    setDetectedDocs([]);
    setSteps(initialSteps(batchMode));
    setStageMsg("");
    setBatchFilenames({ ci: "", bl: "", pl: "" });
    if (fileRef.current) fileRef.current.value = "";
    for (const ref of Object.values(batchRefs)) {
      if (ref.current) ref.current.value = "";
    }
  }

  // ── Load a stored result from the queue into the complete-state view ──────
  async function loadFromQueue(id: number) {
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/verify/result/${id}`);
      if (!res.ok) return;
      const data = await res.json();

      // Populate liveFieldsMap from stored fields
      const map = new Map<string, FieldVerificationResult>();
      for (const f of (data.fields ?? [])) {
        map.set(f.name, f);
      }
      setLiveFieldsMap(map);
      setLatestField(null);
      setCrossCheckIssues([]);
      setDetectedDocs([]);
      setExpandedFields(new Set());
      setSteps(initialSteps(false).map((s) => ({ ...s, status: "done" as StepStatus })));
      setStageMsg("");
      setResult({
        type: "complete",
        verification_id: data.verification_id,
        shipment_id: data.shipment_id,
        received_at: data.received_at,
        customer_id: data.customer_id,
        customer_name: data.customer_name,
        overall_status: data.overall_status,
        draft_reply: data.draft_reply,
      });
      setDraftText(data.draft_reply ?? "");
      setDraftSent(false);
      setPageState("complete");
      setTab("submit");
    } catch {/* ignore */}
  }

  // ── Render ────────────────────────────────────────────────────────────────

  // Derived array — Map preserves insertion order; later events overwrite earlier by key
  const liveFields = Array.from(liveFieldsMap.values());

  const matchCount    = liveFields.filter((f) => f.status === "match").length;
  const mismatchCount = liveFields.filter((f) => f.status === "mismatch").length;
  const uncertainCount = liveFields.filter((f) => f.status === "uncertain").length;
  const noRuleCount   = liveFields.filter((f) => f.status === "no_rule").length;
  const hasSourceInfo = liveFields.some((f) => f.source_document !== null);

  return (
    <div className="min-h-screen bg-slate-50">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900 leading-none">Document Verification</h1>
              <p className="text-[10px] text-slate-400 mt-0.5">SU → CG workflow · Part 2</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Tab switcher */}
            <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
              <button
                onClick={() => setTab("submit")}
                className={`text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${tab === "submit" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              >
                Upload
              </button>
              <button
                onClick={() => setTab("queue")}
                className={`text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${tab === "queue" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              >
                Queue
              </button>
            </div>
            {tab === "submit" && (pageState === "streaming" || pageState === "complete") && (
              <button
                onClick={handleReset}
                className="text-xs text-slate-400 hover:text-slate-700 border border-slate-200 rounded-lg px-3 py-1.5 transition-colors"
              >
                ← New submission
              </button>
            )}
            <a href="/" className="text-xs text-slate-400 hover:text-slate-700 transition-colors">
              Analytics &amp; Docs →
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-5">

        {/* ── Queue tab ──────────────────────────────────────────────────── */}
        {tab === "queue" && <QueuePanel onOpen={loadFromQueue} />}

        {/* ── Submit tab ─────────────────────────────────────────────────── */}
        {tab === "submit" && <>

        {/* ── IDLE: Upload form ───────────────────────────────────────────── */}
        {pageState === "idle" && (
          <div className="grid grid-cols-5 gap-5">

            {/* Upload card — 3 cols */}
            <div className="col-span-3 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              {/* Mode toggle */}
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">
                    {batchMode ? "Submit 3-Document Shipment Set" : "Submit SU Document"}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {batchMode
                      ? "Upload CI + B/L + PL together — agent extracts, cross-checks, and verifies as one shipment"
                      : "Simulates an SU email arriving with an attached trade document"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setBatchMode((v) => !v);
                    setError(null);
                  }}
                  className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
                    batchMode
                      ? "bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                      : "bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-blue-600"
                  }`}
                >
                  {batchMode ? "▦ Batch mode" : "Switch to Batch"}
                </button>
              </div>

              {error && (
                <div className="mx-6 mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <svg className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <p className="text-xs text-red-700">{error}</p>
                </div>
              )}

              {/* ── Single mode form ─────────────────────────────────────── */}
              {!batchMode && (
                <form onSubmit={handleSingleSubmit} className="p-6 space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1.5">Customer</label>
                    <select
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                      className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-slate-800"
                    >
                      {CUSTOMERS.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1.5">Trade Document</label>
                    <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-slate-200 rounded-xl py-6 px-4 cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-all group">
                      <svg className="w-8 h-8 text-slate-300 group-hover:text-blue-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="text-xs text-slate-400 group-hover:text-blue-500 transition-colors">
                        Click to choose or drop a file here
                      </span>
                      <span className="text-[10px] text-slate-300">PDF, PNG or JPEG · max 10 MB</span>
                      <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" required className="hidden" />
                    </label>
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Submit for Verification
                  </button>

                  <p className="text-[10px] text-slate-400 text-center">
                    Trigger:{" "}
                    <code className="font-mono bg-slate-100 px-1 rounded">POST /api/verify/submit/stream</code>
                  </p>
                </form>
              )}

              {/* ── Batch mode form ──────────────────────────────────────── */}
              {batchMode && (
                <form onSubmit={handleBatchSubmit} className="p-6 space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1.5">Customer</label>
                    <select
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                      className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-slate-800"
                    >
                      {CUSTOMERS.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-medium text-slate-600">
                      Documents <span className="text-slate-400 font-normal">(upload any combination — auto-detected)</span>
                    </label>
                    {BATCH_SLOTS.map((slot) => {
                      const colors = SLOT_COLORS[slot.color];
                      const filename = batchFilenames[slot.key];
                      return (
                        <label key={slot.key} className={`flex items-center gap-3 border-2 border-dashed ${colors.border} rounded-xl px-4 py-3 cursor-pointer hover:${colors.ring} transition-all group`}>
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 border ${colors.badge}`}>
                            <span className="text-[10px] font-bold">{slot.hint}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-slate-700">{slot.label}</p>
                            <p className="text-[10px] text-slate-400 truncate">
                              {filename || "Click to choose PDF, PNG or JPEG"}
                            </p>
                          </div>
                          {filename && (
                            <svg className="w-4 h-4 text-emerald-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          )}
                          <input
                            ref={batchRefs[slot.key]}
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              setBatchFilenames((prev) => ({ ...prev, [slot.key]: f?.name ?? "" }));
                            }}
                          />
                        </label>
                      );
                    })}
                  </div>

                  <button
                    type="submit"
                    disabled={Object.values(batchFilenames).every((v) => !v)}
                    className="w-full py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Verify All Documents
                  </button>

                  <p className="text-[10px] text-slate-400 text-center">
                    Trigger:{" "}
                    <code className="font-mono bg-slate-100 px-1 rounded">POST /api/verify/submit-batch/stream</code>
                    {" "}· auto-detects each document type
                  </p>
                </form>
              )}
            </div>

            {/* Rules preview card — 2 cols */}
            <div className="col-span-2 space-y-4">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 h-full">
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-3">
                  Active Rules
                </p>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <p className="text-sm font-semibold text-slate-800">{selectedCustomer.name}</p>
                </div>
                <p className="text-[10px] font-mono text-slate-400 mb-4">{selectedCustomer.id}</p>
                <div className="space-y-2">
                  {selectedCustomer.rulesPreview.split(" · ").map((rule) => (
                    <div key={rule} className="flex items-center gap-2 text-xs text-slate-600">
                      <svg className="w-3 h-3 text-slate-300 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {rule}
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-slate-100 space-y-1">
                  <p className="text-[10px] text-slate-400">
                    <span className="font-medium text-slate-500">{selectedCustomer.ruleCount} rules</span> active for this customer
                  </p>
                  <p className="text-[10px] text-slate-400">
                    Confidence threshold: <span className="font-medium text-slate-500">60%</span>
                  </p>
                  {batchMode && (
                    <p className="text-[10px] text-slate-400 mt-1 pt-1 border-t border-slate-100">
                      Batch mode cross-checks shared fields (port, incoterms, HS code…) across all 3 documents before comparing against rules.
                    </p>
                  )}
                </div>
              </div>
            </div>

          </div>
        )}

        {/* ── STREAMING + COMPLETE ────────────────────────────────────────── */}
        {(pageState === "streaming" || pageState === "complete") && (
          <>
            {/* Pipeline progress card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  {result ? (
                    <div className="space-y-0.5">
                      <p className="text-xs font-mono text-slate-400">{result.shipment_id}</p>
                      <p className="text-sm font-semibold text-slate-800">{result.customer_name ?? result.customer_id}</p>
                      <p className="text-xs text-slate-400">{new Date(result.received_at).toLocaleString()}</p>
                      {result.documents_processed && (
                        <div className="flex gap-1 mt-1">
                          {result.documents_processed.map((d) => (
                            <SourceBadge key={d.doc_type} source={d.label} />
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-xs text-slate-400">Processing</p>
                      <p className="text-sm font-semibold text-slate-800">{selectedCustomer.name}</p>
                      <p className="text-xs text-slate-400 truncate max-w-xs">{uploadedFilename}</p>
                      {detectedDocs.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {detectedDocs.map((d) => (
                            <span key={d.filename} className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                              {d.filename} → <span className="font-medium">{d.label}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Live field count badges */}
                {liveFields.length > 0 && (
                  <div className="flex flex-wrap gap-2 text-xs">
                    {matchCount > 0 && (
                      <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-1 rounded-full font-medium">
                        {matchCount} matched
                      </span>
                    )}
                    {mismatchCount > 0 && (
                      <span className="bg-red-50 text-red-700 border border-red-200 px-2 py-1 rounded-full font-medium">
                        {mismatchCount} mismatched
                      </span>
                    )}
                    {uncertainCount > 0 && (
                      <span className="bg-amber-50 text-amber-700 border border-amber-200 px-2 py-1 rounded-full font-medium">
                        {uncertainCount} uncertain
                      </span>
                    )}
                    {noRuleCount > 0 && (
                      <span className="bg-slate-50 text-slate-500 border border-slate-200 px-2 py-1 rounded-full font-medium">
                        {noRuleCount} no rule
                      </span>
                    )}
                    {crossCheckIssues.length > 0 && (
                      <span className="bg-orange-50 text-orange-700 border border-orange-200 px-2 py-1 rounded-full font-medium">
                        {crossCheckIssues.length} cross-doc conflict{crossCheckIssues.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                )}
              </div>

              <PipelineBar steps={steps} message={stageMsg} />
            </div>

            {/* Cross-document conflict callouts */}
            {crossCheckIssues.length > 0 && (
              <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <p className="text-xs font-semibold text-orange-800">
                    Cross-Document Inconsistencies Detected
                  </p>
                </div>
                {crossCheckIssues.map((issue) => (
                  <div key={issue.field} className="bg-white border border-orange-100 rounded-lg px-3 py-2">
                    <p className="text-[10px] font-semibold text-orange-700 uppercase tracking-wide mb-0.5">{issue.field}</p>
                    <p className="text-xs text-slate-700 font-mono">{issue.conflict}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Status banner — appears only after complete */}
            {pageState === "complete" && result && (
              <StatusBanner status={result.overall_status} />
            )}

            {/* Live field table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Field Verification</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {pageState === "streaming"
                      ? "Fields streaming live — extraction previews update with comparison results"
                      : "Click a flagged row to expand the discrepancy detail"}
                  </p>
                </div>
                {pageState === "streaming" && (
                  <div className="flex items-center gap-1.5 text-xs text-blue-500">
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {liveFields.length > 0 ? "live…" : "extracting…"}
                  </div>
                )}
              </div>

              <table className="w-full">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    {["Field", "Extracted", "Expected", "Status", "Confidence", ...(hasSourceInfo ? ["Source"] : [])].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {liveFields.length === 0 ? (
                    <tr>
                      <td colSpan={hasSourceInfo ? 6 : 5} className="px-4 py-10 text-center text-sm text-slate-400">
                        <svg className="w-6 h-6 text-slate-200 animate-spin mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Waiting for field results…
                      </td>
                    </tr>
                  ) : (
                    liveFields.map((field) => (
                      <FieldRow
                        key={field.name}
                        field={field}
                        isExpanded={expandedFields.has(field.name)}
                        onToggle={() => toggleField(field.name)}
                        animateIn={field.name === latestField}
                        showSource={hasSourceInfo}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Draft reply — shown only on complete */}
            {pageState === "complete" && result && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Draft Reply to SU</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Agent-generated — edit before sending.{" "}
                      <strong className="text-slate-500">Agent never sends autonomously.</strong>
                    </p>
                  </div>
                  {draftSent && (
                    <span className="text-xs text-emerald-700 font-medium bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                      ✓ Sent to SU
                    </span>
                  )}
                </div>

                <div className="bg-slate-50 border-b border-slate-200 px-5 py-2.5 grid grid-cols-3 gap-4 text-xs text-slate-500">
                  <span><span className="text-slate-400">To:</span> Shipping Unit</span>
                  <span><span className="text-slate-400">From:</span> Cargo Control Group</span>
                  <span><span className="text-slate-400">Re:</span> Verification — {result.shipment_id}</span>
                </div>

                <div className="p-5">
                  <textarea
                    value={draftText}
                    onChange={(e) => setDraftText(e.target.value)}
                    disabled={draftSent}
                    rows={11}
                    className="w-full text-sm font-mono text-slate-700 border border-slate-200 rounded-lg p-4 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y disabled:bg-slate-50 disabled:text-slate-400"
                  />

                  {!draftSent && (
                    <div className="flex gap-3 mt-3">
                      <button
                        onClick={() => setDraftSent(true)}
                        className="flex-1 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        Send to SU
                      </button>
                      <button
                        onClick={() => setDraftText(result.draft_reply)}
                        className="py-2.5 px-5 border border-slate-200 text-slate-500 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
                      >
                        Reset draft
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        </> /* end submit tab */}

      </main>
    </div>
  );
}
