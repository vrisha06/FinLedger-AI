"""Fraud Lab Pydantic v2 schemas for FinLedger-AI."""

from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel, Field


class SimulationRunRequest(BaseModel):
    scenario_name: str = Field(
        default="ALL_SCENARIOS_BENCHMARK",
        description="Predefined scenario identifier or benchmark",
    )
    seed: int = Field(
        default=42,
        ge=0,
        le=999999,
        description="Random seed for deterministic reproducibility",
    )
    sample_size: int = Field(
        default=300,
        ge=50,
        le=2000,
        description="Transaction sample size to simulate",
    )


class ScenarioDefinition(BaseModel):
    name: str
    description: str
    default_samples: int


class DetectorMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    pr_auc: float
    review_alerts_count: int
    confusion_matrix: Dict[str, int]


class SimulationRunResponse(BaseModel):
    scenario_name: str
    seed: int
    sample_size: int
    fraud_prevalence: float
    fraud_count: int
    legitimate_count: int
    execution_duration_ms: int
    detectors: Dict[str, DetectorMetrics]
    scenario_breakdown: Dict[str, Dict[str, Any]]
    ablation_finding: str
    disclaimer: str = "SYNTHETIC SIMULATION — NOT REAL CUSTOMER ACTIVITY"
