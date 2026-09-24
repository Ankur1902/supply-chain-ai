"""
Centralized KPI definitions (section 44 of the platform spec).

Every place in the codebase that computes one of these metrics MUST import
the constant/formula from here rather than recomputing its own version, so
the dashboard, analytics pages, alerts, and AI copilot always agree.

All rate/percentage KPIs are computed over `late_delivery_risk` and
`delivery_status`, which are POST-OUTCOME/historical fields — i.e. these are
retrospective analytics, not predictions. Predictions come from
app/ml/inference (see docs/ml-system.md). Do not confuse the two.
"""

KPI_DEFINITIONS: dict[str, str] = {
    "delay_rate": (
        "SOURCE-DATA metric. COUNT(shipments WHERE late_delivery_risk = 1) / "
        "COUNT(shipments) over the selected filter scope. Reflects historical "
        "outcomes, not a prediction."
    ),
    "at_risk_rate": (
        "PREDICTED metric. COUNT(shipments WHERE risk_level IN ('HIGH','CRITICAL')) "
        "/ COUNT(shipments with a prediction) over the selected filter scope."
    ),
    "critical_rate": (
        "PREDICTED metric. COUNT(shipments WHERE risk_level = 'CRITICAL') / "
        "COUNT(shipments with a prediction) over the selected filter scope."
    ),
    "average_delivery_time": (
        "SOURCE-DATA metric. AVG(days_for_shipping_real) over delivered shipments "
        "in the selected filter scope. Historical/retrospective only."
    ),
    "average_scheduled_days": (
        "SOURCE-DATA metric. AVG(scheduled_shipping_days) over shipments in the "
        "selected filter scope. This is a prediction-time feature, safe to show "
        "alongside forward-looking risk figures."
    ),
    "estimated_value_at_risk": (
        "ESTIMATED metric. SUM(sales) over shipments WHERE risk_level IN "
        "('HIGH','CRITICAL'). This is the order value exposed to modeled delay "
        "risk, not a claim that this revenue will be lost. See docs/decisions.md "
        "and the Financial Impact page's 'Assumptions' panel."
    ),
    "profit_at_risk": (
        "ESTIMATED metric. SUM(order_profit_per_order) over shipments WHERE "
        "risk_level IN ('HIGH','CRITICAL'). Same caveat as estimated_value_at_risk."
    ),
    "supplier_score": (
        "DERIVED metric, 0-100. Weighted sum of six normalized (0-100) components: "
        "reliability(25%) + delivery_performance(25%) + quality(15%) + "
        "lead_time(15%) + cost(10%) + risk(10%, inverted so lower risk scores "
        "higher). Weights are configurable — see app/analytics/supplier_scoring.py "
        "SUPPLIER_SCORE_WEIGHTS. Delivery/reliability components are DERIVED from "
        "actual shipment history; quality/cost/risk components originate in the "
        "SYNTHETIC supplier enrichment layer (see docs/data-pipeline.md)."
    ),
}

# Configurable risk-level thresholds (risk_score is 0-100).
RISK_THRESHOLDS = {
    "LOW": (0, 25),
    "MEDIUM": (25, 50),
    "HIGH": (50, 75),
    "CRITICAL": (75, 100.0001),  # upper bound inclusive of 100
}


def risk_level_for_score(score: float) -> str:
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score < high:
            return level
    return "CRITICAL" if score >= 75 else "LOW"


SUPPLIER_SCORE_WEIGHTS = {
    "reliability": 0.25,
    "delivery": 0.25,
    "quality": 0.15,
    "lead_time": 0.15,
    "cost": 0.10,
    "risk": 0.10,
}
