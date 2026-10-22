"""Seed baseline demonstration accounts for FinLedger-AI.

Generates the required demo accounts:
- Customer: rahul_sharma (Role: CUSTOMER, with linked 1:1 Customer profile)
- Staff:    priya_investigator (Role: STAFF)
- Admin:    admin_system (Role: ADMIN)

Passwords are secure bcrypt hashes (cost factor 12).
"""

import os
import sys
from pathlib import Path
import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.models.customer import Customer

DEFAULT_SEED_PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "Password123!")

DEMO_USERS = [
    {
        "username": "rahul_sharma",
        "email": "rahul.sharma@example.com",
        "role": "CUSTOMER",
        "is_active": True,
        "customer": {
            "full_name": "Rahul Sharma",
            "phone": "+91-9876543210",
            "pan_number": "ABCDE1234F",
            "kyc_status": "VERIFIED",
        },
    },
    {
        "username": "priya_investigator",
        "email": "priya.investigator@finledger.internal",
        "role": "STAFF",
        "is_active": True,
        "customer": None,
    },
    {
        "username": "admin_system",
        "email": "admin@finledger.internal",
        "role": "ADMIN",
        "is_active": True,
        "customer": None,
    },
]


def seed_users_for_engine(engine_instance, db_label="Main"):
    """Seed demonstration accounts on target database engine if not present."""
    password_hash = get_password_hash(DEFAULT_SEED_PASSWORD)

    with Session(engine_instance) as session:
        for user_data in DEMO_USERS:
            stmt = select(User).where(User.username == user_data["username"])
            existing_user = session.scalars(stmt).first()

            if not existing_user:
                print(f"[{db_label}] Seeding demo user: {user_data['username']} (Role: {user_data['role']})...")
                new_user = User(
                    id=uuid.uuid4(),
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=password_hash,
                    role=user_data["role"],
                    is_active=user_data["is_active"],
                )
                session.add(new_user)
                session.flush()

                if user_data["customer"]:
                    cust_info = user_data["customer"]
                    customer = Customer(
                        id=uuid.uuid4(),
                        user_id=new_user.id,
                        full_name=cust_info["full_name"],
                        phone=cust_info["phone"],
                        pan_number=cust_info["pan_number"],
                        kyc_status=cust_info["kyc_status"],
                    )
                    session.add(customer)

                session.commit()
                print(f"[{db_label}]   -> Successfully created {user_data['username']}.")
            else:
                print(f"[{db_label}] Demo user '{user_data['username']}' already exists.")


def main():
    print("=" * 60)
    print("FinLedger-AI Demonstration User Seeding")
    print("=" * 60)

    # Seed main database
    main_engine = create_engine(settings.sync_database_url)
    seed_users_for_engine(main_engine, "finledger")
    main_engine.dispose()

    # Seed test database
    test_engine = create_engine(settings.sync_test_database_url)
    seed_users_for_engine(test_engine, "finledger_test")
    test_engine.dispose()

    print("=" * 60)
    print("User seeding completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
