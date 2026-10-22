"""Integration tests for Machine Learning Training, Evaluation, and Inference Pipeline.

Verifies:
- Training pipeline execution, model serialization, and metadata consistency
- Evaluation metric reporting comparing Rule Baseline vs. ML
- Inference engine probability outputs and decision categorizations
- Fail-safe fallback to Rule Baseline when model artifacts are unavailable
"""

from pathlib import Path
import pytest
import numpy as np

from ml.train import train_model, MODEL_VERSION
from ml.evaluate import evaluate_test_split, ACADEMIC_DISCLAIMER
from ml.predict import FraudDetector, DECISION_LOW_RISK, DECISION_HIGH_RISK


def test_train_pipeline_and_artifacts(tmp_path):
    """Verify training pipeline trains and persists compatible model artifacts."""
    # Keep generated data inside tmp_path: never write into the real ml/data directory
    pipeline, metadata = train_model(
        data_path=tmp_path / "synthetic_transactions.csv",
        output_dir=tmp_path,
        random_seed=42,
        num_samples_if_missing=500,
    )

    model_file = tmp_path / "model.joblib"
    meta_file = tmp_path / "metadata.json"

    assert model_file.exists()
    assert meta_file.exists()
    assert metadata["model_version"] == MODEL_VERSION
    assert metadata["algorithm"] == "RandomForestClassifier"
    assert len(metadata["feature_names"]) == 12


def test_evaluation_metrics_reporting(tmp_path):
    """Verify evaluation generates report comparing Rule Baseline vs ML on held-out data."""
    # Ensure artifacts exist
    data_path = tmp_path / "synthetic_transactions.csv"
    train_model(data_path=data_path, output_dir=tmp_path, random_seed=42, num_samples_if_missing=500)

    report = evaluate_test_split(data_path=data_path, artifacts_dir=tmp_path)

    assert "machine_learning_model" in report
    assert "rule_based_baseline" in report
    assert "disclaimer" in report
    assert report["disclaimer"] == ACADEMIC_DISCLAIMER

    ml = report["machine_learning_model"]
    rb = report["rule_based_baseline"]

    # Valid metric bounds
    assert 0.0 <= ml["precision"] <= 1.0
    assert 0.0 <= ml["recall"] <= 1.0
    assert 0.0 <= ml["f1_score"] <= 1.0
    assert 0.0 <= rb["precision"] <= 1.0
    assert 0.0 <= rb["recall"] <= 1.0

    # Confusion matrix structure
    for key in ["true_positives", "false_positives", "true_negatives", "false_negatives"]:
        assert key in ml["confusion_matrix"]
        assert key in rb["confusion_matrix"]


def test_inference_engine_with_model():
    """Verify FraudDetector outputs valid probability score, decision, and explanation."""
    detector = FraudDetector()

    # Normal low-risk transaction
    normal_features = {
        "amount": 1200.0,
        "log_amount": float(np.log1p(1200.0)),
        "hour_of_day": 14,
        "is_night": 0,
        "day_of_week": 2,
        "is_weekend": 0,
        "customer_tx_count": 10,
        "customer_avg_amount": 1300.0,
        "amount_to_avg_ratio": 0.92,
        "time_since_last_tx_sec": 45000.0,
        "tx_velocity_1h": 1,
        "is_new_destination": 0,
    }
    res_normal = detector.predict_features(normal_features)
    assert 0.0 <= res_normal["risk_score"] <= 1.0
    assert res_normal["decision"] in (DECISION_LOW_RISK, "MEDIUM_RISK")
    assert isinstance(res_normal["explanation"], str)

    # High-risk structuring transaction
    suspicious_features = {
        "amount": 49500.0,
        "log_amount": float(np.log1p(49500.0)),
        "hour_of_day": 2,
        "is_night": 1,
        "day_of_week": 1,
        "is_weekend": 0,
        "customer_tx_count": 2,
        "customer_avg_amount": 2500.0,
        "amount_to_avg_ratio": 19.8,
        "time_since_last_tx_sec": 120.0,
        "tx_velocity_1h": 4,
        "is_new_destination": 1,
    }
    res_suspicious = detector.predict_features(suspicious_features)
    assert res_suspicious["risk_score"] >= 0.50
    assert res_suspicious["decision"] in ("MEDIUM_RISK", DECISION_HIGH_RISK)
    assert len(res_suspicious["rule_flags"]) > 0


def test_inference_engine_failsafe_fallback(tmp_path):
    """Verify FraudDetector falls back to RuleBaseline if model artifacts are missing."""
    empty_dir = tmp_path / "empty_artifacts"
    empty_dir.mkdir()

    detector = FraudDetector(artifacts_dir=empty_dir)
    assert detector.is_fallback is True
    assert "fallback" in detector.model_version.lower()

    # Inference must still succeed via RuleBaseline without throwing exception
    features = {
        "amount": 49000.0,
        "is_night": 1,
        "customer_avg_amount": 3000.0,
        "amount_to_avg_ratio": 16.3,
        "time_since_last_tx_sec": 86400.0,
        "tx_velocity_1h": 1,
    }
    result = detector.predict_features(features)
    assert "risk_score" in result
    assert result["risk_score"] > 0.0
    assert "rule-baseline" in result["model_version"]
