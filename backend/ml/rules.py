"""Rule-Based Fraud Detection Baseline for FinLedger-AI.

Implements a deterministic, explainable heuristic baseline covering all five
synthetic fraud scenarios:
1. VELOCITY_BURST: Rapid successive transfers within short intervals.
2. ZSCORE_OUTLIER: High ratio relative to historical customer spending baseline.
3. RAPID_DRAIN: Successive high-value draining transfers.
4. OFF_HOURS_HIGH_VALUE: High-value transfers during night hours (01:00 - 05:00 IST).
5. STRUCTURING: Amounts just below the ₹50,000 threshold (synthetic demonstration assumption).

Serves as an objective benchmark for comparison against machine-learning models.
"""

from typing import Any
import numpy as np
import pandas as pd


# Canonical rule flags
RULE_VELOCITY_BURST = "RULE_VELOCITY_BURST"
RULE_ZSCORE_OUTLIER = "RULE_ZSCORE_OUTLIER"
RULE_RAPID_DRAIN = "RULE_RAPID_DRAIN"
RULE_OFF_HOURS_HIGH_VALUE = "RULE_OFF_HOURS_HIGH_VALUE"
RULE_STRUCTURING = "RULE_STRUCTURING"

# Rule weight contributions to the baseline risk score
RULE_WEIGHTS = {
    RULE_VELOCITY_BURST: 0.40,
    RULE_ZSCORE_OUTLIER: 0.40,
    RULE_RAPID_DRAIN: 0.35,
    RULE_OFF_HOURS_HIGH_VALUE: 0.35,
    RULE_STRUCTURING: 0.40,
}

# Baseline classification threshold
RULE_DECISION_THRESHOLD = 0.50


class RuleBaseline:
    """Deterministic rule-based fraud detection engine."""

    @staticmethod
    def evaluate_features(features: dict[str, Any] | pd.Series) -> tuple[float, list[str], str]:
        """Evaluate tabular features against heuristic rules.

        Args:
            features: Dictionary or pandas Series containing features:
                ['amount', 'is_night', 'customer_avg_amount', 'amount_to_avg_ratio',
                 'time_since_last_tx_sec', 'tx_velocity_1h']

        Returns:
            tuple[float, list[str], str]:
                - risk_score: Composite score in [0.0, 1.0].
                - triggered_flags: List of triggered rule flag strings.
                - explanation: Human-readable narrative explaining triggers.
        """
        amount = float(features.get("amount", 0.0))
        is_night = int(features.get("is_night", 0))
        avg_amount = float(features.get("customer_avg_amount", amount))
        ratio = float(features.get("amount_to_avg_ratio", 1.0))
        time_since = float(features.get("time_since_last_tx_sec", 86400.0))
        velocity_1h = int(features.get("tx_velocity_1h", 1))

        triggered = []

        # Rule 1: VELOCITY_BURST
        # >= 4 transactions within 1 hour or transaction within 3 minutes of previous
        if velocity_1h >= 4 or time_since < 180.0:
            triggered.append(RULE_VELOCITY_BURST)

        # Rule 2: ZSCORE_OUTLIER
        # Transfer amount is at least 5x above customer baseline and >= ₹10,000
        if ratio >= 5.0 and amount >= 10000.0:
            triggered.append(RULE_ZSCORE_OUTLIER)

        # Rule 3: RAPID_DRAIN
        # Elevated transfer within 10 minutes of prior activity with substantial amount
        if ratio >= 3.0 and time_since < 600.0 and amount >= 15000.0:
            triggered.append(RULE_RAPID_DRAIN)

        # Rule 4: OFF_HOURS_HIGH_VALUE
        # Transfer occurring during 01:00 - 05:00 IST with amount >= ₹25,000
        if is_night == 1 and amount >= 25000.0:
            triggered.append(RULE_OFF_HOURS_HIGH_VALUE)

        # Rule 5: STRUCTURING (Synthetic Demonstration Assumption)
        # Amounts in [48000.00, 49999.00] simulating avoidance of ₹50k PAN verification
        if 48000.0 <= amount <= 49999.0 and avg_amount < 25000.0:
            triggered.append(RULE_STRUCTURING)

        # Calculate composite score
        raw_score = sum(RULE_WEIGHTS.get(r, 0.0) for r in triggered)
        risk_score = round(min(1.0, raw_score), 4)

        # Construct explainability summary
        if not triggered:
            explanation = "Transaction conforms to standard customer activity and temporal patterns."
        else:
            narratives = []
            if RULE_VELOCITY_BURST in triggered:
                narratives.append(f"Elevated velocity: {velocity_1h} transactions in trailing hour ({time_since:.0f}s elapsed)")
            if RULE_ZSCORE_OUTLIER in triggered:
                narratives.append(f"Spending deviation: amount INR {amount:,.2f} is {ratio:.1f}x customer baseline (INR {avg_amount:,.2f})")
            if RULE_RAPID_DRAIN in triggered:
                narratives.append(f"Rapid successive draining: INR {amount:,.2f} transfer within {time_since:.0f}s of prior transaction")
            if RULE_OFF_HOURS_HIGH_VALUE in triggered:
                narratives.append(f"Off-hours high value: INR {amount:,.2f} initiated during late-night hours (01:00-05:00 IST)")
            if RULE_STRUCTURING in triggered:
                narratives.append(f"Structuring pattern: INR {amount:,.2f} falls just below ₹50,000 regulatory reporting threshold")

            explanation = "Triggered baseline alerts: " + "; ".join(narratives) + "."

        return risk_score, triggered, explanation

    @staticmethod
    def predict_df(features_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[list[str]]]:
        """Batch evaluate a features DataFrame against the rule baseline.

        Args:
            features_df: DataFrame matching FEATURE_COLUMNS.

        Returns:
            tuple:
                - scores: 1D array of float scores in [0.0, 1.0].
                - predictions: 1D binary array (1 if score >= 0.50 else 0).
                - all_flags: List of triggered flag lists per row.
        """
        scores = np.zeros(len(features_df), dtype=float)
        predictions = np.zeros(len(features_df), dtype=int)
        all_flags = []

        for idx, (_, row) in enumerate(features_df.iterrows()):
            score, flags, _ = RuleBaseline.evaluate_features(row)
            scores[idx] = score
            predictions[idx] = 1 if score >= RULE_DECISION_THRESHOLD else 0
            all_flags.append(flags)

        return scores, predictions, all_flags
