"""Fraud Detection, Alert Triage, Forensic Dossier & AI Health API Endpoints for FinLedger-AI."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.models.fraud import FraudPrediction
from app.models.graph import GraphFinding
from app.models.notes import InvestigationNote
from app.models.dispute import Dispute
from app.models.audit import AuditLog
from app.schemas.fraud import (
    FraudPredictionResponse,
    FraudAlertReviewRequest,
    InvestigationNoteCreateRequest,
    InvestigationNoteResponse,
    TimelineItem,
    ForensicDossierResponse,
    ModelHealthResponse,
)
from app.services.audit_service import AuditService
from ml.predict import fraud_detector

router = APIRouter(prefix="/fraud", tags=["Fraud Detection & Investigation"])


@router.get(
    "/health",
    response_model=ModelHealthResponse,
    summary="Get AI model runtime readiness, governance fingerprint, and queue health",
)
def get_model_health(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff inspection of active ML model artifact fingerprint, readiness, and monitoring indicators."""
    # backend/app/api/v1/fraud.py -> parents[3] is backend/
    artifacts_dir = Path(__file__).resolve().parents[3] / "ml" / "artifacts"
    model_path = artifacts_dir / "model.joblib"
    metadata_path = artifacts_dir / "metadata.json"
    eval_path = artifacts_dir / "evaluation_report.json"

    # Compute artifact fingerprint
    fingerprint = "NONE_FALLBACK"
    if model_path.exists():
        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        fingerprint = hasher.hexdigest()

    metadata: Dict[str, Any] = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    eval_data: Dict[str, Any] = {}
    if eval_path.exists():
        try:
            with open(eval_path, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
        except Exception:
            pass

    # Query alert queue metrics
    total_preds = db.scalar(select(func.count(FraudPrediction.id))) or 0
    pending_count = db.scalar(select(func.count(FraudPrediction.id)).where(FraudPrediction.review_status == "PENDING")) or 0
    cleared_count = db.scalar(select(func.count(FraudPrediction.id)).where(FraudPrediction.review_status == "CLEARED")) or 0
    confirmed_count = db.scalar(select(func.count(FraudPrediction.id)).where(FraudPrediction.review_status == "CONFIRMED_FRAUD")) or 0
    escalated_count = db.scalar(select(func.count(FraudPrediction.id)).where(FraudPrediction.review_status == "ESCALATED")) or 0

    pending_pct = round((pending_count / total_preds * 100), 2) if total_preds > 0 else 0.0

    # Calculate real feature distribution drift indicator (PSI / summary on recent amounts)
    recent_amts_stmt = select(FraudPrediction.feature_snapshot).order_by(FraudPrediction.created_at.desc()).limit(100)
    recent_snapshots = list(db.scalars(recent_amts_stmt).all())
    
    drift_status = "STABLE"
    recent_mean_amt = None
    if recent_snapshots:
        amounts = [float(s.get("amount", 0)) for s in recent_snapshots if isinstance(s, dict) and "amount" in s]
        if amounts:
            recent_mean_amt = round(sum(amounts) / len(amounts), 2)
            baseline_mean = metadata.get("customer_avg_amount", 5000.0)
            if recent_mean_amt > baseline_mean * 2.5:
                drift_status = "ELEVATED_INFLOW_DRIFT"

    return ModelHealthResponse(
        active_model_version=fraud_detector.model_version,
        algorithm=metadata.get("algorithm", "RandomForestClassifier (or Fallback Baseline)"),
        is_fallback=fraud_detector.is_fallback,
        model_loaded=fraud_detector.pipeline is not None and not fraud_detector.is_fallback,
        decision_threshold=fraud_detector.decision_threshold,
        artifact_fingerprint=fingerprint,
        feature_schema=metadata.get("feature_names", []),
        created_at=metadata.get("created_at"),
        train_samples=metadata.get("train_samples"),
        test_samples=metadata.get("test_samples"),
        evaluation_summary=eval_data.get("machine_learning_model"),
        triage_metrics={
            "total_predictions": total_preds,
            "pending_review": pending_count,
            "cleared": cleared_count,
            "confirmed_fraud": confirmed_count,
            "escalated": escalated_count,
            "pending_percentage": pending_pct,
        },
        feature_drift_indicators={
            "distribution_status": drift_status,
            "recent_sample_size": len(recent_snapshots),
            "recent_mean_amount_inr": recent_mean_amt,
            "reference_window": "Synthetic Baseline Calibration (7,000 samples)",
            "interpretation": "Monitors feature distribution stability against reference training population.",
        },
        known_limitations=[
            "Advisory classification only; model does not autonomously hold balances or freeze customer accounts.",
            "Offline trained on synthetic transaction distribution; uncalibrated for macroeconomic shock shifts.",
            "Single-transaction feature inputs miss multi-account layering without supplementary LedgerGraph analysis.",
            "Triage review decisions represent internal determinations, not legally verified fraud convictions.",
        ],
    )


@router.get(
    "/alerts",
    response_model=List[FraudPredictionResponse],
    summary="List advisory fraud alerts for staff investigation",
)
def list_fraud_alerts(
    review_status: Optional[str] = Query(default=None, description="Filter by status (PENDING, CLEARED, CONFIRMED_FRAUD, ESCALATED)"),
    decision: Optional[str] = Query(default=None, description="Filter by risk decision (LOW_RISK, MEDIUM_RISK, HIGH_RISK)"),
    min_risk_score: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum risk score threshold"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Retrieve advisory fraud predictions for staff triage and forensic investigation."""
    stmt = select(FraudPrediction).order_by(FraudPrediction.risk_score.desc(), FraudPrediction.created_at.desc())

    if review_status:
        stmt = stmt.where(FraudPrediction.review_status == review_status)
    if decision:
        stmt = stmt.where(FraudPrediction.decision == decision)
    if min_risk_score is not None:
        stmt = stmt.where(FraudPrediction.risk_score >= Decimal(f"{min_risk_score:.4f}"))

    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.get(
    "/alerts/{alert_id}",
    response_model=FraudPredictionResponse,
    summary="Get fraud alert details, explainability snapshot, and rule flags",
)
def get_fraud_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Retrieve full forensic snapshot for a specific fraud prediction record."""
    alert = db.get(FraudPrediction, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert record not found")
    return alert


@router.get(
    "/alerts/{alert_id}/dossier",
    response_model=ForensicDossierResponse,
    summary="Get unified forensic investigation dossier connecting all evidentiary layers",
)
def get_forensic_dossier(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Unified forensic dossier connecting transfer request, double-entry ledger legs,
    rule flags, ML predictions, LedgerGraph findings, staff notes, and audit events."""
    alert = db.get(FraudPrediction, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert not found")

    transfer = alert.transfer_request
    source_acc = transfer.source_account
    dest_acc = transfer.destination_account

    src_name = source_acc.customer.full_name if source_acc.customer else "Internal Clearing"
    dst_name = dest_acc.customer.full_name if dest_acc.customer else "Internal Clearing"

    # Fetch ledger transaction and legs
    ledger_tx = transfer.ledger_transaction
    ledger_entries = []
    if ledger_tx:
        ledger_entries = [
            {
                "id": str(e.id),
                "account_id": str(e.account_id),
                "account_number": e.account.account_number,
                "entry_type": e.entry_type,
                "amount": str(e.amount),
                "sequence_num": e.sequence_num,
                "created_at": e.created_at.isoformat(),
            }
            for e in ledger_tx.entries
        ]

    # Fetch graph findings involving source or destination account
    graph_stmt = (
        select(GraphFinding)
        .where(
            or_(
                GraphFinding.primary_account_id == transfer.source_account_id,
                GraphFinding.primary_account_id == transfer.destination_account_id,
            )
        )
        .order_by(GraphFinding.created_at.desc())
        .limit(10)
    )
    graph_findings = [
        {
            "id": str(gf.id),
            "pattern_type": gf.pattern_type,
            "severity": gf.severity,
            "heuristic_score": str(gf.heuristic_score),
            "primary_account_id": str(gf.primary_account_id),
            "explanation": gf.explanation,
            "evidence": gf.evidence,
            "created_at": gf.created_at.isoformat(),
            "review_status": gf.review_status,
        }
        for gf in db.scalars(graph_stmt).all()
    ]

    # Fetch investigation notes
    notes_stmt = select(InvestigationNote).where(InvestigationNote.fraud_prediction_id == alert.id).order_by(InvestigationNote.created_at.asc())
    investigation_notes = list(db.scalars(notes_stmt).all())

    # Fetch audit events
    audit_stmt = (
        select(AuditLog)
        .where(
            or_(
                AuditLog.entity_id == str(transfer.id),
                AuditLog.entity_id == str(alert.id),
            )
        )
        .order_by(AuditLog.created_at.asc())
    )
    audit_events = [
        {
            "id": str(a.id),
            "action": a.action,
            "entity_type": a.entity_type,
            "created_at": a.created_at.isoformat(),
            "metadata": a.metadata_json,
        }
        for a in db.scalars(audit_stmt).all()
    ]

    # Fetch disputes
    dispute_stmt = select(Dispute).where(Dispute.transfer_request_id == transfer.id)
    disputes = [
        {
            "id": str(d.id),
            "status": d.status,
            "category": d.category,
            "description": d.description,
            "created_at": d.created_at.isoformat(),
        }
        for d in db.scalars(dispute_stmt).all()
    ]

    # Build chronological evidentiary timeline
    timeline: List[TimelineItem] = []

    # 1. Transfer submission fact
    timeline.append(
        TimelineItem(
            timestamp=transfer.created_at,
            category="FACT",
            title="Transfer Requested",
            detail=f"Transfer of ₹{transfer.amount:,.2f} submitted from {source_acc.account_number} to {dest_acc.account_number}.",
            evidence_ref=f"transfer_request:{transfer.id}",
        )
    )

    # 2. Double-entry posting fact
    if transfer.posted_at and ledger_tx:
        timeline.append(
            TimelineItem(
                timestamp=transfer.posted_at,
                category="FACT",
                title="PostgreSQL Double-Entry Posting Committed",
                detail=f"Ledger Transaction {ledger_tx.id} committed atomically with balanced debit/credit legs.",
                evidence_ref=f"ledger_transaction:{ledger_tx.id}",
            )
        )

    # 3. Advisory Fraud Model Assessment
    timeline.append(
        TimelineItem(
            timestamp=alert.created_at,
            category="STATISTICAL_MODEL",
            title=f"Advisory Risk Assessment ({alert.decision})",
            detail=f"Scored risk of {float(alert.risk_score)*100:.1f}% using {alert.model_version}. Narrative: {alert.explanation}",
            evidence_ref=f"fraud_prediction:{alert.id}",
        )
    )

    # 4. Heuristic Rule flags
    for flag in alert.rule_flags:
        timeline.append(
            TimelineItem(
                timestamp=alert.created_at,
                category="HEURISTIC_RULE",
                title=f"Rule Flagged: {flag}",
                detail=f"Rule engine threshold matched: {flag}.",
                evidence_ref=f"rule:{flag}",
            )
        )

    # 5. Graph Findings
    for gf in graph_findings:
        timeline.append(
            TimelineItem(
                timestamp=datetime.fromisoformat(gf["created_at"]),
                category="GRAPH_TOPOLOGY",
                title=f"LedgerGraph Finding: {gf['pattern_type']}",
                detail=gf["explanation"],
                evidence_ref=f"graph_finding:{gf['id']}",
            )
        )

    # 6. Staff notes and review actions
    for n in investigation_notes:
        timeline.append(
            TimelineItem(
                timestamp=n.created_at,
                category="INVESTIGATOR_ACTION",
                title=f"Investigator Note ({n.note_type})",
                detail=n.content,
                evidence_ref=f"note:{n.id}",
            )
        )

    if alert.reviewed_at and alert.review_notes:
        timeline.append(
            TimelineItem(
                timestamp=alert.reviewed_at,
                category="INVESTIGATOR_ACTION",
                title=f"Triage Decision: {alert.review_status}",
                detail=f"Review notes: {alert.review_notes}",
                evidence_ref=f"review:{alert.id}",
            )
        )

    timeline.sort(key=lambda item: item.timestamp)

    return ForensicDossierResponse(
        alert=alert,
        transfer={
            "id": str(transfer.id),
            "idempotency_key": transfer.idempotency_key,
            "amount": str(transfer.amount),
            "currency": transfer.currency,
            "status": transfer.status,
            "created_at": transfer.created_at.isoformat(),
            "posted_at": transfer.posted_at.isoformat() if transfer.posted_at else None,
            "source_account_id": str(source_acc.id),
            "destination_account_id": str(dest_acc.id),
        },
        source_account={
            "id": str(source_acc.id),
            "account_number": source_acc.account_number,
            "account_type": source_acc.account_type,
            "cached_balance": str(source_acc.cached_balance),
            "customer_legal_name": src_name,
            "status": source_acc.status,
        },
        destination_account={
            "id": str(dest_acc.id),
            "account_number": dest_acc.account_number,
            "account_type": dest_acc.account_type,
            "cached_balance": str(dest_acc.cached_balance),
            "customer_legal_name": dst_name,
            "status": dest_acc.status,
        },
        ledger_transaction={
            "id": str(ledger_tx.id),
            "transaction_type": ledger_tx.transaction_type,
            "description": ledger_tx.description,
            "created_at": ledger_tx.created_at.isoformat(),
        } if ledger_tx else None,
        ledger_entries=ledger_entries,
        graph_findings=graph_findings,
        investigation_notes=investigation_notes,
        audit_events=audit_events,
        disputes=disputes,
        timeline=timeline,
    )


@router.post(
    "/alerts/{alert_id}/notes",
    response_model=InvestigationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an investigator note to the forensic dossier",
)
def add_investigation_note(
    alert_id: uuid.UUID,
    data: InvestigationNoteCreateRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff attaches an evidentiary note or conclusion to the forensic fraud dossier."""
    alert = db.get(FraudPrediction, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert not found")

    note = InvestigationNote(
        fraud_prediction_id=alert.id,
        author_user_id=current_user.id,
        note_type=data.note_type,
        content=data.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Record audit log
    AuditService.log_event(
        action="INVESTIGATION_NOTE_ADDED",
        entity_type="FRAUD_PREDICTION",
        entity_id=str(alert.id),
        actor_user_id=current_user.id,
        metadata={
            "note_id": str(note.id),
            "note_type": note.note_type,
            "content": note.content,
        },
        db=db,
        independent_txn=True,
    )

    return note


@router.patch(
    "/alerts/{alert_id}/review",
    response_model=FraudPredictionResponse,
    summary="Update fraud alert review status (triage action)",
)
def review_fraud_alert(
    alert_id: uuid.UUID,
    payload: FraudAlertReviewRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Update review status of an advisory fraud alert."""
    alert = db.get(FraudPrediction, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert record not found")

    previous_status = alert.review_status
    alert.review_status = payload.review_status
    alert.review_notes = payload.review_notes
    alert.reviewed_by_user_id = current_user.id
    alert.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)

    # Append audit trail for staff triage action
    AuditService.log_event(
        action="FRAUD_ALERT_REVIEW",
        entity_type="FRAUD_PREDICTION",
        entity_id=str(alert.id),
        actor_user_id=current_user.id,
        metadata={
            "previous_status": previous_status,
            "new_status": alert.review_status,
            "transfer_request_id": str(alert.transfer_request_id),
            "review_notes": alert.review_notes,
        },
        db=db,
        independent_txn=True,
    )

    return alert
