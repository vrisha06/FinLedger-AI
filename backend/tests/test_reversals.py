"""CORRECTION_REVERSAL: corrections are new balanced postings, never edits (AGENTS.md §3.4).

Verifies:
- Admin reversal restores both balances with a balanced CORRECTION_REVERSAL posting
- The original transfer is marked REVERSED; its ledger legs stay untouched
- Success audit is written atomically with the posting
- A transfer can be reversed at most once, even under concurrency
- Reversal never overdraws: if the recipient spent the money, nothing moves and the failure is audited
- Only ADMIN may reverse; investment purchases and failed transfers cannot be reversed here
"""

from decimal import Decimal
import threading
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models import Account, AuditLog, Customer, FinancialProduct, TransferRequest, User
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService
from app.services.ledger_service import LedgerService
from app.services.reversal_service import ReversalError, ReversalService
from app.services.transfer_service import TransferService


def _user(session: Session, role: str) -> User:
    tag = uuid.uuid4().hex[:8]
    user = User(username=f"rev_{role.lower()}_{tag}", email=f"rev_{tag}@example.com",
                password_hash="$2b$12$samplepasswordhashforspeed", role=role, is_active=True)
    session.add(user)
    session.flush()
    return user


def _funded_pair(session: Session, src_balance: Decimal):
    """Customer A (funded) and customer B, each with a SAVINGS account; returns (userA, accA, accB)."""
    accounts = []
    owner = None
    for i, bal in enumerate((src_balance, Decimal("0.00"))):
        user = _user(session, "CUSTOMER")
        cust = Customer(user_id=user.id, full_name=f"Reversal Party {i}", kyc_status="VERIFIED")
        session.add(cust)
        session.flush()
        acc = Account(customer_id=cust.id, account_number=f"INR-REV-{uuid.uuid4().hex[:8].upper()}",
                      account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE", version=1)
        session.add(acc)
        session.commit()
        if bal > 0:
            AccountService.deposit_opening_funds(db=session, account_id=acc.id, amount=bal, actor_user_id=user.id)
        accounts.append(acc)
        owner = owner or user
    session.commit()
    return owner, accounts[0], accounts[1]


def _transfer(session: Session, user: User, src: Account, dst: Account, amount: Decimal) -> TransferRequest:
    req, _ = TransferService.execute_transfer(db=session, caller_user_id=user.id, idempotency_key=str(uuid.uuid4()),
                                             source_account_id=src.id, destination_account_id=dst.id, amount=amount)
    return req


def test_admin_reversal_restores_balances_with_balanced_correction(raw_db_session):
    admin = _user(raw_db_session, "ADMIN")
    user, a, b = _funded_pair(raw_db_session, Decimal("1000.00"))
    original = _transfer(raw_db_session, user, a, b, Decimal("400.00"))
    original_id, a_id, b_id, admin_id = original.id, a.id, b.id, admin.id
    original_legs = {(e.account_id, e.entry_type, e.amount) for e in raw_db_session.scalars(
        select(LedgerEntry).join(LedgerTransaction).where(LedgerTransaction.transfer_request_id == original_id))}

    reversal = ReversalService.reverse_transfer(raw_db_session, original_id, admin_id, "Customer dispute upheld")

    assert raw_db_session.get(Account, a_id).cached_balance == Decimal("1000.00")
    assert raw_db_session.get(Account, b_id).cached_balance == Decimal("0.00")
    assert LedgerService.get_derived_balance(raw_db_session, a_id) == Decimal("1000.00")
    assert LedgerService.get_derived_balance(raw_db_session, b_id) == Decimal("0.00")
    assert raw_db_session.get(TransferRequest, original_id).status == "REVERSED"

    txn = raw_db_session.scalars(select(LedgerTransaction).where(LedgerTransaction.transfer_request_id == reversal.id)).one()
    assert txn.transaction_type == "CORRECTION_REVERSAL"
    legs = {(e.account_id, e.entry_type, e.amount) for e in txn.entries}
    assert legs == {(b_id, "DEBIT", Decimal("400.00")), (a_id, "CREDIT", Decimal("400.00"))}

    # Original legs are untouched (append-only)
    assert {(e.account_id, e.entry_type, e.amount) for e in raw_db_session.scalars(
        select(LedgerEntry).join(LedgerTransaction).where(LedgerTransaction.transfer_request_id == original_id))} == original_legs

    audit = raw_db_session.scalars(select(AuditLog).where(AuditLog.action == "TRANSFER_REVERSED",
                                                         AuditLog.entity_id == str(original_id))).one()
    assert audit.actor_user_id == admin_id
    assert audit.metadata_json["reason"] == "Customer dispute upheld"
    assert LedgerService.reconcile_all_accounts(raw_db_session).is_balanced is True


def test_transfer_can_only_be_reversed_once(raw_db_session):
    admin = _user(raw_db_session, "ADMIN")
    user, a, b = _funded_pair(raw_db_session, Decimal("1000.00"))
    original = _transfer(raw_db_session, user, a, b, Decimal("400.00"))
    original_id, a_id, admin_id = original.id, a.id, admin.id
    ReversalService.reverse_transfer(raw_db_session, original_id, admin_id, "First correction")

    with pytest.raises(ReversalError) as exc:
        ReversalService.reverse_transfer(raw_db_session, original_id, admin_id, "Second correction attempt")
    assert exc.value.status_code == 409
    assert raw_db_session.get(Account, a_id).cached_balance == Decimal("1000.00")


def test_reversal_never_overdraws_recipient_and_failure_is_audited(raw_db_session):
    admin = _user(raw_db_session, "ADMIN")
    user, a, b = _funded_pair(raw_db_session, Decimal("1000.00"))
    original = _transfer(raw_db_session, user, a, b, Decimal("400.00"))
    original_id, a_id, b_id, admin_id = original.id, a.id, b.id, admin.id
    # Recipient spends most of it before the correction
    recipient_user = raw_db_session.get(Customer, raw_db_session.get(Account, b_id).customer_id).user
    _transfer(raw_db_session, recipient_user, raw_db_session.get(Account, b_id), raw_db_session.get(Account, a_id), Decimal("300.00"))

    with pytest.raises(ReversalError) as exc:
        ReversalService.reverse_transfer(raw_db_session, original_id, admin_id, "Too late to recover")
    assert exc.value.status_code == 400

    assert raw_db_session.get(Account, b_id).cached_balance == Decimal("100.00")
    assert raw_db_session.get(TransferRequest, original_id).status == "POSTED"
    failed = raw_db_session.scalars(select(AuditLog).where(AuditLog.action == "TRANSFER_REVERSAL_FAILED",
                                                          AuditLog.entity_id == str(original_id))).first()
    assert failed is not None


def test_investment_purchase_cannot_be_reversed_as_a_transfer(raw_db_session):
    admin = _user(raw_db_session, "ADMIN")
    user, a, _ = _funded_pair(raw_db_session, Decimal("50000.00"))
    product = raw_db_session.scalars(select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")).one()
    InvestmentService.purchase_investment(db=raw_db_session, caller_user_id=user.id, idempotency_key=str(uuid.uuid4()),
                                          product_id=product.id, source_account_id=a.id, amount=Decimal("20000.00"))
    purchase = raw_db_session.scalars(select(TransferRequest).where(TransferRequest.source_account_id == a.id,
                                                                   TransferRequest.status == "POSTED")).one()
    with pytest.raises(ReversalError) as exc:
        ReversalService.reverse_transfer(raw_db_session, purchase.id, admin.id, "Not a customer transfer")
    assert exc.value.status_code == 400


def test_concurrent_reversals_post_exactly_once():
    engine = create_engine(settings.sync_test_database_url, pool_size=5)
    try:
        with Session(engine) as setup:
            admin = _user(setup, "ADMIN")
            user, a, b = _funded_pair(setup, Decimal("1000.00"))
            original = _transfer(setup, user, a, b, Decimal("400.00"))
            original_id, a_id, admin_id = original.id, a.id, admin.id

        barrier = threading.Barrier(2)
        outcomes: list = [None, None]

        def worker(i: int):
            with Session(engine) as db:
                barrier.wait()
                try:
                    ReversalService.reverse_transfer(db, original_id, admin_id, f"Concurrent correction {i}")
                    outcomes[i] = "ok"
                except ReversalError as err:
                    outcomes[i] = err.status_code

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert sorted(outcomes, key=str) == [409, "ok"], outcomes
        with Session(engine) as verify:
            assert verify.get(Account, a_id).cached_balance == Decimal("1000.00")
            reversals = verify.scalar(select(func.count(LedgerTransaction.id)).join(
                TransferRequest, LedgerTransaction.transfer_request_id == TransferRequest.id).where(
                LedgerTransaction.transaction_type == "CORRECTION_REVERSAL",
                TransferRequest.idempotency_key == f"reversal-{original_id}"))
            assert reversals == 1
    finally:
        engine.dispose()


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id, role=user.role, username=user.username)}"}


def test_reverse_endpoint_requires_admin_and_a_reason(client, db_session, sample_user, sample_account, sample_dest_account):
    staff = User(username="rev_staff_api", email="rev_staff_api@example.com", password_hash="x", role="STAFF", is_active=True)
    admin = User(username="rev_admin_api", email="rev_admin_api@example.com", password_hash="x", role="ADMIN", is_active=True)
    db_session.add_all([staff, admin])
    db_session.commit()
    tx_id = uuid.uuid4()

    assert client.post(f"/api/v1/transfers/{tx_id}/reverse", json={"reason": "Dispute upheld by admin"}, headers=_auth(sample_user)).status_code == 403
    assert client.post(f"/api/v1/transfers/{tx_id}/reverse", json={"reason": "Dispute upheld by admin"}, headers=_auth(staff)).status_code == 403
    assert client.post(f"/api/v1/transfers/{tx_id}/reverse", json={"reason": "short"}, headers=_auth(admin)).status_code == 422
    assert client.post(f"/api/v1/transfers/{tx_id}/reverse", json={"reason": "Dispute upheld by admin"}, headers=_auth(admin)).status_code == 404
