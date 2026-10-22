"""Transfer Pydantic v2 schemas for FinLedger-AI."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransferCreateRequest(BaseModel):
    """Payload for POST /api/v1/transfers."""

    source_account_id: uuid.UUID = Field(
        ...,
        description="Source account primary key UUID",
    )
    destination_account_id: uuid.UUID = Field(
        ...,
        description="Destination account primary key UUID",
    )
    amount: Decimal = Field(
        ...,
        gt=Decimal("0.00"),
        decimal_places=2,
        le=Decimal("10000000.00"),
        description="Transfer amount in INR (strictly positive, up to 2 decimal places)",
    )
    currency: str = Field(
        default="INR",
        pattern=r"^INR$",
        description="Currency code; strictly INR denominated",
    )
    memo: str | None = Field(
        default=None,
        max_length=255,
        description="Optional transfer description or narrative",
    )


class TransferResponse(BaseModel):
    """Transfer receipt returned on creation or query."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idempotency_key: str
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    failure_reason: str | None = None
    created_at: datetime
    posted_at: datetime | None = None


class TransferReversalRequest(BaseModel):
    """Admin correction of a posted customer transfer (CORRECTION_REVERSAL)."""

    reason: str = Field(..., min_length=10, max_length=500, description="Why the transfer is being reversed")


class TransferHistoryItem(TransferResponse):
    """Transfer row for a customer's history, with human-readable account numbers."""

    source_account_number: str
    destination_account_number: str


class TransferPreviewRequest(BaseModel):
    """Payload for POST /api/v1/transfers/preview (PayeeGuard)."""

    source_account_id: uuid.UUID
    # Exactly one destination identifier: customers know account numbers, not UUIDs
    destination_account_id: uuid.UUID | None = None
    destination_account_number: str | None = Field(None, min_length=3, max_length=50)
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2)

    @model_validator(mode="after")
    def exactly_one_destination(self) -> "TransferPreviewRequest":
        if (self.destination_account_id is None) == (self.destination_account_number is None):
            raise ValueError("Provide exactly one of destination_account_id or destination_account_number")
        return self


class TransferPreviewResponse(BaseModel):
    """Authoritative beneficiary preview returned by PayeeGuard prior to financial commitment."""

    source_account_id: str
    source_account_number: str
    source_available_balance: str
    destination_account_id: str
    recipient_legal_name: str
    masked_account_number: str
    account_type: str
    nickname: Optional[str] = None
    is_first_time_recipient: bool
    prior_transfers_count: int
    last_transferred_at: Optional[str] = None
    amount: str
    currency: str = "INR"
    validation_status: str
    advisory_warnings: List[str] = []
    verification_provider: str
