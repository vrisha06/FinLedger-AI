"""FastAPI router for Investment Management and Portfolio endpoints."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_customer
from app.models.user import User
from app.models.customer import Customer
from app.schemas.investment import (
    InvestmentCreateRequest,
    InvestmentResponse,
    PortfolioSummaryResponse,
)
from app.services.investment_service import (
    InvestmentService,
    InvestmentConflictError,
    InvestmentProductError,
)
from app.services.transfer_service import (
    InsufficientFundsError,
    TransferOwnershipError,
    AccountEligibilityError,
    TransferBusinessError,
)

router = APIRouter(prefix="/investments", tags=["Investments"])


@router.post(
    "",
    response_model=InvestmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Purchase a simulated financial product",
)
def purchase_investment(
    data: InvestmentCreateRequest,
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
    """Execute an atomic double-entry simulated investment purchase."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        investment, is_replay = InvestmentService.purchase_investment(
            db=db,
            caller_user_id=current_user.id,
            idempotency_key=str(idempotency_key),
            product_id=data.product_id,
            source_account_id=data.source_account_id,
            amount=data.amount,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if is_replay:
            response.status_code = status.HTTP_200_OK

        return investment

    except InvestmentConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except InsufficientFundsError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except InvestmentProductError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except TransferOwnershipError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except AccountEligibilityError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except TransferBusinessError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err))


@router.get(
    "/portfolio",
    response_model=PortfolioSummaryResponse,
    summary="Retrieve authenticated customer portfolio summary",
)
def get_portfolio(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Aggregate customer's investment positions, liquid balances, and asset allocation."""
    customer = db.scalars(select(Customer).where(Customer.user_id == current_user.id)).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found for authenticated user",
        )

    return InvestmentService.get_customer_portfolio_summary(db=db, customer_id=customer.id)


@router.get(
    "",
    response_model=List[InvestmentResponse],
    summary="List investment positions for authenticated customer",
)
def list_investments(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Retrieve list of simulated investment positions owned by the caller."""
    customer = db.scalars(select(Customer).where(Customer.user_id == current_user.id)).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found for authenticated user",
        )

    return InvestmentService.list_customer_investments(
        db=db,
        customer_id=customer.id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=InvestmentResponse,
    summary="Retrieve details for a specific investment holding",
)
def get_investment(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch details of an investment position with strict ownership or staff RBAC checks."""
    is_staff = current_user.role in ("STAFF", "ADMIN")
    customer_id = None
    if not is_staff:
        customer = db.scalars(select(Customer).where(Customer.user_id == current_user.id)).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer profile not found",
            )
        customer_id = customer.id

    investment = InvestmentService.get_investment_by_id(
        db=db,
        investment_id=id,
        customer_id=customer_id,
    )
    if not investment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investment holding '{id}' not found or access denied",
        )

    return investment
