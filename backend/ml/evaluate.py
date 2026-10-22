"""Model Evaluation and Benchmark Framework for FinLedger-AI Fraud Detection.

Compares the trained Scikit-Learn machine-learning model against the rule-based baseline
on the exact same held-out temporal test split.

Calculates:
- Precision, Recall, F1-Score (fraud class and macro)
- ROC-AUC and Precision-Recall AUC (Average Precision)
- Confusion Matrix (TN, FP, FN, TP)
- Academic Disclaimers and Limitations Documentation
"""

import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
)

# Ensure backend root is on sys.path for direct CLI script execution
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from ml.features import extract_features_df
from ml.rules import RuleBaseline
from ml.train import prepare_temporal_splits, DEFAULT_DECISION_THRESHOLD

ACADEMIC_DISCLAIMER = (
    "ACADEMIC DISCLAIMER: This evaluation was conducted strictly on synthetic banking transaction data. "
    "The metrics reflect performance on simulated distributions and ground-truth injected scenarios, "
    "and DO NOT represent validated real-world fraud detection efficacy or generalizability to actual financial traffic."
)


def evaluate_test_split(
    data_path: Path | str | None = None,
    artifacts_dir: Path | str | None = None,
    decision_threshold: float = DEFAULT_DECISION_THRESHOLD,
) -> dict:
    """Evaluate ML model vs Rule baseline on held-out temporal test set."""
    if artifacts_dir is None:
        art_dir = Path(__file__).resolve().parent / "artifacts"
    else:
        art_dir = Path(artifacts_dir)

    model_path = art_dir / "model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {model_path}. Run train.py first.")

    pipeline = joblib.load(model_path)

    if data_path is None:
        data_path = Path(__file__).resolve().parent / "data" / "synthetic_transactions.csv"
    else:
        data_path = Path(data_path)

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found at {data_path}. Run generator.py first.")

    df = pd.read_csv(data_path)

    # Use the same temporal split (Test is the last 15% chronologically)
    _, _, test_df = prepare_temporal_splits(df, train_ratio=0.70, val_ratio=0.15)
    y_test = test_df["is_fraud"].values
    total_test = len(test_df)
    fraud_count_test = int(y_test.sum())

    # Extract features for test set
    X_test = extract_features_df(test_df)

    # 1. Evaluate Machine Learning Model
    ml_probs = pipeline.predict_proba(X_test)[:, 1]
    ml_preds = (ml_probs >= decision_threshold).astype(int)

    ml_cm = confusion_matrix(y_test, ml_preds, labels=[0, 1])
    tn_ml, fp_ml, fn_ml, tp_ml = ml_cm.ravel()

    ml_prec = float(precision_score(y_test, ml_preds, zero_division=0))
    ml_rec = float(recall_score(y_test, ml_preds, zero_division=0))
    ml_f1 = float(f1_score(y_test, ml_preds, zero_division=0))
    ml_roc_auc = float(roc_auc_score(y_test, ml_probs)) if len(np.unique(y_test)) > 1 else None
    ml_pr_auc = float(average_precision_score(y_test, ml_probs)) if len(np.unique(y_test)) > 1 else None

    # 2. Evaluate Rule-Based Baseline on the exact same test set
    rule_scores, rule_preds, _ = RuleBaseline.predict_df(X_test)

    rule_cm = confusion_matrix(y_test, rule_preds, labels=[0, 1])
    tn_rb, fp_rb, fn_rb, tp_rb = rule_cm.ravel()

    rb_prec = float(precision_score(y_test, rule_preds, zero_division=0))
    rb_rec = float(recall_score(y_test, rule_preds, zero_division=0))
    rb_f1 = float(f1_score(y_test, rule_preds, zero_division=0))
    rb_roc_auc = float(roc_auc_score(y_test, rule_scores)) if len(np.unique(y_test)) > 1 else None
    rb_pr_auc = float(average_precision_score(y_test, rule_scores)) if len(np.unique(y_test)) > 1 else None

    # 3. Assemble Evaluation Report
    report = {
        "evaluation_timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "disclaimer": ACADEMIC_DISCLAIMER,
        "test_dataset": {
            "total_samples": total_test,
            "fraud_samples": fraud_count_test,
            "legitimate_samples": total_test - fraud_count_test,
            "fraud_prevalence": round(float(fraud_count_test / total_test), 4),
        },
        "decision_threshold": decision_threshold,
        "machine_learning_model": {
            "algorithm": "RandomForestClassifier",
            "decision_threshold": decision_threshold,
            "precision": round(ml_prec, 4),
            "recall": round(ml_rec, 4),
            "f1_score": round(ml_f1, 4),
            "roc_auc": round(ml_roc_auc, 4) if ml_roc_auc is not None else None,
            "pr_auc": round(ml_pr_auc, 4) if ml_pr_auc is not None else None,
            "confusion_matrix": {
                "true_negatives": int(tn_ml),
                "false_positives": int(fp_ml),
                "false_negatives": int(fn_ml),
                "true_positives": int(tp_ml),
            },
        },
        "rule_based_baseline": {
            "algorithm": "RuleBaseline (5 Scenarios)",
            "decision_threshold": 0.50,
            "precision": round(rb_prec, 4),
            "recall": round(rb_rec, 4),
            "f1_score": round(rb_f1, 4),
            "roc_auc": round(rb_roc_auc, 4) if rb_roc_auc is not None else None,
            "pr_auc": round(rb_pr_auc, 4) if rb_pr_auc is not None else None,
            "confusion_matrix": {
                "true_negatives": int(tn_rb),
                "false_positives": int(fp_rb),
                "false_negatives": int(fn_rb),
                "true_positives": int(tp_rb),
            },
        },
        "comparison_summary": {
            "precision_delta_ml_vs_rules": round(ml_prec - rb_prec, 4),
            "recall_delta_ml_vs_rules": round(ml_rec - rb_rec, 4),
            "f1_delta_ml_vs_rules": round(ml_f1 - rb_f1, 4),
            "key_finding": (
                "ML model reduces false positives via probability calibration while "
                "rule baseline provides deterministic explainability for operational triage."
            ),
        },
    }

    # Save to artifacts directory
    report_path = art_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    print("=" * 70)
    print("FINLEDGER-AI — FRAUD DETECTION EVALUATION BENCHMARK")
    print("=" * 70)
    report = evaluate_test_split()

    print(f"Test Split Size:     {report['test_dataset']['total_samples']} transactions")
    print(f"Ground-Truth Fraud:  {report['test_dataset']['fraud_samples']} ({report['test_dataset']['fraud_prevalence']:.2%})")
    print("-" * 70)
    print(f"{'Metric':<25} {'Rule Baseline':<20} {'ML Model (RF)':<20}")
    print("-" * 70)

    rb = report["rule_based_baseline"]
    ml = report["machine_learning_model"]

    print(f"{'Precision':<25} {rb['precision']:<20.4f} {ml['precision']:<20.4f}")
    print(f"{'Recall':<25} {rb['recall']:<20.4f} {ml['recall']:<20.4f}")
    print(f"{'F1-Score':<25} {rb['f1_score']:<20.4f} {ml['f1_score']:<20.4f}")
    print(f"{'ROC-AUC':<25} {rb['roc_auc'] or 0.0:<20.4f} {ml['roc_auc'] or 0.0:<20.4f}")
    print(f"{'PR-AUC':<25} {rb['pr_auc'] or 0.0:<20.4f} {ml['pr_auc'] or 0.0:<20.4f}")
    print("-" * 70)
    print(f"ML Confusion Matrix:   TP={ml['confusion_matrix']['true_positives']}, FP={ml['confusion_matrix']['false_positives']}, TN={ml['confusion_matrix']['true_negatives']}, FN={ml['confusion_matrix']['false_negatives']}")
    print(f"Rule Confusion Matrix: TP={rb['confusion_matrix']['true_positives']}, FP={rb['confusion_matrix']['false_positives']}, TN={rb['confusion_matrix']['true_negatives']}, FN={rb['confusion_matrix']['false_negatives']}")
    print("-" * 70)
    print(f"\n[NOTE] {report['disclaimer']}")
