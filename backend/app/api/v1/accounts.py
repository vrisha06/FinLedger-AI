"""Account API Endpoints for FinLedger-AI."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_current_user, require_customer
from app.models.user import User
from app.models.account import Account
from app.schemas.account import AccountResponse, DepositRequest, AccountCreateRequest
from app.schemas.ledger import LedgerEntryResponse
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["Accounts & Balances"])


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new customer account (SAVINGS or CURRENT)",
)
def create_account(
    data: AccountCreateRequest = AccountCreateRequest(),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Provision a new customer account with zero balance.

    Zero initial balance ensures strict adherence to double-entry ledger invariants.
    Subsequent deposits must be posted against the internal clearing account.
    """
    if not current_user.customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found for user",
        )

    try:
        new_account = AccountService.provision_customer_account(
            db=db,
            customer_id=current_user.customer.id,
            account_type=data.account_type,
        )
        db.commit()
        db.refresh(new_account)
        return new_account
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )


@router.get(
    "",
    response_model=list[AccountResponse],
    summary="List accounts for current user or all accounts for staff",
)
def list_accounts(
    customer_id: uuid.UUID | None = Query(default=None, description="Filter by customer UUID (staff only)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve accounts. Customers only see their own; Staff/Admin can see all or filter."""
    if current_user.role in ("STAFF", "ADMIN"):
        stmt = select(Account).order_by(Account.created_at.asc())
        if customer_id:
            stmt = stmt.where(Account.customer_id == customer_id)
        return list(db.scalars(stmt).all())

    # Customer user
    if not current_user.customer:
        return []

    return AccountService.get_customer_accounts(db, current_user.customer.id)


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Get account details by UUID",
)
def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and cached balance for a single account."""
    account = AccountService.get_account_by_id(db, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Ownership check
    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer or account.customer_id != current_user.customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not own this account",
            )

    return account


@router.get(
    "/{account_id}/ledger",
    response_model=list[LedgerEntryResponse],
    summary="Get immutable ledger entries for an account",
)
def get_account_ledger(
    account_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve posted double-entry ledger records for an account."""
    account = AccountService.get_account_by_id(db, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Ownership check
    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer or account.customer_id != current_user.customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not own this account",
            )

    return AccountService.get_account_ledger_entries(
        db=db,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{account_id}/deposit",
    response_model=AccountResponse,
    summary="Simulate an opening deposit via internal clearing account",
)
def deposit_funds(
    account_id: uuid.UUID,
    data: DepositRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate opening funds deposit against the internal clearing account."""
    account = AccountService.get_account_by_id(db, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Ownership check: Customer can only deposit into own account; Staff/Admin into any
    if current_user.role not in ("STAFF", "ADMIN"):
        if not current_user.customer or account.customer_id != current_user.customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot deposit funds into another customer's account",
            )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        updated_account = AccountService.deposit_opening_funds(
            db=db,
            account_id=account_id,
            amount=data.amount,
            description=data.description,
            actor_user_id=current_user.id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return updated_account
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
