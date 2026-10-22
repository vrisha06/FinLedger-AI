"""Tests for LedgerGraph Temporal Money-Flow Analysis (Innovation A)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.graph import GraphFinding
from app.services.ledger_graph_service import LedgerGraphService

client = TestClient(app)


def test_ledger_graph_fan_in_detection(db_session, test_staff_user):
    """Test deterministic detection of Fan-In pooling topology."""
    dest_acc = Account(account_number="ACC-HUB-FANIN-01", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add(dest_acc)

    sources = [
        Account(account_number=f"ACC-SRC-FANIN-{i}", account_type="SAVINGS", currency="INR", cached_balance=Decimal("50000.00"), status="ACTIVE")
        for i in range(3)
    ]
    for s in sources:
        db_session.add(s)
    db_session.commit()

    now = datetime.now(timezone.utc)

    txns = []
    for i, s in enumerate(sources):
        t = TransferRequest(
            idempotency_key=f"idemp-fanin-{i}-{uuid.uuid4()}",
            source_user_id=test_staff_user.id,
            request_hash=f"hash-fanin-{i}",
            source_account_id=s.id,
            destination_account_id=dest_acc.id,
            amount=Decimal("15000.00"),
            currency="INR",
            status="POSTED",
            created_at=now - timedelta(minutes=30 - i * 5),
            posted_at=now - timedelta(minutes=30 - i * 5),
        )
        db_session.add(t)
        txns.append(t)
    db_session.commit()

    findings = LedgerGraphService.analyze_transaction(
        db=db_session,
        transfer_request_id=txns[-1].id,
        as_of_time=now,
        persist=True,
    )

    pattern_types = [f.pattern_type for f in findings]
    assert "FAN_IN" in pattern_types

    fan_in = next(f for f in findings if f.pattern_type == "FAN_IN")
    assert fan_in.primary_account_id == dest_acc.id
    assert fan_in.heuristic_score >= Decimal("0.6000")
    assert fan_in.evidence["in_degree"] == 3
    assert str(txns[0].id) in fan_in.involved_transfer_ids


def test_ledger_graph_rapid_pass_through_detection(db_session, test_staff_user):
    """Test deterministic detection of Rapid Pass-Through mule forwarding."""
    acc_a = Account(account_number="ACC-PASS-A", account_type="SAVINGS", currency="INR", cached_balance=Decimal("50000.00"), status="ACTIVE")
    acc_mule = Account(account_number="ACC-PASS-MULE", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    acc_c = Account(account_number="ACC-PASS-C", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add_all([acc_a, acc_mule, acc_c])
    db_session.commit()

    t0 = datetime.now(timezone.utc) - timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=7)

    tx_in = TransferRequest(
        idempotency_key=f"idemp-in-{uuid.uuid4()}",
        source_user_id=test_staff_user.id,
        request_hash="hash-in",
        source_account_id=acc_a.id,
        destination_account_id=acc_mule.id,
        amount=Decimal("40000.00"),
        currency="INR",
        status="POSTED",
        created_at=t0,
        posted_at=t0,
    )
    tx_out = TransferRequest(
        idempotency_key=f"idemp-out-{uuid.uuid4()}",
        source_user_id=test_staff_user.id,
        request_hash="hash-out",
        source_account_id=acc_mule.id,
        destination_account_id=acc_c.id,
        amount=Decimal("38000.00"),
        currency="INR",
        status="POSTED",
        created_at=t1,
        posted_at=t1,
    )
    db_session.add_all([tx_in, tx_out])
    db_session.commit()

    findings = LedgerGraphService.analyze_transaction(
        db=db_session,
        transfer_request_id=tx_out.id,
        as_of_time=t1,
        persist=True,
    )

    pattern_types = [f.pattern_type for f in findings]
    assert "RAPID_PASS_THROUGH" in pattern_types

    pass_through = next(f for f in findings if f.pattern_type == "RAPID_PASS_THROUGH")
    assert pass_through.primary_account_id == acc_mule.id
    assert pass_through.severity in ("HIGH", "CRITICAL")
    assert float(pass_through.evidence["pass_through_ratio"]) >= 0.90


def test_ledger_graph_temporal_leakage_prevention(db_session, test_staff_user):
    """Ensure that future transfers occurring AFTER as_of_time are never included in graph findings."""
    acc_x = Account(account_number="ACC-LEAK-X", account_type="SAVINGS", currency="INR", cached_balance=Decimal("10000.00"), status="ACTIVE")
    acc_y = Account(account_number="ACC-LEAK-Y", account_type="SAVINGS", currency="INR", cached_balance=Decimal("0.00"), status="ACTIVE")
    db_session.add_all([acc_x, acc_y])
    db_session.commit()

    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)

    tx_past = TransferRequest(
        idempotency_key=f"idemp-past-{uuid.uuid4()}",
        source_user_id=test_staff_user.id,
        request_hash="hash-past",
        source_account_id=acc_x.id,
        destination_account_id=acc_y.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status="POSTED",
        created_at=past_time,
        posted_at=past_time,
    )
    tx_future = TransferRequest(
        idempotency_key=f"idemp-fut-{uuid.uuid4()}",
        source_user_id=test_staff_user.id,
        request_hash="hash-fut",
        source_account_id=acc_y.id,
        destination_account_id=acc_x.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status="POSTED",
        created_at=future_time,
        posted_at=future_time,
    )
    db_session.add_all([tx_past, tx_future])
    db_session.commit()

    # Score past transaction with cutoff as past_time
    findings = LedgerGraphService.analyze_transaction(
        db=db_session,
        transfer_request_id=tx_past.id,
        as_of_time=past_time,
        persist=False,
    )

    # Future edge must NOT leak into the evaluation of tx_past!
    pattern_types = [f.pattern_type for f in findings]
    assert "CIRCULAR_FLOW" not in pattern_types
