from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from return_agent_contracts.completion import RefundAppliedEvent
from return_agent_contracts.policy_v2 import content_hash
from return_agent_contracts.service import MemoryDistillationJob
from return_agent_service.memory_completion import MemoryCompletionStore, JOINS
from return_agent_service.memory_replay import SqlAlchemyMemoryReplayStore
from test_memory_enqueue_worker import _prepared_input, TIME
from test_memory_worker import replay_engine  # noqa: F401


@pytest.mark.parametrize("order", ["correction-first","applied-first","concurrent"])
def test_durable_join_arbitrary_order_duplicate_and_restart(replay_engine, order):
    engine = replay_engine
    SqlAlchemyMemoryReplayStore(engine).migrate()
    store = MemoryCompletionStore(engine)
    input_ = _prepared_input()
    resolution = input_.final_resolution
    job = MemoryDistillationJob(job_id=f"memory:{resolution.handoff_id}",source_command_id="command",
        case_ref=resolution.case_ref,thread_id="thread",issued_at=TIME,payload={"input":input_})
    applied = RefundAppliedEvent(case_ref=resolution.case_ref,resolution_ref=resolution.handoff_id,
        authorization_ref=f"authorization:{resolution.handoff_id}",resolution_hash=content_hash(resolution),
        execution_ref="execution",application_ref="application",applied_at=TIME)
    if order == "concurrent":
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(store.correction,job),pool.submit(store.applied,applied),
                pool.submit(store.correction,job),pool.submit(store.applied,applied)]
            for future in futures:
                future.result()
    else:
        first,second = ((lambda:store.correction(job)),(lambda:store.applied(applied)))
        if order == "applied-first":
            first,second = second,first
        first()
        assert store.next_job() is None
        second()
    reopened = MemoryCompletionStore(engine)
    assert reopened.next_job() == job
    reopened.correction(job.model_copy(update={"issued_at":TIME+timedelta(seconds=1)}))
    reopened.applied(applied)
    assert reopened.next_job() == job
    reopened.published(job)
    reopened.applied(applied)
    assert reopened.next_job() is None
    with engine.connect() as connection:
        assert len(connection.execute(select(JOINS)).all()) == 1
    with pytest.raises(ValueError,match="binding"):
        reopened.applied(applied.model_copy(update={"resolution_hash":"f"*64}))
    with pytest.raises(ValueError,match="immutable"):
        reopened.applied(applied.model_copy(update={"application_ref":"other"}))


def migration_config():
    cfg = Config()
    cfg.set_main_option("script_location", str(
        Path(__file__).resolve().parents[1] / "src/return_agent_service/migrations"
    ))
    cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://unused/unused")
    return cfg


def test_memory_join_offline_upgrade_and_protected_downgrade():
    cfg = migration_config()
    cfg.output_buffer = StringIO()
    command.upgrade(cfg, "head", sql=True)
    sql = cfg.output_buffer.getvalue()
    assert "CREATE TABLE memory_completion_joins" in sql
    assert "agent_service_alembic_version" in sql
    cfg.output_buffer = StringIO()
    command.downgrade(cfg, "head:0001_memory_replay", sql=True)
    sql = cfg.output_buffer.getvalue()
    assert sql.index("archive memory completion joins") < sql.index("DROP TABLE memory_completion_joins")


def test_memory_join_empty_roundtrip_and_nonempty_guard(replay_engine):
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    cfg = migration_config()
    with replay_engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "0001_memory_replay")
    store.migrate()
    with replay_engine.begin() as connection:
        connection.execute(JOINS.insert().values(
            resolution_ref="ref", case_ref="case", resolution_hash="hash", published=False
        ))
    with pytest.raises(RuntimeError, match="archive memory completion joins"):
        with replay_engine.begin() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, "0001_memory_replay")
    if replay_engine.dialect.name == "postgresql":
        cfg.output_buffer = StringIO()
        command.downgrade(cfg, "0003_memory_completion:0001_memory_replay", sql=True)
        with pytest.raises(DBAPIError, match="archive memory completion joins"):
            with replay_engine.begin() as connection:
                connection.exec_driver_sql(cfg.output_buffer.getvalue())
    with replay_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM agent_service_alembic_version")) == "0003_memory_completion"
        assert connection.scalar(select(JOINS.c.resolution_ref)) == "ref"
