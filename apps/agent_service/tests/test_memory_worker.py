from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from return_agent_contracts.activity import BackgroundStatus, Lifecycle, NodeSummary
from return_agent_contracts.models import (
    DecisionRevisionEvent,
    MemoryCandidateOutput,
    MemoryDistillationInput,
    MemorySkipOutput,
    RevisedReviewResult,
    RevisionReason,
    UserTurn,
)
from return_agent_contracts.service import MemoryDistillationJob
from return_agent_service.broker import BrokerMessage
from return_agent_service.demo import create_demo_runtime
from return_agent_service.journal import CommandClaim, InMemoryCommandJournal
from return_agent_service.memory_replay import SqlAlchemyMemoryReplayStore
from return_agent_service.memory_supervision import MemoryRetryPolicy
from return_agent_service.memory_worker import MemoryWorker
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

TIME = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def replay_engine(tmp_path: Path):
    url = os.environ.get("AGENT_TEST_POSTGRES_URL")
    if not url:
        engine = create_engine(f"sqlite:///{tmp_path / 'replay.db'}")
        try:
            yield engine
        finally:
            engine.dispose()
        return
    schema = f"pr18_replay_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(
        make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


@pytest.mark.asyncio
async def test_agent_migration_and_first_result_survive_reopen(replay_engine) -> None:
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    job = _job()
    await store.load(job, "memory:v1")
    output = CandidateDistiller().distill(job.payload.input)
    await store.save_result(job, output)
    reopened = SqlAlchemyMemoryReplayStore(replay_engine)
    reopened.migrate()
    assert (await reopened.load(job, "memory:v2")).result == output
    with replay_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT version_num FROM agent_service_alembic_version")
            )
            == "0002_memory_model_profile"
        )
        assert "alembic_version" not in inspect(connection).get_table_names()


@pytest.mark.asyncio
async def test_concurrent_first_results_share_one_canonical_output(
    replay_engine,
) -> None:
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    job = _job()
    await asyncio.gather(*(store.load(job, "memory:v1") for _ in range(4)))
    candidate = CandidateDistiller().distill(job.payload.input)
    skip = MemorySkipOutput(
        result_type="SKIP", reason_code="NO_CONFIRMED_GENERALIZABLE_CORRECTION"
    )
    results = await asyncio.gather(
        store.save_result(job, candidate), store.save_result(job, skip)
    )
    assert results[0].result == results[1].result


def memory_reflection():
    return {
        "case_review": {"key_issue": "Evidence context matters.", "actions_taken": ["Assessed evidence."],
            "observations": ["Observed damage."], "judgment_changes": [], "final_action": "FULL_REFUND",
            "limitations": ["Execution and causal benefit not verified."], "source_event_refs": ["EVENT-1"]},
        "learning": {"category": "OPERATIONAL_METHOD", "explanation": "A context-aware observation.",
            "source_event_refs": ["EVENT-1"]},
    }


class CandidateDistiller:
    prompt_version = "memory-distiller:test"

    def distill(self, _input):
        return MemoryCandidateOutput(
            result_type="CREATE_CANDIDATE",
            **memory_reflection(),
            candidate={
                "memory_id": "MEMORY-001",
                "retrieval_summary": "Reviewer correction required; apply the cited correction before review.",
                "trigger_conditions": ["Reviewer corrected a recurring evidence gap."],
                "recommended_behavior": "Request the missing evidence together.",
                "rationale": "The corrected proposal was approved.",
                "source_case_refs": ["CASE-001"],
                "source_event_refs": ["REVISION-001"],
                "policy_version": "POLICY-DEMO:v1",
                "claim_registry_version": "claim-registry:1.0",
                "scope": {
                    "market": "TW",
                    "reason_codes": ["ITEM_DAMAGED"],
                    "claim_ids": ["DAMAGE_PRESENT_ON_ARRIVAL"],
                    "categories": ["CAT-AUDIO-SPEAKERS"],
                },
                "confidence": 0.8,
                "status": "CANDIDATE",
            },
        )


class SkipDistiller:
    prompt_version = "memory-distiller:test"

    def distill(self, _input):
        return MemorySkipOutput(
            result_type="SKIP",
            reason_code="NO_CONFIRMED_GENERALIZABLE_CORRECTION",
        )


class FailingDistiller:
    prompt_version = "memory-distiller:test"

    def distill(self, _input):
        raise RuntimeError("private@example.com must not enter an event")


class CandidateStore:
    def __init__(self) -> None:
        self.candidates = {}

    def submit_candidate(self, candidate):
        existing = self.candidates.get(candidate.memory_id)
        if existing is not None and existing != candidate:
            raise ValueError("candidate content is immutable")
        self.candidates[candidate.memory_id] = candidate
        return f"submission:{candidate.memory_id}"


class MemoryBrokerFake:
    def __init__(self, *bodies: str) -> None:
        self.messages = deque(
            BrokerMessage(message_id=f"1-{index}", body=body)
            for index, body in enumerate(bodies, start=1)
        )
        self.events = []
        self.dead_letters = []
        self.acks = []
        self.fail_event_publication = False

    async def ensure_memory_consumer_group(self):
        return None

    async def read_memory_job(self, **_kwargs):
        return self.messages.popleft() if self.messages else None

    async def publish_memory_event(self, event):
        if self.fail_event_publication:
            raise ConnectionError("Redis unavailable")
        self.events.append(event)
        return f"event-{len(self.events)}"

    async def publish_memory_dead_letter(self, dead_letter):
        self.dead_letters.append(dead_letter)
        return "dlq-1"

    async def acknowledge_memory_job(self, message_id):
        self.acks.append(message_id)


def _memory_input() -> MemoryDistillationInput:
    runtime = create_demo_runtime()
    result = runtime.start(
        thread_id="THREAD-MEMORY-FIXTURE",
        case_ref="CASE-001",
        initial_turn=UserTurn(
            turn_id="TURN-001",
            role="USER",
            text="ORDER-DEMO 的喇叭到貨時損壞",
            attached_artifact_refs=["artifact://demo/damage"],
            received_at=TIME,
        ),
    )
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-MEMORY-FIXTURE"}}
    ).values
    proposal = state["current_handoff"]
    review = RevisedReviewResult(
        verdict="REVISE",
        reviewer_claim_findings=state["evidence_assessment"].claim_findings,
        revision_reasons=[
            RevisionReason(
                code="EVIDENCE_INSUFFICIENT",
                message="The original evidence request split related evidence.",
                subject="LI-DEMO",
                required_change="Request the package and damage together.",
            )
        ],
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at=TIME,
    )
    return MemoryDistillationInput(
        case_context=state["case_context"],
        policy_bundle=state["policy_bundle"],
        evidence_assessment=state["evidence_assessment"],
        proposal_history=[proposal],
        revision_events=[
            DecisionRevisionEvent(
                event_id="REVISION-001",
                case_ref="CASE-001",
                handoff_before_ref=proposal.handoff_id,
                review_result=review,
                revision_round=1,
                created_at=TIME,
            )
        ],
        final_resolution=result.resolution_handoff,
        claimed_categories=["CAT-AUDIO-SPEAKERS"],
    )


def _job() -> MemoryDistillationJob:
    return MemoryDistillationJob(
        job_id="memory:HANDOFF-001",
        source_command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        issued_at=TIME,
        payload={"input": _memory_input()},
    )


def _worker(distiller, broker, store, journal, replay_store=None) -> MemoryWorker:
    if replay_store is None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        replay_store = SqlAlchemyMemoryReplayStore(engine)
        replay_store.migrate()
    return MemoryWorker(
        distiller=distiller,
        store=store,
        broker=broker,
        journal=journal,
        replay_store=replay_store,
        consumer_name="memory-worker",
        clock=lambda: TIME,
        block_ms=1,
        reclaim_idle_ms=1,
    )


@pytest.mark.asyncio
async def test_memory_worker_submits_candidate_before_acknowledging_job() -> None:
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json())
    store = CandidateStore()
    worker = _worker(CandidateDistiller(), broker, store, InMemoryCommandJournal())

    assert await worker.run_once() is True

    assert list(store.candidates) == ["MEMORY-001"]
    assert broker.events[0].event_type == "COMPLETED"
    assert broker.events[0].payload.submission_ref == "submission:MEMORY-001"
    assert broker.events[0].payload.distiller_prompt_version == (
        "memory-distiller:test"
    )
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_memory_worker_skip_does_not_submit_candidate() -> None:
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json())
    store = CandidateStore()

    assert await _worker(
        SkipDistiller(), broker, store, InMemoryCommandJournal()
    ).run_once()

    assert store.candidates == {}
    assert broker.events[0].payload.result.result_type == "SKIP"
    assert broker.events[0].payload.submission_ref is None
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_invalid_memory_job_is_dead_lettered_and_acked() -> None:
    broker = MemoryBrokerFake("{}")
    store = CandidateStore()

    assert await _worker(
        CandidateDistiller(), broker, store, InMemoryCommandJournal()
    ).run_once()

    assert broker.dead_letters[0].error_code == "INVALID_MEMORY_JOB"
    assert broker.acks == ["1-1"]
    assert store.candidates == {}


@pytest.mark.asyncio
async def test_v1_pending_job_is_never_reinterpreted():
    import json
    payload = _job().model_dump(mode="json")
    payload["schema_version"] = "v1"
    broker = MemoryBrokerFake(json.dumps(payload))
    store = CandidateStore()
    assert await _worker(CandidateDistiller(), broker, store, InMemoryCommandJournal()).run_once()
    assert broker.dead_letters[0].error_code == "INVALID_MEMORY_JOB"
    assert store.candidates == {} and broker.events == []


@pytest.mark.asyncio
async def test_pending_replay_refuses_prompt_version_change(replay_engine):
    from return_agent_service.memory_replay import MemoryReplayConflictError
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    await store.load(_job(), "memory-distiller:old")
    with pytest.raises(MemoryReplayConflictError, match="different prompt version"):
        await store.load(_job(), "memory-distiller:new")
    assert (await store.load(_job(), "memory-distiller:old")).result is None


@pytest.mark.asyncio
async def test_replay_pins_profile_but_replays_first_result_after_model_change(replay_engine):
    from return_agent_service.memory_replay import MemoryReplayConflictError
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    job = _job()
    profile = {"model": "compass-5.6-sol", "reasoning_effort": "high"}
    different = profile | {"reasoning_effort": "low"}
    assert (await store.load(job, "memory:3.1", profile)).model_profile == profile
    with pytest.raises(MemoryReplayConflictError, match="different model profile"):
        await store.load(job, "memory:3.1", different)
    output = CandidateDistiller().distill(job.payload.input)
    await store.save_result(job, output)
    reopened = SqlAlchemyMemoryReplayStore(replay_engine)
    replay = await reopened.load(job, "memory:future", different)
    assert replay.result == output and replay.model_profile == profile


@pytest.mark.asyncio
async def test_upgrade_preserves_legacy_hash_results_and_pending_jobs(replay_engine):
    import json
    from hashlib import sha256

    import return_agent_service.memory_replay as replay_module
    from alembic import command
    from alembic.config import Config
    from return_agent_contracts.models import LearningTrace

    config = Config()
    config.set_main_option("script_location", str(Path(replay_module.__file__).with_name("migrations")))
    job = _job()
    job.payload.input.learning_trace = LearningTrace(
        case_ref=job.case_ref, thread_id=job.thread_id, status="COMPLETE",
        events=[{"event_id": "LEARNING-START", "sequence": 1, "node": "parse_request"},
                {"event_id": "LEARNING-END", "sequence": 2, "node": "emit_resolution_handoff"}],
    )
    # Emulate the actual pre-dialogue serialized DTO and its old hash.
    legacy = job.model_dump(mode="json", exclude={"issued_at"})
    trace = legacy["payload"]["input"]["learning_trace"]
    trace.pop("dialogue_version")
    for event in trace["events"]:
        event.pop("dialogue")
        event.pop("dialogue_missing")
    job = MemoryDistillationJob.model_validate(legacy | {"issued_at": TIME})
    old_hash = sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest()
    assert replay_module.SqlAlchemyMemoryReplayStore._hash(job) == old_hash
    with replay_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_memory_replay")
        connection.execute(text("INSERT INTO memory_job_results (job_id,input_hash,prompt_version) VALUES (:job,:hash,:prompt)"),
                           {"job": job.job_id, "hash": old_hash, "prompt": "memory:3.0"})
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    assert (await store.load(job, "memory:3.0")).model_profile is None
    with pytest.raises(replay_module.MemoryReplayConflictError, match="different prompt version"):
        await store.load(job, "memory:3.1", {"model": "compass-5.6-sol"})
    output = CandidateDistiller().distill(job.payload.input)
    await store.save_result(job, output)
    assert (await store.load(job, "memory:3.1", {"model": "compass-5.6-sol"})).result == output
    job.payload.input.learning_trace.events[0].dialogue_missing = True
    with pytest.raises(replay_module.MemoryReplayConflictError, match="conflicting input"):
        await store.load(job, "memory:3.1")


@pytest.mark.asyncio
async def test_profile_migration_downgrade_cannot_erase_provenance(replay_engine):
    import return_agent_service.memory_replay as replay_module
    from alembic import command
    from alembic.config import Config
    store = SqlAlchemyMemoryReplayStore(replay_engine)
    store.migrate()
    await store.load(_job(), "memory:3.1", {"model": "compass-5.6-sol"})
    config = Config()
    config.set_main_option("script_location", str(Path(replay_module.__file__).with_name("migrations")))
    with replay_engine.begin() as connection:
        config.attributes["connection"] = connection
        with pytest.raises(RuntimeError, match="provenance"):
            command.downgrade(config, "0001_memory_replay")
    assert (await store.load(_job(), "memory:3.1", {"model": "compass-5.6-sol"})).model_profile is not None


@pytest.mark.asyncio
async def test_duplicate_terminal_memory_job_is_not_submitted_twice() -> None:
    body = _job().model_dump_json()
    broker = MemoryBrokerFake(body, body)
    store = CandidateStore()
    journal = InMemoryCommandJournal()
    worker = _worker(CandidateDistiller(), broker, store, journal)

    assert await worker.run_once()
    assert await worker.run_once()

    assert list(store.candidates) == ["MEMORY-001"]
    assert len(broker.events) == 1
    assert broker.acks == ["1-1", "1-2"]


@pytest.mark.asyncio
async def test_distillation_failure_is_isolated_as_terminal_memory_event() -> None:
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json())
    store = CandidateStore()

    assert await _worker(
        FailingDistiller(), broker, store, InMemoryCommandJournal()
    ).run_once()

    assert broker.events[0].event_type == "FAILED"
    assert broker.events[0].payload.retryable is False
    assert "private@example.com" not in broker.events[0].payload.message
    assert broker.acks == ["1-1"]
    assert store.candidates == {}


@pytest.mark.asyncio
async def test_event_publish_failure_leaves_job_pending_and_releases_claim() -> None:
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json())
    broker.fail_event_publication = True
    journal = InMemoryCommandJournal()
    worker = _worker(CandidateDistiller(), broker, CandidateStore(), journal)

    with pytest.raises(ConnectionError):
        await worker.run_once()

    assert broker.acks == []
    assert await journal.claim(job.job_id) is CommandClaim.CLAIMED


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_phase", ["publish", "save_event"])
async def test_redelivery_after_submission_uses_durable_first_result(
    tmp_path: Path,
    failure_phase: str,
) -> None:
    from return_agent.capabilities.operational_memory import (
        OperationalMemoryConflictError,
        SqlAlchemyOperationalMemoryStore,
    )
    from return_agent.db.models import Base, OperationalMemoryRecord
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    class ChangingDistiller(CandidateDistiller):
        calls = 0

        def distill(self, input_):
            self.calls += 1
            output = super().distill(input_)
            output.candidate.rationale = f"Valid summary variant {self.calls}."
            return output

    class InterruptReplayStore(SqlAlchemyMemoryReplayStore):
        async def save_event(self, job, event):
            raise ConnectionError("save terminal event unavailable")

    api_engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(api_engine)
    sessions = sessionmaker(api_engine, expire_on_commit=False)

    class EmbeddingFake:
        model_name = "text-embedding-3-large"
        dimensions = 1536

        def embed(self, text):
            return [1.0] + [0.0] * 1535

    store = SqlAlchemyOperationalMemoryStore(sessions, EmbeddingFake())
    agent_url = f"sqlite:///{tmp_path / 'agent.db'}"
    agent_engine = create_engine(agent_url)
    replay_type = (
        InterruptReplayStore
        if failure_phase == "save_event"
        else SqlAlchemyMemoryReplayStore
    )
    replay_store = replay_type(agent_engine)
    replay_store.migrate()
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json(), job.model_dump_json())
    broker.fail_event_publication = failure_phase == "publish"
    distiller = ChangingDistiller()
    journal = InMemoryCommandJournal()
    worker = _worker(distiller, broker, store, journal, replay_store)
    with pytest.raises(ConnectionError):
        await worker.run_once()
    assert broker.acks == []
    with sessions() as session:
        stored = session.scalar(select(OperationalMemoryRecord))
        assert stored.rationale == "Valid summary variant 1."
    agent_engine.dispose()

    # Reconstruct worker and database connections as after a process restart.
    restarted_engine = create_engine(agent_url)
    restarted_store = SqlAlchemyMemoryReplayStore(restarted_engine)
    restarted_store.migrate()
    broker.fail_event_publication = False
    worker = _worker(distiller, broker, store, journal, restarted_store)
    assert await worker.run_once()
    assert distiller.calls == 1
    assert broker.events[-1].event_type == "COMPLETED"
    assert (
        broker.events[-1].payload.result.candidate.rationale
        == "Valid summary variant 1."
    )
    assert broker.acks == ["1-2"]
    with pytest.raises(OperationalMemoryConflictError):
        store.submit_candidate(distiller.distill(job.payload.input).candidate)
    restarted_engine.dispose()
    api_engine.dispose()


@pytest.mark.asyncio
async def test_failed_job_replays_the_same_failure_event_without_model_call() -> None:
    class CountingFailure(FailingDistiller):
        calls = 0

        def distill(self, input_):
            self.calls += 1
            return super().distill(input_)

    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json(), job.model_dump_json())
    broker.fail_event_publication = True
    distiller = CountingFailure()
    worker = _worker(distiller, broker, CandidateStore(), InMemoryCommandJournal())
    with pytest.raises(ConnectionError):
        await worker.run_once()
    broker.fail_event_publication = False
    assert await worker.run_once()
    assert distiller.calls == 1
    assert broker.events[-1].event_type == "FAILED"


@pytest.mark.asyncio
async def test_replay_store_rejects_changed_input_and_keeps_first_output() -> None:
    from return_agent_service.memory_replay import MemoryReplayConflictError

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    store = SqlAlchemyMemoryReplayStore(engine)
    store.migrate()
    job = _job()
    await store.load(job, "prompt:v1")
    first = CandidateDistiller().distill(job.payload.input)
    await store.save_result(job, first)
    second = first.model_copy(deep=True)
    second.candidate.rationale = "Another valid explanation."
    assert (await store.save_result(job, second)).result == first
    assert (await store.load(job, "prompt:v2")).prompt_version == "prompt:v1"
    changed = job.model_copy(update={"source_command_id": "OTHER-COMMAND"})
    with pytest.raises(MemoryReplayConflictError):
        await store.load(changed, "prompt:v1")
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["initialize", "read", "publish"])
async def test_same_memory_worker_recovers_transport_and_processes_next_job(
    phase,
) -> None:
    from redis.exceptions import ConnectionError as RedisConnectionError

    stop = asyncio.Event()

    class RecoveringBroker(MemoryBrokerFake):
        failed = False

        def fail_once(self, operation):
            if phase == operation and not self.failed:
                self.failed = True
                raise RedisConnectionError("temporary Redis outage")

        async def ensure_memory_consumer_group(self):
            self.fail_once("initialize")

        async def read_memory_job(self, **kwargs):
            self.fail_once("read")
            return await super().read_memory_job(**kwargs)

        async def publish_memory_event(self, event):
            self.fail_once("publish")
            return await super().publish_memory_event(event)

        async def acknowledge_memory_job(self, message_id):
            await super().acknowledge_memory_job(message_id)
            if message_id == "1-3":
                stop.set()

    job = _job()
    next_job = job.model_copy(update={"job_id": "memory:SECOND"})
    broker = RecoveringBroker(
        job.model_dump_json(), job.model_dump_json(), next_job.model_dump_json()
    )
    worker = _worker(
        SkipDistiller(), broker, CandidateStore(), InMemoryCommandJournal()
    )
    worker._retry_policy = MemoryRetryPolicy(0.001, 0.002)
    await asyncio.wait_for(worker.run_forever(stop), timeout=3)
    assert broker.failed
    assert {event.job_id for event in broker.events} == {job.job_id, next_job.job_id}
    assert all(event.event_type == "COMPLETED" for event in broker.events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "distiller,status",
    [
        (CandidateDistiller, "COMPLETED"),
        (SkipDistiller, "SKIPPED"),
        (FailingDistiller, "FAILED"),
    ],
)
async def test_memory_activity_attempt_and_terminal_replay(distiller, status):
    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json(), job.model_dump_json())
    worker = _worker(distiller(), broker, CandidateStore(), InMemoryCommandJournal())
    events = []
    worker._activity_sink = events.append
    await worker.run_once()
    assert len({event.attempt_id for event in events}) == 1
    assert all(
        event.scope == "MEMORY" and event.job_id == job.job_id for event in events
    )
    assert [
        event.payload.status
        for event in events
        if isinstance(event.payload, BackgroundStatus)
    ] == ["STARTED", status]
    count = len(events)
    await worker.run_once()
    assert len(events) == count
    assert "private@example.com" not in str([e.model_dump_json() for e in events])
    if status != "FAILED":
        assert any(isinstance(e.payload, NodeSummary) for e in events)
    else:
        assert any(
            isinstance(e.payload, Lifecycle) and e.payload.phase == "FAILED"
            for e in events
        )


@pytest.mark.asyncio
async def test_memory_retry_uses_new_attempt_without_redistilling():
    class TransientStore(CandidateStore):
        calls = 0

        def submit_candidate(self, candidate):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("transient test")
            return super().submit_candidate(candidate)

    job = _job()
    broker = MemoryBrokerFake(job.model_dump_json(), job.model_dump_json())
    worker = _worker(
        CandidateDistiller(), broker, TransientStore(), InMemoryCommandJournal()
    )
    events = []
    worker._activity_sink = events.append
    with pytest.raises(ConnectionError):
        await worker.run_once()
    await worker.run_once()
    assert len({event.attempt_id for event in events}) == 2
    statuses = [
        e.payload.status for e in events if isinstance(e.payload, BackgroundStatus)
    ]
    assert statuses == ["STARTED", "RETRYING", "STARTED", "COMPLETED"]
    assert (
        len(
            [
                e
                for e in events
                if e.node == "distill_memory" and isinstance(e.payload, NodeSummary)
            ]
        )
        == 1
    )
