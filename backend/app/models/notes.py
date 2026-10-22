import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.fraud import FraudPrediction
    from app.models.user import User


class InvestigationNote(Base):
    """Forensic investigator note attached to an advisory fraud prediction."""

    __tablename__ = "investigation_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    fraud_prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fraud_predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    fraud_prediction: Mapped["FraudPrediction"] = relationship("FraudPrediction")
    author_user: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "note_type IN ('OBSERVATION', 'EVIDENCE', 'CONCLUSION', 'ESCALATION')",
            name="chk_investigation_note_type_valid",
        ),
    )
