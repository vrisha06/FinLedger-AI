"""Pydantic v2 schemas for Investment Holdings & Portfolio Management."""

from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.product import ProductResponse


class InvestmentCreateRequest(BaseModel):
    """Payload for customer investment purchase."""

    product_id: uuid.UUID = Field(
        ...,
        description="Target financial product UUID",
    )
    source_account_id: uuid.UUID = Field(
        ...,
        description="Source customer savings/current account UUID",
    )
    amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        decimal_places=2,
        le=Decimal("100000000.00"),
        description="Investment principal amount in INR",
    )


class InvestmentResponse(BaseModel):
    """Investment holding details returned on purchase or retrieval."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    product_id: uuid.UUID
    invested_amount: Decimal
    current_value: Decimal
    status: str
    start_date: datetime
    maturity_date: datetime
    created_at: datetime
    nominal_accrued_yield: Decimal | None = None
    product: ProductResponse | None = None


class PortfolioHoldingItem(BaseModel):
    """Summary representation of an active investment holding."""

    investment_id: uuid.UUID
    product_name: str
    product_code: str
    product_type: str
    annual_yield_rate: Decimal
    invested_amount: Decimal
    current_value: Decimal
    status: str
    start_date: datetime
    maturity_date: datetime
    term_months: int
    nominal_accrued_yield: Decimal


class PortfolioSummaryResponse(BaseModel):
    """Authoritative customer portfolio overview."""

    customer_id: uuid.UUID
    total_invested: Decimal
    total_current_value: Decimal
    active_investments_count: int
    available_savings_balance: Decimal
    total_net_worth: Decimal
    allocation_by_product_type: dict[str, Decimal]
    disclaimer: str = (
        "ACADEMIC NOTICE: Investment yields, terms, and values reflect simulated demonstration rules. "
        "No real-world financial returns or investment advice is guaranteed."
    )
    holdings: list[PortfolioHoldingItem]
