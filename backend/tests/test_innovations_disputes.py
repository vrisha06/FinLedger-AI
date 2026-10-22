"""Tests for Customer Recourse Workflow & Forensic Case Events (Innovation C)."""

from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.dispute import Dispute, CaseEvent
from app.models.user import User


def test_customer_recourse_dispute_lifecycle(client, db_session, sample_user, sample_customer, sample_account, test_staff_user, auth_headers_factory):
    """Test full recourse dispute lifecycle from submission to staff investigation and resolution."""
    headers = auth_headers_factory(sample_user)

    dest_acc = Account(account_number="ACC-DISPUTE-DEST", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add(dest_acc)
    db_session.commit()

    # Create a posted transfer initiated by customer
    transfer = TransferRequest(
        idempotency_key=f"idemp-disp-{uuid.uuid4()}",
        source_user_id=sample_user.id,
        request_hash="hash-disp",
        source_account_id=sample_account.id,
        destination_account_id=dest_acc.id,
        amount=Decimal("4500.00"),
        currency="INR",
        status="POSTED",
    )
    db_session.add(transfer)
    db_session.commit()

    # Step 1: Customer files dispute
    create_payload = {
        "transfer_request_id": str(transfer.id),
        "category": "UNAUTHORIZED",
        "description": "I did not authorize this transfer from my savings account.",
    }
    resp = client.post("/api/v1/disputes", json=create_payload, headers=headers)
    assert resp.status_code == 201
    dispute_data = resp.json()

    dispute_id = dispute_data["id"]
    assert dispute_data["status"] == "OPEN"
    assert dispute_data["category"] == "UNAUTHORIZED"
    assert len(dispute_data["events"]) == 1
    assert dispute_data["events"][0]["event_type"] == "DISPUTE_OPENED"

    # Step 2: Customer views their disputes
    list_resp = client.get("/api/v1/disputes", headers=headers)
    assert list_resp.status_code == 200
    assert any(d["id"] == dispute_id for d in list_resp.json())

    # Step 3: Staff updates status to INVESTIGATING
    staff_headers = auth_headers_factory(test_staff_user)

    status_payload = {
        "status": "INVESTIGATING",
        "notes": "Reviewed IP address and session records; contacting acquiring bank.",
    }
    patch_resp = client.post(f"/api/v1/disputes/{dispute_id}/status", json=status_payload, headers=staff_headers)
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["status"] == "INVESTIGATING"
    assert len(updated_data["events"]) == 2
    assert updated_data["events"][1]["event_type"] == "STATUS_CHANGE"
    assert updated_data["events"][1]["to_status"] == "INVESTIGATING"

    # Step 4: Customer adds a clarification note
    note_payload = {
        "notes": "I was traveling during the transaction timestamp and can provide ticket proof.",
    }
    note_resp = client.post(f"/api/v1/disputes/{dispute_id}/note", json=note_payload, headers=headers)
    assert note_resp.status_code == 200
    with_note = note_resp.json()
    assert len(with_note["events"]) == 3
    assert with_note["events"][2]["event_type"] == "CUSTOMER_RESPONSE"

    # Step 5: Staff resolves dispute
    resolve_payload = {
        "status": "RESOLVED",
        "notes": "Claim verified. Incident documented for regulatory compliance reporting.",
    }
    resolve_resp = client.post(f"/api/v1/disputes/{dispute_id}/status", json=resolve_payload, headers=staff_headers)
    assert resolve_resp.status_code == 200
    resolved = resolve_resp.json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None
    assert len(resolved["events"]) == 4
    assert resolved["events"][3]["event_type"] == "RESOLVED"


def test_customer_cannot_dispute_unrelated_transfer(client, db_session, sample_user, sample_customer, auth_headers_factory):
    """Ensure a customer cannot file a dispute on another customer's transfer."""
    headers = auth_headers_factory(sample_user)

    # Third party user and transfer
    tp_user = User(username="other_tp_user", email="othertp@finledger.io", password_hash="x", role="CUSTOMER")
    db_session.add(tp_user)
    db_session.flush()

    other_user = Account(account_number="ACC-X1-DISP", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    other_dest = Account(account_number="ACC-X2-DISP", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add_all([other_user, other_dest])
    db_session.commit()

    third_party_transfer = TransferRequest(
        idempotency_key=f"idemp-tp-{uuid.uuid4()}",
        source_user_id=tp_user.id,
        request_hash="hash-tp",
        source_account_id=other_user.id,
        destination_account_id=other_dest.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status="POSTED",
    )
    db_session.add(third_party_transfer)
    db_session.commit()

    payload = {
        "transfer_request_id": str(third_party_transfer.id),
        "category": "UNAUTHORIZED",
        "description": "Attempting to dispute someone else's transfer.",
    }
    resp = client.post("/api/v1/disputes", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "own transfers" in resp.json()["detail"].lower()
