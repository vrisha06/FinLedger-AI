"""Transfer API Endpoints for FinLedger-AI."""

import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, select

from app.api.deps import get_db, get_current_user, require_admin, require_customer
from app.models.user import User
from app.models.transfer import TransferRequest
from app.models.account import Account
from app.schemas.transfer import TransferCreateRequest, TransferHistoryItem, TransferResponse, TransferReversalRequest
from app.services.reversal_service import ReversalError, ReversalService
from app.services.transfer_service import (
    TransferService,
    IdempotencyConflictError,
    TransferBusinessError,
    InsufficientFundsError,
    TransferOwnershipError,
    AccountEligibilityError,
)
from app.schemas.transfer import TransferPreviewRequest, TransferPreviewResponse
from app.services.payee_guard_service import PayeeGuardService, PayeeGuardError

router = APIRouter(prefix="/transfers", tags=["Financial Transfers"])


@router.post(
    "/preview",
    response_model=TransferPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview and verify recipient details before transfer confirmation (PayeeGuard)",
)
def preview_transfer(
    data: TransferPreviewRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Authoritative pre-transfer beneficiary verification without moving funds."""
    try:
        return PayeeGuardService.preview_transfer(
            db=db,
            caller_user_id=current_user.id,
            source_account_id=data.source_account_id,
            destination_account_id=data.destination_account_id,
            destination_account_number=data.destination_account_number,
            amount=data.amount,
        )
    except PayeeGuardError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute an atomic financial transfer",
)
def create_transfer(
    data: TransferCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: uuid.UUID = Header(
        ...,
        alias="Idempotency-Key",
        description="Unique UUIDv4 idempotency key per client operation",
    ),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Execute an atomic transfer between two accounts with canonical locking and idempotency."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        transfer_req, is_replay = TransferService.execute_transfer(
            db=db,
            caller_user_id=current_user.id,
            idempotency_key=str(idempotency_key),
            source_account_id=data.source_account_id,
            destination_account_id=data.destination_account_id,
            amount=data.amount,
            currency=data.currency,
            memo=data.memo,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if is_replay:
            response.status_code = status.HTTP_200_OK

        return transfer_req

    except IdempotencyConflictError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        )
    except InsufficientFundsError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
    except TransferOwnershipError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(err),
        )
    except AccountEligibilityError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
    except TransferBusinessError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail=err.message,
        )


@router.get(
    "",
    response_model=list[TransferHistoryItem],
    summary="List the caller's transfers (sent, received, and failed attempts), newest first",
)
def list_my_transfers(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Read-only history scoped to the caller: transfers they initiated or that touch their accounts."""
    my_account_ids = select(Account.id).where(
        Account.customer_id == (current_user.customer.id if current_user.customer else None)
    )
    stmt = (
        select(TransferRequest)
        .options(joinedload(TransferRequest.source_account), joinedload(TransferRequest.destination_account))
        .where(
            or_(
                TransferRequest.source_user_id == current_user.id,
                TransferRequest.source_account_id.in_(my_account_ids),
                TransferRequest.destination_account_id.in_(my_account_ids),
            )
        )
        .order_by(TransferRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        TransferHistoryItem(
            **TransferResponse.model_validate(t).model_dump(),
            source_account_number=t.source_account.account_number,
            destination_account_number=t.destination_account.account_number,
        )
        for t in db.scalars(stmt).unique()
    ]


@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
    summary="Get transfer receipt and status by ID",
)
def get_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific transfer by UUID."""
    stmt = select(TransferRequest).where(TransferRequest.id == transfer_id)
    transfer = db.scalars(stmt).first()

    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer record not found",
        )

    # Authorization guard: customers can only view transfers they initiated or received
    if current_user.role not in ("STAFF", "ADMIN"):
        is_initiator = transfer.source_user_id == current_user.id
        user_account_ids = set()
        if current_user.customer:
            user_account_ids = {
                acc.id
                for acc in db.scalars(
                    select(Account).where(Account.customer_id == current_user.customer.id)
                ).all()
            }
        is_involved = (
            transfer.source_account_id in user_account_ids
            or transfer.destination_account_id in user_account_ids
        )

        if not (is_initiator or is_involved):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot inspect another user's transfer record",
            )

    return transfer


@router.post(
    "/{transfer_id}/reverse",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a posted customer transfer with a balanced CORRECTION_REVERSAL (admin only)",
)
def reverse_transfer(
    transfer_id: uuid.UUID,
    data: TransferReversalRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Post the opposite double-entry transaction; the original's ledger legs are never edited."""
    try:
        return ReversalService.reverse_transfer(
            db=db,
            transfer_id=transfer_id,
            actor_user_id=current_user.id,
            reason=data.reason.strip(),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ReversalError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
