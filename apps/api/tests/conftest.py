"""Each integration test owns a fresh, explicitly named PostgreSQL schema."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from return_agent.cases import CaseStore
from return_agent.db import make_engine, make_sessions
from return_agent.settings import Settings


@pytest.fixture
def database():
    url = os.getenv("TEST_API_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_API_DATABASE_URL to an isolated local test database")
    settings = Settings(profile="integrated-demo", database_url=url)
    schema = f"team27_test_{uuid4().hex}"
    admin = make_engine(settings)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = make_engine(settings, schema=schema)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            # Public may already be at head; that must never skip this schema's migration.
            assert connection.exec_driver_sql("SELECT current_schema()").scalar_one() == schema
            assert {"cases", "case_events", "agent_command_outbox", "alembic_version"} <= set(inspect(connection).get_table_names(schema=schema))
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def store(database):
    return CaseStore(make_sessions(database[0]))
