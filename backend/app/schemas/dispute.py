"""Dispute and Customer Recourse Pydantic schemas for FinLedger-AI."""

from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DisputeCreateRequest(BaseModel):
    transfer_request_id: uuid.UUID = Field(
        ...,
        description="UUID of the disputed transfer",
    )
    category: str = Field(
        ...,
        pattern=r"^(UNAUTHORIZED|INCORRECT_AMOUNT|NOT_RECEIVED|SUSPECTED_FRAUD|OTHER)$",
        description="Reason category for customer recourse",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed factual description of the issue from the customer",
    )


class CaseEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID
    actor_role: str
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    notes: Optional[str] = None
    metadata_snapshot: Dict[str, Any]
    created_at: datetime


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    transfer_request_id: uuid.UUID
    category: str
    description: str
    status: str
    assigned_staff_id: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    events: List[CaseEventResponse] = []


class DisputeStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(INVESTIGATING|RESOLVED|REJECTED)$",
        description="Target dispute status",
    )
    notes: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Required staff determination rationale",
    )


class DisputeAddNoteRequest(BaseModel):
    notes: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Note content or clarification",
    )
