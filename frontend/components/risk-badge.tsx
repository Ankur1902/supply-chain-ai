import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/types/api";

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-risk-low/15 text-risk-low border-risk-low/30",
  MEDIUM: "bg-risk-medium/15 text-risk-medium border-risk-medium/30",
  HIGH: "bg-risk-high/15 text-risk-high border-risk-high/30",
  CRITICAL: "bg-risk-critical/15 text-risk-critical border-risk-critical/30 font-semibold",
};

export function RiskBadge({ level, score }: { level: RiskLevel | null; score?: number | null }) {
  if (!level) {
    return (
      <span className="inline-flex items-center rounded-full border border-dashed px-2.5 py-0.5 text-xs text-muted-foreground">
        Unscored
      </span>
    );
  }
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs", RISK_STYLES[level])}>
      {level}
      {score !== undefined && score !== null ? ` · ${score.toFixed(0)}` : ""}
    </span>
  );
}
