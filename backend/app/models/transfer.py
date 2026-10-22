import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Numeric, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.account import Account
    from app.models.ledger import LedgerTransaction
    from app.models.fraud import FraudPrediction


class TransferRequest(Base):
    """Transfer request master record tracking scoped idempotency, parameters, and status."""

    __tablename__ = "transfer_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    source_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    destination_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    source_user: Mapped["User"] = relationship("User")
    source_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[source_account_id],
        back_populates="source_transfers",
    )
    destination_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[destination_account_id],
        back_populates="destination_transfers",
    )
    ledger_transaction: Mapped["LedgerTransaction"] = relationship(
        "LedgerTransaction",
        back_populates="transfer_request",
        uselist=False,
    )
    fraud_prediction: Mapped["FraudPrediction"] = relationship(
        "FraudPrediction",
        back_populates="transfer_request",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "source_user_id",
            "idempotency_key",
            name="uq_transfers_user_idempotency",
        ),
        CheckConstraint(
            "source_account_id <> destination_account_id",
            name="chk_transfers_distinct_accounts",
        ),
        CheckConstraint(
            "amount > 0.00",
            name="chk_transfers_amount_positive",
        ),
        CheckConstraint(
            "currency = 'INR'",
            name="chk_transfers_currency_inr",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'POSTED', 'FAILED', 'REVERSED')",
            name="chk_transfers_status_valid",
        ),
        Index(
            "idx_transfers_status_created",
            "status",
            created_at.desc(),
        ),
    )
