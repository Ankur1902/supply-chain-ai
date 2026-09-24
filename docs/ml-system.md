# ML System

See also [model-card.md](model-card.md) for the model-card-format summary
and [data-pipeline.md](data-pipeline.md) for how the training data is built.

## Prediction target

`late_delivery_risk` — binary, 1 if a shipment's actual transit time exceeds
its scheduled transit time. This is the DataCo dataset's own
`Late_delivery_risk` column (not derived by this project); a consistency
check in `scripts/check_data_leakage.py` confirms it agrees with
`days_for_shipping_real > scheduled_shipping_days` at 100% on the sample
data.

## Target leakage: what's excluded, and why it matters here specifically

| Excluded field | Why |
|---|---|
| `days_for_shipping_real` | Actual transit time — literally how the target is derived. Only known after delivery. |
| `delivery_status` | Post-delivery outcome label ("Late delivery", "Shipping on time") — the target restated as text. |
| `order_status` | Can reach terminal states (`CANCELED`, `SUSPECTED_FRAUD`) only known after processing completes. |
| `shipping_date` | The actual ship/arrival date — an outcome timestamp, not a plan. |
| `benefit_per_order` | Realized profit, revisable post-hoc (returns, discounts) — excluded out of caution. |

This isn't just a documented rule — `scripts/check_data_leakage.py`
empirically measures each excluded field's correlation with the target
(`delivery_status` correlates at 1.0, as expected — it's nearly a
restatement of the label) and **fails the pipeline** if a feature meant to
be safe ever crosses a 0.9 correlation threshold, or if any dataset column
isn't explicitly classified. This catches both "someone added a leaky
feature" and "the raw dataset schema changed and nobody updated the
classification."

## Feature set

Categorical: `shipping_mode`, `market`, `destination_region`,
`customer_segment`, `category_name`, `department_name`, `order_day_of_week`.

Numeric: `scheduled_shipping_days`, `order_hour`, `order_month`,
`order_item_quantity`, `product_price`, `discount_rate`, `sales`,
`historical_supplier_reliability`, `supplier_lead_time`,
`shipping_mode_delay_rate`, `category_delay_rate`, `supplier_delay_rate`,
`route_risk`.

### Temporal leakage in the "historical rate" features

`shipping_mode_delay_rate`, `category_delay_rate`, `supplier_delay_rate`, and
`route_risk` are trailing delay rates. Computing them as a flat groupby-mean
over the *entire* dataset would leak future information into past rows — a
January shipment would "know" the category's delay rate computed using data
through December. `ml/features/feature_engineering.py` instead computes them
as an **expanding mean, sorted by `order_date`, shifted by one row within
each group** — every row only sees outcomes from strictly earlier orders in
the same group, falling back to the dataset-level trailing rate (also
shifted) when a group has no prior history yet.

### Serving-time approximation (documented, not hidden)

At **training** time, these rate features are computed causally as described
above. At **serving** time (`app/ml/feature_builder.py`, used by the
what-if simulator and AI copilot's `get_prediction`/`run_scenario` tools),
they're computed as live "as of now" aggregates queried directly from MySQL
— there's no practical way to reconstruct "as of this shipment's original
order date" for a live scenario re-score. For a shipment scored shortly
after creation these are nearly identical; the gap only matters when scoring
an old shipment against today's global rates long after the fact. This is a
known, intentional simplification for a portfolio-scale system — called out
here rather than silently glossed over.

## Model selection

Chronological split (sorted by `order_date`, last 20% held out as test) —
**not** `sklearn.train_test_split`'s random shuffle, which would let the
model train on orders that happened after ones it's evaluated on.

Four candidates trained on identical features: Logistic Regression, Random
Forest, Gradient Boosting, XGBoost. All wrapped in the same
`ColumnTransformer` (one-hot encoding for categoricals; Logistic Regression
additionally gets `StandardScaler` on numerics, since tree models don't need
it).

**Selection policy**: rank by PR-AUC (robust under the ~30% positive-class
imbalance seen in this data), with XGBoost preferred as a tiebreak if it's
within 1% PR-AUC of the leader — reflecting XGBoost's usual production
advantages (faster SHAP via `TreeExplainer`, smaller artifact) without
overriding a real, larger performance difference. On the checked-in sample
run, **Random Forest genuinely won** (PR-AUC 0.459 vs. XGBoost's 0.448) and
was selected — the policy doesn't force XGBoost regardless of results.

Because this is a risk-management tool, **recall on the positive class**
(commentary on precision/recall tradeoff) is weighted into the selection
narrative even though PR-AUC is the primary ranking metric: missing a real
delay risk is costlier than a false alarm, so a candidate with much higher
accuracy but poor recall on late shipments would not be preferred even if
its overall PR-AUC were competitive.

Metrics tracked per candidate: accuracy, precision, recall, F1, ROC-AUC,
PR-AUC, full confusion matrix, class distribution, and a 10-bin calibration
table (mean predicted probability vs. observed rate).

## Explainability (SHAP)

Every prediction — training-time batch scoring and live serving — computes
per-shipment SHAP values via `TreeExplainer` (or `LinearExplainer` for
Logistic Regression) and reports the **top 5 contributing features** with
signed SHAP value and direction.

**One-hot aggregation bug and fix**: one-hot encoding turns a categorical
feature into several dummy columns; SHAP assigns a value to every dummy
column independently, including the ones that are "off" for a given row.
Naively ranking the top-N |SHAP| across all transformed columns can surface
two different categories of the *same* original feature for one shipment
(e.g. both "shipping_mode_Standard Class" and "shipping_mode_First Class"),
which reads as a contradiction. `app/ml/shap_utils.py` fixes this by summing
SHAP contributions per **original** feature before ranking, and always
reporting the shipment's actual observed value — never a one-hot label that
happened to have a nonzero coefficient. This is shared code between
`ml/training/train.py` (batch scoring) and `app/ml/inference.py` (live
serving) specifically so the fix can't drift between the two paths.

Global feature importance (mean |SHAP| across a test-set sample, aggregated
the same way) is saved alongside each model artifact as
`model_{version}_global_importance.json`.

## Model registry

`model_versions` table: version (timestamped, e.g. `20260901_051149_random_forest`
— not a sequential counter, which would collide with an existing file if an
old artifact were ever deleted), algorithm, training date, dataset version,
feature count, full metrics JSON, artifact path, status (`active`/`archived`).
Exactly one model is `active` at a time; training a new model archives the
previous one rather than deleting it. Every `shipment_predictions` row
records which `model_version_id` produced it.

## Failing safely

If no model is registered, or the artifact file is missing/incompatible,
`app/ml/inference.py` raises `ModelUnavailableError`, which every caller
(API routes, the scenario simulator, the AI copilot's tools) turns into a
clear "prediction unavailable" response — never a raw 500 or a silently
wrong guess.

## Training

```bash
python ml/training/train.py                    # train, evaluate, register, score all shipments
python ml/training/train.py --skip-registration # train/evaluate only, don't touch MySQL
```
