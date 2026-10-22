"""Tests for Fraud Lab Benchmarking, AI Health Governance, and Forensic Dossier."""

from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.models.fraud import FraudPrediction
from app.services.fraud_lab_service import FraudLabService


def test_fraud_lab_simulation_reproducibility_and_isolation(db_session, test_staff_user):
    """Verify Fraud Lab simulation produces deterministic metrics and strictly preserves ledger isolation."""
    # Count current database accounts and ledger entries before simulation
    accounts_before = db_session.query(Account).count()
    ledger_entries_before = db_session.query(LedgerEntry).count()
    transfers_before = db_session.query(TransferRequest).count()

    # Run 1 with seed 42
    run1 = FraudLabService.run_simulation(
        db=db_session,
        scenario_name="ALL_SCENARIOS_BENCHMARK",
        seed=42,
        sample_size=200,
        user_id=test_staff_user.id,
    )

    # Run 2 with same seed 42
    run2 = FraudLabService.run_simulation(
        db=db_session,
        scenario_name="ALL_SCENARIOS_BENCHMARK",
        seed=42,
        sample_size=200,
        user_id=test_staff_user.id,
    )

    # Assert exact metric reproducibility
    assert run1["sample_size"] == run2["sample_size"]
    assert run1["fraud_count"] == run2["fraud_count"]
    assert run1["detectors"]["rule_baseline"]["f1_score"] == run2["detectors"]["rule_baseline"]["f1_score"]
    assert run1["detectors"]["hybrid_ensemble"]["f1_score"] == run2["detectors"]["hybrid_ensemble"]["f1_score"]

    # Verify all four detectors were evaluated
    for det in ("rule_baseline", "random_forest", "ledger_graph", "hybrid_ensemble"):
        assert det in run1["detectors"]
        assert "confusion_matrix" in run1["detectors"][det]
        assert "precision" in run1["detectors"][det]
        assert "recall" in run1["detectors"][det]

    # STRICT INVARIANT: Verify ZERO authoritative financial records were created
    accounts_after = db_session.query(Account).count()
    ledger_entries_after = db_session.query(LedgerEntry).count()
    transfers_after = db_session.query(TransferRequest).count()

    assert accounts_after == accounts_before
    assert ledger_entries_after == ledger_entries_before
    assert transfers_after == transfers_before


def test_ai_health_governance_endpoint(client, db_session, test_staff_user, auth_headers_factory):
    """Test AI model health workspace reporting artifact readiness, fallback disclosure, and queue metrics."""
    headers = auth_headers_factory(test_staff_user)

    resp = client.get("/api/v1/fraud/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "active_model_version" in data
    assert "artifact_fingerprint" in data
    assert "triage_metrics" in data
    assert "feature_drift_indicators" in data
    assert len(data["known_limitations"]) >= 3
    assert data["triage_metrics"]["pending_review"] >= 0


def test_forensic_dossier_endpoint(client, db_session, test_staff_user, auth_headers_factory):
    """Test unified forensic investigation dossier connecting transfer, ledger entries, and timeline."""
    headers = auth_headers_factory(test_staff_user)

    # Seed an account pair and transfer
    src = Account(account_number="ACC-DOS-SRC", account_type="SAVINGS", currency="INR", cached_balance=Decimal("100000.00"), status="ACTIVE")
    dst = Account(account_number="ACC-DOS-DST", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add_all([src, dst])
    db_session.commit()

    tx = TransferRequest(
        idempotency_key=f"idemp-dos-{uuid.uuid4()}",
        source_user_id=test_staff_user.id,
        request_hash="hash-dos",
        source_account_id=src.id,
        destination_account_id=dst.id,
        amount=Decimal("35000.00"),
        currency="INR",
        status="POSTED",
    )
    db_session.add(tx)
    db_session.flush()

    lt = LedgerTransaction(
        transfer_request_id=tx.id,
        transaction_type="CUSTOMER_TRANSFER",
        description="Dossier Test Transfer",
    )
    db_session.add(lt)
    db_session.flush()

    entry_deb = LedgerEntry(transaction_id=lt.id, account_id=src.id, entry_type="DEBIT", amount=Decimal("35000.00"), sequence_num=1)
    entry_cred = LedgerEntry(transaction_id=lt.id, account_id=dst.id, entry_type="CREDIT", amount=Decimal("35000.00"), sequence_num=2)
    db_session.add_all([entry_deb, entry_cred])

    pred = FraudPrediction(
        transfer_request_id=tx.id,
        model_version="rf-v1.0.0",
        risk_score=Decimal("0.8500"),
        decision="HIGH_RISK",
        rule_flags=["RULE_ZSCORE_OUTLIER"],
        explanation="Transfer exceeds 5x customer typical baseline.",
        review_status="PENDING",
    )
    db_session.add(pred)
    db_session.commit()

    # Request Forensic Dossier
    resp = client.get(f"/api/v1/fraud/alerts/{pred.id}/dossier", headers=headers)
    assert resp.status_code == 200
    dossier = resp.json()

    assert dossier["alert"]["id"] == str(pred.id)
    assert dossier["transfer"]["id"] == str(tx.id)
    assert len(dossier["ledger_entries"]) == 2
    assert len(dossier["timeline"]) >= 3
    categories = [item["category"] for item in dossier["timeline"]]
    assert "FACT" in categories
    assert "STATISTICAL_MODEL" in categories
    assert "HEURISTIC_RULE" in categories

    # Add staff investigation note
    note_payload = {
        "note_type": "OBSERVATION",
        "content": "Transaction occurred outside customary business hours for this merchant account.",
    }
    note_resp = client.post(f"/api/v1/fraud/alerts/{pred.id}/notes", json=note_payload, headers=headers)
    assert note_resp.status_code == 201
    note_data = note_resp.json()
    assert note_data["note_type"] == "OBSERVATION"
    assert "outside customary" in note_data["content"]
