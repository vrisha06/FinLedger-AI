"""Pytest fixtures for FinLedger-AI testing against real PostgreSQL 16."""

import sys
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.models import (
    Base,
    User,
    Customer,
    Account,
    TransferRequest,
    LedgerTransaction,
    LedgerEntry,
    AuditLog,
    FraudPrediction,
    FinancialProduct,
    Investment,
)

# Connect specifically to the test database
test_engine = create_engine(
    settings.sync_test_database_url,
    pool_pre_ping=True,
    echo=False,
)
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="session")
def engine():
    """Session-scoped test engine."""
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def clean_test_database_session(engine):
    """Ensure finledger_test starts clean and ends clean with internal clearing account seeded."""
    from sqlalchemy import text
    from scripts.init_db import seed_clearing_account_for_engine
    from scripts.seed_products import seed_products_for_engine

    def _truncate_and_reseed():
        with engine.connect() as conn:
            # Append-only tables block TRUNCATE unless a reset explicitly opts in for this transaction
            conn.execute(text("SET LOCAL finledger.allow_truncate = 'on'"))
            conn.execute(
                text(
                    "TRUNCATE simulation_runs, case_events, disputes, graph_findings, "
                    "investigation_notes, saved_payees, payee_edges, audit_logs, "
                    "fraud_predictions, transfer_requests, ledger_entries, "
                    "ledger_transactions, investments, financial_products, "
                    "accounts, customers, users CASCADE;"
                )
            )
            conn.commit()
        seed_clearing_account_for_engine(engine, "Test")
        seed_products_for_engine(engine, "Test")

    _truncate_and_reseed()
    yield
    _truncate_and_reseed()


@pytest.fixture(scope="function")
def db_session(engine):
    """Provides an isolated database session rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def raw_db_session(engine):
    """Provides a session that commits to test deferred constraint triggers and rolls back changes after."""
    session = TestSessionLocal()
    yield session
    # Cleanup any created test rows
    session.rollback()
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Fixture providing a test customer user."""
    user = User(
        username="test_customer_1",
        email="customer1@example.com",
        password_hash="$2b$12$e80A1N...samplehash",
        role="CUSTOMER",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def sample_customer(db_session, sample_user):
    """Fixture providing a customer profile."""
    customer = Customer(
        user_id=sample_user.id,
        full_name="Test Customer One",
        phone="+919876543210",
        pan_number="ABCDE1234F",
        kyc_status="VERIFIED",
    )
    db_session.add(customer)
    db_session.flush()
    return customer


@pytest.fixture
def sample_account(db_session, sample_customer):
    """Fixture providing a customer savings account with ₹10,000.00 cached balance."""
    account = Account(
        customer_id=sample_customer.id,
        account_number="INR-ACC-TEST-001",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("10000.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture
def sample_dest_account(db_session, sample_customer):
    """Fixture providing a secondary account with ₹5,000.00 cached balance."""
    account = Account(
        customer_id=sample_customer.id,
        account_number="INR-ACC-TEST-002",
        account_type="SAVINGS",
        currency="INR",
        cached_balance=Decimal("5000.00"),
        status="ACTIVE",
        version=1,
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture
def clearing_account(db_session):
    """Fixture fetching or creating the internal clearing account."""
    stmt = select(Account).where(Account.account_number == settings.CLEARING_ACCOUNT_NUMBER)
    account = db_session.scalars(stmt).first()
    if not account:
        account = Account(
            customer_id=None,
            account_number=settings.CLEARING_ACCOUNT_NUMBER,
            account_type="INTERNAL_CLEARING",
            currency="INR",
            cached_balance=Decimal("0.00"),
            status="ACTIVE",
            version=1,
        )
        db_session.add(account)
        db_session.flush()
    return account


@pytest.fixture
def client(db_session):
    """FastAPI TestClient fixture wired to the isolated db_session."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers_factory():
    """Factory fixture returning Bearer auth headers for a given user."""
    from app.core.security import create_access_token

    def _create_headers(user: User) -> dict[str, str]:
        token = create_access_token(
            subject=user.id,
            role=user.role,
            username=user.username,
        )
        return {"Authorization": f"Bearer {token}"}

    return _create_headers


@pytest.fixture
def test_customer_user(db_session):
    """Fixture providing a test customer user with linked customer profile."""
    from app.core.security import get_password_hash

    stmt = select(User).where(User.username == "test_customer_auth")
    user = db_session.scalars(stmt).first()
    if not user:
        user = User(
            username="test_customer_auth",
            email="test_customer_auth@example.com",
            password_hash=get_password_hash("Password123!"),
            role="CUSTOMER",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        customer = Customer(
            user_id=user.id,
            full_name="Test Customer Auth",
            phone="+91-9988776655",
            pan_number="ABCDE9999Z",
            kyc_status="VERIFIED",
        )
        db_session.add(customer)
        db_session.flush()
    return user


@pytest.fixture
def test_staff_user(db_session):
    """Fixture providing a test staff user."""
    from app.core.security import get_password_hash

    stmt = select(User).where(User.username == "test_staff_auth")
    user = db_session.scalars(stmt).first()
    if not user:
        user = User(
            username="test_staff_auth",
            email="test_staff_auth@finledger.internal",
            password_hash=get_password_hash("Password123!"),
            role="STAFF",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
    return user


@pytest.fixture
def test_admin_user(db_session):
    """Fixture providing a test administrator user."""
    from app.core.security import get_password_hash

    stmt = select(User).where(User.username == "test_admin_auth")
    user = db_session.scalars(stmt).first()
    if not user:
        user = User(
            username="test_admin_auth",
            email="test_admin_auth@finledger.internal",
            password_hash=get_password_hash("Password123!"),
            role="ADMIN",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
    return user
