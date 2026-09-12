"""Run Agent-owned migrations using the composition root's connection."""

from alembic import context

if context.is_offline_mode():
    context.configure(
        url=context.config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="agent_service_alembic_version",
    )
else:
    context.configure(
        connection=context.config.attributes["connection"],
        version_table="agent_service_alembic_version",
    )
with context.begin_transaction():
    context.run_migrations()
