#!/usr/bin/env python
"""
Stage 3 of the pipeline: cleaning/normalization.

- Trims/standardizes string casing on categorical columns.
- Derives a stable, human-readable `shipment_code` (SHP-<order_id>-<item_id>)
  used as the shipments table's natural/business key — this is what makes
  scripts/load_database.py idempotent (upsert on shipment_code).
- Clips a small number of pathological numeric values (e.g. discount_rate
  fractionally over 1.0 due to upstream rounding) rather than dropping them.
- Fills a few non-critical nulls with explicit placeholders instead of
  leaving NaN (which breaks MySQL NOT NULL columns downstream).

Usage:
    python scripts/clean_data.py --input data/processed/02_validated.parquet
"""

import argparse

import pandas as pd

from pipeline_common import DATA_PROCESSED, print_metrics, timed_step

STRING_COLUMNS_TO_STRIP = [
    "shipping_mode", "market", "destination_region", "customer_segment",
    "category_name", "department_name", "order_status", "delivery_status",
    "product_name", "customer_city", "customer_state", "customer_country",
]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in STRING_COLUMNS_TO_STRIP:
        df[col] = df[col].astype(str).str.strip()

    df["discount_rate"] = df["discount_rate"].clip(0, 1)
    df["order_item_quantity"] = df["order_item_quantity"].clip(lower=1)
    df["product_price"] = df["product_price"].clip(lower=0)

    df["customer_state"] = df["customer_state"].fillna("Unknown")
    df["order_state"] = df["order_state"].fillna("Unknown")

    df["shipment_code"] = "SHP-" + df["order_id"].astype(int).astype(str) + "-" + df[
        "order_item_id"
    ].astype(int).astype(str)

    df = df.drop_duplicates(subset=["shipment_code"], keep="first")

    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "02_validated.parquet"))
    parser.add_argument("--output", type=str, default=str(DATA_PROCESSED / "03_cleaned.parquet"))
    args = parser.parse_args()

    with timed_step("clean_data"):
        df = pd.read_parquet(args.input)
        records_in = len(df)
        cleaned = clean(df)
        cleaned.to_parquet(args.output, index=False)

    print_metrics(
        "Cleaning metrics",
        {
            "records_in": records_in,
            "records_out": len(cleaned),
            "duplicate_shipment_codes_dropped": records_in - len(cleaned),
        },
    )


if __name__ == "__main__":
    main()
