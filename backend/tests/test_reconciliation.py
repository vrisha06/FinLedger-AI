"""Integration tests for System-Wide Ledger Reconciliation in FinLedger-AI.

Verifies:
- Reconciliation reports zero discrepancies after simulated deposit and transfer
- Deliberately introduced cache balance tampering is accurately detected and measured
- Staff-only access control on /api/v1/audit/reconciliation endpoint
"""

from decimal import Decimal
import uuid

from app.models.account import Account
from app.services.ledger_service import LedgerService


def test_reconciliation_post_deposit_and_transfer(db_session, clearing_account):
    """Verify reconciliation reports zero discrepancies after simulated deposit and transfer."""
    from app.models.user import User
    from app.models.customer import Customer
    from app.services.account_service import AccountService
    from app.services.transfer_service import TransferService

    # 1. Provision isolated synthetic customer
    user = User(
        username=f"recon_cust_{uuid.uuid4().hex[:8]}",
        email=f"recon_cust_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$2b$12$samplepasswordhashforreconciliation",
        role="CUSTOMER",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    customer = Customer(
        user_id=user.id,
        full_name="Reconciliation Test Customer",
        kyc_status="VERIFIED",
    )
    db_session.add(customer)
    db_session.flush()

    # 2. Provision two fresh accounts with exact 0.00 initial balance
    src_account = Account(
        customer_id=customer.id,
        account_number=f"INR-RECON-SRC-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    dst_account = Account(
        customer_id=customer.id,
        account_number=f"INR-RECON-DST-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add_all([src_account, dst_account])
    db_session.commit()

    # 3. Perform simulated opening deposit from clearing account
    deposit_amount = Decimal("25000.00")
    deposited_account = AccountService.deposit_opening_funds(
        db=db_session,
        account_id=src_account.id,
        amount=deposit_amount,
        description="Opening deposit for reconciliation test",
        actor_user_id=user.id,
    )
    assert deposited_account.cached_balance == Decimal("25000.00")

    # 4. Perform transfer between customer accounts
    transfer_amount = Decimal("7500.00")
    transfer_req, is_replay = TransferService.execute_transfer(
        db=db_session,
        caller_user_id=user.id,
        idempotency_key=str(uuid.uuid4()),
        source_account_id=src_account.id,
        destination_account_id=dst_account.id,
        amount=transfer_amount,
        currency="INR",
        memo="Transfer for reconciliation test",
    )
    assert is_replay is False
    assert transfer_req.status == "POSTED"

    db_session.refresh(src_account)
    db_session.refresh(dst_account)
    assert src_account.cached_balance == Decimal("17500.00")
    assert dst_account.cached_balance == Decimal("7500.00")

    # 5. Verify individual derived balances match cached balances
    src_derived = LedgerService.get_derived_balance(db_session, src_account.id)
    dst_derived = LedgerService.get_derived_balance(db_session, dst_account.id)
    assert src_derived == Decimal("17500.00") == src_account.cached_balance
    assert dst_derived == Decimal("7500.00") == dst_account.cached_balance

    # 6. Verify reconciliation reports zero discrepancies for the affected accounts
    report = LedgerService.reconcile_accounts(
        db=db_session,
        account_ids=[src_account.id, dst_account.id],
    )
    assert report.total_accounts_checked == 2
    assert report.discrepancy_count == 0
    assert len(report.discrepancies) == 0
    assert report.is_balanced is True


def test_reconciliation_detects_deliberate_discrepancy(db_session, sample_customer):
    """Verify reconciliation detects an intentionally desynchronized cached balance."""
    # Create test account with matched cached balance and zero ledger entries
    tampered_acc = Account(
        customer_id=sample_customer.id,
        account_number=f"INR-DISCREP-{uuid.uuid4().hex[:6]}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(tampered_acc)
    db_session.flush()

    # Tamper with cached balance directly without creating ledger entries
    tampered_acc.cached_balance = Decimal("1234.56")
    db_session.flush()

    report = LedgerService.reconcile_all_accounts(db_session)

    # Must detect discrepancy
    assert report.is_balanced is False
    assert report.discrepancy_count >= 1

    discrepant_item = next(d for d in report.discrepancies if d.account_id == tampered_acc.id)
    assert discrepant_item.cached_balance == Decimal("1234.56")
    assert discrepant_item.derived_balance == Decimal("0.00")
    assert discrepant_item.discrepancy == Decimal("1234.56")


def test_reconciliation_api_rbac(client, auth_headers_factory, test_staff_user, test_customer_user):
    """Verify /api/v1/audit/reconciliation requires STAFF or ADMIN role."""
    # Staff access -> 200 OK
    staff_headers = auth_headers_factory(test_staff_user)
    staff_res = client.get("/api/v1/audit/reconciliation", headers=staff_headers)
    assert staff_res.status_code == 200
    data = staff_res.json()
    assert "is_balanced" in data
    assert "total_accounts_checked" in data

    # Customer access -> 403 Forbidden
    cust_headers = auth_headers_factory(test_customer_user)
    cust_res = client.get("/api/v1/audit/reconciliation", headers=cust_headers)
    assert cust_res.status_code == 403

    # Unauthenticated access -> 401 Unauthorized
    anon_res = client.get("/api/v1/audit/reconciliation")
    assert anon_res.status_code == 401
