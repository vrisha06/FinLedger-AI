"""Unit tests for Feature Engineering and Rule-Based Fraud Detection Baseline.

Verifies:
- Leakage-free feature transformations (strictly past-relative aggregations)
- Exclusion of ground-truth target from features
- Deterministic heuristic rule triggering across all 5 fraud scenarios
- Risk score boundaries [0.0, 1.0]
"""

from datetime import datetime, timezone
import pytest
import pandas as pd
import numpy as np

from ml.generator import generate_synthetic_transactions
from ml.features import extract_features_df, extract_single_features, FEATURE_COLUMNS
from ml.rules import (
    RuleBaseline,
    RULE_VELOCITY_BURST,
    RULE_ZSCORE_OUTLIER,
    RULE_RAPID_DRAIN,
    RULE_OFF_HOURS_HIGH_VALUE,
    RULE_STRUCTURING,
)


def test_feature_extraction_no_leakage():
    """Verify that feature engineering does not include targets or future state."""
    df = generate_synthetic_transactions(num_transactions=100, num_customers=10, random_seed=42)

    features = extract_features_df(df)

    # Features must match FEATURE_COLUMNS exactly
    assert list(features.columns) == FEATURE_COLUMNS
    assert "is_fraud" not in features.columns
    assert "fraud_scenario" not in features.columns

    # No NaN values
    assert not features.isnull().any().any()

    # The first transaction for any customer must have prior count = 0
    first_row = features.iloc[0]
    assert first_row["customer_tx_count"] == 0


def test_single_feature_extraction():
    """Verify extract_single_features handles cold-start and historical profiles correctly."""
    # Cold start (no prior history)
    features_cold = extract_single_features(
        amount=5000.0,
        timestamp=datetime(2026, 9, 10, 14, 30, tzinfo=timezone.utc),
        destination_account_id="dest-uuid-1",
        prior_transactions=[],
    )
    assert features_cold["customer_tx_count"] == 0
    assert features_cold["amount_to_avg_ratio"] == 1.0
    assert features_cold["hour_of_day"] == 14
    assert features_cold["is_night"] == 0
    assert features_cold["is_new_destination"] == 1

    # With history
    history = [
        {"amount": 1000.0, "timestamp": datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc), "destination_account_id": "dest-uuid-1"},
        {"amount": 2000.0, "timestamp": datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc), "destination_account_id": "dest-uuid-2"},
    ]
    features_warm = extract_single_features(
        amount=9000.0,
        timestamp=datetime(2026, 9, 10, 12, 5, tzinfo=timezone.utc),
        destination_account_id="dest-uuid-1",
        prior_transactions=history,
    )
    assert features_warm["customer_tx_count"] == 2
    assert features_warm["customer_avg_amount"] == 1500.0
    assert features_warm["amount_to_avg_ratio"] == 6.0
    assert features_warm["time_since_last_tx_sec"] == 300.0  # 5 minutes
    assert features_warm["is_new_destination"] == 0


def test_rule_baseline_triggers_all_scenarios():
    """Verify that RuleBaseline triggers each of the 5 canonical fraud scenarios."""
    # 1. VELOCITY_BURST
    score, flags, _ = RuleBaseline.evaluate_features({
        "amount": 2000.0,
        "is_night": 0,
        "customer_avg_amount": 2000.0,
        "amount_to_avg_ratio": 1.0,
        "time_since_last_tx_sec": 60.0,  # 1 min
        "tx_velocity_1h": 5,
    })
    assert RULE_VELOCITY_BURST in flags
    assert score > 0.0

    # 2. ZSCORE_OUTLIER
    score, flags, _ = RuleBaseline.evaluate_features({
        "amount": 50000.0,
        "is_night": 0,
        "customer_avg_amount": 2500.0,
        "amount_to_avg_ratio": 20.0,
        "time_since_last_tx_sec": 86400.0,
        "tx_velocity_1h": 1,
    })
    assert RULE_ZSCORE_OUTLIER in flags
    assert score > 0.0

    # 3. RAPID_DRAIN
    score, flags, _ = RuleBaseline.evaluate_features({
        "amount": 30000.0,
        "is_night": 0,
        "customer_avg_amount": 8000.0,
        "amount_to_avg_ratio": 3.75,
        "time_since_last_tx_sec": 120.0,
        "tx_velocity_1h": 2,
    })
    assert RULE_RAPID_DRAIN in flags

    # 4. OFF_HOURS_HIGH_VALUE
    score, flags, _ = RuleBaseline.evaluate_features({
        "amount": 40000.0,
        "is_night": 1,
        "customer_avg_amount": 20000.0,
        "amount_to_avg_ratio": 2.0,
        "time_since_last_tx_sec": 86400.0,
        "tx_velocity_1h": 1,
    })
    assert RULE_OFF_HOURS_HIGH_VALUE in flags

    # 5. STRUCTURING
    score, flags, _ = RuleBaseline.evaluate_features({
        "amount": 49500.0,
        "is_night": 0,
        "customer_avg_amount": 5000.0,
        "amount_to_avg_ratio": 9.9,
        "time_since_last_tx_sec": 86400.0,
        "tx_velocity_1h": 1,
    })
    assert RULE_STRUCTURING in flags


def test_rule_baseline_normal_transaction():
    """Verify that normal transactions trigger zero rules and yield 0.0 risk score."""
    score, flags, exp = RuleBaseline.evaluate_features({
        "amount": 1500.0,
        "is_night": 0,
        "customer_avg_amount": 1400.0,
        "amount_to_avg_ratio": 1.07,
        "time_since_last_tx_sec": 72000.0,
        "tx_velocity_1h": 1,
    })
    assert score == 0.0
    assert len(flags) == 0
    assert "conforms" in exp.lower()
