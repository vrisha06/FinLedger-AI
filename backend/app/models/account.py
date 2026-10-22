import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Numeric, Integer, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.ledger import LedgerEntry
    from app.models.transfer import TransferRequest


class Account(Base, TimestampMixin):
    """Financial account entity holding cached balance and status."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,  # Nullable for internal system clearing accounts
        index=True,
    )
    account_number: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )
    account_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )
    cached_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="accounts",
    )
    ledger_entries: Mapped[List["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="account",
    )
    source_transfers: Mapped[List["TransferRequest"]] = relationship(
        "TransferRequest",
        foreign_keys="TransferRequest.source_account_id",
        back_populates="source_account",
    )
    destination_transfers: Mapped[List["TransferRequest"]] = relationship(
        "TransferRequest",
        foreign_keys="TransferRequest.destination_account_id",
        back_populates="destination_account",
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('SAVINGS', 'CURRENT', 'INTERNAL_CLEARING', 'INVESTMENT')",
            name="chk_accounts_type_valid",
        ),
        CheckConstraint(
            "currency = 'INR'",
            name="chk_accounts_currency_inr",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'FROZEN', 'CLOSED')",
            name="chk_accounts_status_valid",
        ),
        CheckConstraint(
            "account_type = 'INTERNAL_CLEARING' OR cached_balance >= 0.00",
            name="chk_accounts_non_negative_balance",
        ),
    )
