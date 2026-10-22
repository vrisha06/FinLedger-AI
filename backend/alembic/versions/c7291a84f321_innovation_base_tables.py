"""Innovation base tables: payee_edges, saved_payees, investigation_notes, and disputes.

Revision ID: c7291a84f321
Revises: b4129e73f910
Create Date: 2026-10-15 12:00:00.000000

Adds:
1. payee_edges: Relational money-flow edges between accounts.
2. saved_payees: Customer-verified payees and nicknames.
3. investigation_notes: Forensic investigator notes for fraud alerts.
4. disputes: Customer dispute cases for financial transfers.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7291a84f321"
down_revision: Union[str, None] = "b4129e73f910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. payee_edges
    op.create_table(
        "payee_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("transfer_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("avg_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.UniqueConstraint("source_account_id", "destination_account_id", name="uq_payee_edges_source_dest"),
    )
    op.create_index("ix_payee_edges_source_account_id", "payee_edges", ["source_account_id"])
    op.create_index("ix_payee_edges_destination_account_id", "payee_edges", ["destination_account_id"])
    op.create_index("ix_payee_edges_dest_source", "payee_edges", ["destination_account_id", "source_account_id"])

    # 2. saved_payees
    op.create_table(
        "saved_payees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payee_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("customer_id", "payee_account_id", name="uq_saved_payees_customer_account"),
    )
    op.create_index("ix_saved_payees_customer_id", "saved_payees", ["customer_id"])
    op.create_index("ix_saved_payees_payee_account_id", "saved_payees", ["payee_account_id"])

    # 3. investigation_notes
    op.create_table(
        "investigation_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fraud_prediction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fraud_predictions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "note_type IN ('OBSERVATION', 'EVIDENCE', 'CONCLUSION', 'ESCALATION')",
            name="chk_investigation_note_type_valid",
        ),
    )
    op.create_index("ix_investigation_notes_fraud_prediction_id", "investigation_notes", ["fraud_prediction_id"])
    op.create_index("ix_investigation_notes_author_user_id", "investigation_notes", ["author_user_id"])
    op.create_index("ix_investigation_notes_created_at", "investigation_notes", ["created_at"])

    # 4. disputes
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transfer_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transfer_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("assigned_staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "category IN ('UNAUTHORIZED', 'INCORRECT_AMOUNT', 'NOT_RECEIVED', 'SUSPECTED_FRAUD', 'OTHER')",
            name="chk_dispute_category_valid",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'REJECTED')",
            name="chk_dispute_status_valid",
        ),
    )
    op.create_index("ix_disputes_customer_id", "disputes", ["customer_id"])
    op.create_index("ix_disputes_transfer_request_id", "disputes", ["transfer_request_id"])
    op.create_index("ix_disputes_status", "disputes", ["status"])
    op.create_index("ix_disputes_assigned_staff_id", "disputes", ["assigned_staff_id"])
    op.create_index("ix_disputes_created_at", "disputes", ["created_at"])


def downgrade() -> None:
    op.drop_table("disputes")
    op.drop_table("investigation_notes")
    op.drop_table("saved_payees")
    op.drop_table("payee_edges")
