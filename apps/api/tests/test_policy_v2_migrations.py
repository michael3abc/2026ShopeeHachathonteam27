"""New history stays on one chain and cannot be silently discarded."""

import os
from io import StringIO
from uuid import uuid4

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from .test_activity_migration import config


@pytest.fixture
def migrated_database(tmp_path, monkeypatch):
    base_url = os.environ.get("PV2_TEST_POSTGRES_URL")
    admin = None
    database = "pv2_migration_" + uuid4().hex
    if base_url:
        admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        url = make_url(base_url).set(database=database).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'policy-v2.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    try:
        cfg = config()
        command.upgrade(cfg, "0013_activity_tracing")
        command.upgrade(cfg, "head")
        yield engine, cfg
    finally:
        engine.dispose()
        if admin is not None:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{database}"')
            admin.dispose()


def test_v2_single_chain_and_offline_upgrade_downgrade(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/unused")
    cfg = config()
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0015_policy_v2_fulfillment"]
    cfg.output_buffer = StringIO()
    command.upgrade(cfg, "0013_activity_tracing:head", sql=True)
    sql = cfg.output_buffer.getvalue()
    for table in ("user_risk_profiles", "user_risk_events", "user_risk_snapshots",
                  "policy_evaluations", "policy_selections", "policy_confirmations",
                  "return_authorizations", "return_event_receipts",
                  "refund_completion_outbox", "demo_sessions"):
        assert f"CREATE TABLE {table}" in sql
    cfg.output_buffer = StringIO()
    command.downgrade(cfg, "head:0013_activity_tracing", sql=True)
    sql = cfg.output_buffer.getvalue()
    assert sql.index("archive v2 records before downgrade") < sql.index("DROP TABLE demo_sessions")
    assert sql.index("user risk history must be archived") < sql.index("DROP TABLE user_risk_snapshots")


def test_v2_empty_upgrade_downgrade_and_preserve_v1(migrated_database):
    engine, cfg = migrated_database
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO cases (case_ref, thread_id, order_ref, user_ref, status, created_at, updated_at) "
            "VALUES ('legacy','legacy','legacy','legacy','OBSERVING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
    command.downgrade(cfg, "0013_activity_tracing")
    assert "user_risk_profiles" not in inspect(engine).get_table_names()
    assert "return_authorizations" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT policy_schema_version FROM cases WHERE case_ref = 'legacy'")) == "v1"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0015_policy_v2_fulfillment"


@pytest.mark.parametrize("seed", [
    "INSERT INTO policy_evaluations VALUES ('evaluation','case','{}')",
    "INSERT INTO policy_selections VALUES ('case',1,'{}')",
    "INSERT INTO policy_confirmations (request_ref,case_ref,request_payload) VALUES ('request','case','{}')",
    "INSERT INTO return_authorizations (authorization_ref,case_ref,execution_ref,payload,payload_hash,state,created_at) VALUES ('authorization','case','execution','{}','hash','EXECUTING',CURRENT_TIMESTAMP)",
    "INSERT INTO return_event_receipts VALUES ('receipt','producer','event','authorization','{}','{}')",
    "INSERT INTO refund_completion_outbox VALUES ('resolution','{}',false)",
    "INSERT INTO demo_sessions VALUES ('hash','user','BUYER',CURRENT_TIMESTAMP)",
    "INSERT INTO cases (case_ref,thread_id,order_ref,user_ref,status,created_at,updated_at,policy_schema_version) VALUES ('v2','v2','v2','v2','OBSERVING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'v2')",
])
def test_v2_each_history_blocks_downgrade(migrated_database, seed):
    engine, cfg = migrated_database
    with engine.begin() as connection:
        connection.execute(text(seed))
    with pytest.raises(RuntimeError, match="archive v2 records"):
        command.downgrade(cfg, "0014_user_risk_authorization")
    if engine.dialect.name == "postgresql":
        cfg.output_buffer = StringIO()
        command.downgrade(cfg, "0015_policy_v2_fulfillment:0014_user_risk_authorization", sql=True)
        with pytest.raises(DBAPIError, match="archive v2 records"):
            with engine.begin() as connection:
                connection.exec_driver_sql(cfg.output_buffer.getvalue())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0015_policy_v2_fulfillment"
    assert "return_authorizations" in inspect(engine).get_table_names()


@pytest.mark.parametrize("seed", [
    "INSERT INTO user_risk_profiles VALUES ('user',CURRENT_TIMESTAMP,1,CURRENT_TIMESTAMP)",
    "INSERT INTO user_risk_events VALUES ('event','user','case','order','REFUND_SUCCEEDED',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
    "INSERT INTO user_risk_snapshots VALUES ('snapshot','case','user','ITEM_DAMAGED',CURRENT_TIMESTAMP,'{}','hash')",
])
def test_risk_each_history_blocks_downgrade(migrated_database, seed):
    engine, cfg = migrated_database
    command.downgrade(cfg, "0014_user_risk_authorization")
    with engine.begin() as connection:
        connection.execute(text(seed))
    with pytest.raises(RuntimeError, match="user risk history must be archived"):
        command.downgrade(cfg, "0013_activity_tracing")
    if engine.dialect.name == "postgresql":
        cfg.output_buffer = StringIO()
        command.downgrade(cfg, "0014_user_risk_authorization:0013_activity_tracing", sql=True)
        with pytest.raises(DBAPIError, match="user risk history must be archived"):
            with engine.begin() as connection:
                connection.exec_driver_sql(cfg.output_buffer.getvalue())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0014_user_risk_authorization"
