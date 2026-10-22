"""Integration tests for FinLedger-AI Investment Service & APIs.

Verifies:
- Atomic double-entry simulated investment purchases
- Deferrable trigger compliance (sum(debits) == sum(credits))
- Automatic provisioning of customer INVESTMENT accounts
- Accurate cached balance updates and ledger reconciliation
- Scoped idempotency per customer (replay caching vs 409 conflicts)
- Independent failure auditing for insufficient funds / below min amount
- Customer ownership isolation and staff inspection RBAC
- Customer portfolio aggregation and nominal accrued yield
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select, func

from app.models.user import User
from app.models.account import Account
from app.models.customer import Customer
from app.models.product import FinancialProduct, Investment
from app.models.ledger import LedgerTransaction, LedgerEntry
from app.models.transfer import TransferRequest
from app.models.audit import AuditLog
from app.services.account_service import AccountService
from app.services.investment_service import (
    InvestmentService,
    InvestmentConflictError,
    InvestmentProductError,
)
from app.services.transfer_service import (
    TransferBusinessError,
    InsufficientFundsError,
    TransferOwnershipError,
)
from app.services.ledger_service import LedgerService


@pytest.fixture
def funded_customer_account(db_session, test_customer_user, clearing_account):
    """Provides a customer savings account with ₹100,000.00 funded via double-entry opening deposit."""
    customer = test_customer_user.customer
    acc = Account(
        customer_id=customer.id,
        account_number=f"INR-SAV-{uuid.uuid4().hex[:6].upper()}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(acc)
    db_session.commit()

    AccountService.deposit_opening_funds(
        db=db_session,
        account_id=acc.id,
        amount=Decimal("100000.00"),
        description="Fund test customer account",
        actor_user_id=test_customer_user.id,
    )
    db_session.refresh(acc)
    return acc


def test_successful_investment_purchase_service(db_session, test_customer_user, funded_customer_account):
    """Verify purchasing an investment creates balanced double-entry postings and updates balances."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    assert product is not None

    invest_amount = Decimal("25000.00")
    idempotency_key = str(uuid.uuid4())
    initial_savings = funded_customer_account.cached_balance

    inv, is_replay = InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=idempotency_key,
        product_id=product.id,
        source_account_id=funded_customer_account.id,
        amount=invest_amount,
    )

    assert is_replay is False
    assert inv.invested_amount == invest_amount
    assert inv.current_value == invest_amount
    assert inv.status == "ACTIVE"
    assert inv.maturity_date > inv.start_date

    # Verify customer's savings account was debited
    db_session.refresh(funded_customer_account)
    assert funded_customer_account.cached_balance == initial_savings - invest_amount

    # Verify investment holding account was credited
    inv_acc = db_session.get(Account, inv.account_id)
    assert inv_acc is not None
    assert inv_acc.account_type == "INVESTMENT"
    assert inv_acc.cached_balance == invest_amount

    # Verify balanced ledger entries: 1 debit, 1 credit, net zero
    ledger_entries = list(
        db_session.scalars(
            select(LedgerEntry).join(LedgerTransaction).where(
                LedgerTransaction.transaction_type == "INVESTMENT_PURCHASE"
            )
        ).all()
    )
    assert len(ledger_entries) >= 2
    debit_legs = [e for e in ledger_entries if e.account_id == funded_customer_account.id]
    credit_legs = [e for e in ledger_entries if e.account_id == inv_acc.id]
    assert len(debit_legs) >= 1
    assert len(credit_legs) >= 1
    assert debit_legs[-1].amount == invest_amount
    assert credit_legs[-1].amount == invest_amount

    # Verify derived balances match cached balances
    derived_savings = LedgerService.get_derived_balance(db_session, funded_customer_account.id)
    derived_inv = LedgerService.get_derived_balance(db_session, inv_acc.id)
    assert derived_savings == funded_customer_account.cached_balance
    assert derived_inv == inv_acc.cached_balance


def test_investment_idempotent_replay(db_session, test_customer_user, funded_customer_account):
    """Verify re-submitting identical investment request returns cached record without extra debits."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    invest_amount = Decimal("20000.00")
    idempotency_key = str(uuid.uuid4())

    inv1, is_replay1 = InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=idempotency_key,
        product_id=product.id,
        source_account_id=funded_customer_account.id,
        amount=invest_amount,
    )
    assert is_replay1 is False

    db_session.refresh(funded_customer_account)
    balance_after_first = funded_customer_account.cached_balance

    # Replay with same key
    inv2, is_replay2 = InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=idempotency_key,
        product_id=product.id,
        source_account_id=funded_customer_account.id,
        amount=invest_amount,
    )
    assert is_replay2 is True
    assert inv1.id == inv2.id

    db_session.refresh(funded_customer_account)
    assert funded_customer_account.cached_balance == balance_after_first


def test_investment_idempotency_conflict(db_session, test_customer_user, funded_customer_account):
    """Verify reusing idempotency key with conflicting amount raises InvestmentConflictError."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    idempotency_key = str(uuid.uuid4())

    InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=idempotency_key,
        product_id=product.id,
        source_account_id=funded_customer_account.id,
        amount=Decimal("15000.00"),
    )

    with pytest.raises(InvestmentConflictError) as exc_info:
        InvestmentService.purchase_investment(
            db=db_session,
            caller_user_id=test_customer_user.id,
            idempotency_key=idempotency_key,
            product_id=product.id,
            source_account_id=funded_customer_account.id,
            amount=Decimal("25000.00"),  # Mismatched amount
        )
    assert "different investment parameters" in str(exc_info.value)


def test_investment_insufficient_funds(raw_db_session):
    """Verify purchasing beyond available balance is rejected and audited independently."""
    user = User(
        username=f"insuf_user_{uuid.uuid4().hex[:6]}",
        email=f"insuf_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="$2b$12$e80A1N...samplehash",
        role="CUSTOMER",
        is_active=True,
    )
    raw_db_session.add(user)
    raw_db_session.commit()

    customer = Customer(
        user_id=user.id,
        full_name="Insuf Customer",
        phone="+919876543210",
        pan_number=f"INSUF{uuid.uuid4().hex[:5].upper()}",
        kyc_status="VERIFIED",
    )
    raw_db_session.add(customer)
    raw_db_session.commit()

    acc = Account(
        customer_id=customer.id,
        account_number=f"INR-INSUF-{uuid.uuid4().hex[:6].upper()}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    raw_db_session.add(acc)
    raw_db_session.commit()

    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=acc.id,
        amount=Decimal("15000.00"),
        description="Fund for insuf test",
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    product = raw_db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    excessive_amount = Decimal("500000.00")
    idempotency_key = str(uuid.uuid4())
    src_id = acc.id
    initial_balance = Decimal("15000.00")

    with pytest.raises(InsufficientFundsError):
        InvestmentService.purchase_investment(
            db=raw_db_session,
            caller_user_id=user.id,
            idempotency_key=idempotency_key,
            product_id=product.id,
            source_account_id=src_id,
            amount=excessive_amount,
        )

    # Balance remains untouched
    fresh_acc = raw_db_session.get(Account, src_id)
    assert fresh_acc.cached_balance == initial_balance

    # Verify failure was logged in independent audit trail
    audit_log = raw_db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "INVESTMENT_PURCHASE_FAILED",
            AuditLog.entity_id == idempotency_key,
        )
    ).first()
    assert audit_log is not None


def test_investment_below_product_minimum(db_session, test_customer_user, funded_customer_account):
    """Verify purchasing below product min_amount is rejected with InvestmentProductError."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    assert product.min_amount == Decimal("10000.00")

    with pytest.raises(InvestmentProductError) as exc_info:
        InvestmentService.purchase_investment(
            db=db_session,
            caller_user_id=test_customer_user.id,
            idempotency_key=str(uuid.uuid4()),
            product_id=product.id,
            source_account_id=funded_customer_account.id,
            amount=Decimal("5000.00"),  # Less than min_amount
        )
    assert "below the product minimum" in str(exc_info.value)


def test_investment_unauthorized_account_ownership(db_session, test_customer_user, sample_dest_account):
    """Verify customer cannot fund an investment using another customer's account."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()

    with pytest.raises(TransferOwnershipError):
        InvestmentService.purchase_investment(
            db=db_session,
            caller_user_id=test_customer_user.id,
            idempotency_key=str(uuid.uuid4()),
            product_id=product.id,
            source_account_id=sample_dest_account.id,  # Owned by different customer
            amount=Decimal("10000.00"),
        )


def test_investment_api_and_portfolio_flow(
    client,
    auth_headers_factory,
    test_customer_user,
    funded_customer_account,
    db_session,
):
    """Verify full HTTP flow: purchase, idempotent replay, list, get, and portfolio summary."""
    headers = auth_headers_factory(test_customer_user)
    idempotency_key = str(uuid.uuid4())
    headers["Idempotency-Key"] = idempotency_key

    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "TB-182D-SOV")
    ).first()

    payload = {
        "product_id": str(product.id),
        "source_account_id": str(funded_customer_account.id),
        "amount": "25000.00",
    }

    # 1. Purchase investment via API
    resp_create = client.post("/api/v1/investments", json=payload, headers=headers)
    assert resp_create.status_code == 201
    created_data = resp_create.json()
    investment_id = created_data["id"]
    assert Decimal(str(created_data["invested_amount"])) == Decimal("25000.00")
    assert created_data["status"] == "ACTIVE"

    # 2. Replay with identical key returns 200 OK
    resp_replay = client.post("/api/v1/investments", json=payload, headers=headers)
    assert resp_replay.status_code == 200
    assert resp_replay.json()["id"] == investment_id

    # 3. Retrieve single investment
    resp_get = client.get(f"/api/v1/investments/{investment_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == investment_id

    # 4. List customer investments
    resp_list = client.get("/api/v1/investments", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) >= 1
    assert any(i["id"] == investment_id for i in items)

    # 5. Customer portfolio summary
    resp_portfolio = client.get("/api/v1/investments/portfolio", headers=headers)
    assert resp_portfolio.status_code == 200
    portfolio = resp_portfolio.json()
    assert Decimal(str(portfolio["total_invested"])) >= Decimal("25000.00")
    assert portfolio["active_investments_count"] >= 1
    assert "ACADEMIC NOTICE" in portfolio["disclaimer"]
    assert len(portfolio["holdings"]) >= 1
    assert portfolio["holdings"][0]["product_code"] == "TB-182D-SOV"


def test_investment_access_control_isolation(
    client,
    auth_headers_factory,
    test_customer_user,
    sample_user,
    test_staff_user,
    funded_customer_account,
    db_session,
):
    """Verify customer ownership isolation and staff inspection rights."""
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "TB-182D-SOV")
    ).first()

    inv, _ = InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=str(uuid.uuid4()),
        product_id=product.id,
        source_account_id=funded_customer_account.id,
        amount=Decimal("25000.00"),
    )

    # Customer B (sample_user) cannot view Customer A's investment
    cust_b_headers = auth_headers_factory(sample_user)
    resp_b = client.get(f"/api/v1/investments/{inv.id}", headers=cust_b_headers)
    assert resp_b.status_code == 404

    # Staff user can inspect Customer A's investment
    staff_headers = auth_headers_factory(test_staff_user)
    resp_staff = client.get(f"/api/v1/investments/{inv.id}", headers=staff_headers)
    assert resp_staff.status_code == 200
    assert resp_staff.json()["id"] == str(inv.id)


def test_forced_failure_investment_atomic_rollback(raw_db_session, monkeypatch):
    """Verify forced failure during investment purchase rolls back investment, ledger, and balances together."""
    user = User(
        username=f"force_fail_user_{uuid.uuid4().hex[:6]}",
        email=f"force_fail_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="$2b$12$samplepasswordhashforspeed",
        role="CUSTOMER",
        is_active=True,
    )
    raw_db_session.add(user)
    raw_db_session.commit()

    customer = Customer(
        user_id=user.id,
        full_name="Forced Failure Customer",
        phone="+919876543210",
        pan_number=f"FAIL{uuid.uuid4().hex[:6].upper()}",
        kyc_status="VERIFIED",
    )
    raw_db_session.add(customer)
    raw_db_session.commit()

    src_acc = Account(
        customer_id=customer.id,
        account_number=f"INR-FAIL-SRC-{uuid.uuid4().hex[:6].upper()}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    raw_db_session.add(src_acc)
    raw_db_session.commit()

    initial_deposit = Decimal("50000.00")
    AccountService.deposit_opening_funds(
        db=raw_db_session,
        account_id=src_acc.id,
        amount=initial_deposit,
        description="Fund forced failure test",
        actor_user_id=user.id,
    )
    raw_db_session.commit()

    product = raw_db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()
    assert product is not None

    idempotency_key = str(uuid.uuid4())
    src_id = src_acc.id
    invest_amount = Decimal("20000.00")

    # Intercept db.commit on raw_db_session to force failure right at transaction commit
    original_commit = raw_db_session.commit

    def simulated_failing_commit():
        raise RuntimeError("Simulated database failure during investment commit")

    monkeypatch.setattr(raw_db_session, "commit", simulated_failing_commit)

    with pytest.raises(TransferBusinessError) as exc_info:
        InvestmentService.purchase_investment(
            db=raw_db_session,
            caller_user_id=user.id,
            idempotency_key=idempotency_key,
            product_id=product.id,
            source_account_id=src_id,
            amount=invest_amount,
        )

    # Internal exception text must never reach the client (AGENTS.md §4.3)
    assert exc_info.value.status_code == 500
    assert "Simulated database failure" not in str(exc_info.value)

    # Restore commit for verification
    monkeypatch.setattr(raw_db_session, "commit", original_commit)

    # Re-fetch from fresh state to verify all financial state rolled back together
    fresh_src = raw_db_session.get(Account, src_id)
    assert fresh_src.cached_balance == initial_deposit

    # Verify derived ledger balance remains initial_deposit
    derived = LedgerService.get_derived_balance(raw_db_session, src_id)
    assert derived == initial_deposit

    # Verify zero investment records were committed
    investments_count = raw_db_session.scalar(
        select(func.count(Investment.id)).where(Investment.customer_id == customer.id)
    )
    assert investments_count == 0

    # Verify zero INVESTMENT_PURCHASE ledger transactions or entries were committed for this source account
    txns_count = raw_db_session.scalar(
        select(func.count(LedgerTransaction.id))
        .join(TransferRequest, LedgerTransaction.transfer_request_id == TransferRequest.id)
        .where(
            TransferRequest.source_account_id == src_id,
            LedgerTransaction.transaction_type == "INVESTMENT_PURCHASE",
        )
    )
    assert txns_count == 0

    # Verify zero debit ledger entries were posted to this source account
    debits_count = raw_db_session.scalar(
        select(func.count(LedgerEntry.id)).where(
            LedgerEntry.account_id == src_id,
            LedgerEntry.entry_type == "DEBIT",
        )
    )
    assert debits_count == 0

    # Verify failure audit record was persisted independently
    failed_audit = raw_db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "INVESTMENT_PURCHASE_FAILED",
            AuditLog.entity_id == idempotency_key,
        )
    ).first()
    assert failed_audit is not None
