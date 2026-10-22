"""Innovations: graph findings, case events, and simulation runs.

Revision ID: d9154a83b271
Revises: c7291a84f321
Create Date: 2026-10-16 15:00:00.000000

Adds:
1. graph_findings: Stores LedgerGraph temporal money-flow detection signals and evidence.
2. case_events: Append-only audit history of customer dispute status transitions and staff determinations.
3. simulation_runs: Isolated metadata records for Fraud Lab synthetic benchmark evaluations.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d9154a83b271"
down_revision: Union[str, None] = "c7291a84f321"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create graph_findings table
    op.create_table(
        "graph_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pattern_type", sa.String(length=50), nullable=False),
        sa.Column("detector_version", sa.String(length=30), nullable=False, server_default="ledgergraph-v1.0"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("heuristic_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("primary_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("involved_transfer_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("involved_account_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("heuristic_score >= 0.0000 AND heuristic_score <= 1.0000", name="chk_graph_heuristic_score_range"),
        sa.CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="chk_graph_severity_valid"),
        sa.CheckConstraint("review_status IN ('PENDING', 'CLEARED', 'CONFIRMED_FRAUD', 'ESCALATED')", name="chk_graph_review_status_valid"),
        sa.CheckConstraint("pattern_type IN ('FAN_IN', 'FAN_OUT', 'RAPID_PASS_THROUGH', 'MULTI_HOP_LAYERING', 'CIRCULAR_FLOW', 'BURST_VELOCITY')", name="chk_graph_pattern_type_valid"),
    )
    op.create_index("ix_graph_findings_pattern_type", "graph_findings", ["pattern_type"])
    op.create_index("ix_graph_findings_primary_account_id", "graph_findings", ["primary_account_id"])
    op.create_index("ix_graph_findings_review_status", "graph_findings", ["review_status"])
    op.create_index("ix_graph_findings_created_at", "graph_findings", ["created_at"])
    op.create_index(
        "idx_graph_findings_pending_queue",
        "graph_findings",
        [sa.text("heuristic_score DESC"), sa.text("created_at DESC")],
        postgresql_where=sa.text("review_status = 'PENDING'"),
    )

    # 2. Create case_events table (append-only timeline on disputes)
    op.create_table(
        "case_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dispute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=25), nullable=True),
        sa.Column("to_status", sa.String(length=25), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('DISPUTE_OPENED', 'STATUS_CHANGE', 'NOTE_ADDED', 'INFO_REQUESTED', 'CUSTOMER_RESPONSE', 'RESOLVED', 'REJECTED')",
            name="chk_case_event_type_valid",
        ),
    )
    op.create_index("ix_case_events_dispute_id", "case_events", ["dispute_id"])
    op.create_index("ix_case_events_created_at", "case_events", ["created_at"])

    # 3. Create simulation_runs table
    op.create_table(
        "simulation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scenario_name", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("detector_configs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("scenario_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_simulation_runs_scenario_name", "simulation_runs", ["scenario_name"])
    op.create_index("ix_simulation_runs_created_at", "simulation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("simulation_runs")
    op.drop_table("case_events")
    op.drop_table("graph_findings")
