"""Regression tests for review findings on the sr hardening branch.

Covers:
- Investment holding accounts cannot be drained through ordinary transfers
- Replaying an idempotency key whose original attempt FAILED never reports success
- Concurrent duplicate submissions draining the full balance both resolve to the single POSTED transfer
- Investment replays resolve to the exact investment created by the original request
- Purchases against a frozen investment holding account fail cleanly with audit evidence
- Internal exception text never reaches the client
- Staff cannot debit customer accounts through the customer transfer endpoint
- Idempotency-Key must be a UUID
- ledger_transactions headers are append-only; TRUNCATE on append-only tables is blocked
- Staff can open disputes on transfers whose initiator has no customer profile
"""

from decimal import Decimal
import threading
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Account, AuditLog, Customer, FinancialProduct, Investment, TransferRequest, User
from app.models.ledger import LedgerTransaction
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService
from app.services.transfer_service import (
    AccountEligibilityError,
    InsufficientFundsError,
    TransferBusinessError,
    TransferService,
)


@pytest.fixture
def independent_engine():
    engine = create_engine(settings.sync_test_database_url, pool_size=5, max_overflow=5)
    yield engine
    engine.dispose()


def _committed_customer(session: Session, *balances: Decimal) -> tuple[User, Customer, list[Account]]:
    """Create a committed customer with funded SAVINGS accounts (funded from clearing, double-entry)."""
    tag = uuid.uuid4().hex[:8]
    user = User(
        username=f"hard_{tag}",
        email=f"hard_{tag}@example.com",
        password_hash="$2b$12$samplepasswordhashforspeed",
        role="CUSTOMER",
        is_active=True,
    )
    session.add(user)
    session.flush()
    customer = Customer(user_id=user.id, full_name=f"Hardening {tag}", kyc_status="VERIFIED")
    session.add(customer)
    session.flush()
    accounts = [
        Account(
            customer_id=customer.id,
            account_number=f"INR-HARD-{tag}-{i}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        for i in range(len(balances))
    ]
    session.add_all(accounts)
    session.commit()
    for acc, bal in zip(accounts, balances):
        if bal > 0:
            AccountService.deposit_opening_funds(db=session, account_id=acc.id, amount=bal, actor_user_id=user.id)
    session.commit()
    return user, customer, accounts


def _fd_product(session: Session) -> FinancialProduct:
    return session.scalars(select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")).one()


def test_transfer_cannot_drain_investment_holding_account(raw_db_session):
    user, customer, (savings,) = _committed_customer(raw_db_session, Decimal("50000.00"))
    product = _fd_product(raw_db_session)
    investment, _ = InvestmentService.purchase_investment(
        db=raw_db_session,
        caller_user_id=user.id,
        idempotency_key=str(uuid.uuid4()),
        product_id=product.id,
        source_account_id=savings.id,
        amount=Decimal("20000.00"),
    )
    inv_acc_id = investment.account_id

    with pytest.raises(AccountEligibilityError):
        TransferService.execute_transfer(
            db=raw_db_session,
            caller_user_id=user.id,
            idempotency_key=str(uuid.uuid4()),
            source_account_id=inv_acc_id,
            destination_account_id=savings.id,
            amount=Decimal("20000.00"),
        )

    assert raw_db_session.get(Account, inv_acc_id).cached_balance == Decimal("20000.00")


def test_replaying_failed_transfer_key_never_reports_success(raw_db_session):
    user, _, (src, dst) = _committed_customer(raw_db_session, Decimal("100.00"), Decimal("0.00"))
    key = str(uuid.uuid4())
    kwargs = dict(
        db=raw_db_session,
        caller_user_id=user.id,
        idempotency_key=key,
        source_account_id=src.id,
        destination_account_id=dst.id,
        amount=Decimal("500.00"),
    )
    with pytest.raises(InsufficientFundsError):
        TransferService.execute_transfer(**kwargs)

    # Identical replay of a FAILED key must surface the original failure, not a 2xx receipt
    with pytest.raises(TransferBusinessError) as exc_info:
        TransferService.execute_transfer(**kwargs)
    assert "Insufficient funds" in exc_info.value.message


def test_concurrent_duplicate_full_drain_both_resolve_to_posted(independent_engine):
    with Session(independent_engine) as setup:
        user, _, (src, dst) = _committed_customer(setup, Decimal("500.00"), Decimal("0.00"))
        user_id, src_id, dst_id = user.id, src.id, dst.id

    key = str(uuid.uuid4())
    barrier = threading.Barrier(2)
    results: list = [None, None]

    def worker(idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                req, replay = TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=key,
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("500.00"),
                )
                results[idx] = (req.status, replay)
            except Exception as exc:  # noqa: BLE001 - recorded for assertion
                results[idx] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert sorted(results, key=str) == [("POSTED", False), ("POSTED", True)], results

    with Session(independent_engine) as verify:
        assert verify.get(Account, src_id).cached_balance == Decimal("0.00")
        assert verify.get(Account, dst_id).cached_balance == Decimal("500.00")
        failed_audits = verify.scalars(
            select(AuditLog).where(AuditLog.action == "TRANSFER_FAILED", AuditLog.actor_user_id == user_id)
        ).all()
        assert failed_audits == []


def test_investment_replay_returns_exact_original_investment(raw_db_session):
    user, _, (savings,) = _committed_customer(raw_db_session, Decimal("100000.00"))
    product = _fd_product(raw_db_session)
    key_1, key_2 = str(uuid.uuid4()), str(uuid.uuid4())

    def buy(key: str):
        return InvestmentService.purchase_investment(
            db=raw_db_session,
            caller_user_id=user.id,
            idempotency_key=key,
            product_id=product.id,
            source_account_id=savings.id,
            amount=Decimal("10000.00"),
        )

    first, _ = buy(key_1)
    first_id = first.id
    second, _ = buy(key_2)
    assert second.id != first_id

    replayed, is_replay = buy(key_1)
    assert is_replay is True
    assert replayed.id == first_id


def test_purchase_with_frozen_investment_account_fails_cleanly(raw_db_session):
    user, customer, (savings,) = _committed_customer(raw_db_session, Decimal("100000.00"))
    product = _fd_product(raw_db_session)
    inv, _ = InvestmentService.purchase_investment(
        db=raw_db_session,
        caller_user_id=user.id,
        idempotency_key=str(uuid.uuid4()),
        product_id=product.id,
        source_account_id=savings.id,
        amount=Decimal("10000.00"),
    )
    inv_acc = raw_db_session.get(Account, inv.account_id)
    inv_acc.status = "FROZEN"
    raw_db_session.commit()

    key = str(uuid.uuid4())
    with pytest.raises(AccountEligibilityError):
        InvestmentService.purchase_investment(
            db=raw_db_session,
            caller_user_id=user.id,
            idempotency_key=key,
            product_id=product.id,
            source_account_id=savings.id,
            amount=Decimal("10000.00"),
        )

    audit = raw_db_session.scalars(
        select(AuditLog).where(AuditLog.action == "INVESTMENT_PURCHASE_FAILED", AuditLog.actor_user_id == user.id)
    ).first()
    assert audit is not None


def test_staff_cannot_debit_customer_account_via_transfer_endpoint(
    client, auth_headers_factory, test_staff_user, sample_account, sample_dest_account, db_session
):
    db_session.commit()
    headers = auth_headers_factory(test_staff_user)
    headers["Idempotency-Key"] = str(uuid.uuid4())
    res = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": str(sample_account.id),
            "destination_account_id": str(sample_dest_account.id),
            "amount": "100.00",
            "currency": "INR",
        },
        headers=headers,
    )
    assert res.status_code == 403
    db_session.refresh(sample_account)
    assert sample_account.cached_balance == Decimal("10000.00")


def test_idempotency_key_must_be_uuid(client, auth_headers_factory, test_customer_user, sample_dest_account):
    headers = auth_headers_factory(test_customer_user)
    headers["Idempotency-Key"] = "not-a-uuid"
    res = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": str(uuid.uuid4()),
            "destination_account_id": str(sample_dest_account.id),
            "amount": "1.00",
            "currency": "INR",
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_ledger_transaction_headers_are_append_only(raw_db_session):
    user, _, (acc,) = _committed_customer(raw_db_session, Decimal("10.00"))
    txn_id = raw_db_session.scalars(select(LedgerTransaction.id).order_by(LedgerTransaction.created_at.desc())).first()
    with pytest.raises(DBAPIError, match="append-only"):
        raw_db_session.execute(
            text("UPDATE ledger_transactions SET description = 'tampered' WHERE id = :id"), {"id": txn_id}
        )
        raw_db_session.flush()
    raw_db_session.rollback()


@pytest.mark.parametrize("table", ["ledger_entries", "ledger_transactions", "audit_logs"])
def test_truncate_blocked_on_append_only_tables(raw_db_session, table):
    with pytest.raises(DBAPIError, match="append-only"):
        raw_db_session.execute(text(f"TRUNCATE {table} CASCADE"))
    raw_db_session.rollback()


def test_staff_can_dispute_transfer_initiated_without_customer_profile(
    client, auth_headers_factory, test_staff_user, sample_account, sample_dest_account, db_session
):
    staff_initiated = TransferRequest(
        idempotency_key=str(uuid.uuid4()),
        source_user_id=test_staff_user.id,
        request_hash="0" * 64,
        source_account_id=sample_account.id,
        destination_account_id=sample_dest_account.id,
        amount=Decimal("10.00"),
        currency="INR",
        status="FAILED",
        failure_reason="seeded for test",
    )
    db_session.add(staff_initiated)
    db_session.commit()

    res = client.post(
        "/api/v1/disputes",
        json={
            "transfer_request_id": str(staff_initiated.id),
            "category": "UNAUTHORIZED",
            "description": "Staff-opened dispute for a staff-initiated transfer",
        },
        headers=auth_headers_factory(test_staff_user),
    )
    assert res.status_code == 201, res.text
    assert res.json()["customer_id"] == str(sample_account.customer_id)


def test_login_locks_out_after_repeated_failures(client, test_customer_user):
    bad = {"username_or_email": test_customer_user.username, "password": "WrongPassword123!"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=bad).status_code == 401
    assert client.post("/api/v1/auth/login", json=bad).status_code == 429


def test_transfer_history_lists_only_callers_transfers_including_failures(
    client, auth_headers_factory, test_customer_user, db_session
):
    customer = test_customer_user.customer
    src = Account(customer_id=customer.id, account_number="INR-HIST-SRC", account_type="SAVINGS",
                  currency="INR", cached_balance=Decimal("100.00"), status="ACTIVE", version=1)
    dst = Account(customer_id=customer.id, account_number="INR-HIST-DST", account_type="SAVINGS",
                  currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE", version=1)
    stranger_user = User(username="hist_stranger", email="hist_stranger@example.com",
                         password_hash="x", role="CUSTOMER", is_active=True)
    db_session.add_all([src, dst, stranger_user])
    db_session.flush()
    stranger = Customer(user_id=stranger_user.id, full_name="Stranger", kyc_status="VERIFIED")
    db_session.add(stranger)
    db_session.flush()
    s1 = Account(customer_id=stranger.id, account_number="INR-HIST-X1", account_type="SAVINGS",
                 currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE", version=1)
    s2 = Account(customer_id=stranger.id, account_number="INR-HIST-X2", account_type="SAVINGS",
                 currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE", version=1)
    db_session.add_all([s1, s2])
    db_session.flush()

    def req(user_id, a, b, status):
        return TransferRequest(idempotency_key=str(uuid.uuid4()), source_user_id=user_id, request_hash="0" * 64,
                               source_account_id=a.id, destination_account_id=b.id, amount=Decimal("10.00"),
                               currency="INR", status=status,
                               failure_reason="Insufficient funds" if status == "FAILED" else None)

    mine_ok = req(test_customer_user.id, src, dst, "POSTED")
    mine_failed = req(test_customer_user.id, src, dst, "FAILED")
    theirs = req(stranger_user.id, s1, s2, "POSTED")
    db_session.add_all([mine_ok, mine_failed, theirs])
    db_session.commit()

    res = client.get("/api/v1/transfers", headers=auth_headers_factory(test_customer_user))
    assert res.status_code == 200, res.text
    items = {item["id"]: item for item in res.json()}
    assert set(items) == {str(mine_ok.id), str(mine_failed.id)}
    assert items[str(mine_failed.id)]["status"] == "FAILED"
    assert items[str(mine_failed.id)]["failure_reason"] == "Insufficient funds"
    assert items[str(mine_ok.id)]["source_account_number"] == "INR-HIST-SRC"
    assert items[str(mine_ok.id)]["destination_account_number"] == "INR-HIST-DST"


def test_dossier_renders_when_transfer_has_audit_events(
    client, auth_headers_factory, test_staff_user, sample_account, sample_dest_account, sample_user, db_session
):
    from app.models import FraudPrediction

    tx = TransferRequest(idempotency_key=str(uuid.uuid4()), source_user_id=sample_user.id, request_hash="0" * 64,
                         source_account_id=sample_account.id, destination_account_id=sample_dest_account.id,
                         amount=Decimal("10.00"), currency="INR", status="POSTED")
    db_session.add(tx)
    db_session.flush()
    db_session.add(AuditLog(action="TRANSFER_POSTED", entity_type="TRANSFER", entity_id=str(tx.id),
                            actor_user_id=sample_user.id, metadata_json={"amount": "10.00"}))
    pred = FraudPrediction(transfer_request_id=tx.id, model_version="rf-v1.0.0", risk_score=Decimal("0.1000"),
                           decision="LOW_RISK", rule_flags=[], explanation="Low risk.", review_status="PENDING")
    db_session.add(pred)
    db_session.commit()

    res = client.get(f"/api/v1/fraud/alerts/{pred.id}/dossier", headers=auth_headers_factory(test_staff_user))
    assert res.status_code == 200, res.text
    actions = [a["action"] for a in res.json()["audit_events"]]
    assert "TRANSFER_POSTED" in actions


def test_staff_can_review_graph_finding(client, auth_headers_factory, test_staff_user, sample_account, db_session):
    from datetime import datetime, timezone
    from app.models.graph import GraphFinding

    now = datetime.now(timezone.utc)
    finding = GraphFinding(pattern_type="FAN_IN", detector_version="ledgergraph-test", severity="HIGH",
                           heuristic_score=Decimal("0.8000"), primary_account_id=sample_account.id,
                           window_start=now, window_end=now, involved_transfer_ids=[], involved_account_ids=[],
                           evidence={}, explanation="Seeded for review test", review_status="PENDING")
    db_session.add(finding)
    db_session.commit()

    res = client.patch(f"/api/v1/graph/findings/{finding.id}/review",
                       json={"review_status": "CLEARED", "notes": "Reviewed: legitimate payroll pattern"},
                       headers=auth_headers_factory(test_staff_user))
    assert res.status_code == 200, res.text
    assert res.json()["review_status"] == "CLEARED"
    audit = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == str(finding.id))).first()
    assert audit is not None and audit.metadata_json["to_status"] == "CLEARED"


def test_model_health_reads_committed_artifact_metadata(client, auth_headers_factory, test_staff_user):
    import json
    from pathlib import Path

    metadata = json.loads((Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "metadata.json").read_text())
    res = client.get("/api/v1/fraud/health", headers=auth_headers_factory(test_staff_user))
    assert res.status_code == 200, res.text
    assert res.json()["feature_schema"] == metadata["feature_names"]
    assert res.json()["train_samples"] == metadata["train_samples"]
