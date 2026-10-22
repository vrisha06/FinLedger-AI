"""Role-Based Access Control (RBAC) and customer resource boundary tests."""

import uuid
import pytest
from app.core.security import get_password_hash
from app.models.user import User
from app.models.customer import Customer


def test_unauthenticated_access_denied(client):
    """Verify unauthenticated requests to protected routes return 401 Unauthorized."""
    endpoints = [
        "/api/v1/auth/demo/customer-only",
        "/api/v1/auth/demo/staff-only",
        "/api/v1/auth/demo/admin-only",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated request to {ep}"


def test_customer_role_permissions(client, test_customer_user, auth_headers_factory):
    """Verify CUSTOMER role can access customer route but is blocked from staff and admin routes."""
    headers = auth_headers_factory(test_customer_user)

    # Customer route -> 200 OK
    resp_cust = client.get("/api/v1/auth/demo/customer-only", headers=headers)
    assert resp_cust.status_code == 200
    assert resp_cust.json()["role"] == "CUSTOMER"

    # Staff route -> 403 Forbidden
    resp_staff = client.get("/api/v1/auth/demo/staff-only", headers=headers)
    assert resp_staff.status_code == 403
    assert "Forbidden" in resp_staff.json()["detail"]

    # Admin route -> 403 Forbidden
    resp_admin = client.get("/api/v1/auth/demo/admin-only", headers=headers)
    assert resp_admin.status_code == 403
    assert "Forbidden" in resp_admin.json()["detail"]


def test_staff_role_permissions(client, test_staff_user, auth_headers_factory):
    """Verify STAFF role can access staff route but is blocked from customer and admin routes."""
    headers = auth_headers_factory(test_staff_user)

    # Customer route -> 403 Forbidden
    resp_cust = client.get("/api/v1/auth/demo/customer-only", headers=headers)
    assert resp_cust.status_code == 403

    # Staff route -> 200 OK
    resp_staff = client.get("/api/v1/auth/demo/staff-only", headers=headers)
    assert resp_staff.status_code == 200
    assert resp_staff.json()["role"] == "STAFF"

    # Admin route -> 403 Forbidden
    resp_admin = client.get("/api/v1/auth/demo/admin-only", headers=headers)
    assert resp_admin.status_code == 403


def test_admin_role_permissions(client, test_admin_user, auth_headers_factory):
    """Verify ADMIN role can access admin route and staff route."""
    headers = auth_headers_factory(test_admin_user)

    # Admin route -> 200 OK
    resp_admin = client.get("/api/v1/auth/demo/admin-only", headers=headers)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["role"] == "ADMIN"

    # Staff route -> 200 OK (staff routes permit STAFF or ADMIN)
    resp_staff = client.get("/api/v1/auth/demo/staff-only", headers=headers)
    assert resp_staff.status_code == 200


def test_customer_resource_boundary_isolation(
    client,
    test_customer_user,
    test_staff_user,
    test_admin_user,
    auth_headers_factory,
    db_session,
):
    """Verify customers cannot access other customers' records, while Staff/Admin can inspect."""
    # Create a secondary customer
    user_two = User(
        username="customer_two",
        email="customer2@example.com",
        password_hash=get_password_hash("Password123!"),
        role="CUSTOMER",
        is_active=True,
    )
    db_session.add(user_two)
    db_session.flush()

    customer_two = Customer(
        user_id=user_two.id,
        full_name="Customer Two Name",
        phone="+91-9123456789",
        pan_number="ABCDE2222Y",
        kyc_status="VERIFIED",
    )
    db_session.add(customer_two)
    db_session.flush()

    headers_one = auth_headers_factory(test_customer_user)
    headers_staff = auth_headers_factory(test_staff_user)
    headers_admin = auth_headers_factory(test_admin_user)

    # 1. Customer One accesses their own resource -> 200 OK
    own_resp = client.get(
        f"/api/v1/auth/demo/customer-resource/{test_customer_user.customer.id}",
        headers=headers_one,
    )
    assert own_resp.status_code == 200

    # 2. Customer One attempts to access Customer Two's resource -> 403 Forbidden
    other_resp = client.get(
        f"/api/v1/auth/demo/customer-resource/{customer_two.id}",
        headers=headers_one,
    )
    assert other_resp.status_code == 403
    assert "cannot access another customer's resources" in other_resp.json()["detail"]

    # 3. Staff accesses Customer Two's resource for investigation -> 200 OK
    staff_resp = client.get(
        f"/api/v1/auth/demo/customer-resource/{customer_two.id}",
        headers=headers_staff,
    )
    assert staff_resp.status_code == 200

    # 4. Admin accesses Customer Two's resource -> 200 OK
    admin_resp = client.get(
        f"/api/v1/auth/demo/customer-resource/{customer_two.id}",
        headers=headers_admin,
    )
    assert admin_resp.status_code == 200
