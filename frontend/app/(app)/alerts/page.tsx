"use client";

import { AlertCircle, Check, CheckCheck } from "lucide-react";
import { useState } from "react";

import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAcknowledgeAlert, useAlerts, useResolveAlert } from "@/hooks/api-hooks";
import { cn, formatDateTime } from "@/lib/utils";

const SEVERITY_STYLES: Record<string, string> = {
  low: "border-l-slate-400",
  medium: "border-l-risk-medium",
  high: "border-l-risk-high",
  critical: "border-l-risk-critical",
};

export default function AlertsPage() {
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const { data, isLoading, isError, refetch } = useAlerts({ severity: severity || undefined, status: status || undefined });
  const acknowledge = useAcknowledgeAlert();
  const resolve = useResolveAlert();

  const alerts = data?.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Alert Center</h1>
        <p className="text-sm text-muted-foreground">Deterministic, rule-based operational alerts</p>
      </div>

      <div className="flex gap-2">
        <NativeSelect className="w-40" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </NativeSelect>
        <NativeSelect className="w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </NativeSelect>
      </div>

      {isError ? (
        <ErrorState message="Couldn't load alerts." onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 p-12 text-center text-muted-foreground">
            <AlertCircle className="h-8 w-8" />
            No alerts match your filters.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <Card key={a.id} className={cn("border-l-4", SEVERITY_STYLES[a.severity])}>
              <CardContent className="flex items-start justify-between gap-4 p-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={a.severity === "critical" ? "destructive" : "outline"} className="uppercase">
                      {a.severity}
                    </Badge>
                    <p className="font-medium">{a.title}</p>
                  </div>
                  <p className="text-sm text-muted-foreground">{a.description}</p>
                  {a.recommended_action && (
                    <p className="text-sm text-primary">→ {a.recommended_action}</p>
                  )}
                  <p className="text-xs text-muted-foreground">{formatDateTime(a.created_at)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {a.status === "open" && (
                    <Button size="sm" variant="outline" onClick={() => acknowledge.mutate(a.id)}>
                      <Check className="h-3.5 w-3.5" /> Acknowledge
                    </Button>
                  )}
                  {a.status !== "resolved" && (
                    <Button size="sm" onClick={() => resolve.mutate(a.id)}>
                      <CheckCheck className="h-3.5 w-3.5" /> Resolve
                    </Button>
                  )}
                  {a.status === "resolved" && (
                    <Badge variant="success">Resolved</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
