"""Run Agent-owned migrations using the composition root's connection."""

from alembic import context

context.configure(
    connection=context.config.attributes["connection"],
    version_table="agent_service_alembic_version",
)
with context.begin_transaction():
    context.run_migrations()
