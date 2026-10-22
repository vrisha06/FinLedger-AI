import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Numeric, SmallInteger, DateTime, ForeignKey, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.transfer import TransferRequest


class LedgerTransaction(Base):
    """Transaction header grouping balanced multi-row ledger legs."""

    __tablename__ = "ledger_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transfer_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_requests.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    transfer_request: Mapped["TransferRequest"] = relationship(
        "TransferRequest",
        back_populates="ledger_transaction",
    )
    entries: Mapped[List["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('CUSTOMER_TRANSFER', 'INITIAL_DEPOSIT', 'CORRECTION_REVERSAL', 'INVESTMENT_PURCHASE')",
            name="chk_ledger_txn_type_valid",
        ),
    )


class LedgerEntry(Base):
    """Immutable double-entry posting leg (DEBIT or CREDIT)."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    sequence_num: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    transaction: Mapped["LedgerTransaction"] = relationship(
        "LedgerTransaction",
        back_populates="entries",
    )
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="ledger_entries",
    )

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('DEBIT', 'CREDIT')",
            name="chk_ledger_entry_type_valid",
        ),
        CheckConstraint(
            "amount > 0.00",
            name="chk_ledger_entry_amount_positive",
        ),
        Index(
            "idx_ledger_entries_account_created_seq",
            "account_id",
            created_at.desc(),
            sequence_num.desc(),
        ),
    )
