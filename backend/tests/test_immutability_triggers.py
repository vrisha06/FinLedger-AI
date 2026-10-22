"""Tests for Database Immutability Triggers on ledger_entries and audit_logs."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.models import (
    User,
    Customer,
    Account,
    LedgerTransaction,
    LedgerEntry,
    AuditLog,
)
from app.services.account_service import AccountService


def test_ledger_entries_immutable_against_update(raw_db_session):
    """Asserts that direct SQL UPDATE on ledger_entries is prohibited by PostgreSQL trigger."""
    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(user_id=user.id, full_name="User")
    acc1 = Account(customer_id=customer.id, account_number=f"A1_{uuid.uuid4().hex[:8]}", account_type="SAVINGS", cached_balance=Decimal("0.00"))
    acc2 = Account(customer_id=customer.id, account_number=f"A2_{uuid.uuid4().hex[:8]}", account_type="SAVINGS", cached_balance=Decimal("0.00"))
    raw_db_session.add_all([customer, acc1, acc2])
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc1.id,
        amount=Decimal("100.00"),
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    txn = LedgerTransaction(transaction_type="CUSTOMER_TRANSFER", description="Transfer")
    raw_db_session.add(txn)
    raw_db_session.flush()

    leg1 = LedgerEntry(transaction_id=txn.id, account_id=acc1.id, entry_type="DEBIT", amount=Decimal("100.00"), sequence_num=1)
    leg2 = LedgerEntry(transaction_id=txn.id, account_id=acc2.id, entry_type="CREDIT", amount=Decimal("100.00"), sequence_num=2)
    acc1.cached_balance -= Decimal("100.00")
    acc2.cached_balance += Decimal("100.00")
    raw_db_session.add_all([leg1, leg2, acc1, acc2])
    raw_db_session.commit()

    # Attempt illicit direct UPDATE on committed ledger entry
    with pytest.raises(DBAPIError) as exc_info:
        raw_db_session.execute(
            text("UPDATE ledger_entries SET amount = 999.00 WHERE id = :id"),
            {"id": str(leg1.id)},
        )
        raw_db_session.commit()

    err_text = str(exc_info.value)
    assert "strictly append-only; updates and deletes are prohibited" in err_text
    raw_db_session.rollback()


def test_ledger_entries_immutable_against_delete(raw_db_session):
    """Asserts that direct SQL DELETE on ledger_entries is prohibited by PostgreSQL trigger."""
    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(user_id=user.id, full_name="User")
    acc1 = Account(customer_id=customer.id, account_number=f"A1_{uuid.uuid4().hex[:8]}", account_type="SAVINGS", cached_balance=Decimal("0.00"))
    acc2 = Account(customer_id=customer.id, account_number=f"A2_{uuid.uuid4().hex[:8]}", account_type="SAVINGS", cached_balance=Decimal("0.00"))
    raw_db_session.add_all([customer, acc1, acc2])
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc1.id,
        amount=Decimal("100.00"),
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    txn = LedgerTransaction(transaction_type="CUSTOMER_TRANSFER", description="Transfer")
    raw_db_session.add(txn)
    raw_db_session.flush()

    leg1 = LedgerEntry(transaction_id=txn.id, account_id=acc1.id, entry_type="DEBIT", amount=Decimal("100.00"), sequence_num=1)
    leg2 = LedgerEntry(transaction_id=txn.id, account_id=acc2.id, entry_type="CREDIT", amount=Decimal("100.00"), sequence_num=2)
    acc1.cached_balance -= Decimal("100.00")
    acc2.cached_balance += Decimal("100.00")
    raw_db_session.add_all([leg1, leg2, acc1, acc2])
    raw_db_session.commit()

    # Attempt illicit DELETE on committed ledger entry
    with pytest.raises(DBAPIError) as exc_info:
        raw_db_session.execute(
            text("DELETE FROM ledger_entries WHERE id = :id"),
            {"id": str(leg1.id)},
        )
        raw_db_session.commit()

    err_text = str(exc_info.value)
    assert "strictly append-only; updates and deletes are prohibited" in err_text
    raw_db_session.rollback()


def test_audit_logs_immutable_against_update(raw_db_session):
    """Asserts that direct SQL UPDATE on audit_logs is prohibited by PostgreSQL trigger."""
    audit = AuditLog(
        action="TRANSFER_FAILED",
        entity_type="TRANSFER",
        entity_id=str(uuid.uuid4()),
        metadata_json={"reason": "insufficient_funds"},
    )
    raw_db_session.add(audit)
    raw_db_session.commit()

    with pytest.raises(DBAPIError) as exc_info:
        raw_db_session.execute(
            text("UPDATE audit_logs SET action = 'ALTERED' WHERE id = :id"),
            {"id": audit.id},
        )
        raw_db_session.commit()

    err_text = str(exc_info.value)
    assert "strictly append-only; updates and deletes are prohibited" in err_text
    raw_db_session.rollback()


def test_audit_logs_immutable_against_delete(raw_db_session):
    """Asserts that direct SQL DELETE on audit_logs is prohibited by PostgreSQL trigger."""
    audit = AuditLog(
        action="AUTH_LOGIN",
        entity_type="USER",
        entity_id=str(uuid.uuid4()),
        metadata_json={"ip": "127.0.0.1"},
    )
    raw_db_session.add(audit)
    raw_db_session.commit()

    with pytest.raises(DBAPIError) as exc_info:
        raw_db_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": audit.id},
        )
        raw_db_session.commit()

    err_text = str(exc_info.value)
    assert "strictly append-only; updates and deletes are prohibited" in err_text
    raw_db_session.rollback()
