"""Authentication & Role-Based Access Control API Endpoints."""

from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_current_user,
    require_customer,
    require_staff,
    require_admin,
    verify_customer_ownership,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_WINDOW = timedelta(minutes=15)


def _recent_login_failures(db: Session, identifier: str) -> int:
    """Count failed logins for an identifier inside the lockout window (from the append-only audit trail)."""
    since = datetime.now(timezone.utc) - LOGIN_LOCKOUT_WINDOW
    return db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "AUTH_LOGIN_FAILURE",
            AuditLog.entity_id == identifier[:50],
            AuditLog.created_at >= since,
        )
    ) or 0


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new customer account",
)
def register_customer(
    data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new customer profile.

    Role is strictly restricted to CUSTOMER. Public requests cannot grant
    privileged roles.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    new_user = AuthService.register_customer(db, data)

    # Append audit trail for customer registration
    AuditService.log_event(
        action="AUTH_REGISTER",
        entity_type="USER",
        entity_id=str(new_user.id),
        actor_user_id=new_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        metadata={"username": new_user.username, "role": new_user.role},
        db=db,
        independent_txn=True,
    )

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT access token",
)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate with username or email + password, returning a signed 60-minute JWT."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if _recent_login_failures(db, data.username_or_email) >= LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again in 15 minutes.",
        )

    user = AuthService.authenticate_user(db, data.username_or_email, data.password)
    if not user:
        # Record failed authentication audit log (passwords/tokens redacted by AuditService)
        AuditService.log_event(
            action="AUTH_LOGIN_FAILURE",
            entity_type="USER",
            entity_id=data.username_or_email[:50],
            actor_user_id=None,
            ip_address=client_ip,
            user_agent=user_agent,
            metadata={"identifier": data.username_or_email},
            db=db,
            independent_txn=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username, email, or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue signed access token
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        username=user.username,
    )

    # Record successful authentication audit log
    AuditService.log_event(
        action="AUTH_LOGIN_SUCCESS",
        entity_type="USER",
        entity_id=str(user.id),
        actor_user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        metadata={"username": user.username, "role": user.role},
        db=db,
        independent_txn=True,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@router.post(
    "/logout",
    summary="Audit logout event",
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Audit user logout."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    AuditService.log_event(
        action="AUTH_LOGOUT",
        entity_type="USER",
        entity_id=str(current_user.id),
        actor_user_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        metadata={"username": current_user.username},
        db=db,
        independent_txn=True,
    )

    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Fetch authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile and customer attributes for the current authenticated user."""
    return current_user


# ------------------------------------------------------------------------------
# Demonstration & Verification Endpoints (Guarded by RBAC dependencies)
# ------------------------------------------------------------------------------

@router.get(
    "/demo/customer-only",
    summary="Demonstration endpoint accessible strictly to CUSTOMER role",
)
def customer_only_demo(current_user: User = Depends(require_customer)):
    return {
        "message": "Customer access granted",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }


@router.get(
    "/demo/staff-only",
    summary="Demonstration endpoint accessible to STAFF and ADMIN roles",
)
def staff_only_demo(current_user: User = Depends(require_staff)):
    return {
        "message": "Staff access granted",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }


@router.get(
    "/demo/admin-only",
    summary="Demonstration endpoint accessible strictly to ADMIN role",
)
def admin_only_demo(current_user: User = Depends(require_admin)):
    return {
        "message": "Admin access granted",
        "user_id": str(current_user.id),
        "role": current_user.role,
    }


@router.get(
    "/demo/customer-resource/{customer_id}",
    summary="Demonstration endpoint verifying customer record isolation",
)
def customer_resource_isolation_demo(
    customer_id: uuid.UUID,
    verified_user: User = Depends(verify_customer_ownership),
):
    return {
        "message": "Customer resource access permitted",
        "requested_customer_id": str(customer_id),
        "accessor_user_id": str(verified_user.id),
        "accessor_role": verified_user.role,
    }
