"""Authentication service implementing customer registration and credential verification."""

from datetime import datetime, timezone
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.customer import Customer
from app.schemas.auth import RegisterRequest


class AuthService:
    """Service handling credential verification, registration, and user retrieval."""

    @staticmethod
    def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
        """Fetch user by primary key with customer profile joined."""
        stmt = (
            select(User)
            .options(joinedload(User.customer))
            .where(User.id == user_id)
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_user_by_username_or_email(db: Session, identifier: str) -> User | None:
        """Fetch user by username or email (case-insensitive) with customer profile joined."""
        clean_identifier = identifier.strip().lower()
        stmt = (
            select(User)
            .options(joinedload(User.customer))
            .where(
                or_(
                    func.lower(User.username) == clean_identifier,
                    func.lower(User.email) == clean_identifier,
                )
            )
        )
        return db.scalars(stmt).first()

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        username_or_email: str,
        password: str,
    ) -> User | None:
        """Verify user credentials and active status.

        Returns User on success, or None on invalid credentials / inactive account.
        Timing-safe password comparison is handled by Passlib/bcrypt.
        """
        user = cls.get_user_by_username_or_email(db, username_or_email)
        if not user:
            # Constant-time dummy verification could be used; verify_password handles empty gracefully
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @classmethod
    def register_customer(cls, db: Session, data: RegisterRequest) -> User:
        """Register a new customer account.

        Role is strictly assigned to 'CUSTOMER'. Registration cannot grant
        privileged STAFF or ADMIN roles.
        """
        # Check for existing username or email conflict
        clean_username = data.username.strip().lower()
        clean_email = data.email.strip().lower()

        conflict_stmt = select(User).where(
            or_(
                func.lower(User.username) == clean_username,
                func.lower(User.email) == clean_email,
            )
        )
        existing_user = db.scalars(conflict_stmt).first()
        if existing_user:
            # Return generic conflict message to prevent account enumeration
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this username or email already exists",
            )

        # Hash password using bcrypt (work factor 12)
        hashed_password = get_password_hash(data.password)

        new_user = User(
            id=uuid.uuid4(),
            username=data.username.strip(),
            email=data.email.strip().lower(),
            password_hash=hashed_password,
            role="CUSTOMER",  # Server-enforced: cannot be elevated via registration
            is_active=True,
        )
        db.add(new_user)
        db.flush()

        # Create linked 1:1 Customer record
        customer = Customer(
            id=uuid.uuid4(),
            user_id=new_user.id,
            full_name=data.full_name.strip(),
            phone=data.phone.strip() if data.phone else None,
            pan_number=data.pan_number.strip().upper() if data.pan_number else None,
            kyc_status="VERIFIED",
        )
        db.add(customer)
        db.flush()

        # Provision initial primary SAVINGS account with INR 0.00 cached balance
        from app.services.account_service import AccountService
        AccountService.provision_customer_account(db, customer.id, account_type="SAVINGS")
        db.commit()

        # Re-query with eager load to return complete profile
        return cls.get_user_by_id(db, new_user.id)
