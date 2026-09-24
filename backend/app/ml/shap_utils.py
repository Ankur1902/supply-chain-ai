"""
Shared SHAP post-processing, used by both offline training
(ml/training/train.py) and online serving (app/ml/inference.py) so the two
never drift into different (and differently-buggy) explanation logic.

WHY AGGREGATION IS NECESSARY: one-hot encoding turns a single categorical
feature (e.g. shipping_mode) into several dummy columns (one per category).
SHAP assigns a value to EVERY dummy column independently — including the
ones that are "off" (0) for this row, since "not First Class" is itself
informative to a tree. Naively taking the top-N |SHAP| across ALL transformed
columns can surface two different one-hot dummies of the SAME original
feature (e.g. both "shipping_mode_Standard Class" and
"shipping_mode_First Class") for one shipment, which reads as a
contradiction ("its shipping mode is both Standard and First Class?").
The fix: sum SHAP values per ORIGINAL feature first, then rank — and always
report the shipment's actual observed value for that feature, never a
one-hot category name that happens to have a nonzero coefficient.
"""

import numpy as np


def _format_value(value) -> str:
    """Rounds float feature values to a readable precision (e.g. a causal
    delay-rate feature like 0.30987654321 displays as 0.31) rather than
    dumping full floating-point precision into the UI."""
    if isinstance(value, float):
        return f"{round(value, 3):g}"
    return str(value)


def original_feature_name(transformed_name: str, categorical_features: list[str]) -> str:
    """Maps a ColumnTransformer output column name back to its original
    feature name, e.g. 'cat__shipping_mode_Same Day' -> 'shipping_mode',
    'num__sales' -> 'sales'."""
    if transformed_name.startswith("num__"):
        return transformed_name[len("num__") :]
    if transformed_name.startswith("cat__"):
        remainder = transformed_name[len("cat__") :]
        for feat in categorical_features:
            if remainder.startswith(feat + "_"):
                return feat
        return remainder
    return transformed_name


def top_risk_factors(
    row_shap: np.ndarray,
    feature_names_out: list[str],
    categorical_features: list[str],
    feature_row: dict,
    top_n: int = 5,
) -> list[dict]:
    """Aggregates SHAP contributions per original feature (summing across
    one-hot dummies), ranks by |aggregated value|, and returns the
    shipment's actual observed value for each — never a one-hot label."""
    aggregated: dict[str, float] = {}
    for idx, name in enumerate(feature_names_out):
        orig = original_feature_name(name, categorical_features)
        aggregated[orig] = aggregated.get(orig, 0.0) + float(row_shap[idx])

    ranked = sorted(aggregated.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_n]

    factors = []
    for rank, (feat_name, shap_val) in enumerate(ranked, start=1):
        factors.append(
            {
                "feature_name": feat_name,
                "feature_value": _format_value(feature_row.get(feat_name, "")),
                "shap_value": shap_val,
                "direction": "positive" if shap_val > 0 else "negative",
                "rank": rank,
            }
        )
    return factors
