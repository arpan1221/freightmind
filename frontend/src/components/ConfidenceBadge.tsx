import type { ConfidenceLevel } from "@/types/api";

interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
}

const styles: Record<ConfidenceLevel, string> = {
  HIGH: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  MEDIUM: "bg-amber-50 text-amber-700 border border-amber-200",
  LOW: "bg-red-50 text-red-700 border border-red-200",
  NOT_FOUND: "bg-slate-50 text-slate-500 border border-slate-200",
};

const labels: Record<ConfidenceLevel, string> = {
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
  NOT_FOUND: "Not found",
};

export default function ConfidenceBadge({ level }: ConfidenceBadgeProps) {
  return (
    <span
      className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${styles[level]}`}
    >
      {labels[level]}
    </span>
  );
}
