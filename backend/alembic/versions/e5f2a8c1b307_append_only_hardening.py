"""Append-only hardening: immutable ledger headers and TRUNCATE guards.

Revision ID: e5f2a8c1b307
Revises: d9154a83b271
Create Date: 2026-10-19 20:00:00.000000

Adds:
1. trg_immutable_ledger_transactions: ledger_transactions headers become append-only, like their legs.
   Rewriting a header (type, description, transfer link) would otherwise alter committed history.
2. BEFORE TRUNCATE statement triggers on ledger_entries, ledger_transactions and audit_logs.
   Row-level UPDATE/DELETE triggers never fire for TRUNCATE.

Test/benchmark database resets opt in per transaction with
`SET LOCAL finledger.allow_truncate = 'on'`. The durable control in production is a
least-privilege application role without TRUNCATE privilege; this guard stops accidents.
"""

from typing import Sequence, Union
from alembic import op


revision: str = "e5f2a8c1b307"
down_revision: Union[str, None] = "d9154a83b271"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APPEND_ONLY_TABLES = ("ledger_entries", "ledger_transactions", "audit_logs")


def upgrade() -> None:
    op.execute("""
    CREATE TRIGGER trg_immutable_ledger_transactions
    BEFORE UPDATE OR DELETE ON ledger_transactions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_record_modification();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_append_only_truncate()
    RETURNS TRIGGER AS $$
    BEGIN
        IF current_setting('finledger.allow_truncate', true) = 'on' THEN
            RETURN NULL;
        END IF;
        RAISE EXCEPTION 'Table % is strictly append-only; TRUNCATE is prohibited', TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql;
    """)

    for table in APPEND_ONLY_TABLES:
        op.execute(f"""
        CREATE TRIGGER trg_no_truncate_{table}
        BEFORE TRUNCATE ON {table}
        FOR EACH STATEMENT
        EXECUTE FUNCTION prevent_append_only_truncate();
        """)


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_no_truncate_{table} ON {table};")
    op.execute("DROP FUNCTION IF EXISTS prevent_append_only_truncate();")
    op.execute("DROP TRIGGER IF EXISTS trg_immutable_ledger_transactions ON ledger_transactions;")
