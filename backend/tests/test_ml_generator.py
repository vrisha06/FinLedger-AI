"""Unit and integration tests for FinLedger-AI Synthetic Transaction Generator.

Verifies:
- Seed reproducibility (identical outputs for identical random seeds)
- Field validation and positive amount constraints
- Representation of all five injected ground-truth fraud scenarios
- Exploratory Benford's Law distribution analysis
"""

from datetime import datetime, timezone
import pytest
import pandas as pd

from ml.generator import (
    generate_synthetic_transactions,
    evaluate_benford_law,
    SCENARIO_NONE,
    SCENARIO_VELOCITY_BURST,
    SCENARIO_ZSCORE_OUTLIER,
    SCENARIO_RAPID_DRAIN,
    SCENARIO_OFF_HOURS_HIGH_VALUE,
    SCENARIO_STRUCTURING,
    ALL_FRAUD_SCENARIOS,
)


def test_generator_seed_reproducibility():
    """Verify that identical random seeds produce identical transaction sequences."""
    df1 = generate_synthetic_transactions(num_transactions=200, num_customers=10, random_seed=12345)
    df2 = generate_synthetic_transactions(num_transactions=200, num_customers=10, random_seed=12345)

    assert len(df1) == len(df2)
    pd.testing.assert_frame_equal(
        df1[["amount", "is_fraud", "fraud_scenario"]],
        df2[["amount", "is_fraud", "fraud_scenario"]],
    )


def test_generator_fields_and_ranges():
    """Verify that generated records satisfy schema constraints and valid ranges."""
    df = generate_synthetic_transactions(num_transactions=500, num_customers=25, random_seed=42)

    required_columns = [
        "transaction_id",
        "timestamp",
        "source_user_id",
        "source_account_id",
        "destination_account_id",
        "amount",
        "currency",
        "is_fraud",
        "fraud_scenario",
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"

    # Amounts must be strictly positive floats
    assert (df["amount"] > 0.0).all()
    # Currency must strictly be INR
    assert (df["currency"] == "INR").all()
    # Labels must be binary 0 or 1
    assert set(df["is_fraud"].unique()).issubset({0, 1})
    # Source and destination must be distinct
    assert (df["source_account_id"] != df["destination_account_id"]).all()
    # Timestamps must be chronologically ordered
    timestamps = pd.to_datetime(df["timestamp"])
    assert timestamps.is_monotonic_increasing


def test_generator_all_fraud_scenarios_present():
    """Verify that all five ground-truth fraud scenarios are generated."""
    df = generate_synthetic_transactions(
        num_transactions=2000,
        num_customers=50,
        fraud_rate=0.05,
        random_seed=42,
    )

    scenarios = set(df[df["is_fraud"] == 1]["fraud_scenario"].unique())
    for expected_scenario in ALL_FRAUD_SCENARIOS:
        assert expected_scenario in scenarios, f"Scenario {expected_scenario} was not generated"

    # Structuring scenario amounts must fall in synthetic demonstration range [48500, 49950]
    structuring_df = df[df["fraud_scenario"] == SCENARIO_STRUCTURING]
    assert len(structuring_df) > 0
    assert (structuring_df["amount"] >= 48500.0).all()
    assert (structuring_df["amount"] <= 49950.0).all()


def test_benford_law_evaluation():
    """Verify that Benford's Law analysis computes valid MAD and frequency metrics."""
    df = generate_synthetic_transactions(num_transactions=1500, num_customers=30, random_seed=42)
    legit_amounts = df[df["is_fraud"] == 0]["amount"]

    report = evaluate_benford_law(legit_amounts)

    assert "mean_absolute_deviation" in report
    assert "conformity_evaluation" in report
    assert "empirical_frequencies" in report
    assert "theoretical_benford_frequencies" in report

    # Empirical frequencies for digits 1..9 must sum to approximately 1.0
    freq_sum = sum(report["empirical_frequencies"].values())
    assert 0.99 <= freq_sum <= 1.01

    # Theoretical digit 1 should have highest probability (~0.3010)
    assert report["theoretical_benford_frequencies"]["1"] > report["theoretical_benford_frequencies"]["9"]
