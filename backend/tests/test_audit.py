"""Tests for Append-Only Audit Logging and Sensitive Data Redaction."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.security import get_password_hash, create_access_token
from app.models.audit import AuditLog
from app.services.audit_service import AuditService, sanitize_audit_metadata


def test_sanitize_metadata_redaction_unit():
    """Verify recursive redaction scrubs sensitive keys and standalone secrets."""
    jwt_sample = create_access_token("123e4567-e89b-12d3-a456-426614174000", "CUSTOMER", "test")
    bcrypt_sample = get_password_hash("SecretPassword123!")

    dirty_payload = {
        "user_id": "123",
        "password": "plain_password",
        "nested": {
            "bearer_token": "token_val",
            "api_key": "key_val",
            "safe_nested": 42,
            "pan_number": "ABCDE1234F",
            "tax_id": "TAX-12345",
        },
        "list_items": [
            {"secret_code": "code123"},
            {"safe_item": "ok"},
            {"pan": "ABCDE1234F"},
        ],
        "random_value_jwt": jwt_sample,
        "random_value_bcrypt": bcrypt_sample,
        "standalone_pan": "ABCDE1234F",
        "harmless_text": "hello_world",
    }

    cleaned = sanitize_audit_metadata(dirty_payload)

    assert cleaned["user_id"] == "123"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["nested"]["bearer_token"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["safe_nested"] == 42
    assert cleaned["nested"]["pan_number"] == "[REDACTED]"
    assert cleaned["nested"]["tax_id"] == "[REDACTED]"
    assert cleaned["list_items"][0]["secret_code"] == "[REDACTED]"
    assert cleaned["list_items"][1]["safe_item"] == "ok"
    assert cleaned["list_items"][2]["pan"] == "[REDACTED]"
    assert cleaned["random_value_jwt"] == "[REDACTED]"
    assert cleaned["random_value_bcrypt"] == "[REDACTED]"
    assert cleaned["standalone_pan"] == "[REDACTED]"
    assert cleaned["harmless_text"] == "hello_world"


def test_audit_event_logged_on_login_success(client, test_customer_user, db_session):
    """Verify successful login generates an AUTH_LOGIN_SUCCESS audit log entry."""
    login_data = {
        "username_or_email": test_customer_user.username,
        "password": "Password123!",
    }
    resp = client.post("/api/v1/auth/login", json=login_data)
    assert resp.status_code == 200

    stmt = select(AuditLog).where(
        AuditLog.action == "AUTH_LOGIN_SUCCESS",
        AuditLog.actor_user_id == test_customer_user.id,
    ).order_by(AuditLog.id.desc())

    # Read from test DB
    log = db_session.scalars(stmt).first()
    assert log is not None
    assert log.action == "AUTH_LOGIN_SUCCESS"
    assert log.entity_type == "USER"
    assert log.entity_id == str(test_customer_user.id)
    assert log.metadata_json["username"] == test_customer_user.username


def test_audit_event_logged_on_login_failure(client, db_session):
    """Verify failed login generates an AUTH_LOGIN_FAILURE audit log entry."""
    login_data = {
        "username_or_email": "unknown_actor_99",
        "password": "WrongPassword!",
    }
    resp = client.post("/api/v1/auth/login", json=login_data)
    assert resp.status_code == 401

    stmt = select(AuditLog).where(
        AuditLog.action == "AUTH_LOGIN_FAILURE",
        AuditLog.entity_id == "unknown_actor_99",
    ).order_by(AuditLog.id.desc())

    log = db_session.scalars(stmt).first()
    assert log is not None
    assert log.actor_user_id is None
    assert log.action == "AUTH_LOGIN_FAILURE"
    assert "password" not in str(log.metadata_json)


def test_audit_event_logged_on_registration(client, db_session):
    """Verify customer registration logs an AUTH_REGISTER audit event."""
    reg_data = {
        "username": "audit_reg_user",
        "email": "audit_reg@example.com",
        "password": "Password123!",
        "full_name": "Audit Registered User",
    }
    resp = client.post("/api/v1/auth/register", json=reg_data)
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    stmt = select(AuditLog).where(
        AuditLog.action == "AUTH_REGISTER",
        AuditLog.entity_id == str(user_id),
    ).order_by(AuditLog.id.desc())

    log = db_session.scalars(stmt).first()
    assert log is not None
    assert log.action == "AUTH_REGISTER"
    assert "password" not in str(log.metadata_json)


def test_audit_event_logged_on_logout(client, test_customer_user, auth_headers_factory, db_session):
    """Verify logout logs an AUTH_LOGOUT audit event."""
    headers = auth_headers_factory(test_customer_user)
    resp = client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 200

    stmt = select(AuditLog).where(
        AuditLog.action == "AUTH_LOGOUT",
        AuditLog.actor_user_id == test_customer_user.id,
    ).order_by(AuditLog.id.desc())

    log = db_session.scalars(stmt).first()
    assert log is not None
    assert log.action == "AUTH_LOGOUT"


def test_audit_log_database_immutability_enforced(db_session):
    """Verify PostgreSQL BEFORE UPDATE/DELETE triggers reject audit tampering."""
    log_entry = AuditService.log_event(
        action="TEST_IMMUTABILITY",
        entity_type="TEST",
        entity_id="123",
        actor_user_id=None,
        metadata={"test": "data"},
        db=db_session,
        independent_txn=False,
    )
    db_session.flush()

    # Attempt UPDATE
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(
            text("UPDATE audit_logs SET action = 'ALTERED' WHERE id = :id"),
            {"id": log_entry.id},
        )
    assert "strictly append-only; updates and deletes are prohibited" in str(exc_info.value)
    db_session.rollback()

    # Attempt DELETE on newly inserted log entry
    log_entry2 = AuditService.log_event(
        action="TEST_IMMUTABILITY_DEL",
        entity_type="TEST",
        entity_id="124",
        actor_user_id=None,
        metadata={"test": "data"},
        db=db_session,
        independent_txn=False,
    )
    db_session.flush()

    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": log_entry2.id},
        )
    assert "strictly append-only; updates and deletes are prohibited" in str(exc_info.value)
    db_session.rollback()
