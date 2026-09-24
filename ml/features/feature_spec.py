"""
Canonical feature specification for the late-delivery-risk model.

This is the SINGLE SOURCE OF TRUTH for which columns are legitimate
prediction-time features vs. which are post-outcome fields that must never
reach the model. Both ml/training/train.py and
backend/app/ml/feature_builder.py (online serving) treat this module as
authoritative. See docs/ml-system.md and scripts/check_data_leakage.py.

Column naming here matches the cleaned/processed dataset produced by
scripts/clean_data.py (snake_case), not the raw DataCo CSV headers.
"""

# --- Raw source-data columns considered PREDICTION-TIME SAFE ---
CATEGORICAL_FEATURES = [
    "shipping_mode",
    "market",
    "destination_region",
    "customer_segment",
    "category_name",
    "department_name",
    "order_day_of_week",
]

NUMERIC_FEATURES = [
    "scheduled_shipping_days",
    "order_hour",
    "order_month",
    "order_item_quantity",
    "product_price",
    "discount_rate",
    "sales",
    "historical_supplier_reliability",  # supplier.reliability_score (synthetic master data)
    "supplier_lead_time",  # supplier.historical_lead_time_days (synthetic master data)
    "shipping_mode_delay_rate",  # trailing/causal, computed at or before order_date
    "category_delay_rate",  # trailing/causal
    "supplier_delay_rate",  # trailing/causal
    "route_risk",  # trailing/causal delay rate for destination_region
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

TARGET_COLUMN = "late_delivery_risk"

# --- POST-OUTCOME fields: retained for analytics/reporting/eval, NEVER fed
# to the model as a feature. See scripts/check_data_leakage.py for the
# automated audit that enforces this list stays in sync with the schema. ---
LEAKAGE_EXCLUDED_COLUMNS = {
    "days_for_shipping_real": (
        "Actual transit days — only known once the shipment has been delivered. "
        "Directly determines late_delivery_risk (late = actual > scheduled)."
    ),
    "delivery_status": (
        "Post-delivery outcome label ('Late delivery', 'Shipping on time', etc.) — "
        "this is essentially the target variable restated as text."
    ),
    "order_status": (
        "Can reach terminal states (e.g. CANCELED, SUSPECTED_FRAUD) only known "
        "after order processing completes; not reliably available at the moment "
        "a shipment is scheduled."
    ),
    "shipping_date": (
        "The actual date the shipment left/arrived — an outcome timestamp, not "
        "a plan. Only order_date and scheduled_shipping_days are prediction-time safe."
    ),
    "benefit_per_order": (
        "Realized profit figure that can be revised after fulfillment outcomes "
        "(e.g. returns, discounts applied post-hoc) — excluded out of caution "
        "even though it correlates weakly with delivery timing."
    ),
}

# Identifier / free-text columns dropped for both leakage and modeling hygiene
# (high cardinality, not generalizable, or PII-adjacent).
NON_FEATURE_IDENTIFIER_COLUMNS = [
    "order_id",
    "order_item_id",
    "shipment_id",
    "customer_id",
    "product_id",
    "product_card_id",
    "product_name",
    "category_id",
    "department_id",
    "customer_email",
    "customer_fname",
    "customer_lname",
    "customer_password",
]

# Order/pricing-derived financial columns that are prediction-time SAFE (not
# outcome-dependent) but deliberately excluded from the ML feature set — used
# instead for financial analytics/KPIs (see app/analytics/kpi_definitions.py).
NON_MODELED_FINANCIAL_COLUMNS = [
    "order_profit_per_order",
]
