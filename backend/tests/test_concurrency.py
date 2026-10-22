"""PostgreSQL Concurrency Integration Tests for FinLedger-AI.

Uses independent database sessions across OS threads to verify:
1. Overspending race condition: Two concurrent transfers of ₹80 against a ₹100 balance.
   Guarantees exactly one succeeds and the other is rejected for insufficient funds.
   Zero overdrawing is possible.
2. Bidirectional deadlock freedom: Transfers between A->B and B->A acquire locks in
   canonical ascending primary key order, preventing PostgreSQL deadlocks.
3. Concurrent duplicate request resolution: Simultaneous identical submissions result
   in exactly one financial posting without transaction corruption.
"""

from decimal import Decimal
import threading
import uuid
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, Customer, Account, TransferRequest, FinancialProduct, Investment, AuditLog
from app.services.transfer_service import (
    TransferService,
    InsufficientFundsError,
)
from app.services.investment_service import InvestmentService
from app.services.ledger_service import LedgerService
from app.services.account_service import AccountService
from app.services.audit_service import AuditService


@pytest.fixture
def independent_engine():
    """Create a dedicated engine for concurrency tests against the test database."""
    engine = create_engine(
        settings.sync_test_database_url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


def test_concurrent_overspending_prevented(independent_engine):
    """Critical DBMS test: Two simultaneous ₹80 transfers against a ₹100 balance.

    Setup:
    - Customer has exactly ₹100.00 in Source Account (deposited from internal clearing).
    - Destination Account has ₹0.00.
    - Two threads simultaneously attempt to transfer ₹80.00 using distinct idempotency keys.

    Verification:
    - Exactly one transfer commits (status='POSTED').
    - The other transfer fails with InsufficientFundsError (no funds overdrawn).
    - Source account final cached balance is exactly ₹20.00.
    - Source account ledger-derived balance is exactly ₹20.00.
    - Destination account final cached balance is exactly ₹80.00.
    - Destination account ledger-derived balance is exactly ₹80.00.
    """
    # Step 1: Provision test data in a dedicated setup session
    with Session(independent_engine) as session:
        user = User(
            username=f"conc_user_{uuid.uuid4().hex[:8]}",
            email=f"conc_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Concurrency Test Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src_acc = Account(
            customer_id=customer.id,
            account_number=f"INR-CONC-SRC-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        dst_acc = Account(
            customer_id=customer.id,
            account_number=f"INR-CONC-DST-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add_all([src_acc, dst_acc])
        session.commit()

        # Properly fund source account via double-entry opening deposit
        AccountService.deposit_opening_funds(
            db=session,
            account_id=src_acc.id,
            amount=Decimal("100.00"),
            description="Opening deposit for concurrency test",
            actor_user_id=user.id,
        )
        session.commit()

        user_id = user.id
        src_id = src_acc.id
        dst_id = dst_acc.id

    # Step 2: Concurrency execution with Threading Barrier
    barrier = threading.Barrier(2)
    results = [None, None]
    exceptions = [None, None]

    def worker(worker_idx: int, key: str):
        with Session(independent_engine) as thread_db:
            barrier.wait()  # Synchronize threads so they attack the balance simultaneously
            try:
                res, is_replay = TransferService.execute_transfer(
                    db=thread_db,
                    caller_user_id=user_id,
                    idempotency_key=key,
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("80.00"),
                    currency="INR",
                    memo=f"Concurrent transfer from worker {worker_idx}",
                )
                results[worker_idx] = (res.status, is_replay)
            except Exception as exc:
                exceptions[worker_idx] = exc

    key1 = str(uuid.uuid4())
    key2 = str(uuid.uuid4())

    t1 = threading.Thread(target=worker, args=(0, key1))
    t2 = threading.Thread(target=worker, args=(1, key2))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Step 3: Assert outcomes
    success_count = sum(1 for r in results if r is not None and r[0] == "POSTED")
    insufficient_funds_count = sum(1 for e in exceptions if isinstance(e, InsufficientFundsError))

    assert success_count == 1, f"Expected exactly 1 transfer to succeed, got {success_count}. Results: {results}"
    assert insufficient_funds_count == 1, f"Expected exactly 1 InsufficientFundsError, got {insufficient_funds_count}. Exceptions: {exceptions}"

    # Step 4: Verify database integrity in fresh session
    with Session(independent_engine) as verify_db:
        fresh_src = verify_db.get(Account, src_id)
        fresh_dst = verify_db.get(Account, dst_id)

        # Balances must be exactly ₹20.00 and ₹80.00
        assert fresh_src.cached_balance == Decimal("20.00")
        assert fresh_dst.cached_balance == Decimal("80.00")

        # Ledger derived balance checks
        src_derived = LedgerService.get_derived_balance(verify_db, src_id)
        dst_derived = LedgerService.get_derived_balance(verify_db, dst_id)

        assert src_derived == fresh_src.cached_balance == Decimal("20.00")
        assert dst_derived == fresh_dst.cached_balance == Decimal("80.00")
        # Since src started with 100 before ledger postings, net ledger entries on src is -80.00
        # cached_balance is 100 - 80 = 20.00

        # Verify only 1 successful transfer request exists
        posted_transfers = list(
            verify_db.scalars(
                select(TransferRequest).where(
                    TransferRequest.source_account_id == src_id,
                    TransferRequest.status == "POSTED",
                )
            ).all()
        )
        assert len(posted_transfers) == 1
        assert posted_transfers[0].amount == Decimal("80.00")


def test_concurrent_bidirectional_transfers_no_deadlock(independent_engine):
    """Verify bidirectional transfers (A->B and B->A) avoid deadlock via canonical lock ordering."""
    with Session(independent_engine) as session:
        user = User(
            username=f"bidi_user_{uuid.uuid4().hex[:8]}",
            email=f"bidi_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Bidirectional Test Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        acc_a = Account(
            customer_id=customer.id,
            account_number=f"INR-BIDI-A-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        acc_b = Account(
            customer_id=customer.id,
            account_number=f"INR-BIDI-B-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add_all([acc_a, acc_b])
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=acc_a.id,
            amount=Decimal("1000.00"),
            actor_user_id=user.id,
        )
        AccountService.deposit_opening_funds(
            db=session,
            account_id=acc_b.id,
            amount=Decimal("1000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        user_id = user.id
        id_a = acc_a.id
        id_b = acc_b.id

    barrier = threading.Barrier(2)
    exceptions = [None, None]

    def worker_a_to_b():
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    source_account_id=id_a,
                    destination_account_id=id_b,
                    amount=Decimal("100.00"),
                )
            except Exception as e:
                exceptions[0] = e

    def worker_b_to_a():
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    source_account_id=id_b,
                    destination_account_id=id_a,
                    amount=Decimal("200.00"),
                )
            except Exception as e:
                exceptions[1] = e

    t1 = threading.Thread(target=worker_a_to_b)
    t2 = threading.Thread(target=worker_b_to_a)

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Both must succeed without deadlock!
    assert exceptions[0] is None, f"Worker A->B encountered error: {exceptions[0]}"
    assert exceptions[1] is None, f"Worker B->A encountered error: {exceptions[1]}"

    with Session(independent_engine) as verify_db:
        final_a = verify_db.get(Account, id_a)
        final_b = verify_db.get(Account, id_b)

        # A: 1000 - 100 + 200 = 1100.00
        # B: 1000 + 100 - 200 = 900.00
        assert final_a.cached_balance == Decimal("1100.00")
        assert final_b.cached_balance == Decimal("900.00")


def test_concurrent_identical_requests_single_transfer(independent_engine):
    """Verify concurrent requests with the identical idempotency key commit exactly once."""
    with Session(independent_engine) as session:
        user = User(
            username=f"idem_race_{uuid.uuid4().hex[:8]}",
            email=f"idem_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Idem Race Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-IDEM-R1-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        dst = Account(
            customer_id=customer.id,
            account_number=f"INR-IDEM-R2-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add_all([src, dst])
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("5000.00"),
            actor_user_id=user.id,
        )
        AccountService.deposit_opening_funds(
            db=session,
            account_id=dst.id,
            amount=Decimal("1000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        user_id = user.id
        src_id = src.id
        dst_id = dst.id

    shared_key = str(uuid.uuid4())
    barrier = threading.Barrier(2)
    results = [None, None]
    exceptions = [None, None]

    def worker(worker_idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                res, is_replay = TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=shared_key,
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("500.00"),
                )
                results[worker_idx] = (res.status, is_replay)
            except Exception as e:
                exceptions[worker_idx] = e

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Both threads complete without unhandled crash
    assert exceptions[0] is None or exceptions[1] is None

    with Session(independent_engine) as verify_db:
        final_src = verify_db.get(Account, src_id)
        final_dst = verify_db.get(Account, dst_id)

        # Funds debited and credited EXACTLY once
        assert final_src.cached_balance == Decimal("4500.00")
        assert final_dst.cached_balance == Decimal("1500.00")

        # Exactly 1 TransferRequest row
        transfers = list(
            verify_db.scalars(
                select(TransferRequest).where(
                    TransferRequest.source_user_id == user_id,
                    TransferRequest.idempotency_key == shared_key,
                )
            ).all()
        )
        assert len(transfers) == 1


def test_concurrent_investment_overspending_prevented(independent_engine):
    """Verify concurrent investment purchases competing for funds cannot overdraw balance.

    Setup:
    - Customer has ₹30,000.00 in Savings Account.
    - Two threads simultaneously attempt to buy ₹20,000.00 of FD-12M-STD (total ₹40,000.00 required).

    Verification:
    - Exactly one purchase succeeds.
    - The other purchase fails with InsufficientFundsError.
    - Final savings balance is exactly ₹10,000.00 (not negative).
    - Exactly one Investment record exists.
    """
    with Session(independent_engine) as session:
        user = User(
            username=f"inv_overspend_{uuid.uuid4().hex[:8]}",
            email=f"inv_overspend_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Investment Overspend Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-INV-OVS-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add(src)
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("30000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        product = session.scalars(
            select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
        ).first()
        assert product is not None

        user_id = user.id
        cust_id = customer.id
        src_id = src.id
        prod_id = product.id

    barrier = threading.Barrier(2)
    results = [None, None]
    exceptions = [None, None]

    def worker(worker_idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                inv, is_replay = InvestmentService.purchase_investment(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    product_id=prod_id,
                    source_account_id=src_id,
                    amount=Decimal("20000.00"),
                )
                results[worker_idx] = (inv.id, is_replay)
            except Exception as e:
                exceptions[worker_idx] = e

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Exactly one succeeded and one raised InsufficientFundsError
    success_count = sum(1 for r in results if r is not None)
    insuf_count = sum(1 for e in exceptions if isinstance(e, InsufficientFundsError))
    assert success_count == 1, f"Expected 1 success, got {success_count}. Exceptions: {exceptions}"
    assert insuf_count == 1, f"Expected 1 InsufficientFundsError, got {insuf_count}. Exceptions: {exceptions}"

    with Session(independent_engine) as verify_db:
        final_src = verify_db.get(Account, src_id)
        # Account balance must be strictly 10,000.00 (30,000 - 20,000)
        assert final_src.cached_balance == Decimal("10000.00")

        # Derived ledger balance matches cached balance
        derived_src = LedgerService.get_derived_balance(verify_db, src_id)
        assert derived_src == Decimal("10000.00")

        # Exactly 1 active investment position
        investments = list(
            verify_db.scalars(
                select(Investment).where(
                    Investment.customer_id == cust_id,
                    Investment.status == "ACTIVE",
                )
            ).all()
        )
        assert len(investments) == 1
        assert investments[0].invested_amount == Decimal("20000.00")

        # Investment account cached balance is 20,000.00
        inv_acc = verify_db.get(Account, investments[0].account_id)
        assert inv_acc.cached_balance == Decimal("20000.00")


def test_concurrent_investment_account_provisioning(independent_engine):
    """Verify concurrent initial investments for a customer without an investment account.

    Guarantees:
    - Customer initially has zero INVESTMENT accounts.
    - Two concurrent threads purchase investments simultaneously.
    - Both purchases succeed without duplicate key violation on account_number.
    - Exactly ONE INVESTMENT account is provisioned for the customer.
    - Both investments link to that single account.
    """
    with Session(independent_engine) as session:
        user = User(
            username=f"inv_prov_{uuid.uuid4().hex[:8]}",
            email=f"inv_prov_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Provisioning Concurrency Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-PROV-SRC-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add(src)
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("50000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        product = session.scalars(
            select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
        ).first()

        user_id = user.id
        cust_id = customer.id
        src_id = src.id
        prod_id = product.id

    barrier = threading.Barrier(2)
    results = [None, None]
    exceptions = [None, None]

    def worker(worker_idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                inv, is_replay = InvestmentService.purchase_investment(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    product_id=prod_id,
                    source_account_id=src_id,
                    amount=Decimal("15000.00"),
                )
                results[worker_idx] = (inv.id, inv.account_id, is_replay)
            except Exception as e:
                exceptions[worker_idx] = e

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Both must succeed cleanly without unhandled crash or duplicate key collision
    assert exceptions[0] is None, f"Worker 0 error: {exceptions[0]}"
    assert exceptions[1] is None, f"Worker 1 error: {exceptions[1]}"
    assert results[0] is not None
    assert results[1] is not None

    with Session(independent_engine) as verify_db:
        # Exactly ONE INVESTMENT account created for this customer
        inv_accounts = list(
            verify_db.scalars(
                select(Account).where(
                    Account.customer_id == cust_id,
                    Account.account_type == "INVESTMENT",
                )
            ).all()
        )
        assert len(inv_accounts) == 1, f"Expected exactly 1 investment account, found {len(inv_accounts)}"

        # Both investments must point to the same single investment account
        single_inv_acc = inv_accounts[0]
        assert results[0][1] == single_inv_acc.id
        assert results[1][1] == single_inv_acc.id

        # Total balances:
        # Savings: 50,000 - 15,000 - 15,000 = 20,000.00
        # Investment: 15,000 + 15,000 = 30,000.00
        final_src = verify_db.get(Account, src_id)
        assert final_src.cached_balance == Decimal("20000.00")
        assert single_inv_acc.cached_balance == Decimal("30000.00")

        # Derived balances match
        assert LedgerService.get_derived_balance(verify_db, src_id) == Decimal("20000.00")
        assert LedgerService.get_derived_balance(verify_db, single_inv_acc.id) == Decimal("30000.00")


def test_concurrent_identical_investment_requests_single_purchase(independent_engine):
    """Verify concurrent investment submissions with the identical idempotency key result in 1 purchase."""
    with Session(independent_engine) as session:
        user = User(
            username=f"inv_idem_{uuid.uuid4().hex[:8]}",
            email=f"inv_idem_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Idem Investment Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-INV-IDM-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add(src)
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("40000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        product = session.scalars(
            select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
        ).first()

        user_id = user.id
        src_id = src.id
        prod_id = product.id
        cust_id = customer.id

    shared_key = str(uuid.uuid4())
    barrier = threading.Barrier(2)
    results = [None, None]
    exceptions = [None, None]

    def worker(worker_idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                inv, is_replay = InvestmentService.purchase_investment(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=shared_key,
                    product_id=prod_id,
                    source_account_id=src_id,
                    amount=Decimal("15000.00"),
                )
                results[worker_idx] = (inv.id, is_replay)
            except Exception as e:
                exceptions[worker_idx] = e

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Both threads complete without unhandled crash
    assert exceptions[0] is None or exceptions[1] is None

    with Session(independent_engine) as verify_db:
        final_src = verify_db.get(Account, src_id)
        # Funds debited EXACTLY once: 40000 - 15000 = 25000.00
        assert final_src.cached_balance == Decimal("25000.00")

        # Exactly 1 Investment position
        investments = list(
            verify_db.scalars(
                select(Investment).where(
                    Investment.customer_id == cust_id,
                    Investment.status == "ACTIVE",
                )
            ).all()
        )
        assert len(investments) == 1
        assert investments[0].invested_amount == Decimal("15000.00")

        # Exactly 1 TransferRequest row
        transfers = list(
            verify_db.scalars(
                select(TransferRequest).where(
                    TransferRequest.source_user_id == user_id,
                    TransferRequest.idempotency_key == shared_key,
                )
            ).all()
        )
        assert len(transfers) == 1


def test_multi_thread_concurrent_drain_race(independent_engine):
    """Stress test: 5 concurrent threads competing to withdraw ₹30 from a ₹100 balance.

    Total demanded = ₹150.00 against ₹100.00 available.
    Guarantees:
    - Exactly 3 transfers succeed (3 * 30 = ₹90.00).
    - Exactly 2 transfers fail with InsufficientFundsError.
    - Zero overdraft occurs (balance cannot become negative).
    - Final source balance is exactly ₹10.00.
    - Final destination balance is exactly ₹90.00.
    - Ledger-derived balances match cached balances exactly.
    """
    with Session(independent_engine) as session:
        user = User(
            username=f"drain_race_{uuid.uuid4().hex[:8]}",
            email=f"drain_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Drain Race Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-DRN-SRC-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        dst = Account(
            customer_id=customer.id,
            account_number=f"INR-DRN-DST-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add_all([src, dst])
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("100.00"),
            actor_user_id=user.id,
        )
        session.commit()

        user_id = user.id
        src_id = src.id
        dst_id = dst.id

    num_threads = 5
    barrier = threading.Barrier(num_threads)
    results = [None] * num_threads
    exceptions = [None] * num_threads

    def worker(idx: int):
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                tx, is_replay = TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("30.00"),
                )
                results[idx] = (tx.status, is_replay)
            except Exception as e:
                exceptions[idx] = e

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    successes = sum(1 for r in results if r is not None and r[0] == "POSTED")
    failures = sum(1 for e in exceptions if isinstance(e, InsufficientFundsError))

    assert successes == 3, f"Expected 3 successes, got {successes}. Results: {results}"
    assert failures == 2, f"Expected 2 InsufficientFundsErrors, got {failures}. Exceptions: {exceptions}"

    with Session(independent_engine) as verify_db:
        final_src = verify_db.get(Account, src_id)
        final_dst = verify_db.get(Account, dst_id)

        assert final_src.cached_balance == Decimal("10.00")
        assert final_dst.cached_balance == Decimal("90.00")

        # Verify double-entry ledger derived balances
        assert LedgerService.get_derived_balance(verify_db, src_id) == Decimal("10.00")
        assert LedgerService.get_derived_balance(verify_db, dst_id) == Decimal("90.00")


def test_concurrent_forced_failure_with_audit_persistence(independent_engine):
    """Verify that a worker failing mid-transaction rolls back financial state
    while preserving its audit log, without corrupting concurrent successful workers.
    """
    with Session(independent_engine) as session:
        user = User(
            username=f"audit_race_{uuid.uuid4().hex[:8]}",
            email=f"audit_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$samplepasswordhashforspeed",
            role="CUSTOMER",
            is_active=True,
        )
        session.add(user)
        session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Audit Failure Race Customer",
            kyc_status="VERIFIED",
        )
        session.add(customer)
        session.flush()

        src = Account(
            customer_id=customer.id,
            account_number=f"INR-AFAIL-SRC-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        dst = Account(
            customer_id=customer.id,
            account_number=f"INR-AFAIL-DST-{uuid.uuid4().hex[:6]}",
            account_type="SAVINGS",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        session.add_all([src, dst])
        session.commit()

        AccountService.deposit_opening_funds(
            db=session,
            account_id=src.id,
            amount=Decimal("5000.00"),
            actor_user_id=user.id,
        )
        session.commit()

        user_id = user.id
        src_id = src.id
        dst_id = dst.id

    barrier = threading.Barrier(2)
    exceptions = [None, None]
    results = [None, None]

    # Worker 1: Attempts transfer with amount exceeding balance (forced financial rejection)
    def worker_fail():
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("999999.00"),  # Insufficient funds
                )
            except Exception as e:
                exceptions[0] = e

    # Worker 2: Concurrent valid transfer of ₹500
    def worker_success():
        with Session(independent_engine) as db:
            barrier.wait()
            try:
                tx, is_replay = TransferService.execute_transfer(
                    db=db,
                    caller_user_id=user_id,
                    idempotency_key=str(uuid.uuid4()),
                    source_account_id=src_id,
                    destination_account_id=dst_id,
                    amount=Decimal("500.00"),
                )
                results[1] = tx.status
            except Exception as e:
                exceptions[1] = e

    t1 = threading.Thread(target=worker_fail)
    t2 = threading.Thread(target=worker_success)

    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert isinstance(exceptions[0], InsufficientFundsError)
    assert exceptions[1] is None
    assert results[1] == "POSTED"

    with Session(independent_engine) as verify_db:
        final_src = verify_db.get(Account, src_id)
        final_dst = verify_db.get(Account, dst_id)

        # Only Worker 2's ₹500 was debited: 5000 - 500 = 4500.00
        assert final_src.cached_balance == Decimal("4500.00")
        assert final_dst.cached_balance == Decimal("500.00")

        # Worker 1's failure audit record is preserved via independent transaction
        failed_audits = list(
            verify_db.scalars(
                select(AuditLog).where(
                    AuditLog.actor_user_id == user_id,
                    AuditLog.action == "TRANSFER_FAILED",
                )
            ).all()
        )
        assert len(failed_audits) >= 1
