#!/usr/bin/env python
"""
Orchestrates the full data pipeline end to end:

  ingest -> validate -> clean -> check_data_leakage -> feature_engineering
  -> load_database -> compute_supplier_scores -> generate_alerts

Each stage is idempotent (see the individual scripts' docstrings), so running
this twice does not duplicate database records.

Usage:
    python scripts/run_pipeline.py --sample          # use the synthetic dev sample
    python scripts/run_pipeline.py                   # use data/raw/ if present, else falls back to sample
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run(cmd: list[str], step_name: str) -> None:
    print(f"\n{'=' * 70}\nSTEP: {step_name}\n{'=' * 70}")
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        print(f"\nFAILED: {step_name} (exit code {result.returncode}, {elapsed:.1f}s)", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"OK: {step_name} completed in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use data/sample/ instead of data/raw/")
    parser.add_argument("--input", type=str, default=None, help="Explicit raw CSV path")
    parser.add_argument("--skip-load", action="store_true", help="Run everything except the MySQL load step")
    parser.add_argument("--skip-scoring", action="store_true", help="Skip supplier scoring + alert generation")
    args = parser.parse_args()

    pipeline_start = time.perf_counter()

    ingest_cmd = [PYTHON, "scripts/ingest_data.py"]
    if args.sample:
        ingest_cmd.append("--sample")
    if args.input:
        ingest_cmd += ["--input", args.input]
    run(ingest_cmd, "1/7 ingest_data")

    run([PYTHON, "scripts/validate_data.py"], "2/7 validate_data")
    run([PYTHON, "scripts/clean_data.py"], "3/7 clean_data")
    run([PYTHON, "scripts/check_data_leakage.py"], "4/7 check_data_leakage")
    run([PYTHON, "scripts/feature_engineering.py"], "5/7 feature_engineering")

    if not args.skip_load:
        run([PYTHON, "scripts/load_database.py"], "6/7 load_database")
        if not args.skip_scoring:
            run([PYTHON, "scripts/compute_supplier_scores.py"], "7/7 compute_supplier_scores + alerts")
    else:
        print("\nSkipping load_database/compute_supplier_scores (--skip-load).")

    total = time.perf_counter() - pipeline_start
    print(f"\n{'=' * 70}\nPIPELINE COMPLETE in {total:.1f}s\n{'=' * 70}")


if __name__ == "__main__":
    main()
