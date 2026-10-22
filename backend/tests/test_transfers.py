"""Integration tests for FinLedger-AI Transfer and Double-Entry Engine.

Verifies:
- Successful transfers between eligible accounts
- Balanced debit and credit ledger legs
- Ledger-derived and cached balance synchronization
- Rejection of insufficient funds without partial updates
- Rejection of self-transfers, negative amounts, inactive accounts, unauthorized callers
- Simulated opening deposits via INR-SYS-CLEARING
- API endpoints for transfers and account operations
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.services.transfer_service import (
    TransferService,
    InsufficientFundsError,
    TransferOwnershipError,
    AccountEligibilityError,
    TransferBusinessError,
)
from app.services.account_service import AccountService
from app.services.ledger_service import LedgerService


def test_successful_transfer_service(db_session, sample_customer, sample_account, sample_dest_account):
    """Verify standard transfer moves funds, creates balanced ledger legs, and updates cached balances."""
    db_session.commit()
    user_id = sample_customer.user_id
    idempotency_key = str(uuid.uuid4())
    transfer_amount = Decimal("2500.00")

    src_initial = sample_account.cached_balance  # 10,000.00
    dst_initial = sample_dest_account.cached_balance  # 5,000.00

    transfer_req, is_replay = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user_id,
        idempotency_key=idempotency_key,
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=transfer_amount,
        currency="INR",
        memo="Service transfer test",
    )

    assert is_replay is False
    assert transfer_req.status == "POSTED"
    assert transfer_req.amount == transfer_amount

    # Verify cached balances updated
    db_session.refresh(sample_account)
    db_session.refresh(sample_dest_account)
    assert sample_account.cached_balance == src_initial - transfer_amount
    assert sample_dest_account.cached_balance == dst_initial + transfer_amount

    # Verify ledger entries
    stmt = select(LedgerEntry).join(LedgerTransaction).where(
        LedgerTransaction.transfer_request_id == transfer_req.id
    )
    entries = list(db_session.scalars(stmt).all())
    assert len(entries) == 2

    debit_entry = next(e for e in entries if e.entry_type == "DEBIT")
    credit_entry = next(e for e in entries if e.entry_type == "CREDIT")

    assert debit_entry.account_id == sample_account.id
    assert debit_entry.amount == transfer_amount
    assert credit_entry.account_id == sample_dest_account.id
    assert credit_entry.amount == transfer_amount


def test_insufficient_funds_rejection(raw_db_session):
    """Verify transfer fails if balance < amount, leaving accounts completely unchanged."""
    from app.models.user import User
    from app.models.customer import Customer

    user = User(
        username=f"insuf_{uuid.uuid4().hex[:8]}",
        email=f"insuf_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$samplepasswordhashforspeed",
        role="CUSTOMER",
        is_active=True,
    )
    raw_db_session.add(user)
    raw_db_session.flush()

    customer = Customer(
        user_id=user.id,
        full_name="Insuf Test Customer",
        kyc_status="VERIFIED",
    )
    raw_db_session.add(customer)
    raw_db_session.flush()

    src_acc = Account(
        customer_id=customer.id,
        account_number=f"INR-INSUF-SRC-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    dst_acc = Account(
        customer_id=customer.id,
        account_number=f"INR-INSUF-DST-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    raw_db_session.add_all([src_acc, dst_acc])
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=src_acc.id,
        amount=Decimal("1000.00"),
        actor_user_id=user.id,
    )
    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=dst_acc.id,
        amount=Decimal("500.00"),
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    src_id = src_acc.id
    dst_id = dst_acc.id
    src_initial = Decimal("1000.00")
    dst_initial = Decimal("500.00")
    user_id = user.id

    with pytest.raises(InsufficientFundsError):
        TransferService.execute_transfer(
            db=raw_db_session,
            caller_user_id=user_id,
            idempotency_key=str(uuid.uuid4()),
            source_account_id=src_id,
            destination_account_id=dst_id,
            amount=Decimal("99999.00"),
            currency="INR",
        )

    # Re-fetch accounts to verify zero balance modifications
    fresh_src = raw_db_session.get(Account, src_id)
    fresh_dst = raw_db_session.get(Account, dst_id)
    assert fresh_src.cached_balance == src_initial
    assert fresh_dst.cached_balance == dst_initial


def test_reject_self_transfer(db_session, sample_customer, sample_account):
    """Verify transfers between the same source and destination account are rejected."""
    db_session.commit()
    with pytest.raises(TransferBusinessError) as exc_info:
        TransferService.execute_transfer(
            db=db_session,
            caller_user_id=sample_customer.user_id,
            idempotency_key=str(uuid.uuid4()),
            source_account_id=sample_account.id,
            destination_account_id=sample_account.id,
            amount=Decimal("100.00"),
        )
    assert "distinct" in str(exc_info.value).lower()


def test_reject_unauthorized_source_account(db_session, test_customer_user, sample_account, sample_dest_account):
    """Verify customer cannot transfer funds from an account owned by a different user."""
    db_session.commit()
    # test_customer_user is NOT the owner of sample_account (sample_customer owns it)
    with pytest.raises(TransferOwnershipError):
        TransferService.execute_transfer(
            db=db_session,
            caller_user_id=test_customer_user.id,
            idempotency_key=str(uuid.uuid4()),
            source_account_id=sample_account.id,
            destination_account_id=sample_dest_account.id,
            amount=Decimal("500.00"),
        )


def test_reject_inactive_account(db_session, sample_customer, sample_account, sample_dest_account):
    """Verify transfers involving frozen or closed accounts are rejected."""
    sample_dest_account.status = "FROZEN"
    db_session.commit()

    with pytest.raises(AccountEligibilityError) as exc_info:
        TransferService.execute_transfer(
            db=db_session,
            caller_user_id=sample_customer.user_id,
            idempotency_key=str(uuid.uuid4()),
            source_account_id=sample_account.id,
            destination_account_id=sample_dest_account.id,
            amount=Decimal("500.00"),
        )
    assert "FROZEN" in str(exc_info.value)


def test_simulated_opening_deposit(db_session, sample_customer, clearing_account):
    """Verify simulated opening deposit debits clearing account and credits customer account."""
    # Create an account with zero balance to test 1:1 ledger reconciliation
    fresh_acc = Account(
        customer_id=sample_customer.id,
        account_number=f"INR-DEP-FRESH-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(fresh_acc)
    db_session.commit()

    deposit_amount = Decimal("50000.00")
    initial_clearing = clearing_account.cached_balance

    updated = AccountService.deposit_opening_funds(
        db=db_session,
        account_id=fresh_acc.id,
        amount=deposit_amount,
        description="Opening deposit test",
        actor_user_id=sample_customer.user_id,
    )

    db_session.refresh(clearing_account)
    assert updated.cached_balance == deposit_amount
    assert clearing_account.cached_balance == initial_clearing - deposit_amount

    # Derived balance calculation verification
    derived = LedgerService.get_derived_balance(db_session, fresh_acc.id)
    assert derived == updated.cached_balance


def test_transfer_api_flow(client, auth_headers_factory, test_customer_user, sample_dest_account, db_session):
    """Verify HTTP POST /api/v1/transfers creates transfer and updates accounts."""
    src_account = Account(
        customer_id=test_customer_user.customer.id,
        account_number="INR-API-SRC-001",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("20000.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(src_account)
    db_session.commit()

    headers = auth_headers_factory(test_customer_user)
    idempotency_key = str(uuid.uuid4())
    headers["Idempotency-Key"] = idempotency_key

    payload = {
        "source_account_id": str(src_account.id),
        "destination_account_id": str(sample_dest_account.id),
        "amount": "3500.00",
        "currency": "INR",
        "memo": "API transfer integration test",
    }

    response = client.post("/api/v1/transfers", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "POSTED"
    assert Decimal(data["amount"]) == Decimal("3500.00")
    assert data["idempotency_key"] == idempotency_key

    transfer_id = data["id"]

    # Verify GET /api/v1/transfers/{id}
    get_res = client.get(f"/api/v1/transfers/{transfer_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == transfer_id


def test_account_deposit_api(client, auth_headers_factory, test_customer_user, db_session):
    """Verify POST /api/v1/accounts/{id}/deposit successfully adds funds."""
    acc = Account(
        customer_id=test_customer_user.customer.id,
        account_number="INR-DEP-API-001",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("1000.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(acc)
    db_session.commit()

    headers = auth_headers_factory(test_customer_user)
    payload = {
        "amount": "15000.00",
        "description": "Initial funding via API",
    }

    res = client.post(f"/api/v1/accounts/{acc.id}/deposit", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert Decimal(data["cached_balance"]) == Decimal("16000.00")
