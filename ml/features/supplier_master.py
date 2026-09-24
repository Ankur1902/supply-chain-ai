"""
Demo Supplier Enrichment Layer (section 4 of the platform spec).

The DataCo dataset has no real supplier identity. This module generates a
DETERMINISTIC SYNTHETIC supplier master — a fixed-size pool of suppliers per
(product_category) with a fixed random seed — and deterministically assigns
every shipment to one of the suppliers serving its category/region, using a
stable hash (not Python's salted `hash()`) so re-running the pipeline always
produces the same assignment.

This is clearly synthetic and must never be presented as real company data.
Every Supplier row has `is_synthetic=True` and the UI badges it accordingly.
"""

import zlib

import numpy as np
import pandas as pd

SUPPLIER_SEED = 42
SUPPLIERS_PER_CATEGORY = 4
SUPPLIER_TIERS = ["strategic", "preferred", "standard"]
SUPPLIER_TIER_WEIGHTS = [0.15, 0.35, 0.50]

SUPPLIER_NAME_PREFIXES = [
    "Meridian", "Northgate", "Summit", "Vanguard", "Atlas", "Beacon", "Cascade",
    "Anchor", "Horizon", "Pinnacle", "Crestline", "Ironbridge", "Sterling",
    "Windward", "Harbor", "Fieldstone", "Redwood", "Granite", "Lighthouse", "Frontier",
]
SUPPLIER_NAME_SUFFIXES = ["Supply Co.", "Logistics", "Trading Group", "Distribution", "Sourcing Partners"]


def _stable_hash(*parts: str) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def generate_supplier_master(categories: list[str], regions: list[str], seed: int = SUPPLIER_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    supplier_seq = 1
    for category in sorted(categories):
        for i in range(SUPPLIERS_PER_CATEGORY):
            region = regions[_stable_hash(category, str(i)) % len(regions)]
            tier = rng.choice(SUPPLIER_TIERS, p=SUPPLIER_TIER_WEIGHTS)
            name_prefix = SUPPLIER_NAME_PREFIXES[_stable_hash(category, str(i), "prefix") % len(SUPPLIER_NAME_PREFIXES)]
            name_suffix = SUPPLIER_NAME_SUFFIXES[_stable_hash(category, str(i), "suffix") % len(SUPPLIER_NAME_SUFFIXES)]

            rows.append(
                {
                    "supplier_code": f"SUP-{supplier_seq:04d}",
                    "supplier_name": f"{name_prefix} {name_suffix}",
                    "supplier_region": region,
                    "supplier_tier": tier,
                    "product_category": category,
                    "historical_lead_time_days": round(float(rng.uniform(1.5, 9.0)), 2),
                    "capacity_score": round(float(rng.uniform(40, 95)), 2),
                    "quality_score": round(float(rng.uniform(50, 98)), 2),
                    "reliability_score": round(float(rng.uniform(45, 97)), 2),
                    "cost_score": round(float(rng.uniform(40, 95)), 2),
                    "risk_score": round(float(rng.uniform(5, 60)), 2),
                    "is_synthetic": True,
                }
            )
            supplier_seq += 1
    return pd.DataFrame(rows)


def assign_suppliers(df: pd.DataFrame, supplier_master: pd.DataFrame) -> pd.Series:
    """Deterministically assign each shipment row to a supplier_code that
    serves its product_category, picking among that category's supplier
    pool using a stable hash of (order_id, order_item_id) so the same
    shipment always maps to the same supplier across pipeline runs."""
    by_category = {
        cat: group["supplier_code"].tolist() for cat, group in supplier_master.groupby("product_category")
    }

    def _pick(row) -> str:
        pool = by_category.get(row["category_name"])
        if not pool:
            # Category not in master (shouldn't happen if master was built
            # from this df's own categories) — fall back to full pool.
            pool = supplier_master["supplier_code"].tolist()
        idx = _stable_hash(row["order_id"], row["order_item_id"]) % len(pool)
        return pool[idx]

    return df.apply(_pick, axis=1)
