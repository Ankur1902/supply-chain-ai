# Model Documentation (Summary)

See docs/model-card.md and docs/ml-system.md for the full, authoritative
version — this file is a condensed copy indexed for the AI copilot's RAG
retrieval, kept intentionally short so it stays a useful citation source
rather than a duplicate of the whole doc.

## Purpose
Predicts `late_delivery_risk` (0 = on-time, 1 = likely late) for a shipment
BEFORE its outcome is known, using only prediction-time-safe features.

## Algorithm
XGBoost (gradient-boosted trees) is the primary model, selected by comparing
against Logistic Regression, Random Forest, and sklearn Gradient Boosting on
a chronological (time-ordered) train/test split — not a random split, to
avoid the model being evaluated on orders that happened before ones it
trained on.

## Excluded Fields (Leakage)
`days_for_shipping_real`, `delivery_status`, `order_status`, `shipping_date`,
and `benefit_per_order` are POST-OUTCOME fields and are NEVER used as model
features, even though they're highly predictive — because they are not known
at the moment a shipment needs to be scored. See
scripts/check_data_leakage.py for the automated audit that enforces this.

## Features Used
Shipping mode, market, destination region, customer segment, product
category, department, order day-of-week, scheduled shipping days, order
hour/month, order quantity, product price, discount rate, sales,
supplier reliability/lead-time (synthetic master data), and four causally-
computed historical delay-rate features (by shipping mode, category,
supplier, and route) — computed using only data available before each
row's own order date.

## Explainability
Every prediction is accompanied by its top 5 SHAP contributing factors
(feature name, value, direction, magnitude), computed from the actual
trained model — never invented or approximated by the LLM.

## Evaluation Priority
Because this is a risk-management tool, recall on the positive (late) class
is weighted more heavily than raw accuracy when selecting between
candidate models — missing a real risk is costlier than a false alarm.
