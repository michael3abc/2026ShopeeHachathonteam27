import os

from alembic import context
from return_agent_service.db import Base, make_engine


def migrate(connection):
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    context.configure(connection=connection, target_metadata=Base.metadata, version_table_schema=schema)
    with context.begin_transaction():
        context.run_migrations()


supplied = context.config.attributes.get("connection")
if supplied is not None:
    migrate(supplied)
else:
    engine = make_engine(os.environ["AGENT_DATABASE_URL"])
    with engine.begin() as connection:
        migrate(connection)
    engine.dispose()
