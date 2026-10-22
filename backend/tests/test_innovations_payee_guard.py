"""Tests for PayeeGuard Pre-Transfer Recipient Verification (Innovation B)."""

from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.account import Account
from app.models.customer import Customer
from app.models.user import User

def test_payee_guard_preview_success(client, db_session, sample_user, sample_customer, sample_account, auth_headers_factory):
    """Test successful PayeeGuard recipient preview displaying legal beneficiary name."""
    headers = auth_headers_factory(sample_user)

    # Create a destination account with a customer profile
    dest_user = User(username="payee_recipient_01", email="payee01@finledger.io", password_hash="x", role="CUSTOMER")
    db_session.add(dest_user)
    db_session.flush()

    dest_cust = Customer(user_id=dest_user.id, full_name="Aarav Sharma", kyc_status="VERIFIED")
    db_session.add(dest_cust)
    db_session.flush()

    dest_acc = Account(
        customer_id=dest_cust.id,
        account_number="ACC-SAV-998877",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("1000.00"),
        status="ACTIVE",
    )
    db_session.add(dest_acc)
    db_session.commit()

    # Request PayeeGuard preview
    payload = {
        "source_account_id": str(sample_account.id),
        "destination_account_id": str(dest_acc.id),
        "amount": "5000.00",
    }
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["source_account_id"] == str(sample_account.id)
    assert data["destination_account_id"] == str(dest_acc.id)
    assert data["recipient_legal_name"] == "Aarav Sharma"
    assert "••••" in data["masked_account_number"]
    assert data["is_first_time_recipient"] is True
    assert data["validation_status"] == "VERIFIED_ELIGIBLE"
    assert len(data["advisory_warnings"]) >= 1
    assert "First-Time Recipient" in data["advisory_warnings"][0]


def test_payee_guard_ownership_enforcement(client, db_session, sample_user, sample_account, auth_headers_factory):
    """Ensure a user cannot preview using an account they do not own."""
    headers = auth_headers_factory(sample_user)

    # Create an un-owned third party account
    other_user = User(username="other_usr_pg", email="other_pg@finledger.io", password_hash="x", role="CUSTOMER")
    db_session.add(other_user)
    db_session.flush()
    other_cust = Customer(user_id=other_user.id, full_name="Other User", kyc_status="VERIFIED")
    db_session.add(other_cust)
    db_session.flush()
    other_acc = Account(
        customer_id=other_cust.id,
        account_number="ACC-SAV-112233",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("50000.00"),
        status="ACTIVE",
    )
    db_session.add(other_acc)
    db_session.commit()

    payload = {
        "source_account_id": str(other_acc.id),  # Not caller's account
        "destination_account_id": str(sample_account.id),
        "amount": "1000.00",
    }
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "do not own" in resp.json()["detail"].lower()


def test_payee_guard_insufficient_funds_rejection(client, db_session, sample_user, sample_account, auth_headers_factory):
    """Ensure preview fails if source balance is insufficient."""
    headers = auth_headers_factory(sample_user)

    dest_acc = Account(
        account_number="ACC-SAV-554433",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
    )
    db_session.add(dest_acc)
    db_session.commit()

    payload = {
        "source_account_id": str(sample_account.id),
        "destination_account_id": str(dest_acc.id),
        "amount": "9999999.00",  # Far exceeds balance
    }
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "insufficient funds" in resp.json()["detail"].lower()


def test_payee_guard_preview_resolves_account_number(client, db_session, sample_user, sample_customer, sample_account, auth_headers_factory):
    """Customers know account numbers, not UUIDs: preview resolves the number to the authoritative account ID."""
    dest_user = User(username="payee_by_number", email="payee_num@finledger.io", password_hash="x", role="CUSTOMER")
    db_session.add(dest_user)
    db_session.flush()
    dest_cust = Customer(user_id=dest_user.id, full_name="Meera Iyer", kyc_status="VERIFIED")
    db_session.add(dest_cust)
    db_session.flush()
    dest_acc = Account(
        customer_id=dest_cust.id,
        account_number="INR-SAV-NUM12345",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
    )
    db_session.add(dest_acc)
    db_session.commit()

    payload = {
        "source_account_id": str(sample_account.id),
        "destination_account_number": " inr-sav-num12345 ",
        "amount": "100.00",
    }
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=auth_headers_factory(sample_user))
    assert resp.status_code == 200, resp.text
    assert resp.json()["destination_account_id"] == str(dest_acc.id)
    assert resp.json()["recipient_legal_name"] == "Meera Iyer"


def test_payee_guard_preview_requires_exactly_one_destination(client, sample_user, sample_account, auth_headers_factory):
    payload = {"source_account_id": str(sample_account.id), "amount": "100.00"}
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=auth_headers_factory(sample_user))
    assert resp.status_code == 422


def test_payee_guard_preview_rejects_investment_holding_destination(client, db_session, sample_user, sample_customer, sample_account, auth_headers_factory):
    inv_acc = Account(
        customer_id=sample_customer.id,
        account_number="INR-INV-PREVIEW1",
        account_type="INVESTMENT",
        currency="INR",
        cached_balance=Decimal("0.00"),
        status="ACTIVE",
    )
    db_session.add(inv_acc)
    db_session.commit()
    payload = {
        "source_account_id": str(sample_account.id),
        "destination_account_id": str(inv_acc.id),
        "amount": "100.00",
    }
    resp = client.post("/api/v1/transfers/preview", json=payload, headers=auth_headers_factory(sample_user))
    assert resp.status_code == 400
