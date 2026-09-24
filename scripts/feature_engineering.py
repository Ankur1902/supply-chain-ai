#!/usr/bin/env python
"""
Stage 4 of the pipeline: temporal feature engineering + synthetic supplier
enrichment. See ml/features/feature_engineering.py and
ml/features/supplier_master.py for the actual logic — this script is a thin
CLI wrapper that also writes data/external/supplier_master.csv (section 4).

Usage:
    python scripts/feature_engineering.py --input data/processed/03_cleaned.parquet
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml.features.feature_engineering import build_feature_table  # noqa: E402
from scripts.pipeline_common import DATA_EXTERNAL, DATA_PROCESSED, print_metrics, timed_step  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "03_cleaned.parquet"))
    parser.add_argument("--output", type=str, default=str(DATA_PROCESSED / "04_features.parquet"))
    parser.add_argument("--supplier-out", type=str, default=str(DATA_EXTERNAL / "supplier_master.csv"))
    args = parser.parse_args()

    with timed_step("feature_engineering"):
        df = pd.read_parquet(args.input)
        features_df, supplier_master = build_feature_table(df)

        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        DATA_EXTERNAL.mkdir(parents=True, exist_ok=True)
        features_df.to_parquet(args.output, index=False)
        supplier_master.to_csv(args.supplier_out, index=False)

    print_metrics(
        "Feature engineering metrics",
        {
            "records": len(features_df),
            "suppliers_generated": len(supplier_master),
            "categories_covered": supplier_master["product_category"].nunique(),
            "avg_shipping_mode_delay_rate": round(float(features_df["shipping_mode_delay_rate"].mean()), 4),
            "avg_supplier_delay_rate": round(float(features_df["supplier_delay_rate"].mean()), 4),
            "output_path": args.output,
            "supplier_master_path": args.supplier_out,
        },
    )


if __name__ == "__main__":
    main()
