"""Tests for secure configuration and credential management in FinLedger-AI.

Verifies:
1. Valid environment-based credentials load correctly.
2. Missing or empty required credentials produce clear configuration errors.
3. No hardcoded password or secret fallbacks exist in model field defaults.
4. Passwords with special characters are safely escaped via SQLAlchemy URL utilities.
5. Secrets and passwords are not exposed in repr, str, dumps, or safe URLs.
6. Existing database connection configuration remains functional against PostgreSQL 16.
"""

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_core import PydanticUndefined
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings, settings


def test_no_hardcoded_credential_fallbacks():
    """Verify that DB_PASSWORD and SECRET_KEY have no hardcoded default fallbacks."""
    pw_field = Settings.model_fields["DB_PASSWORD"]
    assert pw_field.is_required(), "DB_PASSWORD must be a required field"
    assert pw_field.default is PydanticUndefined, "DB_PASSWORD must not have a default fallback"

    secret_field = Settings.model_fields["SECRET_KEY"]
    assert secret_field.is_required(), "SECRET_KEY must be a required field"
    assert secret_field.default is PydanticUndefined, "SECRET_KEY must not have a default fallback"


def test_valid_credentials_loaded_correctly():
    """Verify that explicitly provided valid credentials initialize cleanly."""
    custom_settings = Settings(
        DB_HOST="db.internal.local",
        DB_PORT=5433,
        DB_USER="fin_app_user",
        DB_PASSWORD=SecretStr("StrongP@ssw0rd!123"),
        DB_NAME="fin_prod",
        DB_TEST_NAME="fin_test",
        SECRET_KEY=SecretStr("super_secure_jwt_signing_secret_key_32chars"),
        _env_file=None,
    )

    assert custom_settings.DB_HOST == "db.internal.local"
    assert custom_settings.DB_PORT == 5433
    assert custom_settings.DB_USER == "fin_app_user"
    assert custom_settings.DB_PASSWORD.get_secret_value() == "StrongP@ssw0rd!123"
    assert custom_settings.DB_NAME == "fin_prod"
    assert custom_settings.DB_TEST_NAME == "fin_test"
    assert "postgresql+psycopg2://fin_app_user:" in custom_settings.sync_database_url
    assert "@db.internal.local:5433/fin_prod" in custom_settings.sync_database_url


def test_missing_db_password_fails_clearly(monkeypatch):
    """Verify that omitting DB_PASSWORD raises a clear ValidationError."""
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            SECRET_KEY=SecretStr("some_secret_key"),
            _env_file=None,
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "DB_PASSWORD" in field_names


@pytest.mark.parametrize("empty_pw", ["", "   ", "\t\n"])
def test_empty_or_whitespace_db_password_fails_clearly(empty_pw):
    """Verify that empty or whitespace-only DB_PASSWORD produces a clear error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DB_PASSWORD=SecretStr(empty_pw),
            SECRET_KEY=SecretStr("some_secret_key"),
            _env_file=None,
        )
    errors = exc_info.value.errors()
    pw_errors = [e for e in errors if e["loc"][0] == "DB_PASSWORD"]
    assert len(pw_errors) > 0
    assert "Database password (DB_PASSWORD) is required and cannot be empty" in pw_errors[0]["msg"]


def test_missing_secret_key_fails_clearly(monkeypatch):
    """Verify that omitting SECRET_KEY raises a clear ValidationError."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DB_PASSWORD=SecretStr("some_password"),
            _env_file=None,
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "SECRET_KEY" in field_names


@pytest.mark.parametrize("empty_secret", ["", "   "])
def test_empty_secret_key_fails_clearly(empty_secret):
    """Verify that empty or whitespace-only SECRET_KEY produces a clear error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DB_PASSWORD=SecretStr("some_password"),
            SECRET_KEY=SecretStr(empty_secret),
            _env_file=None,
        )
    errors = exc_info.value.errors()
    secret_errors = [e for e in errors if e["loc"][0] == "SECRET_KEY"]
    assert len(secret_errors) > 0
    assert "Secret key (SECRET_KEY) is required and cannot be empty" in secret_errors[0]["msg"]


def test_special_characters_in_password_safely_escaped():
    """Verify URL.create properly percent-encodes special characters in credentials."""
    special_pw = "p@ss:w/ord#%&?^"
    custom_settings = Settings(
        DB_USER="fin_user",
        DB_PASSWORD=SecretStr(special_pw),
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="finledger",
        SECRET_KEY=SecretStr("dummy_secret"),
        _env_file=None,
    )

    url_str = custom_settings.sync_database_url
    # Ensure plain special characters that break URLs are safely escaped
    assert special_pw not in url_str, "Raw unescaped special password string should not appear in URL"

    # Verify SQLAlchemy can parse the constructed URL and recovers the original password
    parsed = make_url(url_str)
    assert parsed.password == special_pw
    assert parsed.username == "fin_user"


def test_secrets_masked_in_repr_str_and_dumps():
    """Verify credentials and secrets do not leak in representations, dumps, or safe URLs."""
    raw_pw = "SuperSecretPassword123!"
    raw_secret = "SuperSecretSigningKey456!"
    custom_settings = Settings(
        DB_PASSWORD=SecretStr(raw_pw),
        SECRET_KEY=SecretStr(raw_secret),
        DATABASE_URL=SecretStr(f"postgresql+psycopg2://postgres:{raw_pw}@localhost:5432/finledger"),
        _env_file=None,
    )

    repr_str = repr(custom_settings)
    str_output = str(custom_settings)
    dump_dict = custom_settings.model_dump()
    dump_str = str(dump_dict)

    # Password and secret key must not leak
    assert raw_pw not in repr_str
    assert raw_pw not in str_output
    assert raw_pw not in dump_str

    assert raw_secret not in repr_str
    assert raw_secret not in str_output
    assert raw_secret not in dump_str

    # safe URLs must mask passwords with ***
    safe_db_url = custom_settings.safe_database_url
    assert "***" in safe_db_url
    assert raw_pw not in safe_db_url

    safe_test_url = custom_settings.safe_test_database_url
    assert "***" in safe_test_url
    assert raw_pw not in safe_test_url


def test_explicit_database_url_override():
    """Verify explicit DATABASE_URL override takes precedence when provided."""
    custom_settings = Settings(
        DB_PASSWORD=SecretStr("dummy_pw"),
        SECRET_KEY=SecretStr("dummy_key"),
        DATABASE_URL=SecretStr("postgresql+psycopg2://custom_user:custom_pass@remotehost:5433/custom_db"),
        _env_file=None,
    )
    assert "remotehost:5433/custom_db" in custom_settings.sync_database_url


def test_live_settings_database_connectivity(engine):
    """Verify live settings successfully connect to the test PostgreSQL database."""
    assert settings.DB_PASSWORD.get_secret_value() != "", "Live settings must have a non-empty DB_PASSWORD"
    assert settings.SECRET_KEY.get_secret_value() != "", "Live settings must have a non-empty SECRET_KEY"

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1;")).scalar()
        assert result == 1
