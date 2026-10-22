"""Audit log response schemas."""

from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Sanitized audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: uuid.UUID | None = None
    action: str
    entity_type: str
    entity_id: str
    ip_address: str | None = None
    user_agent: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
