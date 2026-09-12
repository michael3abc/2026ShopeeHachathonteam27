from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime

import pytest
from return_agent_contracts.models import (
    DecisionRevisionEvent,
    MemoryDistillationInput,
    RevisedReviewResult,
    RevisionReason,
    UserTurn,
)
from return_agent_contracts.service import AgentResolvedEvent
from return_agent_service.broker import BrokerMessage
from return_agent_service.demo import create_demo_runtime
from return_agent_service.memory_enqueue_worker import MemoryEnqueueWorker
from return_agent_service.memory_supervision import MemoryRetryPolicy

TIME = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["initialize", "read", "checkpoint", "publish"])
async def test_same_enqueuer_recovers_and_consumes_later_events(phase) -> None:
    from psycopg import OperationalError
    from redis.exceptions import ConnectionError as RedisConnectionError

    stop = asyncio.Event()
    failed = False

    def fail_once(operation):
        nonlocal failed
        if operation == phase and not failed:
            failed = True
            if phase == "checkpoint":
                raise OperationalError("temporary checkpoint connection outage")
            raise RedisConnectionError("temporary Redis outage")

    class RecoveringInput(InputProviderFake):
        async def aget_memory_distillation_input(self, **kwargs):
            fail_once("checkpoint")
            return await super().aget_memory_distillation_input(**kwargs)

    class RecoveringBroker(EnqueueBrokerFake):
        async def ensure_memory_enqueue_consumer_group(self):
            fail_once("initialize")

        async def read_agent_event_for_memory(self, **kwargs):
            fail_once("read")
            return await super().read_agent_event_for_memory(**kwargs)

        async def publish_memory_job(self, job):
            fail_once("publish")
            return await super().publish_memory_job(job)

        async def acknowledge_agent_event_for_memory(self, message_id):
            await super().acknowledge_agent_event_for_memory(message_id)
            if message_id == "1-3":
                stop.set()

    body = _resolved_event().model_dump_json()
    broker = RecoveringBroker(body, body, body)
    worker = _worker(RecoveringInput(_prepared_input()), broker)
    worker._retry_policy = MemoryRetryPolicy(0.001, 0.002)
    await asyncio.wait_for(worker.run_forever(stop), timeout=3)
    assert failed
    assert broker.acks[-1] == "1-3"
    assert len(broker.jobs) >= 2


class InputProviderFake:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = []

    async def aget_memory_distillation_input(self, *, thread_id):
        self.calls.append(thread_id)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class EnqueueBrokerFake:
    def __init__(self, *bodies: str) -> None:
        self.messages = deque(
            BrokerMessage(message_id=f"1-{index}", body=body)
            for index, body in enumerate(bodies, start=1)
        )
        self.jobs = []
        self.acks = []
        self.fail_publish = False

    async def ensure_memory_enqueue_consumer_group(self):
        return None

    async def read_agent_event_for_memory(self, **_kwargs):
        return self.messages.popleft() if self.messages else None

    async def publish_memory_job(self, job):
        if self.fail_publish:
            raise ConnectionError("Redis unavailable")
        self.jobs.append(job)
        return "memory-job-1"

    async def acknowledge_agent_event_for_memory(self, message_id):
        self.acks.append(message_id)


def _resolved_event() -> AgentResolvedEvent:
    runtime = create_demo_runtime()
    result = runtime.start(
        thread_id="THREAD-001",
        case_ref="CASE-001",
        initial_turn=UserTurn(
            turn_id="TURN-001",
            role="USER",
            text="ORDER-DEMO 的喇叭到貨時損壞",
            attached_artifact_refs=["artifact://demo/damage"],
            received_at=TIME,
        ),
    )
    return AgentResolvedEvent(
        event_type="RESOLVED",
        event_id="EVENT-001",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=1,
        occurred_at=TIME,
        payload={"result": result},
    )


def _prepared_input() -> MemoryDistillationInput:
    runtime = create_demo_runtime()
    result = runtime.start(
        thread_id="THREAD-MEMORY-INPUT",
        case_ref="CASE-001",
        initial_turn=UserTurn(
            turn_id="TURN-MEMORY-INPUT",
            role="USER",
            text="ORDER-DEMO 的喇叭到貨時損壞",
            attached_artifact_refs=["artifact://demo/damage"],
            received_at=TIME,
        ),
    )
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-MEMORY-INPUT"}}
    ).values
    proposal = state["current_handoff"]
    review = RevisedReviewResult(
        verdict="REVISE",
        reviewer_claim_findings=state["evidence_assessment"].claim_findings,
        revision_reasons=[
            RevisionReason(
                code="EVIDENCE_INSUFFICIENT",
                message="Related evidence was split across requests.",
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


def _worker(provider, broker) -> MemoryEnqueueWorker:
    return MemoryEnqueueWorker(
        input_provider=provider,
        broker=broker,
        consumer_name="memory-enqueue-worker",
        clock=lambda: TIME,
        block_ms=1,
        reclaim_idle_ms=1,
    )


@pytest.mark.asyncio
async def test_resolved_event_enqueues_stable_memory_job_then_acks() -> None:
    event = _resolved_event()
    provider = InputProviderFake(_prepared_input())
    broker = EnqueueBrokerFake(event.model_dump_json())

    assert await _worker(provider, broker).run_once()

    assert provider.calls == ["THREAD-001"]
    assert len(broker.jobs) == 1
    job = broker.jobs[0]
    assert job.job_id == (
        f"memory:{event.payload.result.resolution_handoff.handoff_id}"
    )
    assert job.source_command_id == "COMMAND-001"
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_resolution_without_correction_payload_is_acked_without_job() -> None:
    provider = InputProviderFake(None)
    broker = EnqueueBrokerFake(_resolved_event().model_dump_json())

    assert await _worker(provider, broker).run_once()

    assert broker.jobs == []
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_memory_enqueue_failure_does_not_ack_durable_resolution_event() -> None:
    provider = InputProviderFake(_prepared_input())
    broker = EnqueueBrokerFake(_resolved_event().model_dump_json())
    broker.fail_publish = True

    with pytest.raises(ConnectionError):
        await _worker(provider, broker).run_once()

    assert broker.acks == []


@pytest.mark.asyncio
async def test_invalid_agent_event_is_consumed_without_poisoning_memory_pipeline() -> (
    None
):
    provider = InputProviderFake(_prepared_input())
    broker = EnqueueBrokerFake("{}")

    assert await _worker(provider, broker).run_once()

    assert provider.calls == []
    assert broker.jobs == []
    assert broker.acks == ["1-1"]
