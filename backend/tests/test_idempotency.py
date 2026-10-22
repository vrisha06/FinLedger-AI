"""Integration tests for Scoped Idempotency in FinLedger-AI.

Verifies:
- Replaying an identical request returns the original result without duplicate postings
- Reusing an idempotency key with differing financial payload yields HTTP 409 Conflict
- Scoped uniqueness prevents collision across different customer users
"""

from decimal import Decimal
import uuid
from sqlalchemy import select

from app.models.account import Account
from app.models.transfer import TransferRequest


def test_idempotent_replay_returns_cached_result(client, auth_headers_factory, test_customer_user, sample_dest_account, db_session):
    """Verify replaying identical transfer request returns 200 OK and duplicates zero ledger activity."""
    src_account = Account(
        customer_id=test_customer_user.customer.id,
        account_number="INR-IDEM-001",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("50000.00"),
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
        "amount": "1000.00",
        "currency": "INR",
        "memo": "Idempotent replay test",
    }

    # First call -> 201 Created
    res1 = client.post("/api/v1/transfers", json=payload, headers=headers)
    assert res1.status_code == 201
    transfer_id1 = res1.json()["id"]

    db_session.refresh(src_account)
    balance_after_first = src_account.cached_balance
    assert balance_after_first == Decimal("49000.00")

    # Second call (replay) -> 200 OK
    res2 = client.post("/api/v1/transfers", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["id"] == transfer_id1

    # Verify no second debit occurred
    db_session.refresh(src_account)
    assert src_account.cached_balance == balance_after_first

    # Verify only 1 TransferRequest row exists
    stmt = select(TransferRequest).where(
        TransferRequest.source_user_id == test_customer_user.id,
        TransferRequest.idempotency_key == idempotency_key,
    )
    requests = list(db_session.scalars(stmt).all())
    assert len(requests) == 1


def test_idempotency_payload_mismatch_conflict(client, auth_headers_factory, test_customer_user, sample_dest_account, db_session):
    """Verify altering transfer amount under the same idempotency key raises HTTP 409 Conflict."""
    src_account = Account(
        customer_id=test_customer_user.customer.id,
        account_number="INR-IDEM-002",
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

    payload_initial = {
        "source_account_id": str(src_account.id),
        "destination_account_id": str(sample_dest_account.id),
        "amount": "2000.00",
        "currency": "INR",
    }

    res1 = client.post("/api/v1/transfers", json=payload_initial, headers=headers)
    assert res1.status_code == 201

    # Second call with materially different amount (₹5,000 instead of ₹2,000)
    payload_altered = {
        "source_account_id": str(src_account.id),
        "destination_account_id": str(sample_dest_account.id),
        "amount": "5000.00",
        "currency": "INR",
    }

    res2 = client.post("/api/v1/transfers", json=payload_altered, headers=headers)
    assert res2.status_code == 409
    assert "conflict" in res2.json()["detail"].lower()

    # Balance must reflect only the first ₹2,000 transfer
    db_session.refresh(src_account)
    assert src_account.cached_balance == Decimal("18000.00")
