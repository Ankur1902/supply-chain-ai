"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ProvenanceBadge } from "@/components/provenance-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSupplier } from "@/hooks/api-hooks";
import { formatDate, formatPercent } from "@/lib/utils";

const COMPONENT_LABELS: Record<string, string> = {
  reliability_component: "Reliability (25%)",
  delivery_component: "Delivery Performance (25%)",
  quality_component: "Quality (15%)",
  lead_time_component: "Lead Time (15%)",
  cost_component: "Cost (10%)",
  risk_component: "Risk (10%)",
};

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading } = useSupplier(Number(params.id));
  const supplier = data?.data;

  if (isLoading || !supplier) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/suppliers" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold">{supplier.supplier_name}</h1>
          <p className="text-sm text-muted-foreground">
            {supplier.supplier_code} · {supplier.supplier_region}
          </p>
        </div>
        {supplier.is_synthetic && <ProvenanceBadge kind="SYNTHETIC" />}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Supplier Score</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-semibold tabular-nums">{supplier.score?.toFixed(0) ?? "—"}</p>
            <p className="text-xs text-muted-foreground">out of 100 · <ProvenanceBadge kind="DERIVED" /></p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <Badge variant="outline" className="capitalize">{supplier.supplier_tier}</Badge>
              <Badge variant="outline">{supplier.product_category}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Score Breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {supplier.score_breakdown &&
              Object.entries(supplier.score_breakdown).map(([key, value]) => (
                <div key={key} className="flex items-center gap-3 text-sm">
                  <span className="w-48 shrink-0 text-muted-foreground">{COMPONENT_LABELS[key] ?? key}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${value}%` }} />
                  </div>
                  <span className="w-10 text-right tabular-nums">{value.toFixed(0)}</span>
                </div>
              ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MiniStat label="Delay Rate" value={supplier.delay_rate !== null ? formatPercent(supplier.delay_rate) : "—"} provenance="DERIVED" />
        <MiniStat label="Avg Lead Time" value={supplier.avg_lead_time_days !== null ? `${supplier.avg_lead_time_days.toFixed(1)}d` : "—"} provenance="DERIVED" />
        <MiniStat label="Order Volume" value={supplier.order_volume?.toString() ?? "—"} provenance="SOURCE" />
        <MiniStat label="Risk Score" value={supplier.risk_score.toFixed(0)} provenance="SYNTHETIC" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Score Trend</CardTitle>
          </CardHeader>
          <CardContent className="h-56">
            {supplier.trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={supplier.trend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="period_start" tick={{ fontSize: 11 }} tickFormatter={(v) => formatDate(v).slice(0, 6)} />
                  <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} width={30} />
                  <Tooltip labelFormatter={(l) => formatDate(l)} />
                  <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Not enough history yet.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Delay Rate Trend</CardTitle>
          </CardHeader>
          <CardContent className="h-56">
            {supplier.trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={supplier.trend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="period_start" tick={{ fontSize: 11 }} tickFormatter={(v) => formatDate(v).slice(0, 6)} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={40} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} labelFormatter={(l) => formatDate(l)} />
                  <Bar dataKey="delay_rate" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Not enough history yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MiniStat({ label, value, provenance }: { label: string; value: string; provenance: "SOURCE" | "DERIVED" | "SYNTHETIC" }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold tabular-nums">{value}</p>
        <ProvenanceBadge kind={provenance} className="mt-1" />
      </CardContent>
    </Card>
  );
}
