"""Fraud Lab API Endpoints for FinLedger-AI."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, require_staff
from app.models.user import User
from app.models.simulation import SimulationRun
from app.schemas.fraud_lab import (
    SimulationRunRequest,
    SimulationRunResponse,
    ScenarioDefinition,
)
from app.services.fraud_lab_service import FraudLabService

router = APIRouter(prefix="/fraud-lab", tags=["Fraud Lab Simulation & Benchmarking"])


@router.get(
    "/scenarios",
    response_model=List[ScenarioDefinition],
    summary="List predefined reproducible synthetic fraud scenarios",
)
def list_scenarios(current_user: User = Depends(require_staff)):
    """Retrieve catalog of configurable synthetic scenarios including benign lookalikes."""
    return FraudLabService.get_available_scenarios()


@router.post(
    "/run",
    response_model=SimulationRunResponse,
    summary="Execute an isolated synthetic scenario simulation and benchmark detectors",
)
def run_simulation(
    payload: SimulationRunRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Run an isolated in-memory simulation comparing Rule Baseline, Random Forest,
    LedgerGraph, and Hybrid Ensemble without modifying customer accounts or balances."""
    return FraudLabService.run_simulation(
        db=db,
        scenario_name=payload.scenario_name,
        seed=payload.seed,
        sample_size=payload.sample_size,
        user_id=current_user.id,
    )


@router.get(
    "/history",
    summary="List historical simulation runs",
)
def list_simulation_history(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Staff inspection of previously recorded benchmark simulation runs."""
    stmt = select(SimulationRun).order_by(SimulationRun.created_at.desc()).limit(20)
    runs = db.scalars(stmt).all()
    return [
        {
            "id": str(r.id),
            "scenario_name": r.scenario_name,
            "seed": r.seed,
            "sample_size": r.sample_size,
            "metrics": r.metrics,
            "scenario_breakdown": r.scenario_breakdown,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
