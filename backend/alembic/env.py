import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_target_url() -> str:
    """Return database URL based on runtime arguments (e.g. -x db=test, -x db=bench, -x db=<custom>)."""
    x_args = context.get_x_argument(as_dictionary=True)
    db_arg = x_args.get("db")
    if db_arg == "test":
        return settings.sync_test_database_url
    elif db_arg == "bench":
        base_url = settings.sync_database_url
        return base_url.replace(f"/{settings.DB_NAME}", "/finledger_bench")
    elif db_arg:
        base_url = settings.sync_database_url
        return base_url.replace(f"/{settings.DB_NAME}", f"/{db_arg}")
    return settings.sync_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_target_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_target_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
