"""Account Pydantic v2 schemas for FinLedger-AI."""

from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    """Account attributes with cached balance."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID | None = None
    account_number: str
    account_type: str
    currency: str = "INR"
    cached_balance: Decimal
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class DepositRequest(BaseModel):
    """Payload for simulated opening deposit."""

    amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        decimal_places=2,
        le=Decimal("100000000.00"),
        description="Deposit amount in INR (strictly positive, up to 2 decimal places)",
    )
    description: str = Field(
        default="Simulated Opening Deposit",
        max_length=255,
        description="Human-readable ledger description",
    )


class AccountCreateRequest(BaseModel):
    """Payload for provisioning a customer account."""

    account_type: str = Field(
        default="SAVINGS",
        pattern=r"^(SAVINGS|CURRENT)$",
        description="Account type to provision (SAVINGS or CURRENT)",
    )
