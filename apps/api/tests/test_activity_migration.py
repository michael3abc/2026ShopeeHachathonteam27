import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from return_agent.activities import ActivityRepository
from return_agent.db.case import CaseRecord
from return_agent_contracts.activity import ActivityEmission, ActivityFacts, NodeSummary
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def config():
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def test_activity_offline_upgrade(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/unused")
    cfg = config()
    cfg.output_buffer = StringIO()
    command.upgrade(cfg, "0012_human_review_dossier:0013_activity_tracing", sql=True)
    sql = cfg.output_buffer.getvalue()
    assert "CREATE TABLE case_activities" in sql
    assert "CREATE TABLE activity_narration_outbox" in sql


def test_activity_migration_and_concurrent_sequences(tmp_path, monkeypatch):
    url = os.getenv("ACTIVITY_TEST_POSTGRES_URL")
    admin = None
    schema = "activity_" + uuid4().hex
    if url:
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = (
            make_url(url)
            .update_query_dict({"options": f"-csearch_path={schema},public"})
            .render_as_string(hide_password=False)
        )
    else:
        url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    try:
        cfg = config()
        command.upgrade(cfg, "0012_human_review_dossier")
        command.upgrade(cfg, "head")
        assert "case_activities" in inspect(engine).get_table_names()
        command.downgrade(cfg, "0012_human_review_dossier")
        assert "case_activities" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "head")
        sessions = sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        with sessions.begin() as session:
            session.add(
                CaseRecord(
                    case_ref="CASE-1",
                    thread_id="THREAD-1",
                    order_ref="ORDER-1",
                    user_ref="USER-1",
                    status="RESOLVED",
                    created_at=now,
                    updated_at=now,
                )
            )
        repository = ActivityRepository(sessions)

        def append(index):
            return repository.append(
                ActivityEmission(
                    event_id=f"EVENT-{index}",
                    case_ref="CASE-1",
                    run_id="RUN-1",
                    scope="CASE",
                    node="reviewer",
                    operation_id=f"OP-{index}",
                    attempt_id="ATTEMPT-1",
                    occurred_at=now,
                    payload=NodeSummary(facts=ActivityFacts(verdict="APPROVE")),
                )
            )

        if admin:
            with ThreadPoolExecutor(max_workers=8) as pool:
                events = list(
                    pool.map(append, [i for i in range(20) for _ in range(2)])
                )
            assert len({event.event_id for event in events}) == 20
            assert {event.seq for event in events} == set(range(1, 21))
        else:
            append(1)
        with engine.connect() as connection:
            version_before = connection.scalar(text("SELECT version_num FROM alembic_version"))
        with pytest.raises(RuntimeError, match="audit history"):
            command.downgrade(cfg, "0012_human_review_dossier")
        with engine.connect() as connection:
            # PostgreSQL rolls back the entire downgrade transaction, including
            # later migrations. SQLite may already have applied those migrations.
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == (version_before if engine.dialect.name == "postgresql" else "0013_activity_tracing")
            )
            assert connection.scalar(text("SELECT count(*) FROM case_activities")) == (20 if admin else 1)
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin.dispose()
