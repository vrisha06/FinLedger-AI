"""Fraud Prediction Pydantic v2 schemas for FinLedger-AI."""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, Dict
import uuid
from pydantic import BaseModel, ConfigDict, Field


class FraudPredictionResponse(BaseModel):
    """Advisory fraud prediction score and staff review details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transfer_request_id: uuid.UUID
    model_version: str
    risk_score: Decimal
    decision: str
    rule_flags: list[str]
    feature_snapshot: dict[str, Any]
    explanation: str
    review_status: str
    reviewed_by_user_id: uuid.UUID | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class FraudAlertReviewRequest(BaseModel):
    """Staff triage review payload for an advisory fraud alert."""

    review_status: str = Field(
        ...,
        pattern=r"^(CLEARED|CONFIRMED_FRAUD|ESCALATED)$",
        description="Updated review status (canonical enum: CLEARED, CONFIRMED_FRAUD, ESCALATED)",
    )
    review_notes: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Mandatory forensic investigation notes from staff member",
    )


class InvestigationNoteCreateRequest(BaseModel):
    """Staff note added to a forensic fraud dossier."""

    note_type: str = Field(
        ...,
        pattern=r"^(OBSERVATION|EVIDENCE|CONCLUSION|ESCALATION)$",
        description="Type of forensic note",
    )
    content: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Forensic observation or evidence finding",
    )


class InvestigationNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fraud_prediction_id: uuid.UUID
    author_user_id: uuid.UUID
    note_type: str
    content: str
    created_at: datetime


class TimelineItem(BaseModel):
    timestamp: datetime
    category: str = Field(
        ...,
        pattern=r"^(FACT|HEURISTIC_RULE|STATISTICAL_MODEL|GRAPH_TOPOLOGY|INVESTIGATOR_ACTION)$",
    )
    title: str
    detail: str
    evidence_ref: Optional[str] = None


class ForensicDossierResponse(BaseModel):
    """Unified forensic dossier connecting transfers, ledger entries, ML predictions, graph findings, and audit trails."""

    alert: FraudPredictionResponse
    transfer: Dict[str, Any]
    source_account: Dict[str, Any]
    destination_account: Dict[str, Any]
    ledger_transaction: Optional[Dict[str, Any]] = None
    ledger_entries: List[Dict[str, Any]] = []
    graph_findings: List[Dict[str, Any]] = []
    investigation_notes: List[InvestigationNoteResponse] = []
    audit_events: List[Dict[str, Any]] = []
    disputes: List[Dict[str, Any]] = []
    timeline: List[TimelineItem] = []


class ModelHealthResponse(BaseModel):
    """AI health, governance, runtime readiness, and drift monitoring response."""

    active_model_version: str
    algorithm: str
    is_fallback: bool
    model_loaded: bool
    decision_threshold: float
    artifact_fingerprint: str
    feature_schema: List[str]
    created_at: Optional[str] = None
    train_samples: Optional[int] = None
    test_samples: Optional[int] = None
    evaluation_summary: Optional[Dict[str, Any]] = None
    triage_metrics: Dict[str, Any]
    feature_drift_indicators: Dict[str, Any]
    known_limitations: List[str]
