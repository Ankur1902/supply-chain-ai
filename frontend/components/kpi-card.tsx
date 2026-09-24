import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { Provenance } from "@/components/provenance-badge";
import { ProvenanceBadge } from "@/components/provenance-badge";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  provenance: Provenance;
  tone?: "default" | "warning" | "danger";
  subtext?: string;
}

const TONE_STYLES = {
  default: "text-foreground",
  warning: "text-risk-medium",
  danger: "text-risk-critical",
};

export function KpiCard({ label, value, icon: Icon, provenance, tone = "default", subtext }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-2 p-4">
        <div className="min-w-0 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          </div>
          <p className={cn("text-2xl font-semibold tabular-nums", TONE_STYLES[tone])}>{value}</p>
          <div className="flex items-center gap-1.5">
            <ProvenanceBadge kind={provenance} />
            {subtext && <span className="text-xs text-muted-foreground">{subtext}</span>}
          </div>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Icon className="h-4.5 w-4.5 text-muted-foreground" />
        </div>
      </CardContent>
    </Card>
  );
}
