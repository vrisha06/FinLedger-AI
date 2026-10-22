import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Numeric, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.customer import Customer


class PayeeEdge(Base):
    """Authoritative relational money-flow edge between two accounts."""

    __tablename__ = "payee_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    transfer_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    avg_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Relationships
    source_account: Mapped["Account"] = relationship("Account", foreign_keys=[source_account_id])
    destination_account: Mapped["Account"] = relationship("Account", foreign_keys=[destination_account_id])

    __table_args__ = (
        UniqueConstraint("source_account_id", "destination_account_id", name="uq_payee_edges_source_dest"),
    )


class SavedPayee(Base):
    """Customer-verified beneficiary record for PayeeGuard pre-validation."""

    __tablename__ = "saved_payees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payee_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nickname: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")
    payee_account: Mapped["Account"] = relationship("Account")

    __table_args__ = (
        UniqueConstraint("customer_id", "payee_account_id", name="uq_saved_payees_customer_account"),
    )
