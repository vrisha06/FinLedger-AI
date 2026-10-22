"""Append-only Audit Service for FinLedger-AI.

Enforces auditable tracking of administrative, security, and financial events.
Automatically sanitizes sensitive information (passwords, tokens, keys) from
metadata payloads before committing.

Supports independent transaction persistence to ensure audit logs survive
outer financial rollbacks or failed operation handlers.
"""

from typing import Any
import uuid
import re
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audit import AuditLog

# Regex patterns for sensitive values
JWT_PATTERN = re.compile(r"^eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$")
BCRYPT_PATTERN = re.compile(r"^\$2[abxy]\$\d{2}\$[A-Za-z0-9./]{53}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

# Sensitive key fragments (case-insensitive match)
SENSITIVE_KEY_FRAGMENTS = {
    "password",
    "token",
    "secret",
    "authorization",
    "auth",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "credit_card",
    "cvv",
    "pin",
    "private_key",
    "pan",
    "pan_number",
    "ssn",
    "tax_id",
    "aadhaar",
    "national_id",
}


def sanitize_audit_metadata(data: Any) -> Any:
    """Recursively scrub sensitive fields, tokens, hashes, and PANs from audit metadata."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            key_lower = str(k).lower()
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_metadata(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_metadata(item) for item in data]
    elif isinstance(data, str):
        # Scrub standalone JWTs, password hashes, or PAN identifiers passed as values
        if JWT_PATTERN.match(data) or BCRYPT_PATTERN.match(data) or PAN_PATTERN.match(data):
            return "[REDACTED]"
        return data
    elif isinstance(data, (int, float, bool)) or data is None:
        return data
    else:
        return str(data)


class AuditService:
    """Service managing append-only, sanitized audit event persistence."""

    @staticmethod
    def log_event(
        action: str,
        entity_type: str,
        entity_id: str,
        actor_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        db: Session | None = None,
        independent_txn: bool = True,
    ) -> AuditLog:
        """Record an append-only audit log entry.

        Args:
            action: Canonical action identifier (e.g. AUTH_LOGIN_SUCCESS, AUTH_LOGOUT).
            entity_type: Target entity type (e.g. USER, ACCOUNT, TRANSFER).
            entity_id: Identifier of target entity.
            actor_user_id: Authenticated user initiating event (None for unauthenticated).
            ip_address: Client IP address.
            user_agent: Client User-Agent string.
            metadata: Context dictionary; automatically sanitized before insert.
            db: Existing SQLAlchemy session. If None or independent_txn=True,
                uses an isolated session committed immediately.
            independent_txn: When True, commits in an independent transaction so that
                outer rollbacks never erase audit evidence.
        """
        sanitized_metadata = sanitize_audit_metadata(metadata or {})

        if independent_txn or db is None:
            # Independent transaction: failure or rollback in calling code cannot wipe audit log
            target_engine = db.get_bind() if db is not None else SessionLocal.kw.get("bind")
            with Session(target_engine) as isolated_db:
                log_entry = AuditLog(
                    actor_user_id=actor_user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata_json=sanitized_metadata,
                )
                isolated_db.add(log_entry)
                isolated_db.commit()
                isolated_db.refresh(log_entry)
                return log_entry
        else:
            # Attached to caller's existing transaction
            log_entry = AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                ip_address=ip_address,
                user_agent=user_agent,
                metadata_json=sanitized_metadata,
            )
            db.add(log_entry)
            db.flush()
            return log_entry
