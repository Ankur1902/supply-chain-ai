"""
Shared constants/helpers for the data pipeline scripts (ingest -> validate ->
clean -> feature_engineering -> load_database). Kept dependency-free (pandas
only) so these scripts can run standalone, outside the FastAPI backend venv
if needed.
"""

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_SAMPLE = REPO_ROOT / "data" / "sample"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
DATA_EXTERNAL = REPO_ROOT / "data" / "external"

# Maps the raw DataCo CSV headers to snake_case working column names used by
# every downstream pipeline stage.
RAW_COLUMN_RENAME = {
    "Type": "payment_type",
    "Days for shipping (real)": "days_for_shipping_real",
    "Days for shipment (scheduled)": "scheduled_shipping_days",
    "Benefit per order": "benefit_per_order",
    "Sales per customer": "sales_per_customer",
    "Delivery Status": "delivery_status",
    "Late_delivery_risk": "late_delivery_risk",
    "Category Id": "category_id",
    "Category Name": "category_name",
    "Customer City": "customer_city",
    "Customer Country": "customer_country",
    "Customer Email": "customer_email",
    "Customer Fname": "customer_fname",
    "Customer Id": "customer_id",
    "Customer Lname": "customer_lname",
    "Customer Login Type": "customer_login_type",
    "Customer Segment": "customer_segment",
    "Customer State": "customer_state",
    "Customer Street": "customer_street",
    "Customer Zipcode": "customer_zipcode",
    "Department Id": "department_id",
    "Department Name": "department_name",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Market": "market",
    "Order City": "order_city",
    "Order Country": "order_country",
    "Order Customer Id": "order_customer_id",
    "order date (DateOrders)": "order_date",
    "Order Id": "order_id",
    "Order Item Cardprod Id": "order_item_cardprod_id",
    "Order Item Discount": "order_item_discount",
    "Order Item Discount Rate": "discount_rate",
    "Order Item Id": "order_item_id",
    "Order Item Product Price": "order_item_product_price",
    "Order Item Profit Ratio": "order_item_profit_ratio",
    "Order Item Quantity": "order_item_quantity",
    "Sales": "sales",
    "Order Item Total": "order_item_total",
    "Order Profit Per Order": "order_profit_per_order",
    "Order Region": "destination_region",
    "Order State": "order_state",
    "Order Status": "order_status",
    "Order Zipcode": "order_zipcode",
    "Product Card Id": "product_card_id",
    "Product Category Id": "product_category_id",
    "Product Name": "product_name",
    "Product Price": "product_price",
    "Product Status": "product_status",
    "shipping date (DateOrders)": "shipping_date",
    "Shipping Mode": "shipping_mode",
}

REQUIRED_COLUMNS = list(RAW_COLUMN_RENAME.values())


@contextmanager
def timed_step(name: str):
    start = time.perf_counter()
    print(f"[{name}] starting...")
    yield
    elapsed = time.perf_counter() - start
    print(f"[{name}] done in {elapsed:.2f}s")


def print_metrics(title: str, metrics: dict) -> None:
    print(f"\n=== {title} ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print()


def read_raw_csv(path: Path):
    import pandas as pd

    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode {path} with utf-8 or latin-1")


def resolve_input_path(explicit: str | None, use_sample: bool) -> Path:
    if explicit:
        return Path(explicit)
    if use_sample:
        return DATA_SAMPLE / "sample_shipments.csv"
    default_full = DATA_RAW / "DataCoSupplyChainDataset.csv"
    if default_full.exists():
        return default_full
    sample_fallback = DATA_SAMPLE / "sample_shipments.csv"
    print(
        f"WARNING: {default_full} not found — falling back to sample dataset "
        f"at {sample_fallback}. Run scripts/generate_sample_data.py first if "
        f"that's missing too, or see docs/data-pipeline.md to obtain the real dataset.",
        file=sys.stderr,
    )
    return sample_fallback
