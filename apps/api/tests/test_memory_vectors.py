from __future__ import annotations

import pytest
from return_agent.capabilities.operational_memory import (
    OperationalMemoryDataIntegrityError,
    OperationalMemoryGovernanceService,
    SqlAlchemyOperationalMemoryStore,
)
from return_agent.db.models import OperationalMemoryEventRecord, OperationalMemoryRecord
from return_agent.memory_cli import backfill_memory_vectors
from sqlalchemy import select

from tests.test_operational_memory import (
    EmbeddingFake,
    _candidate,
    _query,
    _session_factory,
)


class SemanticEmbedding(EmbeddingFake):
    def __init__(self):
        self.calls = []
        self.fail_at = None

    def embed(self, text):
        self.calls.append(text)
        if self.fail_at == len(self.calls):
            raise ConnectionError("embedding unavailable")
        # Controlled geometry isolates ordering from governance quality metadata.
        axes = [1.0, 0.0] if "packaging" in text else [0.0, 1.0]
        return axes + [0.0] * 1534


def test_cosine_precedes_confidence_and_caps_top_three():
    sessions = _session_factory()
    embedding = SemanticEmbedding()
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    governance = OperationalMemoryGovernanceService(sessions)
    for name, summary, confidence in [
        ("MEM-LOW", "packaging evidence: inspect the carton", 0.1),
        ("MEM-HIGH", "serial number mismatch: compare labels", 0.99),
        ("MEM-THIRD", "sound distortion: collect recording", 0.8),
        ("MEM-FOURTH", "battery failure: inspect charger", 0.7),
    ]:
        store.submit_candidate(
            _candidate(memory_id=name, retrieval_summary=summary, confidence=confidence)
        )
        governance.approve(name)
    hits = _query(store, query_summary="packaging was crushed")
    assert [hit.memory.memory_id for hit in hits] == [
        "MEM-LOW",
        "MEM-HIGH",
        "MEM-THIRD",
    ]
    assert [hit.similarity for hit in hits] == [1.0, 0.0, 0.0]
    assert len(hits) == 3
    with pytest.raises(ValueError):
        _query(store, top_k=4)


def test_failed_embedding_is_atomic_and_replay_does_not_embed():
    sessions = _session_factory()
    embedding = SemanticEmbedding()
    embedding.fail_at = 1
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    candidate = _candidate()
    with pytest.raises(ConnectionError):
        store.submit_candidate(candidate)
    with sessions() as session:
        assert session.scalar(select(OperationalMemoryRecord)) is None
    store.submit_candidate(candidate)
    store.submit_candidate(candidate)
    assert len(embedding.calls) == 2
    with sessions() as session:
        row = session.get(OperationalMemoryRecord, candidate.memory_id)
        assert row.summary_hash and row.summary_version and len(row.embedding) == 1536


@pytest.mark.parametrize(
    "field,value",
    [
        ("embedding", None),
        ("embedding", [0.0] * 1536),
        ("embedding_model", "other-model"),
        ("summary_hash", "stale"),
        ("retrieval_summary", None),
        ("summary_version", None),
    ],
)
def test_incomplete_or_incompatible_vectors_are_never_normal_results(field, value):
    sessions = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(sessions, EmbeddingFake())
    store.submit_candidate(_candidate())
    OperationalMemoryGovernanceService(sessions).approve("MEM-001")
    with sessions.begin() as session:
        setattr(session.get(OperationalMemoryRecord, "MEM-001"), field, value)
    with pytest.raises((OperationalMemoryDataIntegrityError, ValueError)):
        _query(store)


def test_retirement_during_query_embedding_cannot_leak_memory():
    sessions = _session_factory()
    embedding = SemanticEmbedding()
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    store.submit_candidate(_candidate())
    governance = OperationalMemoryGovernanceService(sessions)
    governance.approve("MEM-001")
    original = embedding.embed

    def retire_then_embed(text):
        governance.retire("MEM-001")
        return original(text)

    embedding.embed = retire_then_embed
    assert _query(store) == []


def test_backfill_dry_run_failure_resume_preserves_governance_and_idempotency():
    sessions = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(sessions, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(sessions)
    for name in ["MEM-1", "MEM-2", "MEM-3"]:
        store.submit_candidate(_candidate(memory_id=name))
    governance.approve("MEM-2")
    governance.approve("MEM-3")
    governance.retire("MEM-3")
    with sessions.begin() as session:
        for row in session.scalars(select(OperationalMemoryRecord)):
            row.retrieval_summary = row.summary_version = row.summary_hash = None
            row.embedding = row.embedding_model = None
        immutable = {
            row.memory_id: (
                row.candidate_payload_hash,
                row.status,
                row.submission_ref,
                row.trigger_conditions,
                row.recommended_behavior,
                row.source_case_refs,
                row.approved_at,
                row.retired_at,
            )
            for row in session.scalars(select(OperationalMemoryRecord))
        }
        event_ids = list(session.scalars(select(OperationalMemoryEventRecord.event_id)))
    embedding = SemanticEmbedding()
    assert [
        r["action"] for r in backfill_memory_vectors(sessions, embedding, dry_run=True)
    ] == ["would_embed"] * 3
    assert embedding.calls == []
    embedding.fail_at = 2
    with pytest.raises(ConnectionError):
        list(backfill_memory_vectors(sessions, embedding))
    actions = list(backfill_memory_vectors(sessions, embedding))
    assert [r["action"] for r in actions] == ["unchanged", "embedded", "embedded"]
    with sessions() as session:
        for row in session.scalars(select(OperationalMemoryRecord)):
            assert row.summary_version == "legacy-composed:1.0"
            assert (
                row.retrieval_summary
                == "Situation: "
                + "; ".join(row.trigger_conditions)
                + "\nAction: "
                + row.recommended_behavior
            )
            assert immutable[row.memory_id] == (
                row.candidate_payload_hash,
                row.status,
                row.submission_ref,
                row.trigger_conditions,
                row.recommended_behavior,
                row.source_case_refs,
                row.approved_at,
                row.retired_at,
            )
        assert event_ids == list(
            session.scalars(select(OperationalMemoryEventRecord.event_id))
        )


def test_empty_backfill_and_multiple_keyset_batches():
    sessions = _session_factory()
    embedding = SemanticEmbedding()
    assert list(backfill_memory_vectors(sessions, embedding)) == []
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    for index in range(205):
        store.submit_candidate(_candidate(memory_id=f"MEM-{index:04d}"))
    before = len(embedding.calls)
    results = list(backfill_memory_vectors(sessions, embedding, dry_run=True))
    assert len(results) == 205
    assert len({r["memory_id"] for r in results}) == 205
    assert all(r["action"] == "unchanged" for r in results)
    assert len(embedding.calls) == before


@pytest.mark.parametrize("failure", ["summary", "blank_summary", "vector"])
def test_backfill_reports_the_exact_failed_validation_target(failure):
    sessions = _session_factory()
    embedding = SemanticEmbedding()
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    store.submit_candidate(_candidate())
    with sessions.begin() as session:
        row = session.get(OperationalMemoryRecord, "MEM-001")
        if failure == "summary":
            row.retrieval_summary = "private@example.com"
        elif failure == "blank_summary":
            row.retrieval_summary = ""
        else:
            row.embedding = [0.0] * 1536
    before = len(embedding.calls)
    results = backfill_memory_vectors(sessions, embedding, dry_run=True)
    failed = next(results)
    assert failed["memory_id"] == "MEM-001"
    assert failed["action"] == "failed"
    assert "private@example.com" not in str(failed)
    with pytest.raises(ValueError):
        next(results)
    assert len(embedding.calls) == before


def test_backfill_does_not_report_missing_summary_as_unchanged():
    from return_agent.capabilities.operational_memory import _canonical_hash

    sessions = _session_factory()
    embedding = SemanticEmbedding()
    store = SqlAlchemyOperationalMemoryStore(sessions, embedding)
    store.submit_candidate(_candidate())
    with sessions.begin() as session:
        row = session.get(OperationalMemoryRecord, "MEM-001")
        summary = "Situation: " + "; ".join(row.trigger_conditions) + "\nAction: " + row.recommended_behavior
        row.retrieval_summary = None
        row.summary_hash = _canonical_hash(summary)
    assert list(backfill_memory_vectors(sessions, embedding, dry_run=True)) == [
        {"memory_id": "MEM-001", "action": "would_embed"}
    ]
    assert list(backfill_memory_vectors(sessions, embedding)) == [
        {"memory_id": "MEM-001", "action": "embedded"}
    ]
    with sessions() as session:
        assert session.get(OperationalMemoryRecord, "MEM-001").retrieval_summary == summary


def test_wrong_vector_dimension_rejected_before_storage():
    embedding = SemanticEmbedding()
    embedding.dimensions = 2
    with pytest.raises(ValueError, match="1536"):
        SqlAlchemyOperationalMemoryStore(_session_factory(), embedding)


def test_negative_similarity_is_not_thresholded_and_equal_hits_sort_by_id(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from return_agent.capabilities import operational_memory

    class OppositeEmbedding(EmbeddingFake):
        def embed(self, text):
            return [-1.0 if text == "query" else 1.0] + [0.0] * 1535

    sessions = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(sessions, OppositeEmbedding())
    governance = OperationalMemoryGovernanceService(sessions)
    for name in ["MEM-B", "MEM-A"]:
        store.submit_candidate(_candidate(memory_id=name))
    approved_at = datetime.now(UTC) + timedelta(minutes=1)
    monkeypatch.setattr(operational_memory, "_now_utc", lambda: approved_at)
    for name in ["MEM-B", "MEM-A"]:
        governance.approve(name)
    hits = _query(store, query_summary="query")
    assert [hit.memory.memory_id for hit in hits] == ["MEM-A", "MEM-B"]
    assert [hit.similarity for hit in hits] == [-1.0, -1.0]
