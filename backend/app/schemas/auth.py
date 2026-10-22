"""Authentication and user management Pydantic v2 schemas."""

from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    """Payload for POST /api/v1/auth/login."""

    username_or_email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Username or email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=72,
        description="User plaintext password (max 72 bytes)",
    )


class RegisterRequest(BaseModel):
    """Payload for public customer registration POST /api/v1/auth/register.

    Role is intentionally excluded from the request schema; all registrations
    are strictly assigned the CUSTOMER role server-side.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username containing alphanumeric characters, underscores, or hyphens",
    )
    email: str = Field(
        ...,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="Valid email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Plaintext password (8-72 characters)",
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Customer legal full name",
    )
    phone: str | None = Field(
        None,
        max_length=20,
        description="Contact telephone number",
    )
    pan_number: str | None = Field(
        None,
        max_length=10,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
        description="Indian Permanent Account Number (10 alphanumeric chars)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce basic password complexity."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes")
        return v


class CustomerProfileResponse(BaseModel):
    """Customer profile summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str | None = None
    pan_number: str | None = None
    kyc_status: str
    created_at: datetime


class UserResponse(BaseModel):
    """Safe user profile response; password_hash is never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    customer: CustomerProfileResponse | None = None


class TokenResponse(BaseModel):
    """JWT Bearer token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
