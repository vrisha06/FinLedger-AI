"""Security & Cryptography Utilities for FinLedger-AI.

Implements:
1. Bcrypt password hashing (cost factor 12) via Passlib.
2. Stateless JWT access token issuance and signature verification via PyJWT.
3. Safe token claim validation and rejection of tampered/expired tokens.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Configure passlib to use bcrypt with cost factor (rounds) 12
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def get_password_hash(password: str) -> str:
    """Hash plaintext password using bcrypt with work factor 12."""
    if not password:
        raise ValueError("Password cannot be empty")
    # Bcrypt silently truncates passwords beyond 72 bytes; enforce strict boundary
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password exceeds maximum length of 72 bytes")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str | uuid.UUID,
    role: str,
    username: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Issue a signed JWT access token with standard claims and 60-minute default expiry."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "username": username,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if extra_claims:
        # Prevent collision with reserved claims
        reserved = {"sub", "username", "role", "type", "jti", "iat", "exp"}
        for k, v in extra_claims.items():
            if k not in reserved:
                payload[k] = v

    # Sign using configured secret key and algorithm
    secret_key = settings.SECRET_KEY.get_secret_value()
    token = jwt.encode(payload, secret_key, algorithm=settings.ALGORITHM)
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token signature, expiration, and claims.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token signature invalid or malformed.
        ValueError: Missing or invalid required token claims.
    """
    secret_key = settings.SECRET_KEY.get_secret_value()
    # Explicitly specify allowed algorithms to prevent algorithm substitution attacks
    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[settings.ALGORITHM],
        options={"require": ["sub", "role", "username", "exp", "iat"]},
    )

    if payload.get("type") != "access":
        raise ValueError("Invalid token type; access token required")

    return payload
