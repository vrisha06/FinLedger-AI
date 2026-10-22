"""Audit & Reconciliation API Endpoints for FinLedger-AI."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.schemas.ledger import ReconciliationReport
from app.services.ledger_service import LedgerService

router = APIRouter(prefix="/audit", tags=["Audit & Reconciliation"])


@router.get(
    "/reconciliation",
    response_model=ReconciliationReport,
    summary="Run full ledger-balance reconciliation audit",
)
def get_reconciliation_report(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Perform system-wide double-entry ledger balance reconciliation.

    Restricted to STAFF and ADMIN roles.
    Compares cached balances against derived sums of posted ledger legs.
    """
    return LedgerService.reconcile_all_accounts(db)


@router.get(
    "/logs",
    response_model=list[AuditLogResponse],
    summary="Inspect append-only audit trail records",
)
def list_audit_logs(
    action: str | None = Query(default=None, description="Filter by action name"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    entity_id: str | None = Query(default=None, description="Filter by entity ID"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Retrieve append-only audit log records with optional filtering.

    Restricted to STAFF and ADMIN roles.
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)

    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())
