"""FastAPI router for Financial Reporting and System Analytics endpoints."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_staff
from app.models.user import User
from app.models.customer import Customer
from app.schemas.report import (
    CustomerFinancialSummaryResponse,
    ProductsSummaryResponse,
    DailyVolumeResponse,
    BalanceDistributionResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get(
    "/customer-summary",
    response_model=CustomerFinancialSummaryResponse,
    summary="Retrieve customer-level financial summary",
)
def get_customer_summary(
    customer_id: Optional[uuid.UUID] = Query(
        None,
        description="Target customer UUID (staff only; regular customers default to self)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate comprehensive financial summary for a customer.

    Customers are restricted to their own profile. Staff/Admins may inspect any customer.
    """
    is_staff = current_user.role in ("STAFF", "ADMIN")

    if not is_staff:
        # Regular customers can only view their own summary
        customer = db.scalars(select(Customer).where(Customer.user_id == current_user.id)).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer profile not found for authenticated user",
            )
        target_customer_id = customer.id
    else:
        # Staff inspection
        if customer_id:
            target_customer_id = customer_id
        else:
            # Check if staff has linked customer, otherwise require customer_id parameter
            customer = db.scalars(select(Customer).where(Customer.user_id == current_user.id)).first()
            if customer:
                target_customer_id = customer.id
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Query parameter 'customer_id' is required for staff inspection",
                )

    try:
        return ReportService.get_customer_financial_summary(db=db, customer_id=target_customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/products-summary",
    response_model=ProductsSummaryResponse,
    summary="Retrieve catalogue performance and subscription metrics (staff only)",
)
def get_products_summary(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Aggregate total subscriptions, active holdings, and volumes across all products."""
    return ReportService.get_products_summary(db=db)


@router.get(
    "/daily-volume",
    response_model=DailyVolumeResponse,
    summary="Retrieve daily transactional and investment volumes (staff only)",
)
def get_daily_volume(
    days: int = Query(14, ge=1, le=90, description="Number of past days to aggregate"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Aggregate daily transfer and investment activity over a sliding date window."""
    return ReportService.get_daily_volume(db=db, days=days)


@router.get(
    "/balance-distribution",
    response_model=BalanceDistributionResponse,
    summary="Retrieve system-wide account balance tier distributions (staff only)",
)
def get_balance_distribution(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Aggregate distribution of account balances across financial tiers."""
    return ReportService.get_balance_distribution(db=db)
