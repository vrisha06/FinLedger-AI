import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Dict, Any
from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.transfer import TransferRequest
    from app.models.user import User


class Dispute(Base):
    """Customer-initiated recourse dispute on an executed financial transfer."""

    __tablename__ = "disputes"

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
    transfer_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN",
        index=True,
    )
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")
    transfer_request: Mapped["TransferRequest"] = relationship("TransferRequest")
    assigned_staff: Mapped["User"] = relationship("User", foreign_keys=[assigned_staff_id])
    events: Mapped[List["CaseEvent"]] = relationship(
        "CaseEvent",
        back_populates="dispute",
        order_by="CaseEvent.created_at.asc()",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('UNAUTHORIZED', 'INCORRECT_AMOUNT', 'NOT_RECEIVED', 'SUSPECTED_FRAUD', 'OTHER')",
            name="chk_dispute_category_valid",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'REJECTED')",
            name="chk_dispute_status_valid",
        ),
    )


class CaseEvent(Base):
    """Append-only audit trail and status transition history for a customer recourse dispute."""

    __tablename__ = "case_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    dispute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(25),
        nullable=True,
    )
    to_status: Mapped[str | None] = mapped_column(
        String(25),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    metadata_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="events")
    actor_user: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('DISPUTE_OPENED', 'STATUS_CHANGE', 'NOTE_ADDED', 'INFO_REQUESTED', 'CUSTOMER_RESPONSE', 'RESOLVED', 'REJECTED')",
            name="chk_case_event_type_valid",
        ),
    )
