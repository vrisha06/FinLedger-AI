"""Integration tests for Financial Reporting and Analytics APIs.

Verifies:
- Customer financial summary with balances, net worth, and transfer aggregates
- Staff inspection of customer financial standing
- Staff-only access to catalogue performance and subscription volume metrics
- Daily transactional and investment volume trends
- Account balance tier distribution reporting
- Strict RBAC enforcement: Customer access blocked on staff reporting routes
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.product import FinancialProduct
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService


@pytest.fixture
def populated_customer_data(db_session, test_customer_user, clearing_account):
    """Sets up a customer with savings, an investment, and posted transfers."""
    customer = test_customer_user.customer

    # 1. Savings account funded with ₹50,000.00
    sav_acc = Account(
        customer_id=customer.id,
        account_number=f"INR-SAV-{uuid.uuid4().hex[:6].upper()}",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(sav_acc)
    db_session.commit()

    AccountService.deposit_opening_funds(
        db=db_session,
        account_id=sav_acc.id,
        amount=Decimal("50000.00"),
        description="Opening deposit for reporting test",
        actor_user_id=test_customer_user.id,
    )

    # 2. Purchase an investment of ₹10,000.00
    product = db_session.scalars(
        select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    ).first()

    InvestmentService.purchase_investment(
        db=db_session,
        caller_user_id=test_customer_user.id,
        idempotency_key=str(uuid.uuid4()),
        product_id=product.id,
        source_account_id=sav_acc.id,
        amount=Decimal("10000.00"),
    )

    return customer, sav_acc


def test_customer_financial_summary_self(
    client,
    auth_headers_factory,
    test_customer_user,
    populated_customer_data,
    db_session,
):
    """Verify customer can view their aggregated financial profile."""
    headers = auth_headers_factory(test_customer_user)
    response = client.get("/api/v1/reports/customer-summary", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["customer_id"] == str(test_customer_user.customer.id)
    assert data["accounts_count"] >= 2  # savings + investment holding account
    assert Decimal(str(data["total_savings_balance"])) == Decimal("40000.00")
    assert Decimal(str(data["total_invested_balance"])) == Decimal("10000.00")
    assert Decimal(str(data["total_net_worth"])) == Decimal("50000.00")
    assert data["active_investments_count"] >= 1


def test_customer_financial_summary_staff_inspection(
    client,
    auth_headers_factory,
    test_staff_user,
    test_customer_user,
    populated_customer_data,
    db_session,
):
    """Verify staff can inspect any customer's financial summary."""
    headers = auth_headers_factory(test_staff_user)
    customer = test_customer_user.customer

    response = client.get(
        f"/api/v1/reports/customer-summary?customer_id={customer.id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == str(customer.id)
    assert Decimal(str(data["total_net_worth"])) == Decimal("50000.00")


def test_customer_financial_summary_staff_missing_param(
    client,
    auth_headers_factory,
    test_staff_user,
    db_session,
):
    """Verify staff requesting summary without customer_id receives 400 Bad Request."""
    headers = auth_headers_factory(test_staff_user)
    response = client.get("/api/v1/reports/customer-summary", headers=headers)
    assert response.status_code == 400
    assert "customer_id" in response.json()["detail"].lower()


def test_products_summary_staff(
    client,
    auth_headers_factory,
    test_staff_user,
    populated_customer_data,
    db_session,
):
    """Verify staff can access product catalogue performance report."""
    headers = auth_headers_factory(test_staff_user)
    response = client.get("/api/v1/reports/products-summary", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total_products_count"] >= 4
    assert Decimal(str(data["total_system_invested_volume"])) >= Decimal("10000.00")

    products = data["products"]
    fd_prod = next(p for p in products if p["code"] == "FD-12M-STD")
    assert fd_prod["active_subscriptions"] >= 1


def test_products_summary_customer_forbidden(
    client,
    auth_headers_factory,
    test_customer_user,
    db_session,
):
    """Verify customer cannot access staff product performance report."""
    headers = auth_headers_factory(test_customer_user)
    response = client.get("/api/v1/reports/products-summary", headers=headers)
    assert response.status_code == 403


def test_daily_volume_staff(
    client,
    auth_headers_factory,
    test_staff_user,
    populated_customer_data,
    db_session,
):
    """Verify staff can access daily activity metrics over sliding date window."""
    headers = auth_headers_factory(test_staff_user)
    response = client.get("/api/v1/reports/daily-volume?days=7", headers=headers)
    assert response.status_code == 200

    data = response.json()
    records = data["daily_records"]
    assert len(records) == 8  # 7 days + current day
    # Check that investment volume is captured
    total_vol = sum(Decimal(str(r["total_day_volume"])) for r in records)
    assert total_vol >= Decimal("10000.00")


def test_daily_volume_customer_forbidden(
    client,
    auth_headers_factory,
    test_customer_user,
    db_session,
):
    """Verify customer cannot access daily volume analytics."""
    headers = auth_headers_factory(test_customer_user)
    response = client.get("/api/v1/reports/daily-volume", headers=headers)
    assert response.status_code == 403


def test_balance_distribution_staff(
    client,
    auth_headers_factory,
    test_staff_user,
    populated_customer_data,
    db_session,
):
    """Verify staff can inspect account balance tier distribution."""
    headers = auth_headers_factory(test_staff_user)
    response = client.get("/api/v1/reports/balance-distribution", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total_accounts"] >= 3
    # Customer liabilities must equal 50000 (40000 savings + 10000 investment)
    assert Decimal(str(data["total_customer_liabilities"])) >= Decimal("50000.00")
    # Clearing balance is negative equal to total liabilities created via opening deposit
    assert Decimal(str(data["system_clearing_balance"])) <= Decimal("-50000.00")


def test_balance_distribution_customer_forbidden(
    client,
    auth_headers_factory,
    test_customer_user,
    db_session,
):
    """Verify customer cannot access system-wide balance distribution metrics."""
    headers = auth_headers_factory(test_customer_user)
    response = client.get("/api/v1/reports/balance-distribution", headers=headers)
    assert response.status_code == 403
