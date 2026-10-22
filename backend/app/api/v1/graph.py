"""LedgerGraph API Endpoints for FinLedger-AI."""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.models.graph import GraphFinding
from app.models.audit import AuditLog
from app.schemas.graph import GraphFindingResponse, GraphReviewRequest, SubgraphResponse
from app.services.ledger_graph_service import LedgerGraphService

router = APIRouter(prefix="/graph", tags=["LedgerGraph Analysis"])


@router.get(
    "/subgraph",
    response_model=SubgraphResponse,
    summary="Get bounded money-flow network around an account or transfer",
)
def get_subgraph(
    account_id: Optional[uuid.UUID] = Query(None, description="Center account UUID"),
    transfer_id: Optional[uuid.UUID] = Query(None, description="Center transfer UUID"),
    hops: int = Query(2, ge=1, le=3, description="Neighborhood expansion hop limit"),
    limit: int = Query(60, ge=5, le=100, description="Max transfers in neighborhood"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Retrieve topological graph of accounts and transfers for staff forensic exploration."""

    return LedgerGraphService.get_subgraph(
        db=db,
        account_id=account_id,
        transfer_id=transfer_id,
        hops=hops,
        limit=limit,
    )


@router.get(
    "/findings",
    response_model=List[GraphFindingResponse],
    summary="Search persisted LedgerGraph pattern findings",
)
def list_findings(
    pattern_type: Optional[str] = Query(None, description="Pattern filter"),
    severity: Optional[str] = Query(None, description="Severity filter"),
    review_status: Optional[str] = Query(None, description="Review status filter"),
    account_id: Optional[uuid.UUID] = Query(None, description="Filter by primary account"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff triage queue for multi-account money laundering topologies."""

    conditions = []
    if pattern_type:
        conditions.append(GraphFinding.pattern_type == pattern_type)
    if severity:
        conditions.append(GraphFinding.severity == severity)
    if review_status:
        conditions.append(GraphFinding.review_status == review_status)
    if account_id:
        conditions.append(GraphFinding.primary_account_id == account_id)

    stmt = select(GraphFinding)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(GraphFinding.heuristic_score.desc(), GraphFinding.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.get(
    "/findings/{finding_id}",
    response_model=GraphFindingResponse,
    summary="Get single LedgerGraph pattern finding by ID",
)
def get_finding(
    finding_id: uuid.UUID,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Retrieve full forensic evidence dossier for a specific graph finding."""

    finding = db.get(GraphFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph finding not found")

    return finding


@router.post(
    "/findings/{finding_id}/review",
    response_model=GraphFindingResponse,
    summary="Record staff triage review on a graph finding",
)
@router.patch(
    "/findings/{finding_id}/review",
    response_model=GraphFindingResponse,
    summary="Record staff triage review on a graph finding (PATCH)",
)
def review_finding(
    finding_id: uuid.UUID,
    data: GraphReviewRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff review determination for a detected multi-account money movement topology."""

    finding = db.get(GraphFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph finding not found")

    old_status = finding.review_status
    finding.review_status = data.review_status
    finding.review_notes = data.notes
    finding.reviewed_by_user_id = current_user.id
    finding.reviewed_at = datetime.now(timezone.utc)

    # Record audit log
    audit = AuditLog(
        action="GRAPH_FINDING_REVIEWED",
        entity_type="GRAPH_FINDING",
        entity_id=str(finding.id),
        actor_user_id=current_user.id,
        metadata_json={
            "finding_id": str(finding.id),
            "pattern_type": finding.pattern_type,
            "from_status": old_status,
            "to_status": data.review_status,
            "notes": data.notes,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(finding)
    return finding
