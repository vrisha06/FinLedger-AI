"""Integration tests for Advisory Fraud Scoring, Separation Invariants, and Staff Triage API.

Verifies:
- Transfers automatically receive advisory FraudPrediction records in fraud_predictions table
- Fraud scoring NEVER mutates account balances, ledger entries, or transfer status
- Replaying an idempotent request does NOT create duplicate FraudPrediction records
- Staff-only access control on /api/v1/fraud/alerts
- Staff triage review updates review_status and records immutable audit log
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.fraud import FraudPrediction
from app.models.audit import AuditLog
from app.services.transfer_service import TransferService
from app.services.ledger_service import LedgerService
from app.services.account_service import AccountService


def test_transfer_creates_advisory_fraud_prediction(db_session, sample_customer, sample_account, sample_dest_account):
    """Verify executing a transfer creates an advisory FraudPrediction record."""
    db_session.commit()
    user_id = sample_customer.user_id
    idempotency_key = str(uuid.uuid4())
    transfer_amount = Decimal("3000.00")

    transfer_req, is_replay = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user_id,
        idempotency_key=idempotency_key,
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=transfer_amount,
        currency="INR",
        memo="Integration test transfer for fraud scoring",
    )

    assert is_replay is False
    assert transfer_req.status == "POSTED"

    # Query fraud prediction
    stmt = select(FraudPrediction).where(FraudPrediction.transfer_request_id == transfer_req.id)
    pred = db_session.scalars(stmt).first()

    assert pred is not None
    assert pred.review_status == "PENDING"
    assert Decimal("0.0000") <= pred.risk_score <= Decimal("1.0000")
    assert pred.decision in ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK")
    assert isinstance(pred.rule_flags, list)
    assert isinstance(pred.explanation, str)


def test_fraud_scoring_does_not_mutate_balances(db_session, sample_customer):
    """Verify that fraud scoring strictly preserves financial balances and ledger entries."""
    user_id = sample_customer.user_id
    src_account = Account(
        customer_id=sample_customer.id,
        account_number=f"INR-TEST-FRD-SRC-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    dst_account = Account(
        customer_id=sample_customer.id,
        account_number=f"INR-TEST-FRD-DST-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add_all([src_account, dst_account])
    db_session.commit()

    # Deposit opening funds via double-entry clearing leg
    AccountService.deposit_opening_funds(
        db=db_session,
        account_id=src_account.id,
        amount=Decimal("10000.00"),
        actor_user_id=user_id,
    )
    db_session.commit()

    transfer_amount = Decimal("1500.00")
    src_initial = src_account.cached_balance
    dst_initial = dst_account.cached_balance

    transfer_req, _ = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user_id,
        idempotency_key=str(uuid.uuid4()),
        source_account_id=src_account.id,
        destination_account_id=dst_account.id,
        amount=transfer_amount,
        currency="INR",
    )

    db_session.refresh(src_account)
    db_session.refresh(dst_account)

    # Balances must reflect ONLY the ₹1500 transfer, zero modifications from AI
    assert src_account.cached_balance == src_initial - transfer_amount
    assert dst_account.cached_balance == dst_initial + transfer_amount

    # Derived balances match cached balances exactly
    src_derived = LedgerService.get_derived_balance(db_session, src_account.id)
    dst_derived = LedgerService.get_derived_balance(db_session, dst_account.id)
    assert src_derived == src_account.cached_balance
    assert dst_derived == dst_account.cached_balance


def test_idempotent_replay_does_not_duplicate_prediction(db_session, sample_customer, sample_account, sample_dest_account):
    """Verify replaying an identical transfer does not create duplicate fraud predictions."""
    db_session.commit()
    user_id = sample_customer.user_id
    idempotency_key = str(uuid.uuid4())
    transfer_amount = Decimal("2000.00")

    # Call 1
    t1, is_replay1 = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user_id,
        idempotency_key=idempotency_key,
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=transfer_amount,
    )
    assert is_replay1 is False

    # Call 2 (identical replay)
    t2, is_replay2 = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user_id,
        idempotency_key=idempotency_key,
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=transfer_amount,
    )
    assert is_replay2 is True
    assert t1.id == t2.id

    # Verify exactly 1 FraudPrediction row exists
    preds = list(
        db_session.scalars(
            select(FraudPrediction).where(FraudPrediction.transfer_request_id == t1.id)
        ).all()
    )
    assert len(preds) == 1


def test_fraud_alert_triage_rbac(client, auth_headers_factory, test_staff_user, test_customer_user):
    """Verify /api/v1/fraud/alerts is accessible to staff but forbidden to customers."""
    staff_headers = auth_headers_factory(test_staff_user)
    cust_headers = auth_headers_factory(test_customer_user)

    # Staff -> 200 OK
    res_staff = client.get("/api/v1/fraud/alerts", headers=staff_headers)
    assert res_staff.status_code == 200
    assert isinstance(res_staff.json(), list)

    # Customer -> 403 Forbidden
    res_cust = client.get("/api/v1/fraud/alerts", headers=cust_headers)
    assert res_cust.status_code == 403

    # Unauthenticated -> 401 Unauthorized
    res_anon = client.get("/api/v1/fraud/alerts")
    assert res_anon.status_code == 401


def test_fraud_alert_review_workflow(client, auth_headers_factory, test_staff_user, db_session, sample_customer, sample_account, sample_dest_account):
    """Verify staff can review an alert, update review_status, and append an audit record."""
    db_session.commit()
    # Deposit opening funds so sample_account has sufficient balance for 49500 transfer
    AccountService.deposit_opening_funds(
        db=db_session,
        account_id=sample_account.id,
        amount=Decimal("50000.00"),
        actor_user_id=sample_customer.user_id,
    )
    db_session.commit()

    # Create transfer and fraud prediction
    transfer_req, _ = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=sample_customer.user_id,
        idempotency_key=str(uuid.uuid4()),
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("49500.00"),  # Structuring amount
    )

    pred = db_session.scalars(
        select(FraudPrediction).where(FraudPrediction.transfer_request_id == transfer_req.id)
    ).first()
    assert pred is not None
    assert pred.review_status == "PENDING"

    staff_headers = auth_headers_factory(test_staff_user)
    patch_payload = {
        "review_status": "CONFIRMED_FRAUD",
        "review_notes": "Pattern matches structuring just below 50k reporting limit",
    }

    res = client.patch(f"/api/v1/fraud/alerts/{pred.id}/review", json=patch_payload, headers=staff_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["review_status"] == "CONFIRMED_FRAUD"
    assert data["review_notes"] == patch_payload["review_notes"]
    assert data["reviewed_by_user_id"] == str(test_staff_user.id)

    # Verify audit log was recorded
    audit_entry = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "FRAUD_ALERT_REVIEW",
            AuditLog.entity_id == str(pred.id),
        )
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor_user_id == test_staff_user.id


def test_fraud_alert_review_validation(client, auth_headers_factory, test_staff_user, db_session, sample_customer, sample_account, sample_dest_account):
    """Verify validation enforcement: mandatory review notes and canonical enum review status."""
    db_session.commit()
    transfer_req, _ = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=sample_customer.user_id,
        idempotency_key=str(uuid.uuid4()),
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("100.00"),
    )
    pred = db_session.scalars(
        select(FraudPrediction).where(FraudPrediction.transfer_request_id == transfer_req.id)
    ).first()
    assert pred is not None

    staff_headers = auth_headers_factory(test_staff_user)

    # 1. Missing review_notes -> 422
    res_missing_notes = client.patch(
        f"/api/v1/fraud/alerts/{pred.id}/review",
        json={"review_status": "CLEARED"},
        headers=staff_headers,
    )
    assert res_missing_notes.status_code == 422

    # 2. Too short review_notes (< 3 chars) -> 422
    res_short_notes = client.patch(
        f"/api/v1/fraud/alerts/{pred.id}/review",
        json={"review_status": "CLEARED", "review_notes": "ok"},
        headers=staff_headers,
    )
    assert res_short_notes.status_code == 422

    # 3. Invalid review_status -> 422
    res_invalid_status = client.patch(
        f"/api/v1/fraud/alerts/{pred.id}/review",
        json={"review_status": "INVALID_STATUS", "review_notes": "Forensic investigation complete"},
        headers=staff_headers,
    )
    assert res_invalid_status.status_code == 422

    # 4. Attempting to set review_status to PENDING -> 422
    res_pending_status = client.patch(
        f"/api/v1/fraud/alerts/{pred.id}/review",
        json={"review_status": "PENDING", "review_notes": "Resetting status"},
        headers=staff_headers,
    )
    assert res_pending_status.status_code == 422


def test_fraud_prediction_privacy_no_sensitive_leaks(db_session, sample_customer, sample_account, sample_dest_account):
    """Verify that persisted FraudPrediction records contain zero credentials, PANs, or tokens."""
    db_session.commit()
    transfer_req, _ = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=sample_customer.user_id,
        idempotency_key=str(uuid.uuid4()),
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("250.00"),
    )

    pred = db_session.scalars(
        select(FraudPrediction).where(FraudPrediction.transfer_request_id == transfer_req.id)
    ).first()
    assert pred is not None

    # Check feature snapshot keys
    snapshot_keys = set(pred.feature_snapshot.keys())
    disallowed_substrings = ["password", "token", "secret", "pan", "ssn", "cvv", "pin", "auth"]
    for key in snapshot_keys:
        for dis in disallowed_substrings:
            assert dis not in key.lower(), f"Sensitive key fragment '{dis}' found in feature snapshot: '{key}'"

    # Explanation text should not contain auth tokens or sensitive patterns
    assert "Bearer" not in pred.explanation
    assert "eyJ" not in pred.explanation

