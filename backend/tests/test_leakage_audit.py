"""
Unit tests for the target-leakage audit (scripts/check_data_leakage.py).
Verifies the classification logic and the empirical correlation check
against small, hand-built DataFrames — not the full pipeline.
"""

import pandas as pd
import pytest

from scripts.check_data_leakage import classify_columns, correlation_with_target, HIGH_CARDINALITY_THRESHOLD
from ml.features.feature_spec import TARGET_COLUMN


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "late_delivery_risk": [0, 1, 0, 1, 0, 1, 0, 1],
            "days_for_shipping_real": [2, 5, 2, 6, 3, 5, 2, 7],
            "delivery_status": [
                "Shipping on time", "Late delivery", "Shipping on time", "Late delivery",
                "Shipping on time", "Late delivery", "Shipping on time", "Late delivery",
            ],
            "shipping_mode": ["Standard Class"] * 4 + ["Same Day"] * 4,
            "category_name": ["Cameras"] * 8,
            "customer_id": list(range(8)),
            "totally_new_unexpected_column": ["x"] * 8,
        }
    )


def test_target_is_classified_as_target(sample_df):
    classification = classify_columns(sample_df)
    assert classification["late_delivery_risk"][0] == "TARGET"


def test_known_leakage_field_is_excluded(sample_df):
    classification = classify_columns(sample_df)
    assert classification["days_for_shipping_real"][0] == "EXCLUDED_LEAKAGE"
    assert classification["delivery_status"][0] == "EXCLUDED_LEAKAGE"


def test_identifier_column_is_flagged(sample_df):
    classification = classify_columns(sample_df)
    assert classification["customer_id"][0] == "IDENTIFIER"


def test_safe_feature_is_classified_correctly(sample_df):
    classification = classify_columns(sample_df)
    assert classification["shipping_mode"][0] == "SAFE_FEATURE"


def test_unknown_column_triggers_unclassified_warning(sample_df):
    """This is the schema-drift guard: an unreviewed column must never
    silently pass through as safe."""
    classification = classify_columns(sample_df)
    assert classification["totally_new_unexpected_column"][0] == "UNCLASSIFIED"


def test_leakage_field_correlates_strongly_with_target(sample_df):
    """Empirical evidence, not just a rule: the excluded field should show
    a strong, measurable relationship with the target."""
    corr = correlation_with_target(sample_df, ["delivery_status"], sample_df[TARGET_COLUMN])
    assert corr["delivery_status"] is not None
    assert abs(corr["delivery_status"]) > 0.5


def test_high_cardinality_categorical_column_is_not_misleadingly_scored():
    """A near-unique CATEGORICAL column (e.g. a raw timestamp string) would
    trivially show a 1.0 delay-rate spread under the naive groupby approach
    — this must be reported as unmeasured (None), not a fake perfect
    correlation. (A high-cardinality *numeric* column is handled by the
    ordinary Pearson-correlation path, not this categorical guard.)"""
    n = HIGH_CARDINALITY_THRESHOLD + 1
    df = pd.DataFrame(
        {
            "late_delivery_risk": [0, 1] * n,
            "near_unique_timestamp": [f"2024-01-01 00:00:{i:02d}" for i in range(2 * n)],
        }
    )
    corr = correlation_with_target(df, ["near_unique_timestamp"], df[TARGET_COLUMN])
    assert corr["near_unique_timestamp"] is None
