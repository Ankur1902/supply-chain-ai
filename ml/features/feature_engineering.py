"""
Feature engineering — turns the cleaned dataset into the ML-ready feature
table described by ml/features/feature_spec.py.

TEMPORAL LEAKAGE PREVENTION (section 13):
`shipping_mode_delay_rate`, `category_delay_rate`, `supplier_delay_rate`, and
`route_risk` are historical rate features. Computing them as a plain
groupby-mean over the WHOLE dataset would leak future information into past
rows (e.g. a shipment on day 1 would "know" the category's delay rate
computed using data through day 730). Instead we compute them as an
EXPANDING mean, sorted by order_date, SHIFTED by one row within each group —
i.e. each row only sees outcomes from strictly earlier orders in the same
group. The first occurrence of a group has no prior history, so it falls
back to the global trailing rate at that point in time (also shifted).
"""

import numpy as np
import pandas as pd

from ml.features.supplier_master import assign_suppliers, generate_supplier_master

MIN_HISTORY_FOR_GROUP_RATE = 1  # a single prior observation is enough to start using the group rate


def _causal_group_rate(df: pd.DataFrame, group_col: str, target_col: str = "late_delivery_risk") -> pd.Series:
    """Expanding mean of target_col within group_col, shifted by 1, computed
    on data sorted by order_date. Falls back to the global expanding mean
    (also shifted) wherever the group has no prior history yet."""
    global_expanding = df[target_col].expanding().mean().shift(1)
    group_expanding = (
        df.groupby(group_col)[target_col]
        .apply(lambda s: s.expanding().mean().shift(1))
        .reset_index(level=0, drop=True)
    )
    result = group_expanding.fillna(global_expanding)
    result = result.fillna(df[target_col].mean())  # first-ever row: dataset-level fallback constant
    return result


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("order_date").reset_index(drop=True)

    df["order_hour"] = df["order_date"].dt.hour
    df["order_day_of_week"] = df["order_date"].dt.day_name()
    df["order_month"] = df["order_date"].dt.month

    df["shipping_mode_delay_rate"] = _causal_group_rate(df, "shipping_mode")
    df["category_delay_rate"] = _causal_group_rate(df, "category_name")
    df["route_risk"] = _causal_group_rate(df, "destination_region")

    return df


def add_supplier_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    categories = sorted(df["category_name"].unique().tolist())
    regions = sorted(df["destination_region"].unique().tolist())
    supplier_master = generate_supplier_master(categories, regions)

    df = df.copy()
    df["supplier_code"] = assign_suppliers(df, supplier_master)

    supplier_lookup = supplier_master.set_index("supplier_code")
    df["historical_supplier_reliability"] = df["supplier_code"].map(supplier_lookup["reliability_score"])
    df["supplier_lead_time"] = df["supplier_code"].map(supplier_lookup["historical_lead_time_days"])

    # Supplier delay rate must ALSO be causal (computed only from that
    # supplier's own prior shipments), consistent with the other rate features.
    df = df.sort_values("order_date").reset_index(drop=True)
    df["supplier_delay_rate"] = _causal_group_rate(df, "supplier_code")

    return df, supplier_master


def build_feature_table(cleaned_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = add_temporal_features(cleaned_df)
    df, supplier_master = add_supplier_features(df)
    return df, supplier_master
