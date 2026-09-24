#!/usr/bin/env python
"""
Stage 2 of the pipeline: schema/quality validation of the ingested data.

Performs (section 12 of the platform spec):
  - required-column / null checks
  - duplicate detection (exact row + business-key duplicates)
  - invalid dates (shipping before ordering, dates out of plausible range)
  - invalid categorical values
  - impossible numeric values (negative price/quantity, discount outside [0,1])
  - outlier checks (IQR on sales / scheduled_shipping_days)
  - class imbalance analysis on the target (late_delivery_risk)

Writes a human-readable data-quality report to
data/processed/data_quality_report.md and a machine-readable version to
data/processed/data_quality_report.json. Rows failing a HARD check are
dropped and counted in `records_rejected`; rows only tripping a SOFT
(warning-level) check are kept and counted separately.

Usage:
    python scripts/validate_data.py --input data/processed/01_ingested.parquet
"""

import argparse
import json

import pandas as pd

from pipeline_common import DATA_PROCESSED, print_metrics, timed_step

KNOWN_SHIPPING_MODES = {"Standard Class", "First Class", "Second Class", "Same Day"}
KNOWN_MARKETS = {"LATAM", "Europe", "Pacific Asia", "USCA", "Africa"}


def _iqr_outlier_mask(series: pd.Series) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 3 * iqr, q3 + 3 * iqr
    return (series < lower) | (series > upper)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict = {"hard_failures": {}, "soft_warnings": {}, "class_balance": {}}
    n_start = len(df)
    hard_reject_mask = pd.Series(False, index=df.index)

    # --- Required-field nulls (hard) ---
    required = [
        "order_id", "order_date", "shipping_mode", "scheduled_shipping_days",
        "order_item_quantity", "product_price", "sales", "late_delivery_risk",
        "destination_region", "market", "category_name",
    ]
    null_counts = {}
    for col in required:
        mask = df[col].isna()
        null_counts[col] = int(mask.sum())
        hard_reject_mask |= mask
    report["hard_failures"]["null_required_fields"] = null_counts

    # --- Exact duplicate rows (hard, idempotency) ---
    dup_mask = df.duplicated(subset=["order_id", "order_item_id"], keep="first")
    report["hard_failures"]["duplicate_order_items"] = int(dup_mask.sum())
    hard_reject_mask |= dup_mask

    # --- Invalid dates (hard) ---
    bad_date_order_mask = df["shipping_date"].notna() & (df["shipping_date"] < df["order_date"])
    report["hard_failures"]["shipping_before_order"] = int(bad_date_order_mask.sum())
    hard_reject_mask |= bad_date_order_mask

    plausible_range_mask = (df["order_date"] < "2010-01-01") | (df["order_date"] > "2035-01-01")
    report["hard_failures"]["implausible_order_date"] = int(plausible_range_mask.sum())
    hard_reject_mask |= plausible_range_mask

    # --- Impossible numeric values (hard) ---
    neg_qty_mask = df["order_item_quantity"] <= 0
    report["hard_failures"]["non_positive_quantity"] = int(neg_qty_mask.sum())
    hard_reject_mask |= neg_qty_mask

    neg_price_mask = df["product_price"] < 0
    report["hard_failures"]["negative_price"] = int(neg_price_mask.sum())
    hard_reject_mask |= neg_price_mask

    bad_discount_mask = (df["discount_rate"] < 0) | (df["discount_rate"] > 1)
    report["hard_failures"]["discount_rate_out_of_range"] = int(bad_discount_mask.sum())
    hard_reject_mask |= bad_discount_mask

    bad_target_mask = ~df["late_delivery_risk"].isin([0, 1])
    report["hard_failures"]["invalid_target_value"] = int(bad_target_mask.sum())
    hard_reject_mask |= bad_target_mask

    negative_scheduled_mask = df["scheduled_shipping_days"] < 0
    report["hard_failures"]["negative_scheduled_days"] = int(negative_scheduled_mask.sum())
    hard_reject_mask |= negative_scheduled_mask

    # --- Invalid categorical values (soft — flagged, not dropped, since the
    # real Kaggle dataset may have region/market spellings we haven't
    # enumerated; dropping on this would be too aggressive) ---
    unknown_mode = (~df["shipping_mode"].isin(KNOWN_SHIPPING_MODES)).sum()
    unknown_market = (~df["market"].isin(KNOWN_MARKETS)).sum()
    report["soft_warnings"]["unknown_shipping_mode_count"] = int(unknown_mode)
    report["soft_warnings"]["unknown_market_count"] = int(unknown_market)

    # --- Outliers (soft) ---
    report["soft_warnings"]["sales_outliers"] = int(_iqr_outlier_mask(df["sales"]).sum())
    report["soft_warnings"]["scheduled_days_outliers"] = int(
        _iqr_outlier_mask(df["scheduled_shipping_days"]).sum()
    )

    # --- Class imbalance ---
    valid_df = df[~hard_reject_mask]
    balance = valid_df["late_delivery_risk"].value_counts(normalize=True).to_dict()
    report["class_balance"] = {str(k): round(v, 4) for k, v in balance.items()}

    clean_df = valid_df.copy()
    report["records_read"] = n_start
    report["records_rejected"] = int(hard_reject_mask.sum())
    report["records_passed"] = len(clean_df)
    return clean_df, report


def write_report(report: dict, out_dir) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# Data Quality Report\n"]
    lines.append(f"- Records read: {report['records_read']:,}")
    lines.append(f"- Records rejected (hard failures): {report['records_rejected']:,}")
    lines.append(f"- Records passed: {report['records_passed']:,}\n")
    lines.append("## Hard failures (row dropped)")
    for k, v in report["hard_failures"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n## Soft warnings (row kept, flagged)")
    for k, v in report["soft_warnings"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("\n## Class balance (late_delivery_risk, post-cleaning)")
    for k, v in report["class_balance"].items():
        lines.append(f"- class `{k}`: {v:.1%}")
    (out_dir / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "01_ingested.parquet"))
    parser.add_argument("--output", type=str, default=str(DATA_PROCESSED / "02_validated.parquet"))
    args = parser.parse_args()

    with timed_step("validate_data"):
        df = pd.read_parquet(args.input)
        clean_df, report = validate(df)
        clean_df.to_parquet(args.output, index=False)
        write_report(report, DATA_PROCESSED)

    print_metrics(
        "Validation metrics",
        {
            "records_read": report["records_read"],
            "records_rejected": report["records_rejected"],
            "records_passed": report["records_passed"],
            "report_path": str(DATA_PROCESSED / "data_quality_report.md"),
        },
    )


if __name__ == "__main__":
    main()
