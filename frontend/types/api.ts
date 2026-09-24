export interface ApiMeta {
  page?: number;
  page_size?: number;
  total?: number;
  total_pages?: number;
}

export interface ApiSuccess<T> {
  data: T;
  meta?: ApiMeta;
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown };
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  roles: string[];
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface ShipmentListItem {
  id: number;
  shipment_code: string;
  order_date: string;
  product_name: string;
  supplier_name: string;
  origin_market: string;
  destination_region: string;
  shipping_mode: string;
  scheduled_shipping_days: number;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  status: string;
  sales: number;
}

export interface RiskFactor {
  feature_name: string;
  feature_value: string;
  shap_value: number;
  direction: "positive" | "negative";
  rank: number;
}

export interface Prediction {
  probability: number;
  risk_score: number;
  risk_level: RiskLevel;
  model_version: string;
  predicted_at: string;
  risk_factors: RiskFactor[];
}

export interface Recommendation {
  id: number;
  action_type: string;
  recommendation_text: string;
  reason: string;
  expected_impact: string;
  confidence: number;
  ai_generated: boolean;
}

export interface ShipmentDetail {
  id: number;
  shipment_code: string;
  order_date: string;
  shipping_mode: string;
  scheduled_shipping_days: number;
  order_item_quantity: number;
  product_price: number;
  discount_rate: number;
  sales: number;
  order_profit_per_order: number;
  origin_market: string;
  destination_region: string;
  status: string;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  product_name: string;
  product_category: string;
  supplier_id: number;
  supplier_name: string;
  customer_segment: string;
  days_for_shipping_real: number;
  delivery_status: string;
  late_delivery_risk: boolean;
  prediction: Prediction | null;
  recommendations: Recommendation[];
}

export interface SupplierListItem {
  id: number;
  supplier_code: string;
  supplier_name: string;
  supplier_region: string;
  supplier_tier: string;
  product_category: string;
  score: number | null;
  delay_rate: number | null;
  avg_lead_time_days: number | null;
  order_volume: number | null;
  risk_score: number;
  is_synthetic: boolean;
}

export interface SupplierScoreBreakdown {
  reliability_component: number;
  delivery_component: number;
  quality_component: number;
  lead_time_component: number;
  cost_component: number;
  risk_component: number;
}

export interface SupplierTrendPoint {
  period_start: string;
  score: number;
  delay_rate: number;
  order_volume: number;
}

export interface SupplierDetail {
  id: number;
  supplier_code: string;
  supplier_name: string;
  supplier_region: string;
  supplier_tier: string;
  product_category: string;
  historical_lead_time_days: number;
  capacity_score: number;
  quality_score: number;
  reliability_score: number;
  cost_score: number;
  risk_score: number;
  is_synthetic: boolean;
  score: number | null;
  score_breakdown: SupplierScoreBreakdown | null;
  delay_rate: number | null;
  avg_lead_time_days: number | null;
  order_volume: number | null;
  trend: SupplierTrendPoint[];
}

export interface Alert {
  id: number;
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  entity_type: string;
  entity_id: number | null;
  recommended_action: string;
  status: "open" | "acknowledged" | "resolved";
  created_at: string;
}

export interface DashboardKpis {
  total_shipments: number;
  at_risk_shipments: number;
  critical_shipments: number;
  delay_rate: number;
  at_risk_rate: number;
  critical_rate: number;
  average_delivery_time: number;
  average_scheduled_days: number;
  estimated_value_at_risk: number;
  profit_at_risk: number;
  supplier_health_avg_score: number | null;
}

export interface DashboardData {
  kpis: DashboardKpis;
  charts: {
    delay_trend: { period: string; total: number; delayed: number; delay_rate: number }[];
    risk_distribution: { risk_level: string; count: number }[];
    delay_by_shipping_mode: { dimension: string; total: number; delayed: number; delay_rate: number; avg_delivery_days: number }[];
    delay_by_region: { dimension: string; total: number; delayed: number; delay_rate: number; avg_delivery_days: number }[];
  };
}

export interface ScenarioResult {
  shipment_code: string;
  baseline_risk_score: number;
  scenario_risk_score: number;
  risk_delta: number;
  baseline_risk_level: RiskLevel;
  scenario_risk_level: RiskLevel;
  estimated_cost_delta: number;
  note: string;
  assumptions: string[];
}

export interface ChatToolCall {
  tool: string;
  input: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface ChatResponse {
  conversation_id: number;
  message: string;
  tool_calls: ChatToolCall[];
}
