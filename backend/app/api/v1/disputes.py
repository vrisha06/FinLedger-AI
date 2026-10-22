"""Dispute & Customer Recourse API Endpoints for FinLedger-AI."""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, desc

from app.api.deps import get_db, get_current_user, require_staff
from app.models.user import User
from app.models.account import Account
from app.models.transfer import TransferRequest
from app.models.dispute import Dispute, CaseEvent
from app.models.audit import AuditLog
from app.schemas.dispute import (
    DisputeCreateRequest,
    DisputeResponse,
    DisputeStatusUpdateRequest,
    DisputeAddNoteRequest,
)

router = APIRouter(prefix="/disputes", tags=["Customer Recourse & Disputes"])


@router.post(
    "",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer recourse dispute on a financial transfer",
)
def create_dispute(
    data: DisputeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Customer initiates a dispute inquiry on an executed transfer."""
    if not current_user.customer and current_user.role not in ("STAFF", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user lacks customer profile",
        )

    # 1. Fetch transfer and verify ownership
    transfer = db.get(TransferRequest, data.transfer_request_id)
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer record not found",
        )

    if current_user.customer:
        customer_id = current_user.customer.id
    else:
        # Staff filing on a customer's behalf: the disputing customer owns the debited (or credited) account
        party_accounts = [db.get(Account, transfer.source_account_id), db.get(Account, transfer.destination_account_id)]
        customer_id = next((acc.customer_id for acc in party_accounts if acc and acc.customer_id), None)
        if customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer has no customer-owned account to attach a dispute to",
            )

    if current_user.role not in ("STAFF", "ADMIN"):
        # Verify customer initiated this transfer or owns the source/destination account
        user_account_ids = {
            acc.id for acc in db.scalars(select(Account).where(Account.customer_id == customer_id)).all()
        }
        is_initiator = transfer.source_user_id == current_user.id
        is_party = (transfer.source_account_id in user_account_ids or transfer.destination_account_id in user_account_ids)
        if not (is_initiator or is_party):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only file a dispute on your own transfers",
            )

    # Check for existing open dispute on this transfer
    existing = db.scalars(
        select(Dispute).where(
            and_(
                Dispute.transfer_request_id == data.transfer_request_id,
                Dispute.status.in_(["OPEN", "INVESTIGATING"]),
            )
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active dispute is already in progress for this transaction",
        )

    # 2. Create Dispute
    dispute = Dispute(
        customer_id=customer_id,
        transfer_request_id=data.transfer_request_id,
        category=data.category,
        description=data.description,
        status="OPEN",
    )
    db.add(dispute)
    db.flush()

    # 3. Create initial CaseEvent
    initial_event = CaseEvent(
        dispute_id=dispute.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        event_type="DISPUTE_OPENED",
        from_status=None,
        to_status="OPEN",
        notes=f"Dispute opened under category '{data.category}'. Description: {data.description}",
        metadata_snapshot={
            "transfer_id": str(data.transfer_request_id),
            "amount": str(transfer.amount),
            "currency": transfer.currency,
        },
    )
    db.add(initial_event)

    # 4. Record audit log
    audit = AuditLog(
        action="DISPUTE_CREATED",
        entity_type="DISPUTE",
        entity_id=str(dispute.id),
        actor_user_id=current_user.id,
        metadata_json={
            "dispute_id": str(dispute.id),
            "transfer_id": str(data.transfer_request_id),
            "category": data.category,
        },
    )
    db.add(audit)
    db.commit()

    # Refresh with events eager-loaded
    stmt = select(Dispute).where(Dispute.id == dispute.id).options(joinedload(Dispute.events))
    return db.scalars(stmt).unique().first()


@router.get(
    "",
    response_model=List[DisputeResponse],
    summary="List recourse disputes",
)
def list_disputes(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve customer disputes. Customers see only their own; staff sees all."""
    stmt = select(Dispute).options(joinedload(Dispute.events))

    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer:
            return []
        stmt = stmt.where(Dispute.customer_id == current_user.customer.id)
    elif status_filter:
        stmt = stmt.where(Dispute.status == status_filter)

    stmt = stmt.order_by(Dispute.created_at.desc())
    return list(db.scalars(stmt).unique().all())


@router.get(
    "/{dispute_id}",
    response_model=DisputeResponse,
    summary="Get dispute details and timeline by ID",
)
def get_dispute(
    dispute_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve specific dispute and its append-only event timeline."""
    stmt = select(Dispute).where(Dispute.id == dispute_id).options(joinedload(Dispute.events))
    dispute = db.scalars(stmt).unique().first()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer or dispute.customer_id != current_user.customer.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: You cannot inspect another customer's dispute")

    return dispute


@router.post(
    "/{dispute_id}/status",
    response_model=DisputeResponse,
    summary="Update dispute status with staff determination",
)
def update_dispute_status(
    dispute_id: uuid.UUID,
    data: DisputeStatusUpdateRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff updates investigation status with required explanatory notes."""

    stmt = select(Dispute).where(Dispute.id == dispute_id).options(joinedload(Dispute.events))
    dispute = db.scalars(stmt).unique().first()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    old_status = dispute.status
    dispute.status = data.status
    dispute.assigned_staff_id = current_user.id
    if data.status in ("RESOLVED", "REJECTED"):
        dispute.resolved_at = datetime.now(timezone.utc)
        dispute.resolution_notes = data.notes

    event_type = "RESOLVED" if data.status == "RESOLVED" else "REJECTED" if data.status == "REJECTED" else "STATUS_CHANGE"

    # Append-only CaseEvent
    case_event = CaseEvent(
        dispute_id=dispute.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        event_type=event_type,
        from_status=old_status,
        to_status=data.status,
        notes=data.notes,
        metadata_snapshot={
            "previous_status": old_status,
            "new_status": data.status,
            "staff_id": str(current_user.id),
        },
    )
    db.add(case_event)

    # Record AuditLog
    audit = AuditLog(
        action=f"DISPUTE_{data.status}",
        entity_type="DISPUTE",
        entity_id=str(dispute.id),
        actor_user_id=current_user.id,
        metadata_json={
            "from_status": old_status,
            "to_status": data.status,
            "notes": data.notes,
        },
    )
    db.add(audit)
    db.commit()

    return db.scalars(stmt).unique().first()


@router.post(
    "/{dispute_id}/note",
    response_model=DisputeResponse,
    summary="Add an inquiry note or customer clarification to a dispute",
)
def add_dispute_note(
    dispute_id: uuid.UUID,
    data: DisputeAddNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add notes or customer responses to the append-only case timeline."""
    stmt = select(Dispute).where(Dispute.id == dispute_id).options(joinedload(Dispute.events))
    dispute = db.scalars(stmt).unique().first()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer or dispute.customer_id != current_user.customer.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    event_type = "NOTE_ADDED" if current_user.role in ("STAFF", "ADMIN") else "CUSTOMER_RESPONSE"
    case_event = CaseEvent(
        dispute_id=dispute.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        event_type=event_type,
        notes=data.notes,
        metadata_snapshot={"actor_username": current_user.username},
    )
    db.add(case_event)
    db.commit()

    return db.scalars(stmt).unique().first()
