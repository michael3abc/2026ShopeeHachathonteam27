"""Upgrade real legacy memory without losing provenance or governance."""

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from return_agent.capabilities.operational_memory import SqlAlchemyOperationalMemoryStore
from .test_operational_memory import EmbeddingFake, _candidate


@pytest.fixture
def migrated_database(tmp_path, monkeypatch):
    url = os.getenv("MEMORY_TEST_POSTGRES_URL")
    admin = None
    schema = "memory_test_" + uuid4().hex
    if url:
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = make_url(url).update_query_dict({"options": f"-csearch_path={schema},public"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'memory-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        command.upgrade(cfg, "0013_activity_tracing")
        yield cfg, engine
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as conn:
                conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin.dispose()


def test_upgrade_preserves_sources_vectors_governance_and_idempotency(migrated_database):
    cfg, engine = migrated_database
    table = Table("operational_memories", MetaData(), autoload_with=engine)
    now = datetime.now(UTC)
    candidates = []
    hashes = {}
    with engine.begin() as conn:
        for status in ["CANDIDATE", "APPROVED", "RETIRED"]:
            candidate = _candidate(memory_id="LEGACY-" + status)
            candidates.append(candidate)
            old = candidate.model_dump(mode="json")
            old["source_revision_event_refs"] = old.pop("source_event_refs")
            old.pop("applicability_limits"); old.pop("prohibited_inferences")
            hashes[status] = sha256(json.dumps(old, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            conn.execute(table.insert().values(
                memory_id=candidate.memory_id, submission_ref="submission:" + status,
                candidate_payload_hash=hashes[status], retrieval_summary=candidate.retrieval_summary,
                summary_version="memory-summary:1.0", summary_hash="s" * 64,
                embedding_model="test", embedding=[1.0] + [0.0] * 1535,
                trigger_conditions=candidate.trigger_conditions, recommended_behavior=candidate.recommended_behavior,
                rationale=candidate.rationale, source_case_refs=candidate.source_case_refs,
                source_revision_event_refs=candidate.source_event_refs, policy_version=candidate.policy_version,
                claim_registry_version=candidate.claim_registry_version, scope_market="TW",
                scope_reason_codes=[v.value for v in candidate.scope.reason_codes],
                scope_claim_ids=[v.value for v in candidate.scope.claim_ids], scope_categories=candidate.scope.categories,
                confidence=candidate.confidence, status=status, submitted_at=now,
                approved_at=now if status != "CANDIDATE" else None,
                retired_at=now if status == "RETIRED" else None,
            ))
    command.upgrade(cfg, "head")
    upgraded = Table("operational_memories", MetaData(), autoload_with=engine)
    store = SqlAlchemyOperationalMemoryStore(sessionmaker(engine), EmbeddingFake())
    for candidate in candidates:
        assert store.submit_candidate(candidate).startswith("submission:")
    with engine.connect() as conn:
        rows = conn.execute(select(upgraded)).mappings().all()
    assert {row["status"] for row in rows} == {"CANDIDATE", "APPROVED", "RETIRED"}
    for row in rows:
        assert row["source_event_refs"] == ["REV-001"]
        assert row["embedding"][0] == 1 and row["summary_hash"] == "s" * 64
        assert row["applicability_limits"] == []
        assert bool(row["approved_at"]) == (row["status"] != "CANDIDATE")
        assert bool(row["retired_at"]) == (row["status"] == "RETIRED")
    command.downgrade(cfg, "0013_activity_tracing")
    restored = Table("operational_memories", MetaData(), autoload_with=engine)
    with engine.connect() as conn:
        for row in conn.execute(select(restored)).mappings():
            assert row["candidate_payload_hash"] == hashes[row["status"]]
            assert row["source_revision_event_refs"] == ["REV-001"]


def test_downgrade_refuses_to_mislabel_general_events_as_revisions(migrated_database):
    cfg, engine = migrated_database
    command.upgrade(cfg, "head")
    store = SqlAlchemyOperationalMemoryStore(sessionmaker(engine), EmbeddingFake())
    candidate = _candidate().model_copy(update={"source_event_refs": ["LEARNING-abc"],
        "applicability_limits": ["Arrival damage only."],
        "prohibited_inferences": ["Not refund authority."]})
    store.submit_candidate(candidate)
    with pytest.raises(RuntimeError, match="cannot downgrade v2 learning"):
        command.downgrade(cfg, "0013_activity_tracing")
    assert "source_event_refs" in {c["name"] for c in inspect(engine).get_columns("operational_memories")}
    assert store.submit_candidate(candidate) == "memory-submission:MEM-001"
