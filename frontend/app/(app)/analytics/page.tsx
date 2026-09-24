"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ProvenanceBadge } from "@/components/provenance-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalytics, useDashboard, useModels } from "@/hooks/api-hooks";
import { formatCurrency } from "@/lib/utils";

interface DimensionRow {
  dimension: string;
  total: number;
  delayed: number;
  delay_rate: number;
  avg_delivery_days: number;
}

interface RootCauseFactor {
  factor_name: string;
  contribution_pct: number;
  rank: number;
  supporting_metric: string;
}

function DimensionChart({ data }: { data: DimensionRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis dataKey="dimension" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={70} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={40} />
        <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
        <Bar dataKey="delay_rate" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function AnalyticsPage() {
  const routes = useAnalytics("routes");
  const products = useAnalytics("products");
  const risk = useAnalytics("risk");
  const { data: dashboard } = useDashboard();
  const { data: models } = useModels();

  const kpis = dashboard?.data.kpis;
  const rootCauses = (risk.data?.data.top_root_causes ?? []) as RootCauseFactor[];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">Route, product, risk, financial, and model analytics</p>
      </div>

      <Tabs defaultValue="routes">
        <TabsList>
          <TabsTrigger value="routes">Route Analytics</TabsTrigger>
          <TabsTrigger value="products">Product Analytics</TabsTrigger>
          <TabsTrigger value="risk">Risk & Root Cause</TabsTrigger>
          <TabsTrigger value="financial">Financial Impact</TabsTrigger>
          <TabsTrigger value="model">Model Performance</TabsTrigger>
        </TabsList>

        <TabsContent value="routes">
          <Card>
            <CardHeader>
              <CardTitle>Delay Rate by Destination Region</CardTitle>
            </CardHeader>
            <CardContent>
              {routes.data && <DimensionChart data={(routes.data.data.by_region as DimensionRow[]) ?? []} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="products">
          <Card>
            <CardHeader>
              <CardTitle>Delay Rate by Product Category</CardTitle>
            </CardHeader>
            <CardContent>
              {products.data && <DimensionChart data={(products.data.data.by_category as DimensionRow[]) ?? []} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risk">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                Top Root Cause Factors <ProvenanceBadge kind="DERIVED" />
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Deterministic variance-attribution ranking, not a causal model — see docs/ml-system.md.
              </p>
              {rootCauses.map((f) => (
                <div key={f.rank} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">
                      {f.rank}. {f.factor_name}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{f.contribution_pct.toFixed(1)}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${f.contribution_pct}%` }} />
                  </div>
                  <p className="text-xs text-muted-foreground">{f.supporting_metric}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="financial">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                Financial Impact <ProvenanceBadge kind="ESTIMATED" />
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {kpis && (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <FinancialStat label="Value at Risk" value={formatCurrency(kpis.estimated_value_at_risk)} />
                  <FinancialStat label="Profit at Risk" value={formatCurrency(kpis.profit_at_risk)} />
                  <FinancialStat label="At-Risk Shipments" value={kpis.at_risk_shipments.toLocaleString()} />
                </div>
              )}
              <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                <p className="mb-1 font-medium text-foreground">Assumptions</p>
                <ul className="list-inside list-disc space-y-1">
                  <li>Value/Profit at Risk = SUM(sales or profit) over shipments currently HIGH or CRITICAL risk.</li>
                  <li>This is order value exposed to modeled delay risk, not a forecast of realized loss.</li>
                  <li>What-if scenario cost deltas use an assumed shipping-mode cost multiplier (see shipment detail).</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="model">
          <Card>
            <CardHeader>
              <CardTitle>Model Registry</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(models?.data ?? []).map((m) => {
                const model = m as { id: number; version: string; algorithm: string; status: string; metrics: Record<string, number> };
                return (
                  <div key={model.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <p className="font-medium">
                        {model.version} ({model.algorithm})
                      </p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${model.status === "active" ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"}`}
                      >
                        {model.status}
                      </span>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-4">
                      <span>ROC-AUC: {model.metrics?.roc_auc?.toFixed(3)}</span>
                      <span>PR-AUC: {model.metrics?.pr_auc?.toFixed(3)}</span>
                      <span>Recall: {model.metrics?.recall?.toFixed(3)}</span>
                      <span>Precision: {model.metrics?.precision?.toFixed(3)}</span>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FinancialStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}
