#!/usr/bin/env python
"""
Explicit target-leakage audit (section 3 of the platform spec).

This script is the enforcement mechanism behind the platform's core ML
integrity claim: "no post-outcome field is ever used as a prediction-time
feature." It:

  1. Classifies every column in the cleaned dataset into one of: TARGET,
     EXCLUDED_LEAKAGE, IDENTIFIER (dropped, not leakage per se), SAFE_FEATURE,
     or UNCLASSIFIED (a schema-drift warning — a new column nobody has
     reviewed yet).
  2. Empirically measures how strongly the excluded fields correlate with
     the target, to demonstrate *why* they're excluded (not just assert it).
  3. Sanity-checks that the *included* features correlate much more weakly,
     as a smoke test that leakage isn't hiding in a feature we think is safe.
  4. Verifies the target's derivation is internally consistent
     (late_delivery_risk should agree with days_for_shipping_real >
     scheduled_shipping_days).
  5. Writes a human-readable report to data/processed/leakage_report.md.

Fails (non-zero exit) if any column is UNCLASSIFIED, or if a feature in
ALL_FEATURES correlates suspiciously strongly (>0.9) with the target — both
are treated as "stop and review before training," not silently ignored.

Usage:
    python scripts/check_data_leakage.py --input data/processed/03_cleaned.parquet
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml.features.feature_spec import (  # noqa: E402
    ALL_FEATURES,
    LEAKAGE_EXCLUDED_COLUMNS,
    NON_FEATURE_IDENTIFIER_COLUMNS,
    NON_MODELED_FINANCIAL_COLUMNS,
    TARGET_COLUMN,
)
from scripts.pipeline_common import DATA_PROCESSED, print_metrics, timed_step  # noqa: E402

SUSPICIOUS_CORRELATION_THRESHOLD = 0.9

# Columns computed downstream by feature_engineering.py (not present yet in
# the cleaned dataset this script normally audits, but allow-listed so
# running the audit post-feature-engineering doesn't false-positive).
DOWNSTREAM_DERIVED_COLUMNS = {
    "order_hour", "order_day_of_week", "order_month",
    "historical_supplier_reliability", "supplier_lead_time",
    "shipping_mode_delay_rate", "category_delay_rate", "supplier_delay_rate",
    "route_risk", "supplier_id", "shipment_code",
}

# Raw columns that exist in the cleaned dataset purely as inputs to derive
# other things (e.g. dates), or as non-modeling metadata — not leakage, not
# features, just administrative.
ADMINISTRATIVE_COLUMNS = {
    "order_date", "shipping_date", "payment_type", "sales_per_customer",
    "order_customer_id", "order_item_cardprod_id", "order_zipcode",
    "customer_zipcode", "customer_city", "customer_country", "customer_state",
    "customer_street", "customer_login_type", "order_city", "order_country",
    "order_state", "latitude", "longitude", "order_item_discount",
    "order_item_product_price", "order_item_profit_ratio", "order_item_total",
    "product_category_id", "product_status",
}


def classify_columns(df: pd.DataFrame) -> dict:
    classification = {}
    for col in df.columns:
        if col == TARGET_COLUMN:
            classification[col] = ("TARGET", "The prediction target itself.")
        elif col in LEAKAGE_EXCLUDED_COLUMNS:
            classification[col] = ("EXCLUDED_LEAKAGE", LEAKAGE_EXCLUDED_COLUMNS[col])
        elif col in NON_FEATURE_IDENTIFIER_COLUMNS:
            classification[col] = ("IDENTIFIER", "High-cardinality identifier / PII-adjacent, dropped.")
        elif col in NON_MODELED_FINANCIAL_COLUMNS:
            classification[col] = (
                "ADMINISTRATIVE",
                "Prediction-time safe but deliberately not modeled — used for financial KPIs instead.",
            )
        elif col in ALL_FEATURES:
            classification[col] = ("SAFE_FEATURE", "Available before the outcome is known.")
        elif col in ADMINISTRATIVE_COLUMNS:
            classification[col] = ("ADMINISTRATIVE", "Raw input used to derive features/keys, not modeled directly.")
        elif col in DOWNSTREAM_DERIVED_COLUMNS:
            classification[col] = ("SAFE_FEATURE", "Derived prediction-time-safe feature (see feature_engineering.py).")
        else:
            classification[col] = ("UNCLASSIFIED", "New/unexpected column — review before training.")
    return classification


HIGH_CARDINALITY_THRESHOLD = 50


def correlation_with_target(df: pd.DataFrame, columns: list[str], target: pd.Series) -> dict:
    correlations = {}
    for col in columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            corr = series.astype(float).corr(target.astype(float))
        elif pd.api.types.is_bool_dtype(series):
            corr = series.astype(int).corr(target.astype(float))
        elif series.nunique(dropna=True) > HIGH_CARDINALITY_THRESHOLD:
            # High-cardinality categorical/datetime columns (e.g. shipping_date,
            # a near-unique timestamp) make the group-by delay-rate spread
            # trivially 1.0 for almost any column — not a meaningful leakage
            # signal, so report it as unmeasured rather than misleadingly 1.0.
            correlations[col] = None
            continue
        else:
            # Low-cardinality categorical: use the delay-rate spread across
            # categories as a proxy for association strength (Cramer's V
            # would be more rigorous; sufficient for a leakage smoke test).
            rates = df.groupby(series)[TARGET_COLUMN].mean()
            corr = float(rates.max() - rates.min()) if len(rates) > 1 else 0.0
        correlations[col] = round(float(corr), 4) if corr is not None else None
    return correlations


def check_target_derivation(df: pd.DataFrame) -> dict:
    implied = (df["days_for_shipping_real"] > df["scheduled_shipping_days"]).astype(int)
    agreement = (implied == df[TARGET_COLUMN]).mean()
    return {"agreement_with_days_diff_rule": round(float(agreement), 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "03_cleaned.parquet"))
    args = parser.parse_args()

    with timed_step("check_data_leakage"):
        df = pd.read_parquet(args.input)
        classification = classify_columns(df)

        unclassified = [c for c, (label, _) in classification.items() if label == "UNCLASSIFIED"]

        excluded_cols = [c for c, (label, _) in classification.items() if label == "EXCLUDED_LEAKAGE"]
        excluded_corr = correlation_with_target(df, excluded_cols, df[TARGET_COLUMN])

        safe_cols = [c for c in ALL_FEATURES if c in df.columns]
        safe_corr = correlation_with_target(df, safe_cols, df[TARGET_COLUMN]) if safe_cols else {}

        derivation = check_target_derivation(df)

        suspicious_features = {
            c: v for c, v in safe_corr.items() if v is not None and abs(v) > SUSPICIOUS_CORRELATION_THRESHOLD
        }

        report_lines = ["# Target Leakage Audit Report\n"]
        report_lines.append(f"Target column: `{TARGET_COLUMN}`\n")
        report_lines.append(
            f"Target derivation check — agreement with "
            f"`days_for_shipping_real > scheduled_shipping_days`: "
            f"{derivation['agreement_with_days_diff_rule']:.1%}\n"
        )

        report_lines.append("## Column classification\n")
        report_lines.append("| Column | Classification | Reason |")
        report_lines.append("|---|---|---|")
        for col, (label, reason) in sorted(classification.items()):
            report_lines.append(f"| `{col}` | {label} | {reason} |")

        report_lines.append("\n## Excluded (leakage) field correlation with target\n")
        report_lines.append(
            "These fields correlate strongly with the target precisely *because* they "
            "encode the outcome — this is the empirical evidence for exclusion, not just a rule. "
            "`null` means the column is high-cardinality (e.g. a near-unique timestamp) and the "
            "delay-rate-spread proxy isn't meaningful for it; exclusion still applies by rule.\n"
        )
        report_lines.append("| Field | Correlation / delay-rate spread |")
        report_lines.append("|---|---|")
        for col, corr in excluded_corr.items():
            report_lines.append(f"| `{col}` | {corr} |")

        report_lines.append("\n## Included feature correlation with target (sanity check)\n")
        report_lines.append("| Feature | Correlation / delay-rate spread |")
        report_lines.append("|---|---|")
        for col, corr in safe_corr.items():
            report_lines.append(f"| `{col}` | {corr} |")

        if unclassified:
            report_lines.append("\n## ⚠️ UNCLASSIFIED COLUMNS (must review before training)\n")
            for col in unclassified:
                report_lines.append(f"- `{col}`")

        if suspicious_features:
            report_lines.append("\n## ⚠️ SUSPICIOUSLY STRONG FEATURE CORRELATIONS\n")
            for col, corr in suspicious_features.items():
                report_lines.append(f"- `{col}`: {corr} (threshold {SUSPICIOUS_CORRELATION_THRESHOLD})")

        report_path = DATA_PROCESSED / "leakage_report.md"
        report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print_metrics(
        "Leakage audit",
        {
            "columns_checked": len(classification),
            "excluded_leakage_fields": len(excluded_cols),
            "safe_features": len(safe_cols),
            "unclassified_columns": len(unclassified),
            "suspicious_feature_correlations": len(suspicious_features),
            "report_path": str(report_path),
        },
    )

    if unclassified:
        print(f"\nFAIL: {len(unclassified)} unclassified column(s): {unclassified}", file=sys.stderr)
        sys.exit(1)
    if suspicious_features:
        print(f"\nFAIL: suspicious feature correlations: {suspicious_features}", file=sys.stderr)
        sys.exit(1)
    print("PASS: no unclassified columns, no suspicious feature correlations.")


if __name__ == "__main__":
    main()
