"""Script to seed simulated financial products into FinLedger-AI databases."""

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.product_service import ProductService


def seed_products_for_engine(engine_instance, db_label="Main"):
    """Seed financial products into target database engine."""
    with Session(engine_instance) as session:
        seeded = ProductService.seed_default_products(session)
        if seeded:
            print(f"[{db_label}] Seeded {len(seeded)} financial products.")
        else:
            print(f"[{db_label}] Financial products already seeded.")


def main():
    """Seed products into main database and optionally test database."""
    from app.core.database import engine

    print("Seeding financial products...")
    seed_products_for_engine(engine, "finledger")

    if "--test" in sys.argv:
        test_engine = create_engine(settings.sync_test_database_url)
        seed_products_for_engine(test_engine, "finledger_test")
        test_engine.dispose()


if __name__ == "__main__":
    main()
