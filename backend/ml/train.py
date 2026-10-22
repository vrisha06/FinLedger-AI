"""Machine Learning Training Pipeline for FinLedger-AI Fraud Detection.

Implements:
1. Temporal holdout split (70% Train, 15% Validation, 15% Test) ensuring zero future leakage.
2. Leakage-free preprocessing (fitted strictly on training data).
3. Class-imbalanced classification using Scikit-Learn RandomForestClassifier.
4. Model artifact serialization (model.joblib) and comprehensive metadata logging (metadata.json).
"""

from datetime import datetime, timezone
import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Ensure backend root is on sys.path for direct CLI script execution
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings
from ml.generator import generate_synthetic_transactions
from ml.features import extract_features_df, FEATURE_COLUMNS


MODEL_VERSION = "rf-v1.0.0"
DEFAULT_DECISION_THRESHOLD = 0.70


def prepare_temporal_splits(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split chronological transactions into temporal Train, Validation, and Test sets.

    Ensures that test records occur chronologically after validation records,
    and validation records occur chronologically after training records.
    """
    sorted_df = df.copy()
    sorted_df["parsed_time"] = pd.to_datetime(sorted_df["timestamp"], utc=True)
    sorted_df.sort_values(by="parsed_time", inplace=True)
    sorted_df.reset_index(drop=True, inplace=True)

    n_total = len(sorted_df)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    train_df = sorted_df.iloc[:n_train].copy()
    val_df = sorted_df.iloc[n_train : n_train + n_val].copy()
    test_df = sorted_df.iloc[n_train + n_val :].copy()

    return train_df, val_df, test_df


def train_model(
    data_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    random_seed: int = 42,
    num_samples_if_missing: int = 10000,
) -> tuple[Pipeline, dict]:
    """Train the fraud classification pipeline and persist artifacts.

    Args:
        data_path: Path to synthetic_transactions.csv. If missing, generated automatically.
        output_dir: Directory where model.joblib and metadata.json are saved.
        random_seed: Random generator seed.
        num_samples_if_missing: Number of synthetic transactions to generate if file missing.

    Returns:
        tuple[Pipeline, dict]: Trained Scikit-Learn pipeline and metadata dictionary.
    """
    if output_dir is None:
        artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    else:
        artifacts_dir = Path(output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load or generate synthetic data
    if data_path is None:
        data_path = Path(__file__).resolve().parent / "data" / "synthetic_transactions.csv"
    else:
        data_path = Path(data_path)

    if not data_path.exists():
        print(f"[Train] Dataset not found at {data_path}. Generating {num_samples_if_missing} transactions...")
        df = generate_synthetic_transactions(
            num_transactions=num_samples_if_missing,
            random_seed=random_seed,
        )
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
    else:
        print(f"[Train] Loading existing dataset from {data_path}...")
        df = pd.read_csv(data_path)

    # 2. Split temporally
    train_df, val_df, test_df = prepare_temporal_splits(df, train_ratio=0.70, val_ratio=0.15)
    print(f"[Train] Temporal split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # 3. Extract features (leakage-free per partition)
    X_train = extract_features_df(train_df)
    y_train = train_df["is_fraud"].values

    X_val = extract_features_df(val_df)
    y_val = val_df["is_fraud"].values

    # 4. Construct Scikit-Learn Pipeline
    # Preprocessor scaler fitted strictly on X_train
    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=random_seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    print(f"[Train] Fitting RandomForestClassifier with {len(FEATURE_COLUMNS)} features...")
    pipeline.fit(X_train, y_train)

    # 5. Validation performance check
    val_probs = pipeline.predict_proba(X_val)[:, 1]
    val_preds = (val_probs >= DEFAULT_DECISION_THRESHOLD).astype(int)
    val_fraud_count = int(y_val.sum())
    val_detected = int((val_preds & y_val).sum())
    print(f"[Train] Validation check: Total fraud={val_fraud_count}, Detected at thr={DEFAULT_DECISION_THRESHOLD}: {val_detected}")

    # 6. Save model artifact and metadata
    model_path = artifacts_dir / "model.joblib"
    metadata_path = artifacts_dir / "metadata.json"

    joblib.dump(pipeline, model_path)
    print(f"[Train] Model pipeline saved to {model_path}")

    metadata = {
        "model_version": MODEL_VERSION,
        "algorithm": "RandomForestClassifier",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": random_seed,
        "decision_threshold": DEFAULT_DECISION_THRESHOLD,
        "feature_names": FEATURE_COLUMNS,
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "train_fraud_count": int(y_train.sum()),
        "train_fraud_rate": round(float(y_train.mean()), 4),
        "val_fraud_count": val_fraud_count,
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[Train] Training metadata saved to {metadata_path}")

    return pipeline, metadata


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train FinLedger-AI fraud classification model.")
    parser.add_argument("--data", type=str, default=None, help="Path to synthetic_transactions.csv")
    parser.add_argument("--output", type=str, default=None, help="Directory to save model artifacts")
    parser.add_argument("--seed", type=int, default=42, help="Random generator seed")
    parser.add_argument("--count", type=int, default=10000, help="Transactions to generate if data missing")
    args = parser.parse_args()

    train_model(
        data_path=args.data,
        output_dir=args.output,
        random_seed=args.seed,
        num_samples_if_missing=args.count,
    )
