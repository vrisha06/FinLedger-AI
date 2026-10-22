"""Tests for the PostgreSQL Deferrable Constraint Trigger validating double-entry balance."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy.exc import DBAPIError
from app.models import (
    User,
    Customer,
    Account,
    TransferRequest,
    LedgerTransaction,
    LedgerEntry,
)
from app.services.account_service import AccountService


def test_balanced_ledger_transaction_commits_cleanly(raw_db_session):
    """Asserts that a balanced 2-leg transfer (SUM(Debits) == SUM(Credits)) commits successfully."""
    # Setup test entities
    user = User(
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        role="CUSTOMER",
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(user_id=user.id, full_name="Customer")
    raw_db_session.add(customer)
    raw_db_session.flush()

    acc1 = Account(
        customer_id=customer.id,
        account_number=f"ACC_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("0.00"),
    )
    acc2 = Account(
        customer_id=customer.id,
        account_number=f"ACC_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("0.00"),
    )
    raw_db_session.add_all([acc1, acc2])
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc1.id,
        amount=Decimal("1000.00"),
        actor_user_id=user.id,
    )
    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc2.id,
        amount=Decimal("500.00"),
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    # Create transaction header
    txn = LedgerTransaction(
        transaction_type="CUSTOMER_TRANSFER",
        description="Transfer of INR 200.00",
    )
    raw_db_session.add(txn)
    raw_db_session.flush()

    # Balanced entries: ₹200 Debit and ₹200 Credit
    entry_debit = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc1.id,
        entry_type="DEBIT",
        amount=Decimal("200.00"),
        sequence_num=1,
    )
    entry_credit = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc2.id,
        entry_type="CREDIT",
        amount=Decimal("200.00"),
        sequence_num=2,
    )
    acc1.cached_balance -= Decimal("200.00")
    acc2.cached_balance += Decimal("200.00")
    raw_db_session.add_all([entry_debit, entry_credit, acc1, acc2])

    # Must commit with zero trigger exceptions
    raw_db_session.commit()
    assert txn.id is not None


def test_unbalanced_ledger_transaction_rejected_at_commit(raw_db_session):
    """Asserts that an unbalanced transaction (SUM(Debits) != SUM(Credits)) is rejected by PostgreSQL trigger."""
    user = User(
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        role="CUSTOMER",
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(user_id=user.id, full_name="Customer")
    raw_db_session.add(customer)
    raw_db_session.flush()

    acc1 = Account(
        customer_id=customer.id,
        account_number=f"ACC_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("1000.00"),
    )
    acc2 = Account(
        customer_id=customer.id,
        account_number=f"ACC_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("500.00"),
    )
    raw_db_session.add_all([acc1, acc2])
    raw_db_session.flush()

    txn = LedgerTransaction(
        transaction_type="CUSTOMER_TRANSFER",
        description="Unbalanced transfer attempt",
    )
    raw_db_session.add(txn)
    raw_db_session.flush()

    # Unbalanced: Debit ₹500.00 but Credit only ₹400.00 (Delta = ₹100.00)
    entry_debit = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc1.id,
        entry_type="DEBIT",
        amount=Decimal("500.00"),
        sequence_num=1,
    )
    entry_credit = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc2.id,
        entry_type="CREDIT",
        amount=Decimal("400.00"),
        sequence_num=2,
    )
    raw_db_session.add_all([entry_debit, entry_credit])

    # Deferrable trigger evaluates at COMMIT time
    with pytest.raises(DBAPIError) as exc_info:
        raw_db_session.commit()

    err_text = str(exc_info.value)
    assert "is unbalanced: debit minus credit delta is" in err_text
    raw_db_session.rollback()


def test_multi_leg_balanced_transaction_commits_cleanly(raw_db_session):
    """Asserts that a 3-leg split transaction (1 debit of ₹1,000, 2 credits of ₹500 each) commits successfully."""
    user = User(
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        role="CUSTOMER",
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(user_id=user.id, full_name="Customer")
    raw_db_session.add(customer)
    raw_db_session.flush()

    acc_src = Account(
        customer_id=customer.id,
        account_number=f"SRC_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("0.00"),
    )
    acc_dst1 = Account(
        customer_id=customer.id,
        account_number=f"DST1_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("0.00"),
    )
    acc_dst2 = Account(
        customer_id=customer.id,
        account_number=f"DST2_{uuid.uuid4().hex[:8]}",
        account_type="SAVINGS",
        cached_balance=Decimal("0.00"),
    )
    raw_db_session.add_all([acc_src, acc_dst1, acc_dst2])
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc_src.id,
        amount=Decimal("2000.00"),
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    txn = LedgerTransaction(
        transaction_type="CUSTOMER_TRANSFER",
        description="Split transfer of ₹1,000",
    )
    raw_db_session.add(txn)
    raw_db_session.flush()

    leg1 = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc_src.id,
        entry_type="DEBIT",
        amount=Decimal("1000.00"),
        sequence_num=1,
    )
    leg2 = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc_dst1.id,
        entry_type="CREDIT",
        amount=Decimal("500.00"),
        sequence_num=2,
    )
    leg3 = LedgerEntry(
        transaction_id=txn.id,
        account_id=acc_dst2.id,
        entry_type="CREDIT",
        amount=Decimal("500.00"),
        sequence_num=3,
    )
    acc_src.cached_balance -= Decimal("1000.00")
    acc_dst1.cached_balance += Decimal("500.00")
    acc_dst2.cached_balance += Decimal("500.00")
    raw_db_session.add_all([leg1, leg2, leg3, acc_src, acc_dst1, acc_dst2])

    raw_db_session.commit()
    assert txn.id is not None
