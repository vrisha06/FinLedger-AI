"""Pydantic v2 schemas for Financial Products."""

from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    """Base financial product attributes."""

    name: str = Field(
        ...,
        max_length=100,
        description="Display name of the financial product",
    )
    code: str = Field(
        ...,
        max_length=32,
        description="Unique product identifier code (e.g. FD-12M-01)",
    )
    product_type: str = Field(
        ...,
        pattern=r"^(FIXED_DEPOSIT|RECURRING_DEPOSIT|MUTUAL_FUND|TREASURY_BILL)$",
        description="Categorical product type",
    )
    annual_yield_rate: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        decimal_places=2,
        description="Annual yield rate in percent (e.g. 7.10 for 7.10% p.a.)",
    )
    min_amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        decimal_places=2,
        description="Minimum investment amount in INR",
    )
    term_months: int = Field(
        ...,
        gt=0,
        description="Term duration in months",
    )
    is_active: bool = Field(
        default=True,
        description="Availability status of product for new subscriptions",
    )


class ProductCreateRequest(ProductBase):
    """Payload for staff product creation."""
    pass


class ProductResponse(ProductBase):
    """Product model attributes returned by catalogue endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
