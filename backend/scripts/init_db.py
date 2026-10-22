"""Database Provisioning and Seeding Script for FinLedger-AI."""

import sys
from decimal import Decimal
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings


def create_databases_if_missing():
    """Connect to default postgres DB and create finledger and finledger_test if they don't exist."""
    print(f"Connecting to PostgreSQL at {settings.DB_HOST}:{settings.DB_PORT} as {settings.DB_USER}...")
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        dbname="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    for db_name in [settings.DB_NAME, settings.DB_TEST_NAME]:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        if not cursor.fetchone():
            print(f"Creating database: {db_name}...")
            cursor.execute(f'CREATE DATABASE "{db_name}" ENCODING "UTF8";')
            print(f"Database '{db_name}' created successfully.")
        else:
            print(f"Database '{db_name}' already exists.")

    cursor.close()
    conn.close()


def seed_clearing_account_for_engine(engine_instance, db_label="Main"):
    """Ensure internal system clearing account (INR-SYS-CLEARING) exists on target engine."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models.account import Account

    with Session(engine_instance) as session:
        stmt = select(Account).where(Account.account_number == settings.CLEARING_ACCOUNT_NUMBER)
        clearing_acc = session.scalars(stmt).first()
        if not clearing_acc:
            print(f"[{db_label}] Seeding internal clearing account: {settings.CLEARING_ACCOUNT_NUMBER}...")
            clearing_acc = Account(
                customer_id=None,
                account_number=settings.CLEARING_ACCOUNT_NUMBER,
                account_type="INTERNAL_CLEARING",
                currency=settings.DEFAULT_CURRENCY,
                cached_balance=Decimal("0.00"),
                status="ACTIVE",
                version=1,
            )
            session.add(clearing_acc)
            session.commit()
            print(f"[{db_label}] Internal clearing account '{settings.CLEARING_ACCOUNT_NUMBER}' created.")
        else:
            print(f"[{db_label}] Internal clearing account '{settings.CLEARING_ACCOUNT_NUMBER}' already exists.")


def seed_system_clearing_account():
    """Seed clearing accounts in both development and test databases."""
    from sqlalchemy import create_engine
    from app.core.database import engine

    # Seed main database
    seed_clearing_account_for_engine(engine, "finledger")

    # Seed test database
    test_engine = create_engine(settings.sync_test_database_url)
    seed_clearing_account_for_engine(test_engine, "finledger_test")
    test_engine.dispose()


if __name__ == "__main__":
    # Fresh machines must migrate between these steps: seeding needs the accounts table.
    #   --create-only: create finledger / finledger_test databases
    #   --seed-only:   seed INR-SYS-CLEARING (after `alembic upgrade head`)
    if "--seed-only" not in sys.argv:
        create_databases_if_missing()
    if "--create-only" not in sys.argv:
        seed_system_clearing_account()
