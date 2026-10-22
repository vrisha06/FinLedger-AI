"""LedgerGraph Pydantic schemas for FinLedger-AI."""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class GraphFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_type: str
    detector_version: str
    severity: str
    heuristic_score: Decimal
    primary_account_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    involved_transfer_ids: List[str]
    involved_account_ids: List[str]
    evidence: Dict[str, Any]
    explanation: str
    review_status: str
    reviewed_by_user_id: Optional[uuid.UUID] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class GraphReviewRequest(BaseModel):
    review_status: str = Field(
        ...,
        pattern=r"^(CLEARED|CONFIRMED_FRAUD|ESCALATED)$",
        description="Updated triage status for graph pattern finding",
    )
    notes: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Forensic investigation rationale",
    )


class SubgraphNode(BaseModel):
    id: str
    account_number: str
    account_type: str
    cached_balance: str
    customer_name: str
    status: str


class SubgraphEdge(BaseModel):
    id: str
    source: str
    target: str
    amount: str
    currency: str
    created_at: str
    status: str


class SubgraphResponse(BaseModel):
    target_account_id: Optional[str] = None
    nodes: List[SubgraphNode]
    edges: List[SubgraphEdge]
    findings: List[Dict[str, Any]]
