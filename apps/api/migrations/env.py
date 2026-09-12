from alembic import context
from sqlalchemy import pool, create_engine

from return_agent.db import Base
from return_agent.settings import Settings

config = context.config
target_metadata = Base.metadata


def run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    settings = Settings.from_env()
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        run(supplied)
    else:
        settings = Settings.from_env()
        if not settings.database_url:
            raise ValueError("API_DATABASE_URL is required for migrations")
        engine = create_engine(settings.database_url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            run(connection)
