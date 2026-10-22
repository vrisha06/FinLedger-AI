"""Schema Introspection Script for FinLedger-AI."""

import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings


def inspect_database_schema():
    engine = create_engine(settings.sync_database_url)
    inspector = inspect(engine)

    print("=================================================================")
    print(f" PostgreSQL Schema Report: {settings.DB_NAME} ")
    print("=================================================================")

    tables = inspector.get_table_names()
    print(f"Total Tables ({len(tables)}): {', '.join(sorted(tables))}\n")

    for table in sorted(tables):
        print(f"--- Table: {table} ---")
        columns = inspector.get_columns(table)
        print(f"  Columns ({len(columns)}):")
        for col in columns:
            col_type = str(col['type'])
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get('default') else ""
            print(f"    - {col['name']}: {col_type} {nullable}{default}")

        pks = inspector.get_pk_constraint(table)
        if pks and pks.get('constrained_columns'):
            print(f"  Primary Key: {pks['constrained_columns']}")

        fks = inspector.get_foreign_keys(table)
        if fks:
            print("  Foreign Keys:")
            for fk in fks:
                print(f"    - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']} (ondelete={fk.get('options', {}).get('ondelete')})")

        uqs = inspector.get_unique_constraints(table)
        if uqs:
            print("  Unique Constraints:")
            for uq in uqs:
                print(f"    - {uq['name']}: {uq['column_names']}")

        check_constraints = inspector.get_check_constraints(table)
        if check_constraints:
            print("  Check Constraints:")
            for chk in check_constraints:
                print(f"    - {chk['name']}: {chk['sqltext']}")

        indexes = inspector.get_indexes(table)
        if indexes:
            print("  Indexes:")
            for idx in indexes:
                unique_flag = " UNIQUE" if idx.get('unique') else ""
                print(f"    - {idx['name']}{unique_flag}: {idx['column_names']}")

        print()

    # Query PostgreSQL Triggers
    with engine.connect() as conn:
        print("--- Active PostgreSQL Database Triggers ---")
        trigger_query = text("""
            SELECT event_object_table AS table_name,
                   trigger_name,
                   action_timing,
                   event_manipulation,
                   action_statement
            FROM information_schema.triggers
            WHERE trigger_schema = 'public'
            ORDER BY event_object_table, trigger_name;
        """)
        triggers = conn.execute(trigger_query).fetchall()
        for trg in triggers:
            print(f"  - Table: {trg.table_name} | Trigger: {trg.trigger_name} | Timing: {trg.action_timing} {trg.event_manipulation}")

    engine.dispose()


if __name__ == "__main__":
    inspect_database_schema()
