"use client";

import { AlertOctagon, Clock, DollarSign, Package, ShieldAlert, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { useDashboard } from "@/hooks/api-hooks";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils";

const RISK_COLORS: Record<string, string> = {
  LOW: "hsl(var(--risk-low))",
  MEDIUM: "hsl(var(--risk-medium))",
  HIGH: "hsl(var(--risk-high))",
  CRITICAL: "hsl(var(--risk-critical))",
  UNSCORED: "hsl(var(--muted-foreground))",
};

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useDashboard();
  const kpis = data?.data.kpis;
  const charts = data?.data.charts;

  if (isError) {
    return <ErrorState message="Couldn't load the dashboard." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Executive Overview</h1>
        <p className="text-sm text-muted-foreground">Real-time supply-chain risk and delay analytics</p>
      </div>

      {isLoading || !kpis ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Total Shipments" value={formatNumber(kpis.total_shipments)} icon={Package} provenance="SOURCE" />
          <KpiCard
            label="At-Risk Shipments"
            value={formatNumber(kpis.at_risk_shipments)}
            icon={ShieldAlert}
            provenance="PREDICTED"
            tone="warning"
            subtext={formatPercent(kpis.at_risk_rate)}
          />
          <KpiCard
            label="Critical Shipments"
            value={formatNumber(kpis.critical_shipments)}
            icon={AlertOctagon}
            provenance="PREDICTED"
            tone="danger"
            subtext={formatPercent(kpis.critical_rate)}
          />
          <KpiCard label="Delay Rate" value={formatPercent(kpis.delay_rate)} icon={TrendingUp} provenance="SOURCE" />
          <KpiCard
            label="Avg Delivery Time"
            value={`${kpis.average_delivery_time.toFixed(1)}d`}
            icon={Clock}
            provenance="SOURCE"
            subtext={`scheduled ${kpis.average_scheduled_days.toFixed(1)}d`}
          />
          <KpiCard
            label="Value at Risk"
            value={formatCurrency(kpis.estimated_value_at_risk)}
            icon={DollarSign}
            provenance="ESTIMATED"
            tone="warning"
          />
          <KpiCard
            label="Profit at Risk"
            value={formatCurrency(kpis.profit_at_risk)}
            icon={DollarSign}
            provenance="ESTIMATED"
          />
          <KpiCard
            label="Supplier Health"
            value={kpis.supplier_health_avg_score !== null ? kpis.supplier_health_avg_score.toFixed(0) : "—"}
            icon={ShieldAlert}
            provenance="DERIVED"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Delay Rate Trend</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {charts && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={charts.delay_trend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(0, 7)} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={40} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} labelFormatter={(l) => l} />
                  <Line type="monotone" dataKey="delay_rate" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk Distribution</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {charts && (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={charts.risk_distribution}
                    dataKey="count"
                    nameKey="risk_level"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                  >
                    {charts.risk_distribution.map((entry) => (
                      <Cell key={entry.risk_level} fill={RISK_COLORS[entry.risk_level] ?? "#999"} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Delay Rate by Shipping Mode</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            {charts && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={charts.delay_by_shipping_mode} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                  <YAxis type="category" dataKey="dimension" tick={{ fontSize: 11 }} width={90} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  <Bar dataKey="delay_rate" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Delay Rate by Region</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            {charts && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={charts.delay_by_region}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="dimension" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={70} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={40} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  <Bar dataKey="delay_rate" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
