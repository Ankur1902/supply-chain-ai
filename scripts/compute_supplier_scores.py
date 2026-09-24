#!/usr/bin/env python
"""
Stage 7: recompute supplier scores (app/analytics/supplier_scoring.py) and
run the deterministic alert rules (app/alerts/rules.py) against the current
database state. Safe to re-run — both are idempotent (upsert / dedupe on
open alerts).

Usage:
    python scripts/compute_supplier_scores.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from app.alerts.rules import run_all_alert_checks  # noqa: E402
from app.analytics.supplier_scoring import compute_supplier_metrics  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from scripts.pipeline_common import print_metrics, timed_step  # noqa: E402


def main():
    with timed_step("compute_supplier_scores"):
        db = SessionLocal()
        try:
            supplier_rows = compute_supplier_metrics(db)
            alerts_created = run_all_alert_checks(db)
        finally:
            db.close()

    print_metrics(
        "Supplier scoring + alerts",
        {"supplier_metric_rows_written": supplier_rows, "new_alerts_created": alerts_created},
    )


if __name__ == "__main__":
    main()
