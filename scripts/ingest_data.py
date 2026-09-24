#!/usr/bin/env python
"""
Stage 1 of the pipeline: raw CSV -> renamed, minimally-typed parquet.

Handles both the real Kaggle DataCo CSV (latin-1 encoded) and the synthetic
sample/full-size CSVs produced by scripts/generate_sample_data.py (utf-8).

Usage:
    python scripts/ingest_data.py --sample               # use data/sample/
    python scripts/ingest_data.py                        # use data/raw/ if present, else falls back to sample
    python scripts/ingest_data.py --input path/to/file.csv
"""

import argparse

import pandas as pd

from pipeline_common import (
    DATA_PROCESSED,
    RAW_COLUMN_RENAME,
    print_metrics,
    read_raw_csv,
    resolve_input_path,
    timed_step,
)


def ingest(input_path, output_path) -> dict:
    metrics = {"records_read": 0, "records_rejected": 0, "records_inserted": 0}

    with timed_step("ingest_data"):
        df = read_raw_csv(input_path)
        metrics["records_read"] = len(df)

        missing_cols = set(RAW_COLUMN_RENAME.keys()) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Input file is missing expected raw columns: {missing_cols}")

        df = df.rename(columns=RAW_COLUMN_RENAME)
        df = df[list(RAW_COLUMN_RENAME.values())]

        before = len(df)
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df["shipping_date"] = pd.to_datetime(df["shipping_date"], errors="coerce")
        rejected_mask = df["order_date"].isna()
        metrics["records_rejected"] = int(rejected_mask.sum())
        df = df[~rejected_mask].copy()
        metrics["records_inserted"] = len(df)

        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)

    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=None)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--output", type=str, default=str(DATA_PROCESSED / "01_ingested.parquet"))
    args = parser.parse_args()

    input_path = resolve_input_path(args.input, args.sample)
    if not input_path.exists():
        raise SystemExit(
            f"Input file not found: {input_path}\n"
            f"Run 'python scripts/generate_sample_data.py' to create a dev sample, "
            f"or see docs/data-pipeline.md to download the real dataset."
        )

    metrics = ingest(input_path, args.output)
    print_metrics("Ingestion metrics", {**metrics, "source_file": str(input_path)})


if __name__ == "__main__":
    main()
