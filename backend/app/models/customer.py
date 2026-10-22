import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import String, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.account import Account
    from app.models.product import Investment


class Customer(Base, TimestampMixin):
    """Customer profile linked to an authenticated User."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    pan_number: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    kyc_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="VERIFIED",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="customer",
    )
    accounts: Mapped[List["Account"]] = relationship(
        "Account",
        back_populates="customer",
    )
    investments: Mapped[List["Investment"]] = relationship(
        "Investment",
        back_populates="customer",
    )

    __table_args__ = (
        CheckConstraint(
            "kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="chk_customers_kyc_status_valid",
        ),
    )
