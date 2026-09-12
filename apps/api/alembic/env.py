"""Alembic configuration for Louis-owned tables."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from return_agent.db import activity as _activity_models  # noqa: F401
from return_agent.db import agent_bridge as _agent_bridge_models  # noqa: F401
from return_agent.db import case as _case_models  # noqa: F401  (register tables)
from return_agent.db import attachments as _attachment_models  # noqa: F401
from return_agent.db.models import Base
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # Workspace tests load API migrations and Runtime tests in one process.
    # Alembic must not disable loggers owned by other packages.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
