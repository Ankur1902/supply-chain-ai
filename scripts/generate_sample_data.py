#!/usr/bin/env python
"""
Generate a DETERMINISTIC SYNTHETIC development dataset that mirrors the raw
column schema of the DataCo Smart Supply Chain Dataset (Kaggle).

This is NOT the real dataset. It exists so the pipeline, backend, ML
training, and frontend can all be developed and demoed without requiring
the ~180K-row Kaggle download. See docs/data-pipeline.md ("Dataset" section)
for the documented process to obtain and use the real dataset instead.

Usage:
    python scripts/generate_sample_data.py --rows 8000 --out data/sample/sample_shipments.csv
    python scripts/generate_sample_data.py --rows 180000 --out data/raw/DataCoSupplyChainDataset.csv --seed 42

The output uses the SAME raw column headers as the real Kaggle CSV so that
scripts/ingest_data.py can consume either file interchangeably.
"""

import argparse
import zlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

RNG_SEED_DEFAULT = 42


def _stable_hash(*parts: str) -> int:
    """Deterministic string hash (Python's builtin hash() is salted per
    process via PYTHONHASHSEED and would break reproducibility)."""
    return zlib.crc32("|".join(parts).encode("utf-8"))

SHIPPING_MODES = ["Standard Class", "First Class", "Second Class", "Same Day"]
SHIPPING_MODE_WEIGHTS = [0.60, 0.15, 0.20, 0.05]
SHIPPING_MODE_SCHEDULED_DAYS = {
    "Same Day": 0,
    "First Class": 1,
    "Second Class": 2,
    "Standard Class": 4,
}
# Base probability a shipment ships late, by mode (Same Day is riskiest to promise).
SHIPPING_MODE_BASE_DELAY_PROB = {
    "Same Day": 0.55,
    "First Class": 0.38,
    "Second Class": 0.30,
    "Standard Class": 0.22,
}

MARKETS = ["LATAM", "Europe", "Pacific Asia", "USCA", "Africa"]
MARKET_REGIONS = {
    "LATAM": ["South America", "Central America", "Caribbean"],
    "Europe": ["Western Europe", "Northern Europe", "Southern Europe", "Eastern Europe"],
    "Pacific Asia": ["Southeast Asia", "Eastern Asia", "Oceania", "South Asia"],
    "USCA": ["US Center", "West of USA", "East of USA", "Canada"],
    "Africa": ["West Africa", "North Africa", "East Africa", "Southern Africa"],
}
# Extra region-level delay pressure (some regions/routes are just worse).
REGION_DELAY_ADJUSTMENT = {
    "South America": 0.08, "Central America": 0.10, "Caribbean": 0.06,
    "Western Europe": -0.05, "Northern Europe": -0.07, "Southern Europe": 0.02, "Eastern Europe": 0.05,
    "Southeast Asia": 0.07, "Eastern Asia": -0.02, "Oceania": 0.03, "South Asia": 0.09,
    "US Center": -0.06, "West of USA": -0.08, "East of USA": -0.04, "Canada": -0.05,
    "West Africa": 0.12, "North Africa": 0.05, "East Africa": 0.11, "Southern Africa": 0.04,
}

DEPARTMENTS_CATEGORIES = {
    "Fan Shop": ["Cleats", "Men's Footwear", "Women's Apparel", "Fitness Accessories"],
    "Apparel": ["Men's Footwear", "Women's Apparel", "Kids' Golf Clubs"],
    "Golf": ["Golf Bags & Carts", "Kids' Golf Clubs", "Golf Shoes"],
    "Outdoors": ["Camping & Hiking", "Water Sports", "Hunting & Shooting"],
    "Fitness": ["Cardio Equipment", "Fitness Accessories", "Strength Training"],
    "Team Sports": ["Baseball & Softball", "Basketball", "Soccer"],
    "Electronics": ["Cameras", "Consumer Electronics", "GPS Devices"],
}

CUSTOMER_SEGMENTS = ["Consumer", "Corporate", "Home Office"]
CUSTOMER_SEGMENT_WEIGHTS = [0.55, 0.30, 0.15]

ORDER_STATUSES = [
    "COMPLETE", "PENDING", "CLOSED", "PENDING_PAYMENT", "PROCESSING", "ON_HOLD", "CANCELED",
]
ORDER_STATUS_WEIGHTS = [0.45, 0.15, 0.15, 0.08, 0.09, 0.05, 0.03]

RAW_COLUMNS = [
    "Type", "Days for shipping (real)", "Days for shipment (scheduled)", "Benefit per order",
    "Sales per customer", "Delivery Status", "Late_delivery_risk", "Category Id", "Category Name",
    "Customer City", "Customer Country", "Customer Email", "Customer Fname", "Customer Id",
    "Customer Lname", "Customer Login Type", "Customer Segment", "Customer State", "Customer Street",
    "Customer Zipcode", "Department Id", "Department Name", "Latitude", "Longitude", "Market",
    "Order City", "Order Country", "Order Customer Id", "order date (DateOrders)", "Order Id",
    "Order Item Cardprod Id", "Order Item Discount", "Order Item Discount Rate", "Order Item Id",
    "Order Item Product Price", "Order Item Profit Ratio", "Order Item Quantity", "Sales",
    "Order Item Total", "Order Profit Per Order", "Order Region", "Order State", "Order Status",
    "Order Zipcode", "Product Card Id", "Product Category Id", "Product Name", "Product Price",
    "Product Status", "shipping date (DateOrders)", "Shipping Mode",
]


def _weighted_choice(rng: np.random.Generator, options: list, weights: list, size: int) -> np.ndarray:
    return rng.choice(options, size=size, p=np.array(weights) / sum(weights))


def _fmt_date(d: datetime) -> str:
    """Matches the raw DataCo CSV's 'M/D/YYYY HH:MM' timestamp format,
    without relying on platform-specific strftime flags (%-m is glibc-only
    and breaks on Windows)."""
    return f"{d.month}/{d.day}/{d.year} {d.hour:02d}:{d.minute:02d}"


def generate(n_rows: int, seed: int = RNG_SEED_DEFAULT) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    shipping_mode = _weighted_choice(rng, SHIPPING_MODES, SHIPPING_MODE_WEIGHTS, n_rows)
    market = rng.choice(MARKETS, size=n_rows)
    region = np.array([rng.choice(MARKET_REGIONS[m]) for m in market])
    department = rng.choice(list(DEPARTMENTS_CATEGORIES.keys()), size=n_rows)
    category = np.array([rng.choice(DEPARTMENTS_CATEGORIES[d]) for d in department])
    customer_segment = _weighted_choice(rng, CUSTOMER_SEGMENTS, CUSTOMER_SEGMENT_WEIGHTS, n_rows)
    order_status = _weighted_choice(rng, ORDER_STATUSES, ORDER_STATUS_WEIGHTS, n_rows)

    scheduled_days = np.array([SHIPPING_MODE_SCHEDULED_DAYS[m] for m in shipping_mode])

    base_delay_prob = np.array([SHIPPING_MODE_BASE_DELAY_PROB[m] for m in shipping_mode])
    region_adj = np.array([REGION_DELAY_ADJUSTMENT.get(r, 0.0) for r in region])
    # A hidden "supplier proxy" signal (category+region hash) so category/route
    # combinations have a consistent, learnable delay tendency.
    proxy_hash = np.array([_stable_hash(c, r) % 1000 / 1000 for c, r in zip(category, region)])
    proxy_adj = (proxy_hash - 0.5) * 0.20

    delay_prob = np.clip(base_delay_prob + region_adj + proxy_adj, 0.03, 0.95)
    is_late = rng.random(n_rows) < delay_prob

    delay_extra_days = np.where(
        is_late, rng.integers(1, 5, size=n_rows), -rng.integers(0, 2, size=n_rows)
    )
    days_real = np.clip(scheduled_days + delay_extra_days, 0, None)
    late_delivery_risk = (days_real > scheduled_days).astype(int)

    delivery_status = np.select(
        [
            order_status == "CANCELED",
            late_delivery_risk == 1,
            days_real < scheduled_days,
        ],
        ["Shipping canceled", "Late delivery", "Advance shipping"],
        default="Shipping on time",
    )

    product_price = np.round(rng.uniform(15, 500, size=n_rows), 2)
    quantity = rng.integers(1, 6, size=n_rows)
    discount_rate = np.round(rng.uniform(0, 0.35, size=n_rows), 4)
    order_item_discount = np.round(product_price * quantity * discount_rate, 2)
    sales = np.round(product_price * quantity, 2)
    order_item_total = np.round(sales - order_item_discount, 2)
    profit_ratio = np.round(rng.uniform(-0.1, 0.35, size=n_rows), 4)
    benefit_per_order = np.round(order_item_total * profit_ratio, 2)
    sales_per_customer = np.round(order_item_total * rng.uniform(0.8, 1.0, size=n_rows), 2)

    start_date = datetime(2022, 1, 1)
    order_offsets = rng.integers(0, 730, size=n_rows)
    order_hours = rng.integers(0, 24, size=n_rows)
    order_dates = [
        start_date + timedelta(days=int(o), hours=int(h)) for o, h in zip(order_offsets, order_hours)
    ]
    shipping_dates = [
        od + timedelta(days=int(d)) for od, d in zip(order_dates, days_real)
    ]

    n_customers = max(200, n_rows // 8)
    n_products = max(50, n_rows // 40)
    customer_id = rng.integers(1, n_customers + 1, size=n_rows)
    product_card_id = rng.integers(1, n_products + 1, size=n_rows)
    category_id = pd.factorize(category)[0] + 1
    department_id = pd.factorize(department)[0] + 1

    df = pd.DataFrame(
        {
            "Type": "DEBIT",
            "Days for shipping (real)": days_real,
            "Days for shipment (scheduled)": scheduled_days,
            "Benefit per order": benefit_per_order,
            "Sales per customer": sales_per_customer,
            "Delivery Status": delivery_status,
            "Late_delivery_risk": late_delivery_risk,
            "Category Id": category_id,
            "Category Name": category,
            "Customer City": "Demo City",
            "Customer Country": "EE. UU.",
            "Customer Email": "XXXXXXXXX",
            "Customer Fname": "Demo",
            "Customer Id": customer_id,
            "Customer Lname": "Customer",
            "Customer Login Type": "Individual",
            "Customer Segment": customer_segment,
            "Customer State": "CA",
            "Customer Street": "XXXXXXXXX",
            "Customer Zipcode": 90001,
            "Department Id": department_id,
            "Department Name": department,
            "Latitude": np.round(rng.uniform(-50, 60, size=n_rows), 4),
            "Longitude": np.round(rng.uniform(-120, 120, size=n_rows), 4),
            "Market": market,
            "Order City": "Demo City",
            "Order Country": "Demo Country",
            "Order Customer Id": customer_id,
            "order date (DateOrders)": [_fmt_date(d) for d in order_dates],
            "Order Id": np.arange(1, n_rows + 1),
            "Order Item Cardprod Id": product_card_id,
            "Order Item Discount": order_item_discount,
            "Order Item Discount Rate": discount_rate,
            "Order Item Id": np.arange(1, n_rows + 1),
            "Order Item Product Price": product_price,
            "Order Item Profit Ratio": profit_ratio,
            "Order Item Quantity": quantity,
            "Sales": sales,
            "Order Item Total": order_item_total,
            "Order Profit Per Order": benefit_per_order,
            "Order Region": region,
            "Order State": "NA",
            "Order Status": order_status,
            "Order Zipcode": 90001,
            "Product Card Id": product_card_id,
            "Product Category Id": category_id,
            "Product Name": [f"{c} Item #{p}" for c, p in zip(category, product_card_id)],
            "Product Price": product_price,
            "Product Status": 0,
            "shipping date (DateOrders)": [_fmt_date(d) for d in shipping_dates],
            "Shipping Mode": shipping_mode,
        }
    )
    return df[RAW_COLUMNS]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=RNG_SEED_DEFAULT)
    parser.add_argument("--out", type=str, default="data/sample/sample_shipments.csv")
    args = parser.parse_args()

    df = generate(args.rows, args.seed)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} SYNTHETIC rows (seed={args.seed}) to {args.out}")
    print(f"Late delivery rate: {df['Late_delivery_risk'].mean():.1%}")


if __name__ == "__main__":
    main()
