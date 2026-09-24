#!/usr/bin/env python
"""
Stage 5 of the pipeline: bulk-load the feature-engineered dataset into MySQL.

Idempotent by design: every table this script writes to has a UNIQUE
constraint on a natural/business key (source_customer_id, source_product_id,
supplier_code, source_order_id, shipment_code). Inserts use
`INSERT IGNORE ... ON DUPLICATE KEY UPDATE` semantics via SQLAlchemy Core in
BATCH_SIZE=5000 chunks — never one ORM object per row — so re-running this
script against the same input does not duplicate records, and stays fast at
180K+ rows.

Requires the backend's Alembic migrations to have already created the schema
(`cd backend && alembic upgrade head`), and MySQL to be reachable via
DATABASE_URL (see backend/.env or the repo-root .env).

Usage:
    python scripts/load_database.py --input data/processed/04_features.parquet \
        --supplier-master data/external/supplier_master.csv
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, insert, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from app.models.shipment import Customer, Order, Product, Shipment  # noqa: E402
from app.models.supplier import Supplier  # noqa: E402
from scripts.pipeline_common import DATA_EXTERNAL, DATA_PROCESSED, print_metrics, timed_step  # noqa: E402

BATCH_SIZE = 5000


def _batched(records: list[dict], size: int):
    for i in range(0, len(records), size):
        yield records[i : i + size]


def _upsert(engine, table, records: list[dict], update_cols: list[str] | None = None) -> int:
    """MySQL-native upsert: INSERT ... ON DUPLICATE KEY UPDATE. If
    update_cols is empty/None, behaves like INSERT IGNORE (skip duplicates,
    never overwrite) — used for immutable dimension rows. Returns rows sent
    (not necessarily rows changed, since MySQL doesn't cheaply distinguish)."""
    if not records:
        return 0
    total = 0
    with engine.begin() as conn:
        for batch in _batched(records, BATCH_SIZE):
            stmt = mysql_insert(table).values(batch)
            if update_cols:
                update_dict = {c: getattr(stmt.inserted, c) for c in update_cols}
                stmt = stmt.on_duplicate_key_update(**update_dict)
            else:
                stmt = stmt.prefix_with("IGNORE")
            conn.execute(stmt)
            total += len(batch)
    return total


def load_customers(engine, df: pd.DataFrame) -> int:
    customers = (
        df.drop_duplicates(subset=["customer_id"])
        .rename(columns={"customer_id": "source_customer_id"})[
            ["source_customer_id", "customer_segment", "customer_city", "customer_state", "customer_country", "customer_zipcode"]
        ]
        .rename(columns={"customer_segment": "segment", "customer_city": "city", "customer_state": "state", "customer_country": "country", "customer_zipcode": "zipcode"})
    )
    customers["zipcode"] = customers["zipcode"].astype(str)
    records = customers.to_dict("records")
    return _upsert(engine, Customer.__table__, records, update_cols=["segment", "city", "state", "country"])


def load_products(engine, df: pd.DataFrame) -> int:
    products = (
        df.drop_duplicates(subset=["product_card_id"])
        .rename(columns={"product_card_id": "source_product_id", "product_name": "name", "category_id": "category_id", "category_name": "category_name", "department_id": "department_id", "department_name": "department_name", "product_price": "price"})[
            ["source_product_id", "name", "category_id", "category_name", "department_id", "department_name", "price"]
        ]
    )
    records = products.to_dict("records")
    return _upsert(engine, Product.__table__, records, update_cols=["price"])


def load_suppliers(engine, supplier_master: pd.DataFrame) -> int:
    records = supplier_master.to_dict("records")
    update_cols = [
        "supplier_name", "supplier_region", "supplier_tier", "historical_lead_time_days",
        "capacity_score", "quality_score", "reliability_score", "cost_score", "risk_score",
    ]
    return _upsert(engine, Supplier.__table__, records, update_cols=update_cols)


def load_orders(engine, df: pd.DataFrame, customer_id_map: dict) -> int:
    orders = df.drop_duplicates(subset=["order_id"]).copy()
    orders["customer_id"] = orders["customer_id"].map(customer_id_map)
    orders = orders.rename(
        columns={
            "order_id": "source_order_id",
            "destination_region": "order_region",
        }
    )
    records = orders[
        [
            "source_order_id", "customer_id", "order_date", "order_status", "market",
            "order_region", "order_country", "order_state", "order_city",
        ]
    ].to_dict("records")
    return _upsert(engine, Order.__table__, records, update_cols=["order_status"])


def load_shipments(engine, df: pd.DataFrame, order_id_map: dict, product_id_map: dict, supplier_id_map: dict) -> int:
    s = df.copy()
    s["order_id"] = s["order_id"].map(order_id_map)
    s["product_id"] = s["product_card_id"].map(product_id_map)
    s["supplier_id"] = s["supplier_code"].map(supplier_id_map)

    records = (
        s[
            [
                "shipment_code", "order_id", "product_id", "supplier_id", "order_date",
                "shipping_mode", "scheduled_shipping_days", "order_item_quantity", "product_price",
                "discount_rate", "sales", "order_profit_per_order", "market", "destination_region",
                "days_for_shipping_real", "delivery_status", "late_delivery_risk",
            ]
        ]
        .rename(columns={"market": "origin_market"})
        .to_dict("records")
    )

    for r in records:
        r["status"] = "delivered" if r["delivery_status"] != "Shipping canceled" else "canceled"
        r["late_delivery_risk"] = bool(r["late_delivery_risk"])

    return _upsert(engine, Shipment.__table__, records, update_cols=["status"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "04_features.parquet"))
    parser.add_argument("--supplier-master", type=str, default=str(DATA_EXTERNAL / "supplier_master.csv"))
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set (check your .env)")
    engine = create_engine(database_url, pool_pre_ping=True)

    metrics = {"records_read": 0, "records_inserted": 0}
    start = time.perf_counter()

    with timed_step("load_database"):
        df = pd.read_parquet(args.input)
        supplier_master = pd.read_csv(args.supplier_master)
        metrics["records_read"] = len(df)

        load_customers(engine, df)
        load_products(engine, df)
        load_suppliers(engine, supplier_master)

        with Session(engine) as session:
            customer_id_map = dict(
                session.execute(select(Customer.source_customer_id, Customer.id)).all()
            )
            product_id_map = dict(
                session.execute(select(Product.source_product_id, Product.id)).all()
            )
            supplier_id_map = dict(
                session.execute(select(Supplier.supplier_code, Supplier.id)).all()
            )

        load_orders(engine, df, customer_id_map)

        with Session(engine) as session:
            order_id_map = dict(session.execute(select(Order.source_order_id, Order.id)).all())

        inserted = load_shipments(engine, df, order_id_map, product_id_map, supplier_id_map)
        metrics["records_inserted"] = inserted

    metrics["execution_time_seconds"] = round(time.perf_counter() - start, 2)
    print_metrics("Load metrics", metrics)


if __name__ == "__main__":
    main()
