import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any
from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SimulationRun(Base):
    """Execution record of an isolated Fraud Lab synthetic benchmark simulation."""

    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scenario_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    sample_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    detector_configs: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    scenario_breakdown: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationship
    created_by_user: Mapped["User"] = relationship("User")
