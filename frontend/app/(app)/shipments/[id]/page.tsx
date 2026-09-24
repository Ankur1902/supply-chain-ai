"use client";

import { ArrowLeft, ArrowRight, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ProvenanceBadge } from "@/components/provenance-badge";
import { RiskBadge } from "@/components/risk-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunScenario, useShipment } from "@/hooks/api-hooks";
import { cn, formatCurrency, formatDateTime, formatFeatureValue, formatPercent } from "@/lib/utils";
import type { ScenarioResult } from "@/types/api";

const SHIPPING_MODES = ["Standard Class", "First Class", "Second Class", "Same Day"];

export default function ShipmentDetailPage() {
  const params = useParams<{ id: string }>();
  const shipmentId = Number(params.id);
  const { data, isLoading } = useShipment(shipmentId);
  const shipment = data?.data;

  const [scenarioMode, setScenarioMode] = useState("");
  const [scenarioBuffer, setScenarioBuffer] = useState(0);
  const runScenario = useRunScenario();
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);

  const handleRunScenario = () => {
    if (!shipment) return;
    runScenario.mutate(
      {
        shipment_code: shipment.shipment_code,
        shipping_mode: scenarioMode || undefined,
        scheduled_shipping_days:
          scenarioBuffer > 0 ? shipment.scheduled_shipping_days + scenarioBuffer : undefined,
      },
      { onSuccess: (res) => setScenarioResult(res.data) }
    );
  };

  if (isLoading || !shipment) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/shipments" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold">{shipment.shipment_code}</h1>
          <p className="text-sm text-muted-foreground">Ordered {formatDateTime(shipment.order_date)}</p>
        </div>
        <RiskBadge level={shipment.risk_level} score={shipment.risk_score} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Overview */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Overview</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Field label="Product" value={shipment.product_name} />
            <Field label="Category" value={shipment.product_category} />
            <Field label="Customer segment" value={shipment.customer_segment} />
            <Field label="Supplier" value={shipment.supplier_name} link={`/suppliers/${shipment.supplier_id}`} />
            <Field label="Shipping mode" value={shipment.shipping_mode} />
            <Field label="Scheduled days" value={String(shipment.scheduled_shipping_days)} />
            <Field label="Route" value={`${shipment.origin_market} → ${shipment.destination_region}`} />
            <Field label="Order quantity" value={String(shipment.order_item_quantity)} />
            <Field label="Sales" value={formatCurrency(shipment.sales)} />
            <Field label="Order profit" value={formatCurrency(shipment.order_profit_per_order)} />
            <Field label="Discount rate" value={formatPercent(shipment.discount_rate)} />
            <Field label="Status" value={shipment.status} />
          </CardContent>
        </Card>

        {/* Historical outcome (post-outcome, clearly labeled) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              Historical Outcome <ProvenanceBadge kind="SOURCE" />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Field label="Delivery status" value={shipment.delivery_status} />
            <Field label="Actual transit days" value={String(shipment.days_for_shipping_real)} />
            <Field label="Was late" value={shipment.late_delivery_risk ? "Yes" : "No"} />
            <p className="pt-2 text-xs text-muted-foreground">
              These fields describe what actually happened and were NEVER used as model inputs — see the
              prediction below for the pre-outcome risk estimate.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Prediction + SHAP */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            ML Risk Prediction <ProvenanceBadge kind="PREDICTED" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          {shipment.prediction ? (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <p className="text-3xl font-semibold tabular-nums">{shipment.prediction.risk_score.toFixed(1)}</p>
                <p className="text-xs text-muted-foreground">
                  Risk score (0-100) · model {shipment.prediction.model_version} · scored{" "}
                  {formatDateTime(shipment.prediction.predicted_at)}
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Top contributing factors (SHAP)
                </p>
                {shipment.prediction.risk_factors.map((f) => (
                  <div key={f.feature_name} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-1.5">
                      {f.direction === "positive" ? (
                        <TrendingUp className="h-3.5 w-3.5 text-risk-high" />
                      ) : (
                        <TrendingDown className="h-3.5 w-3.5 text-risk-low" />
                      )}
                      {f.feature_name.replace(/_/g, " ")}:{" "}
                      <span className="text-muted-foreground">{formatFeatureValue(f.feature_value)}</span>
                    </span>
                    <span className={cn("tabular-nums", f.direction === "positive" ? "text-risk-high" : "text-risk-low")}>
                      {f.shap_value > 0 ? "+" : ""}
                      {f.shap_value.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No prediction available for this shipment yet.</p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Sparkles className="h-4 w-4" /> AI Recommendations <ProvenanceBadge kind="AI-GENERATED" />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {shipment.recommendations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No recommendations generated (shipment is not currently HIGH/CRITICAL risk).
              </p>
            ) : (
              shipment.recommendations.map((r) => (
                <div key={r.id} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{r.recommendation_text}</p>
                    <span className="text-xs text-muted-foreground">{formatPercent(r.confidence, 0)} confidence</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{r.reason}</p>
                  <p className="mt-1 text-xs text-primary">{r.expected_impact}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* What-if simulator */}
        <Card>
          <CardHeader>
            <CardTitle>What-If Simulator</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground">Shipping mode</label>
                <NativeSelect value={scenarioMode} onChange={(e) => setScenarioMode(e.target.value)}>
                  <option value="">Keep current ({shipment.shipping_mode})</option>
                  {SHIPPING_MODES.filter((m) => m !== shipment.shipping_mode).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Extra delivery buffer (days)</label>
                <NativeSelect value={scenarioBuffer} onChange={(e) => setScenarioBuffer(Number(e.target.value))}>
                  {[0, 1, 2, 3, 5].map((d) => (
                    <option key={d} value={d}>
                      +{d} days
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>
            <Button onClick={handleRunScenario} disabled={runScenario.isPending} className="w-full">
              Run scenario
            </Button>

            {scenarioResult && (
              <div className="space-y-2 rounded-md border bg-muted/30 p-3 text-sm">
                <div className="flex items-center justify-center gap-3">
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Baseline</p>
                    <p className="text-lg font-semibold">{scenarioResult.baseline_risk_score.toFixed(1)}</p>
                    <RiskBadge level={scenarioResult.baseline_risk_level} />
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Scenario</p>
                    <p className="text-lg font-semibold">{scenarioResult.scenario_risk_score.toFixed(1)}</p>
                    <RiskBadge level={scenarioResult.scenario_risk_level} />
                  </div>
                </div>
                <p
                  className={cn(
                    "text-center text-sm font-medium",
                    scenarioResult.risk_delta < 0 ? "text-risk-low" : "text-risk-high"
                  )}
                >
                  {scenarioResult.risk_delta > 0 ? "+" : ""}
                  {scenarioResult.risk_delta.toFixed(1)} risk points
                  {scenarioResult.estimated_cost_delta !== 0 &&
                    ` · ${scenarioResult.estimated_cost_delta > 0 ? "+" : ""}${formatCurrency(scenarioResult.estimated_cost_delta)} est. cost`}
                </p>
                <p className="text-center text-xs italic text-muted-foreground">{scenarioResult.note}</p>
                {scenarioResult.assumptions.map((a, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    ⓘ {a}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Field({ label, value, link }: { label: string; value: string; link?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      {link ? (
        <Link href={link} className="font-medium text-primary hover:underline">
          {value}
        </Link>
      ) : (
        <p className="font-medium">{value}</p>
      )}
    </div>
  );
}
