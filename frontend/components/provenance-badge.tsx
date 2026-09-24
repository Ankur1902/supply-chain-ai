import { cn } from "@/lib/utils";

/**
 * Section 52 (anti-hallucination rule): every value in the UI must be
 * classified as SOURCE DATA, DERIVED, PREDICTED, ESTIMATED, SYNTHETIC, or
 * AI-GENERATED. This badge is the visual mechanism for that — used next to
 * KPIs, supplier fields, and AI output throughout the app so a viewer never
 * has to guess where a number came from.
 */
export type Provenance = "SOURCE" | "DERIVED" | "PREDICTED" | "ESTIMATED" | "SYNTHETIC" | "AI-GENERATED";

const STYLES: Record<Provenance, string> = {
  SOURCE: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  DERIVED: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  PREDICTED: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  ESTIMATED: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  SYNTHETIC: "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
  "AI-GENERATED": "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
};

const LABELS: Record<Provenance, string> = {
  SOURCE: "Source data",
  DERIVED: "Derived",
  PREDICTED: "ML prediction",
  ESTIMATED: "Estimated",
  SYNTHETIC: "Synthetic demo data",
  "AI-GENERATED": "AI-generated",
};

export function ProvenanceBadge({ kind, className }: { kind: Provenance; className?: string }) {
  return (
    <span
      title={LABELS[kind]}
      className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide", STYLES[kind], className)}
    >
      {LABELS[kind]}
    </span>
  );
}
