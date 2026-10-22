"""Product Service for FinLedger-AI Financial Products Catalogue.

Manages simulated product creation, listing, filtering, and initial seeding.
"""

from decimal import Decimal
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import FinancialProduct
from app.schemas.product import ProductCreateRequest
from app.services.audit_service import AuditService


class ProductConflictError(Exception):
    """Raised when creating a product with an existing code."""
    pass


class ProductNotFoundError(Exception):
    """Raised when product cannot be found."""
    pass


DEFAULT_PRODUCTS = [
    {
        "name": "12-Month Standard Fixed Deposit",
        "code": "FD-12M-STD",
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": Decimal("7.10"),
        "min_amount": Decimal("10000.00"),
        "term_months": 12,
        "is_active": True,
    },
    {
        "name": "36-Month High-Yield Fixed Deposit",
        "code": "FD-36M-HY",
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": Decimal("7.50"),
        "min_amount": Decimal("25000.00"),
        "term_months": 36,
        "is_active": True,
    },
    {
        "name": "24-Month Systematic Recurring Deposit",
        "code": "RD-24M-SYS",
        "product_type": "RECURRING_DEPOSIT",
        "annual_yield_rate": Decimal("6.80"),
        "min_amount": Decimal("5000.00"),
        "term_months": 24,
        "is_active": True,
    },
    {
        "name": "Simulated Liquid Debt Growth Fund",
        "code": "MF-LIQ-GROWTH",
        "product_type": "MUTUAL_FUND",
        "annual_yield_rate": Decimal("6.50"),
        "min_amount": Decimal("1000.00"),
        "term_months": 3,
        "is_active": True,
    },
    {
        "name": "182-Day Sovereign Treasury Bill",
        "code": "TB-182D-SOV",
        "product_type": "TREASURY_BILL",
        "annual_yield_rate": Decimal("6.90"),
        "min_amount": Decimal("10000.00"),
        "term_months": 6,
        "is_active": True,
    },
]


class ProductService:
    """Service managing financial product lifecycle and catalogue inspection."""

    @staticmethod
    def list_products(
        db: Session,
        product_type: str | None = None,
        is_active: bool | None = True,
        skip: int = 0,
        limit: int = 50,
    ) -> list[FinancialProduct]:
        """Fetch list of financial products with optional filters and pagination."""
        stmt = select(FinancialProduct)
        if product_type is not None:
            stmt = stmt.where(FinancialProduct.product_type == product_type)
        if is_active is not None:
            stmt = stmt.where(FinancialProduct.is_active == is_active)
        stmt = stmt.order_by(FinancialProduct.min_amount.asc(), FinancialProduct.name.asc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_product_by_id(db: Session, product_id: uuid.UUID) -> FinancialProduct | None:
        """Fetch a financial product by primary key."""
        stmt = select(FinancialProduct).where(FinancialProduct.id == product_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_product_by_code(db: Session, code: str) -> FinancialProduct | None:
        """Fetch a financial product by unique code."""
        stmt = select(FinancialProduct).where(FinancialProduct.code == code)
        return db.scalars(stmt).first()

    @staticmethod
    def create_product(
        db: Session,
        product_in: ProductCreateRequest,
        actor_user_id: uuid.UUID | None = None,
    ) -> FinancialProduct:
        """Create a new financial product in the catalogue."""
        existing = ProductService.get_product_by_code(db, product_in.code)
        if existing:
            raise ProductConflictError(f"Product with code '{product_in.code}' already exists")

        product = FinancialProduct(
            name=product_in.name,
            code=product_in.code,
            product_type=product_in.product_type,
            annual_yield_rate=product_in.annual_yield_rate,
            min_amount=product_in.min_amount,
            term_months=product_in.term_months,
            is_active=product_in.is_active,
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        AuditService.log_event(
            action="PRODUCT_CREATED",
            entity_type="PRODUCT",
            entity_id=str(product.id),
            actor_user_id=actor_user_id,
            metadata={
                "code": product.code,
                "name": product.name,
                "product_type": product.product_type,
                "annual_yield_rate": str(product.annual_yield_rate),
            },
            db=db,
            independent_txn=True,
        )

        return product

    @staticmethod
    def seed_default_products(db: Session) -> list[FinancialProduct]:
        """Seed standard financial products if the catalogue is empty."""
        seeded = []
        for p_data in DEFAULT_PRODUCTS:
            stmt = select(FinancialProduct).where(FinancialProduct.code == p_data["code"])
            prod = db.scalars(stmt).first()
            if not prod:
                prod = FinancialProduct(**p_data)
                db.add(prod)
                seeded.append(prod)
        if seeded:
            db.commit()
            for p in seeded:
                db.refresh(p)
        return seeded
