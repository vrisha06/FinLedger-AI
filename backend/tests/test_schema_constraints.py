"""Tests for Relational Constraints, Check Constraints, and Scoped Idempotency."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import (
    User,
    Customer,
    Account,
    TransferRequest,
    LedgerTransaction,
    LedgerEntry,
    AuditLog,
    FraudPrediction,
    FinancialProduct,
)


def test_customer_account_non_negative_balance_constraint(db_session, sample_customer):
    """Asserts that customer accounts cannot have negative cached balance."""
    account = Account(
        customer_id=sample_customer.id,
        account_number="INR-ACC-NEGATIVE",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("-50.00"),
        status="ACTIVE",
    )
    db_session.add(account)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_accounts_non_negative_balance" in str(exc_info.value)


def test_clearing_account_can_have_signed_balance(db_session):
    """Asserts that internal clearing accounts are exempt from non-negative constraint."""
    account = Account(
        customer_id=None,
        account_number="INR-CLEARING-SIGNED",
        account_type="INTERNAL_CLEARING",
        currency="INR",
        cached_balance=Decimal("-100000.00"),
        status="ACTIVE",
    )
    db_session.add(account)
    db_session.flush()
    assert account.cached_balance == Decimal("-100000.00")


def test_currency_check_constraint(db_session, sample_customer):
    """Asserts that non-INR currency is rejected by check constraint."""
    account = Account(
        customer_id=sample_customer.id,
        account_number="USD-ACC-INVALID",
        account_type="SAVINGS",
        currency="USD",
        cached_balance=Decimal("100.00"),
        status="ACTIVE",
    )
    db_session.add(account)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_accounts_currency_inr" in str(exc_info.value)


def test_user_role_check_constraint(db_session):
    """Asserts that invalid user roles are rejected."""
    user = User(
        username="hacker",
        email="hacker@example.com",
        password_hash="hash",
        role="SUPERUSER",  # Invalid role
    )
    db_session.add(user)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_users_role_valid" in str(exc_info.value)


def test_transfer_positive_amount_check_constraint(db_session, sample_user, sample_account, sample_dest_account):
    """Asserts that transfer requests must have amount > 0.00."""
    transfer = TransferRequest(
        idempotency_key=str(uuid.uuid4()),
        source_user_id=sample_user.id,
        request_hash="dummyhash",
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("0.00"),  # Zero amount prohibited
        currency="INR",
        status="PENDING",
    )
    db_session.add(transfer)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_transfers_amount_positive" in str(exc_info.value)


def test_transfer_distinct_accounts_check_constraint(db_session, sample_user, sample_account):
    """Asserts that transfer requests cannot have identical source and destination accounts."""
    transfer = TransferRequest(
        idempotency_key=str(uuid.uuid4()),
        source_user_id=sample_user.id,
        request_hash="dummyhash",
        source_account_id=sample_account.id,
        destination_account_id=sample_account.id,  # Same account
        amount=Decimal("500.00"),
        currency="INR",
        status="PENDING",
    )
    db_session.add(transfer)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_transfers_distinct_accounts" in str(exc_info.value)


def test_scoped_idempotency_unique_constraint(db_session, sample_user, sample_account, sample_dest_account):
    """Asserts that a user cannot submit duplicate transfer requests with the same idempotency key."""
    shared_key = str(uuid.uuid4())
    t1 = TransferRequest(
        idempotency_key=shared_key,
        source_user_id=sample_user.id,
        request_hash="hash1",
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("100.00"),
        currency="INR",
        status="POSTED",
    )
    db_session.add(t1)
    db_session.flush()

    # Re-insert with same user and same key
    t2 = TransferRequest(
        idempotency_key=shared_key,
        source_user_id=sample_user.id,
        request_hash="hash2",
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("200.00"),
        currency="INR",
        status="PENDING",
    )
    db_session.add(t2)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "uq_transfers_user_idempotency" in str(exc_info.value)


def test_fraud_review_status_canonical_enum_constraint(db_session, sample_user, sample_account, sample_dest_account):
    """Asserts that fraud review_status strictly enforces the canonical enum."""
    transfer = TransferRequest(
        idempotency_key=str(uuid.uuid4()),
        source_user_id=sample_user.id,
        request_hash="hash",
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("100.00"),
        currency="INR",
        status="POSTED",
    )
    db_session.add(transfer)
    db_session.flush()

    fraud = FraudPrediction(
        transfer_request_id=transfer.id,
        model_version="v1.0",
        risk_score=Decimal("0.8500"),
        decision="HIGH_RISK",
        rule_flags=["VELOCITY_SPIKE"],
        feature_snapshot={},
        explanation="High velocity detected",
        review_status="INVALID_STATUS",  # Not in ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED')
    )
    db_session.add(fraud)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()
    assert "chk_fraud_review_status_valid" in str(exc_info.value)
