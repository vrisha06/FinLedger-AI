import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Numeric, DateTime, ForeignKey, CheckConstraint, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.transfer import TransferRequest
    from app.models.user import User


class FraudPrediction(Base):
    """Advisory fraud prediction score, explainability snapshot, and staff review status."""

    __tablename__ = "fraud_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transfer_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfer_requests.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=4),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    rule_flags: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    feature_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    transfer_request: Mapped["TransferRequest"] = relationship(
        "TransferRequest",
        back_populates="fraud_prediction",
    )
    reviewed_by_user: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "risk_score >= 0.0000 AND risk_score <= 1.0000",
            name="chk_fraud_risk_score_range",
        ),
        CheckConstraint(
            "decision IN ('LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK')",
            name="chk_fraud_decision_valid",
        ),
        CheckConstraint(
            "review_status IN ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED')",
            name="chk_fraud_review_status_valid",
        ),
        Index(
            "idx_fraud_pending_risk",
            "risk_score",
            created_at.desc(),
        ),
        Index(
            "idx_fraud_pending_queue",
            risk_score.desc(),
            created_at.desc(),
            postgresql_where=(review_status == "PENDING"),
        ),
    )
