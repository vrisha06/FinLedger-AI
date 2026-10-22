"""Integration tests for Financial Products Catalogue.

Verifies:
- Public catalogue listing and category filtering
- Retrieval of individual products by ID
- Staff-only product creation and validation rules
- Duplicate product code rejection (409 Conflict)
- RBAC protection: Customer cannot create products (403 Forbidden)
- Unauthenticated requests rejected (401 Unauthorized)
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select

from app.models.product import FinancialProduct
from app.services.product_service import ProductService


def test_list_products_public(client, db_session):
    """Verify any caller can list active financial products."""
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 4

    codes = [p["code"] for p in products]
    assert "FD-12M-STD" in codes
    assert "MF-LIQ-GROWTH" in codes
    assert "TB-182D-SOV" in codes


def test_list_products_filter_by_type(client, db_session):
    """Verify filtering products by product_type category."""
    response = client.get("/api/v1/products?product_type=FIXED_DEPOSIT")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 1
    for p in products:
        assert p["product_type"] == "FIXED_DEPOSIT"


def test_get_product_by_id(client, db_session):
    """Verify retrieving a specific product by UUID."""
    stmt = select(FinancialProduct).where(FinancialProduct.code == "FD-12M-STD")
    product = db_session.scalars(stmt).first()
    assert product is not None

    response = client.get(f"/api/v1/products/{product.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(product.id)
    assert data["code"] == "FD-12M-STD"
    assert Decimal(str(data["annual_yield_rate"])) == Decimal("7.10")
    assert Decimal(str(data["min_amount"])) == Decimal("10000.00")
    assert data["term_months"] == 12


def test_get_product_not_found(client, db_session):
    """Verify 404 response for non-existent product UUID."""
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/products/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_product_staff_success(client, auth_headers_factory, test_staff_user, db_session):
    """Verify authorized staff can create a new financial product."""
    headers = auth_headers_factory(test_staff_user)
    unique_code = f"FD-SPEC-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "name": "Special Senior Citizen FD 18M",
        "code": unique_code,
        "product_type": "FIXED_DEPOSIT",
        "description": "High yield deposit product for senior citizens",
        "annual_yield_rate": "7.75",
        "min_amount": "25000.00",
        "max_amount": "5000000.00",
        "term_months": 18,
        "is_active": True,
    }

    response = client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == unique_code
    assert Decimal(str(data["annual_yield_rate"])) == Decimal("7.75")
    assert Decimal(str(data["min_amount"])) == Decimal("25000.00")


def test_create_product_customer_forbidden(client, auth_headers_factory, test_customer_user, db_session):
    """Verify regular customer cannot create financial products."""
    headers = auth_headers_factory(test_customer_user)
    payload = {
        "name": "Unauthorized Product",
        "code": "FORBIDDEN-01",
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": "10.00",
        "min_amount": "1000.00",
        "term_months": 12,
    }

    response = client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 403


def test_create_product_unauthenticated(client, db_session):
    """Verify unauthenticated user cannot create financial products."""
    payload = {
        "name": "Unauth Product",
        "code": "UNAUTH-01",
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": "10.00",
        "min_amount": "1000.00",
        "term_months": 12,
    }

    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 401


def test_create_product_duplicate_code_conflict(client, auth_headers_factory, test_staff_user, db_session):
    """Verify duplicate product code returns 409 Conflict."""
    headers = auth_headers_factory(test_staff_user)
    payload = {
        "name": "Duplicate FD",
        "code": "FD-12M-STD",  # Already seeded
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": "7.50",
        "min_amount": "10000.00",
        "term_months": 12,
    }

    response = client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_product_validation_errors(client, auth_headers_factory, test_staff_user, db_session):
    """Verify Pydantic input validation rejects invalid payload attributes."""
    headers = auth_headers_factory(test_staff_user)

    # Invalid product_type
    bad_type = {
        "name": "Bad Type Product",
        "code": "BAD-TYPE-01",
        "product_type": "CRYPTO_CURRENCY",
        "annual_yield_rate": "5.00",
        "min_amount": "1000.00",
        "term_months": 12,
    }
    resp1 = client.post("/api/v1/products", json=bad_type, headers=headers)
    assert resp1.status_code == 422

    # Negative min_amount
    bad_amount = {
        "name": "Bad Amount Product",
        "code": "BAD-AMT-01",
        "product_type": "FIXED_DEPOSIT",
        "annual_yield_rate": "5.00",
        "min_amount": "-1000.00",
        "term_months": 12,
    }
    resp2 = client.post("/api/v1/products", json=bad_amount, headers=headers)
    assert resp2.status_code == 422
