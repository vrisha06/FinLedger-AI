"""FinLedger-AI System Settings & Configuration Module.

Secure configuration management using Pydantic Settings.
Enforces strict secret handling, avoids hardcoded credential fallbacks,
masks credentials in object representations, and safely constructs
database connection URLs handling special characters.
"""

from pathlib import Path
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

# Resolve workspace root directory where .env is stored
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """FinLedger-AI System Settings."""

    # Environment
    ENVIRONMENT: str = "development"
    # Secure by default: Swagger docs are only exposed when DEBUG is explicitly enabled
    DEBUG: bool = False
    # Browser origins allowed to call the API (Vite dev server and preview build)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL 16 Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    # Mandatory: Must be provided via environment or local .env file.
    # No hardcoded password fallback.
    DB_PASSWORD: SecretStr
    DB_NAME: str = "finledger"
    DB_TEST_NAME: str = "finledger_test"

    # Explicit URLs (optional in .env, computed if not provided)
    # Stored as SecretStr to prevent credential leakage in repr or dumps
    DATABASE_URL: SecretStr | None = None
    TEST_DATABASE_URL: SecretStr | None = None

    # Security & Auth
    # Mandatory: Must be provided via environment or local .env file.
    # No hardcoded secret key fallback.
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Financial / Accounting Defaults
    DEFAULT_CURRENCY: str = "INR"
    CLEARING_ACCOUNT_NUMBER: str = "INR-SYS-CLEARING"

    # AI & ML Defaults
    FRAUD_RISK_THRESHOLD: float = 0.70
    RANDOM_SEED: int = 42

    @field_validator("DB_PASSWORD")
    @classmethod
    def validate_db_password(cls, v: SecretStr) -> SecretStr:
        """Ensure database password is not empty or whitespace-only."""
        if not v.get_secret_value().strip():
            raise ValueError(
                "Database password (DB_PASSWORD) is required and cannot be empty. "
                "Please configure DB_PASSWORD in your .env file or environment variables."
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: SecretStr) -> SecretStr:
        """Ensure secret key is not empty or whitespace-only."""
        if not v.get_secret_value().strip():
            raise ValueError(
                "Secret key (SECRET_KEY) is required and cannot be empty. "
                "Please configure SECRET_KEY in your .env file or environment variables."
            )
        return v

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def normalize_optional_url(cls, v: str | SecretStr | None) -> str | SecretStr | None:
        """Normalize empty string URLs to None."""
        if isinstance(v, str) and not v.strip():
            return None
        if isinstance(v, SecretStr) and not v.get_secret_value().strip():
            return None
        return v

    @property
    def sync_database_url(self) -> str:
        """Returns valid sync connection URL for SQLAlchemy (psycopg2).

        Constructed via SQLAlchemy's URL.create to safely escape any special
        characters in user credentials. Defined as a property (not computed_field)
        to prevent credentials from appearing in repr() or model_dump().
        """
        if self.DATABASE_URL and self.DATABASE_URL.get_secret_value().strip():
            url = make_url(self.DATABASE_URL.get_secret_value().strip())
            return url.render_as_string(hide_password=False)
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )
        return url.render_as_string(hide_password=False)

    @property
    def sync_test_database_url(self) -> str:
        """Returns valid sync connection URL for pytest against finledger_test.

        Constructed via SQLAlchemy's URL.create to safely escape any special
        characters in user credentials. Defined as a property (not computed_field)
        to prevent credentials from appearing in repr() or model_dump().
        """
        if self.TEST_DATABASE_URL and self.TEST_DATABASE_URL.get_secret_value().strip():
            url = make_url(self.TEST_DATABASE_URL.get_secret_value().strip())
            return url.render_as_string(hide_password=False)
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_TEST_NAME,
        )
        return url.render_as_string(hide_password=False)

    @property
    def safe_database_url(self) -> str:
        """Returns connection URL with password masked (safe for logging/debug)."""
        url = make_url(self.sync_database_url)
        return url.render_as_string(hide_password=True)

    @property
    def safe_test_database_url(self) -> str:
        """Returns test connection URL with password masked (safe for logging/debug)."""
        url = make_url(self.sync_test_database_url)
        return url.render_as_string(hide_password=True)

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
