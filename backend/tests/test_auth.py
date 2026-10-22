"""Comprehensive tests for authentication, password security, and JWT tokens in FinLedger-AI."""

from datetime import timedelta
from decimal import Decimal
import pytest
import jwt
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.models.user import User


# ==============================================================================
# 1. Password Security Unit Tests
# ==============================================================================

def test_password_hashing_and_verification():
    """Verify bcrypt work factor 12 hashing and verification."""
    password = "MySecurePassword123!"
    hashed = get_password_hash(password)

    # Assert bcrypt work factor 12 format ($2b$12$...)
    assert hashed.startswith("$2b$12$"), "Hash must be bcrypt with work factor 12"
    assert hashed != password, "Plaintext password must never equal hash"
    assert verify_password(password, hashed) is True, "Valid password must verify against hash"
    assert verify_password("WrongPassword!", hashed) is False, "Wrong password must be rejected"
    assert verify_password("", hashed) is False, "Empty password must be rejected"


def test_empty_password_rejected():
    """Verify empty password raises ValueError during hash generation."""
    with pytest.raises(ValueError, match="Password cannot be empty"):
        get_password_hash("")


def test_excessive_password_length_rejected():
    """Verify password exceeding 72 bytes is rejected to prevent silent truncation."""
    long_pw = "A" * 73
    with pytest.raises(ValueError, match="Password exceeds maximum length of 72 bytes"):
        get_password_hash(long_pw)


# ==============================================================================
# 2. JWT Access Token Unit Tests
# ==============================================================================

def test_jwt_issuance_and_decoding():
    """Verify token encoding, claims preservation, and decoding."""
    token = create_access_token(
        subject="123e4567-e89b-12d3-a456-426614174000",
        role="CUSTOMER",
        username="test_user",
    )
    payload = decode_access_token(token)

    assert payload["sub"] == "123e4567-e89b-12d3-a456-426614174000"
    assert payload["role"] == "CUSTOMER"
    assert payload["username"] == "test_user"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload


def test_jwt_expired_token_rejected():
    """Verify expired token raises ExpiredSignatureError."""
    expired_token = create_access_token(
        subject="123e4567-e89b-12d3-a456-426614174000",
        role="CUSTOMER",
        username="test_user",
        expires_delta=timedelta(seconds=-10),  # Expired 10 seconds ago
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_jwt_tampered_signature_rejected():
    """Verify modified payload or signature raises InvalidTokenError."""
    token = create_access_token(
        subject="123e4567-e89b-12d3-a456-426614174000",
        role="CUSTOMER",
        username="test_user",
    )
    # Alter last characters of token
    tampered_token = token[:-4] + "AAAA"
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_jwt_wrong_secret_key_rejected():
    """Verify token signed with different key fails verification."""
    token = create_access_token(
        subject="123e4567-e89b-12d3-a456-426614174000",
        role="CUSTOMER",
        username="test_user",
    )
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "wrong_signing_key_32_bytes_long_12345", algorithms=[settings.ALGORITHM])


# ==============================================================================
# 3. Authentication API Integration Tests
# ==============================================================================

def test_customer_registration_success(client):
    """Verify customer registration creates user and customer records with CUSTOMER role."""
    reg_data = {
        "username": "ananya_singh",
        "email": "ananya.singh@example.com",
        "password": "SecurePassword123!",
        "full_name": "Ananya Singh",
        "phone": "+91-9876543211",
        "pan_number": "ABCDE5678G",
    }
    response = client.post("/api/v1/auth/register", json=reg_data)
    assert response.status_code == 201

    body = response.json()
    assert body["username"] == "ananya_singh"
    assert body["email"] == "ananya.singh@example.com"
    assert body["role"] == "CUSTOMER"
    assert body["is_active"] is True
    assert "password_hash" not in body, "Password hash must never leak in API response"
    assert body["customer"] is not None
    assert body["customer"]["full_name"] == "Ananya Singh"
    assert body["customer"]["pan_number"] == "ABCDE5678G"


def test_registration_prevents_role_elevation(client):
    """Verify public registration cannot specify or elevate role."""
    reg_data = {
        "username": "attacker_user",
        "email": "attacker@example.com",
        "password": "SecurePassword123!",
        "full_name": "Attacker Name",
        "role": "ADMIN",  # Attempt to inject role
    }
    response = client.post("/api/v1/auth/register", json=reg_data)
    assert response.status_code == 201

    body = response.json()
    assert body["role"] == "CUSTOMER", "Server must strictly enforce CUSTOMER role on public registration"


def test_registration_duplicate_username_conflict(client):
    """Verify duplicate username returns 409 Conflict."""
    reg_data = {
        "username": "dup_user",
        "email": "user1@example.com",
        "password": "SecurePassword123!",
        "full_name": "User One",
    }
    resp1 = client.post("/api/v1/auth/register", json=reg_data)
    assert resp1.status_code == 201

    # Attempt same username with different email
    reg_data2 = {
        "username": "dup_user",
        "email": "user2@example.com",
        "password": "SecurePassword123!",
        "full_name": "User Two",
    }
    resp2 = client.post("/api/v1/auth/register", json=reg_data2)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_registration_duplicate_email_conflict(client):
    """Verify duplicate email returns 409 Conflict."""
    reg_data = {
        "username": "user_a",
        "email": "shared@example.com",
        "password": "SecurePassword123!",
        "full_name": "User A",
    }
    resp1 = client.post("/api/v1/auth/register", json=reg_data)
    assert resp1.status_code == 201

    reg_data2 = {
        "username": "user_b",
        "email": "shared@example.com",
        "password": "SecurePassword123!",
        "full_name": "User B",
    }
    resp2 = client.post("/api/v1/auth/register", json=reg_data2)
    assert resp2.status_code == 409


def test_login_success(client, test_customer_user):
    """Verify login with valid credentials returns signed token and user profile."""
    login_data = {
        "username_or_email": test_customer_user.username,
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200

    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["username"] == test_customer_user.username
    assert body["user"]["role"] == "CUSTOMER"
    assert "password_hash" not in body["user"]

    # Decode and verify token
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_customer_user.id)
    assert payload["role"] == "CUSTOMER"


def test_login_with_email_success(client, test_customer_user):
    """Verify login using email address returns token."""
    login_data = {
        "username_or_email": test_customer_user.email,
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_credentials_rejected(client, test_customer_user):
    """Verify invalid password returns generic 401 Unauthorized."""
    login_data = {
        "username_or_email": test_customer_user.username,
        "password": "WrongPassword123!",
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401
    assert "Invalid username, email, or password" in response.json()["detail"]


def test_login_nonexistent_user_rejected(client):
    """Verify nonexistent username returns generic 401 Unauthorized."""
    login_data = {
        "username_or_email": "nonexistent_user_404",
        "password": "SomePassword123!",
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401
    assert "Invalid username, email, or password" in response.json()["detail"]


def test_login_inactive_user_rejected(client, db_session):
    """Verify deactivated account is denied login."""
    inactive_user = User(
        username="inactive_customer",
        email="inactive@example.com",
        password_hash=get_password_hash("Password123!"),
        role="CUSTOMER",
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.flush()

    login_data = {
        "username_or_email": "inactive_customer",
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401


def test_current_user_me_endpoint(client, test_customer_user, auth_headers_factory):
    """Verify GET /api/v1/auth/me returns authenticated user."""
    headers = auth_headers_factory(test_customer_user)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["username"] == test_customer_user.username
    assert body["email"] == test_customer_user.email
    assert body["role"] == "CUSTOMER"
    assert "password_hash" not in body


def test_current_user_me_unauthenticated(client):
    """Verify GET /api/v1/auth/me without token returns 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_logout_endpoint(client, test_customer_user, auth_headers_factory):
    """Verify POST /api/v1/auth/logout succeeds with valid token."""
    headers = auth_headers_factory(test_customer_user)
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


def test_registration_provisions_primary_savings_account(client, db_session):
    """Verify customer registration automatically provisions an active primary SAVINGS account with 0 balance."""
    from sqlalchemy import select
    from app.models.account import Account

    reg_data = {
        "username": "auto_acc_user",
        "email": "auto_acc@example.com",
        "password": "SecurePassword123!",
        "full_name": "Auto Account User",
        "pan_number": "ABCDE9999Z",
        "phone": "+919876500000",
    }
    response = client.post("/api/v1/auth/register", json=reg_data)
    assert response.status_code == 201

    user = db_session.scalars(select(User).where(User.username == "auto_acc_user")).first()
    assert user is not None
    assert user.customer is not None

    accounts = db_session.scalars(
        select(Account).where(Account.customer_id == user.customer.id)
    ).all()
    assert len(accounts) == 1
    savings_acc = accounts[0]
    assert savings_acc.account_type == "SAVINGS"
    assert savings_acc.cached_balance == Decimal("0.00")
    assert savings_acc.currency == "INR"
    assert savings_acc.status == "ACTIVE"
    assert savings_acc.account_number.startswith("INR-SAV-")


def test_customer_can_provision_additional_account(client, auth_headers_factory, test_customer_user, db_session):
    """Verify authenticated customer can provision a secondary account via POST /api/v1/accounts."""
    headers = auth_headers_factory(test_customer_user)
    response = client.post("/api/v1/accounts", json={"account_type": "CURRENT"}, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["account_type"] == "CURRENT"
    assert Decimal(str(data["cached_balance"])) == Decimal("0.00")
    assert data["status"] == "ACTIVE"
    assert data["account_number"].startswith("INR-CUR-")
