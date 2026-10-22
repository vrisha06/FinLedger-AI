"""Inference and Advisory Fraud Detection Engine for FinLedger-AI.

Provides:
1. Thread-safe model artifact loading with fail-safe rule baseline fallback.
2. Real-time feature extraction and prediction (risk score in [0.0000, 1.0000]).
3. Explainable narrative generation highlighting triggered rules and behavioral deviations.
4. Post-commit financial transfer scoring persisting into fraud_predictions table.
5. Strict non-negotiable financial isolation: scoring failures never affect committed transfers.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Any
import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.fraud import FraudPrediction
from app.models.transfer import TransferRequest
from app.services.audit_service import AuditService
from ml.features import extract_single_features, FEATURE_COLUMNS
from ml.rules import RuleBaseline

logger = logging.getLogger(__name__)

DECISION_LOW_RISK = "LOW_RISK"
DECISION_MEDIUM_RISK = "MEDIUM_RISK"
DECISION_HIGH_RISK = "HIGH_RISK"


class FraudDetector:
    """Production inference engine with automatic rule baseline fallback."""

    def __init__(self, artifacts_dir: Path | str | None = None):
        if artifacts_dir is None:
            self.artifacts_dir = Path(__file__).resolve().parent / "artifacts"
        else:
            self.artifacts_dir = Path(artifacts_dir)

        self.model_path = self.artifacts_dir / "model.joblib"
        self.metadata_path = self.artifacts_dir / "metadata.json"

        self.pipeline = None
        self.metadata = {}
        self.model_version = "rule-baseline-v1.0.0"
        self.decision_threshold = float(getattr(settings, "FRAUD_RISK_THRESHOLD", 0.70))
        self.is_fallback = False

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Safely load Scikit-Learn pipeline and training metadata."""
        if self.model_path.exists() and self.metadata_path.exists():
            try:
                self.pipeline = joblib.load(self.model_path)
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                self.model_version = self.metadata.get("model_version", "rf-v1.0.0")
                self.decision_threshold = float(self.metadata.get("decision_threshold", 0.70))
                self.is_fallback = False
                logger.info(f"Loaded fraud model version {self.model_version}")
            except Exception as e:
                logger.warning(f"Failed to load model artifact at {self.model_path}: {e}. Falling back to Rule Baseline.")
                self.pipeline = None
                self.is_fallback = True
                self.model_version = "rule-baseline-fallback"
        else:
            logger.info("Model artifact not found. Initialized with Rule Baseline fallback.")
            self.pipeline = None
            self.is_fallback = True
            self.model_version = "rule-baseline-fallback"

    def predict_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """Perform advisory inference on a dictionary of features.

        Returns:
            dict:
                - risk_score: float in [0.0000, 1.0000]
                - decision: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK'
                - rule_flags: list[str]
                - explanation: str
                - model_version: str
        """
        # Always evaluate rule baseline for explainability and flags
        rule_score, rule_flags, rule_explanation = RuleBaseline.evaluate_features(features)

        if self.pipeline is not None and not self.is_fallback:
            try:
                # Ensure input aligns with training schema
                df_input = pd.DataFrame([features])[FEATURE_COLUMNS]
                ml_prob = float(self.pipeline.predict_proba(df_input)[0, 1])
                risk_score = round(ml_prob, 4)
                version = self.model_version
            except Exception as e:
                logger.warning(f"Inference error with ML pipeline: {e}. Using rule baseline.")
                risk_score = round(rule_score, 4)
                version = "rule-baseline-fallback"
        else:
            risk_score = round(rule_score, 4)
            version = "rule-baseline-fallback"

        # Categorize decision
        if risk_score < 0.30:
            decision = DECISION_LOW_RISK
        elif risk_score < self.decision_threshold:
            decision = DECISION_MEDIUM_RISK
        else:
            decision = DECISION_HIGH_RISK

        # Construct explanation
        if rule_flags:
            flags_detail = rule_explanation
        else:
            if decision == DECISION_LOW_RISK:
                flags_detail = "Transaction features conform to standard customer activity and temporal patterns."
            else:
                flags_detail = "Elevated risk driven by statistical multivariate feature anomaly in model inference (heuristic thresholds not breached individually)."

        if decision == DECISION_LOW_RISK:
            explanation = f"Transaction risk score is low ({risk_score:.4f}). {flags_detail}"
        elif decision == DECISION_MEDIUM_RISK:
            explanation = f"Moderate risk (score {risk_score:.4f}). {flags_detail}"
        else:
            explanation = f"HIGH RISK ALERT (score {risk_score:.4f} >= threshold {self.decision_threshold:.2f}). {flags_detail}"

        return {
            "risk_score": risk_score,
            "decision": decision,
            "rule_flags": rule_flags,
            "explanation": explanation,
            "model_version": version,
        }

    def score_transfer(
        self,
        transfer: TransferRequest,
        db: Session | None = None,
    ) -> FraudPrediction | None:
        """Execute post-commit advisory fraud scoring for a financial transfer.

        Strict Separation Invariants:
        1. Executed strictly AFTER core financial transfer commits and row locks are released.
        2. Uses an isolated database session so scoring failures never corrupt financial state.
        3. Prevents duplicate predictions when an idempotent request is replayed.
        4. Never mutates account balances, ledger entries, or transfer status.

        Returns:
            FraudPrediction | None: The persisted advisory record.
        """
        target_engine = db.get_bind() if db is not None else SessionLocal.kw.get("bind")

        try:
            with Session(target_engine) as scoring_db:
                # 1. Idempotency replay check: Return existing prediction if already scored
                stmt = select(FraudPrediction).where(
                    FraudPrediction.transfer_request_id == transfer.id
                )
                existing_pred = scoring_db.scalars(stmt).first()
                if existing_pred:
                    return existing_pred

                # 2. Extract prior customer transaction history for feature engineering
                # Look back up to 50 previous transfers for this customer
                history_stmt = (
                    select(TransferRequest)
                    .where(
                        TransferRequest.source_user_id == transfer.source_user_id,
                        TransferRequest.id != transfer.id,
                        TransferRequest.created_at <= transfer.created_at,
                    )
                    .order_by(TransferRequest.created_at.desc())
                    .limit(50)
                )
                past_transfers = list(scoring_db.scalars(history_stmt).all())

                prior_records = [
                    {
                        "amount": float(p.amount),
                        "timestamp": p.created_at,
                        "destination_account_id": str(p.destination_account_id),
                    }
                    for p in past_transfers
                ]

                # 3. Extract single transaction features
                features = extract_single_features(
                    amount=float(transfer.amount),
                    timestamp=transfer.created_at or datetime.now(timezone.utc),
                    destination_account_id=str(transfer.destination_account_id),
                    prior_transactions=prior_records,
                )

                # 4. Predict score and decision
                pred_result = self.predict_features(features)

                # 5. Persist FraudPrediction record (defaults to PENDING for staff triage)
                prediction_record = FraudPrediction(
                    transfer_request_id=transfer.id,
                    model_version=pred_result["model_version"],
                    risk_score=Decimal(f"{pred_result['risk_score']:.4f}"),
                    decision=pred_result["decision"],
                    rule_flags=pred_result["rule_flags"],
                    feature_snapshot=features,
                    explanation=pred_result["explanation"],
                    review_status="PENDING",
                )
                scoring_db.add(prediction_record)
                scoring_db.commit()
                scoring_db.refresh(prediction_record)

                # 6. Audit log advisory prediction
                AuditService.log_event(
                    action="FRAUD_SCORE_COMPUTED",
                    entity_type="TRANSFER",
                    entity_id=str(transfer.id),
                    actor_user_id=transfer.source_user_id,
                    metadata={
                        "risk_score": str(prediction_record.risk_score),
                        "decision": prediction_record.decision,
                        "model_version": prediction_record.model_version,
                        "rule_flags": prediction_record.rule_flags,
                    },
                    db=scoring_db,
                    independent_txn=False,
                )
                scoring_db.commit()

                return prediction_record

        except Exception as err:
            logger.error(f"Advisory fraud scoring failed for transfer {transfer.id}: {err}", exc_info=True)
            # Log failure to audit trail without rolling back or altering the committed transfer
            try:
                AuditService.log_event(
                    action="FRAUD_SCORING_FAILED",
                    entity_type="TRANSFER",
                    entity_id=str(transfer.id),
                    actor_user_id=transfer.source_user_id,
                    metadata={"error": str(err)},
                    independent_txn=True,
                )
            except Exception:
                logger.exception("Could not audit fraud scoring failure for transfer %s", transfer.id)
            return None


# Global singleton instance for application use
fraud_detector = FraudDetector()
