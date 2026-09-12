from __future__ import annotations

from datetime import UTC, datetime, timedelta
from inspect import signature

import pytest
from return_agent.capabilities import operational_memory
from return_agent.capabilities.operational_memory import (
    OperationalMemoryCandidateError,
    OperationalMemoryConflictError,
    OperationalMemoryGovernanceService,
    OperationalMemoryLifecycleError,
    SqlAlchemyOperationalMemoryStore,
)
from return_agent.db.models import (
    Base,
    OperationalMemoryEventRecord,
    OperationalMemoryRecord,
)
from return_agent_contracts.enums import ClaimId, MemoryStatus, ReasonCode
from return_agent_contracts.models import MemoryCandidate, MemoryScope
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


class EmbeddingFake:
    model_name = "text-embedding-3-large"
    dimensions = 1536

    def embed(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 1535


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _candidate(
    *,
    memory_id: str = "MEM-001",
    policy_version: str = "RETURNS-TW:v1",
    claim_registry_version: str = "claim-registry:1.0",
    market: str = "TW",
    reason_codes: list[ReasonCode] | None = None,
    claim_ids: list[ClaimId] | None = None,
    categories: list[str] | None = None,
    confidence: float = 0.72,
    retrieval_summary: str = "Damaged-item claim; request evidence together.",
) -> MemoryCandidate:
    return MemoryCandidate(
        memory_id=memory_id,
        retrieval_summary=retrieval_summary,
        trigger_conditions=[
            "A damaged-item claim has several missing user-evidence facts."
        ],
        recommended_behavior="Request all missing evidence in one EvidenceRequest.",
        rationale="A reviewed correction showed repeated evidence rounds were avoidable.",
        source_case_refs=["CASE-005"],
        source_event_refs=["REV-001"],
        policy_version=policy_version,
        claim_registry_version=claim_registry_version,
        scope=MemoryScope(
            market=market,
            reason_codes=(
                [ReasonCode.ITEM_DAMAGED] if reason_codes is None else reason_codes
            ),
            claim_ids=(
                [ClaimId.DAMAGE_PRESENT_ON_ARRIVAL] if claim_ids is None else claim_ids
            ),
            categories=(["CAT-AUDIO-SPEAKERS"] if categories is None else categories),
        ),
        confidence=confidence,
        status=MemoryStatus.CANDIDATE,
    )


def _query(store: SqlAlchemyOperationalMemoryStore, **overrides: object) -> list:
    defaults: dict[str, object] = {
        "query_summary": "Damaged-item claim; current evidence.",
        "market": "TW",
        "reason_code": ReasonCode.ITEM_DAMAGED,
        "required_claim_ids": [ClaimId.DAMAGE_PRESENT_ON_ARRIVAL],
        "categories": ["CAT-AUDIO-SPEAKERS"],
        "policy_versions": ["RETURNS-TW:v1"],
        "claim_registry_major": 1,
        "top_k": 3,
    }
    return list(store.query_approved(**(defaults | overrides)))


def test_submission_is_idempotent_by_memory_id_and_rejects_changed_payload() -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    candidate = _candidate()

    assert store.submit_candidate(candidate) == "memory-submission:MEM-001"
    assert store.submit_candidate(candidate) == "memory-submission:MEM-001"

    with session_factory() as session:
        assert session.query(OperationalMemoryRecord).count() == 1

    changed = candidate.model_copy(update={"confidence": 0.73})
    with pytest.raises(OperationalMemoryConflictError):
        store.submit_candidate(changed)


def test_submission_rejects_pii_before_persistence() -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    candidate = _candidate().model_copy(
        update={"recommended_behavior": "Call 0912-345-678 for more evidence."}
    )

    with pytest.raises(OperationalMemoryCandidateError):
        store.submit_candidate(candidate)

    with session_factory() as session:
        assert session.query(OperationalMemoryRecord).count() == 0


def test_candidate_is_not_retrievable_until_explicit_governance_approval() -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(session_factory)
    store.submit_candidate(_candidate())

    assert _query(store) == []

    approved = governance.approve("MEM-001")
    assert approved.status == MemoryStatus.APPROVED
    assert [memory.memory.memory_id for memory in _query(store)] == ["MEM-001"]
    assert list(signature(governance.approve).parameters) == ["memory_id"]
    assert list(signature(governance.retire).parameters) == ["memory_id"]


def test_query_applies_category_policy_and_registry_major_hard_gates() -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(session_factory)
    candidates = [
        _candidate(memory_id="MEM-MATCH"),
        _candidate(
            memory_id="MEM-CATEGORY-MISMATCH",
            categories=["CAT-AUDIO-HEADPHONES"],
        ),
        _candidate(memory_id="MEM-MARKET-MISMATCH", market="SG"),
        _candidate(
            memory_id="MEM-REASON-MISMATCH",
            reason_codes=[ReasonCode.WRONG_ITEM],
        ),
        _candidate(
            memory_id="MEM-CLAIM-MISMATCH",
            claim_ids=[ClaimId.ITEM_UNUSED],
        ),
        _candidate(memory_id="MEM-POLICY-MISMATCH", policy_version="RETURNS-TW:v2"),
        _candidate(
            memory_id="MEM-REGISTRY-MISMATCH",
            claim_registry_version="claim-registry:2.0",
        ),
    ]
    for candidate in candidates:
        store.submit_candidate(candidate)
        governance.approve(candidate.memory_id)

    assert [memory.memory.memory_id for memory in _query(store)] == ["MEM-MATCH"]


def test_query_sorts_by_confidence_then_approval_time_and_honours_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(session_factory)
    candidates = [
        _candidate(memory_id="MEM-LOW", confidence=0.5),
        _candidate(memory_id="MEM-OLDER", confidence=0.9),
        _candidate(memory_id="MEM-NEWER", confidence=0.9),
    ]
    for candidate in candidates:
        store.submit_candidate(candidate)

    base = datetime.now(UTC) + timedelta(minutes=1)
    approval_times = iter([base, base + timedelta(hours=1), base + timedelta(hours=2)])
    monkeypatch.setattr(operational_memory, "_now_utc", lambda: next(approval_times))
    governance.approve("MEM-LOW")
    governance.approve("MEM-OLDER")
    governance.approve("MEM-NEWER")

    assert [memory.memory.memory_id for memory in _query(store, top_k=2)] == [
        "MEM-NEWER",
        "MEM-OLDER",
    ]


def test_lifecycle_transitions_are_ordered_and_leave_append_only_events() -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(session_factory)
    store.submit_candidate(_candidate())

    with pytest.raises(OperationalMemoryLifecycleError):
        governance.retire("MEM-001")

    governance.approve("MEM-001")
    with pytest.raises(OperationalMemoryLifecycleError):
        governance.approve("MEM-001")

    governance.retire("MEM-001")
    with pytest.raises(OperationalMemoryLifecycleError):
        governance.retire("MEM-001")
    assert _query(store) == []

    with session_factory() as session:
        events = session.scalars(
            select(OperationalMemoryEventRecord).order_by(
                OperationalMemoryEventRecord.occurred_at
            )
        ).all()
        record = session.get(OperationalMemoryRecord, "MEM-001")
    assert [(event.from_status, event.to_status) for event in events] == [
        ("CANDIDATE", "APPROVED"),
        ("APPROVED", "RETIRED"),
    ]
    assert record is not None
    assert record.status == MemoryStatus.RETIRED
    assert record.approved_at is not None
    assert record.retired_at is not None


def test_service_and_database_reject_reverse_lifecycle_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()
    store = SqlAlchemyOperationalMemoryStore(session_factory, EmbeddingFake())
    governance = OperationalMemoryGovernanceService(session_factory)
    store.submit_candidate(_candidate())

    with session_factory() as session:
        record = session.get(OperationalMemoryRecord, "MEM-001")
        assert record is not None
        submitted_at = record.submitted_at.replace(tzinfo=UTC)

    monkeypatch.setattr(
        operational_memory,
        "_now_utc",
        lambda: submitted_at - timedelta(seconds=1),
    )
    with pytest.raises(OperationalMemoryLifecycleError):
        governance.approve("MEM-001")

    with pytest.raises(IntegrityError), session_factory.begin() as session:
        record = session.get(OperationalMemoryRecord, "MEM-001")
        assert record is not None
        record.status = MemoryStatus.APPROVED.value
        record.approved_at = record.submitted_at - timedelta(seconds=1)

    approved_at = submitted_at + timedelta(seconds=1)
    monkeypatch.setattr(operational_memory, "_now_utc", lambda: approved_at)
    governance.approve("MEM-001")

    monkeypatch.setattr(operational_memory, "_now_utc", lambda: submitted_at)
    with pytest.raises(OperationalMemoryLifecycleError):
        governance.retire("MEM-001")

    with pytest.raises(IntegrityError), session_factory.begin() as session:
        record = session.get(OperationalMemoryRecord, "MEM-001")
        assert record is not None
        record.status = MemoryStatus.RETIRED.value
        record.retired_at = record.approved_at - timedelta(seconds=1)
