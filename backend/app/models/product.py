import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Numeric, Integer, Boolean, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.account import Account


class FinancialProduct(Base):
    """Simulated financial product (e.g. Fixed Deposit, Liquid Fund)."""

    __tablename__ = "financial_products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )
    product_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    annual_yield_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=False,
    )
    min_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    term_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    investments: Mapped[List["Investment"]] = relationship(
        "Investment",
        back_populates="product",
    )

    __table_args__ = (
        CheckConstraint(
            "product_type IN ('FIXED_DEPOSIT', 'RECURRING_DEPOSIT', 'MUTUAL_FUND', 'TREASURY_BILL')",
            name="chk_products_type_valid",
        ),
        CheckConstraint(
            "annual_yield_rate >= 0.00",
            name="chk_products_yield_positive",
        ),
        CheckConstraint(
            "min_amount > 0.00",
            name="chk_products_min_amount_positive",
        ),
        CheckConstraint(
            "term_months > 0",
            name="chk_products_term_positive",
        ),
    )


class Investment(Base):
    """Customer investment position linked to an asset account."""

    __tablename__ = "investments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invested_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    current_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    maturity_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="investments",
    )
    account: Mapped["Account"] = relationship("Account")
    product: Mapped["FinancialProduct"] = relationship(
        "FinancialProduct",
        back_populates="investments",
    )

    __table_args__ = (
        CheckConstraint(
            "invested_amount > 0.00",
            name="chk_investments_amount_positive",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'MATURED', 'LIQUIDATED')",
            name="chk_investments_status_valid",
        ),
    )
