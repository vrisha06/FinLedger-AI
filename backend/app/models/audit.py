from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import String, BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """Append-only audit log tracking administrative, security, and financial events."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    actor_user_id: Mapped[Any | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    metadata_json: Mapped[dict] = mapped_column(
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
    actor_user: Mapped["User"] = relationship(
        "User",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index(
            "idx_audit_logs_action_created",
            "action",
            created_at.desc(),
        ),
    )
