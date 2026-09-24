# Model Card — Late Delivery Risk Classifier

## Model Purpose

Predicts the probability that a shipment will be delivered later than its
scheduled transit window, using only information available at the moment the
shipment is created/scheduled — so operations staff can intervene *before*
the outcome happens, not after.

## Training Data

DataCo Smart Supply Chain Dataset (or a deterministic synthetic sample with
the identical schema — see [data-pipeline.md](data-pipeline.md)), processed
through `scripts/run_pipeline.py`. The checked-in demo model was trained on
an 8,000-row synthetic sample; the pipeline and training code work
identically at the full ~180K-row scale.

## Prediction Target

`late_delivery_risk` (binary): 1 if actual transit days exceeded scheduled
transit days.

## Feature Definitions

See [ml-system.md](ml-system.md) "Feature set" for the full list and
`ml/features/feature_spec.py` for the authoritative, machine-readable
definition. Summary: shipping/order attributes known at scheduling time
(mode, market, region, segment, category, day/hour/month), plus four
causally-computed historical delay-rate features and two static synthetic
supplier attributes (reliability, lead time).

## Excluded Leakage Fields

`days_for_shipping_real`, `delivery_status`, `order_status`, `shipping_date`,
`benefit_per_order` — all post-outcome fields. See
[ml-system.md](ml-system.md) for the empirical correlation evidence behind
each exclusion, and `scripts/check_data_leakage.py` for the automated audit
that enforces this on every pipeline run.

## Training Strategy

Chronological (time-ordered) 80/20 train/test split — not random — to avoid
evaluating on orders that happened before ones the model trained on. Four
candidate algorithms compared on identical features: Logistic Regression,
Random Forest, Gradient Boosting, XGBoost, each behind the same
`ColumnTransformer` preprocessing pipeline persisted as a single sklearn
`Pipeline` artifact (so serving code never reimplements encoding logic).

## Validation Strategy

Held-out chronological test set. Metrics: accuracy, precision, recall, F1,
ROC-AUC, PR-AUC, full confusion matrix, class distribution, 10-bin
calibration table. Selection ranks by PR-AUC (robust under class imbalance),
with a same-family XGBoost/LightGBM tiebreak preference within 1% — not a
hard override.

## Metrics (checked-in demo model, `v2_random_forest`, 8,000-row sample)

| Metric | Value |
|---|---|
| ROC-AUC | 0.651 |
| PR-AUC | 0.459 |
| Recall (positive class) | 0.431 |
| Precision (positive class) | 0.446 |
| F1 | 0.438 |

These numbers reflect a small (8K-row) synthetic sample with intentionally
moderate signal-to-noise, evaluated on genuinely held-out future orders —
not cherry-picked or inflated by leakage. Retraining on the full ~180K-row
real dataset would be expected to improve these figures materially given
more data and (likely) stronger real-world signal than the synthetic
generator's simplified delay model.

## Limitations

- Trained on synthetic or sample-scale data by default; production use
  requires retraining on the full real dataset.
- The "historical delay rate" features use a live-aggregate approximation at
  serving time rather than a true as-of-date reconstruction (documented in
  [ml-system.md](ml-system.md)).
- Supplier-level features come from a synthetic enrichment layer, not real
  supplier performance history — the model has learned patterns tied to
  *how suppliers were synthetically assigned to categories/regions*, not
  real supplier behavior.
- No hyperparameter search was run beyond reasonable defaults; this is a
  demonstration of a correct, leakage-safe ML pipeline, not a tuned
  production model.
- Recall on the positive class (~0.43) means roughly half of genuinely late
  shipments are not flagged HIGH/CRITICAL by the model alone — the platform
  pairs this with deterministic root-cause/alert rules rather than relying
  on the model as the sole signal.

## Known Biases

The synthetic supplier assignment is a deterministic hash of
`(order_id, order_item_id)` within a category's supplier pool — it has no
relationship to real supplier quality, so any "supplier effect" the model
learns on synthetic data reflects the synthetic generator's category/region
delay-rate biases, not genuine supplier performance differences. On the real
dataset (no synthetic suppliers needed, since it would use the same
enrichment layer), the same caveat applies to supplier-level signal
specifically — shipping-mode, region, and category signals derive directly
from real DataCo data and don't carry this caveat.

## Explainability

Every prediction carries its top-5 SHAP contributing factors (feature,
observed value, signed contribution, direction), aggregated to the original
feature level to avoid the one-hot-encoding double-counting bug described in
[ml-system.md](ml-system.md). Global feature importance is computed the same
way over a test-set sample and saved per model version.

## Appropriate Use

- Prioritizing operational attention (which shipments to review first).
- Informing what-if scenario exploration (estimated relative risk change).
- Feeding a deterministic, schema-validated recommendation engine.
- Portfolio/interview demonstration of a leakage-safe, explainable ML
  pipeline.

## Inappropriate Use

- Sole basis for contractual/SLA decisions without human review.
- Presenting synthetic supplier scores as real supplier performance data.
- Treating risk scores as calibrated real-world probabilities without first
  checking the calibration table for the currently active model version.
- Any production deployment without retraining on real, sufficiently large,
  representative data and re-validating leakage assumptions against that
  data's actual schema.
