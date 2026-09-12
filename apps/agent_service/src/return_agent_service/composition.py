"""Agent service composition root."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from return_agent_contracts import (
    HttpCaseContextProvider,
    HttpEvidenceProvider,
    HttpHumanReviewProvider,
    HttpOperationalMemoryStore,
    HttpPolicyProvider,
    HttpVerificationProvider,
)
from return_agent_contracts.activity_observer import ObservedProvider
from return_agent_contracts.review_gates import load_reviewer_gate_config
from return_agent_runtime import (
    AgentDependencies,
    MemoryDistiller,
    ReturnAgentRuntime,
    create_checkpoint_serializer,
)
from return_agent_runtime.model import StructuredOutputModel
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from .activity_workers import ActivityPublisher, NarrationWorker
from .app import ServiceResources, create_health_app
from .broker import RedisStreamBroker
from .journal import InMemoryCommandJournal, PostgresCommandJournal
from .memory_enqueue_worker import MemoryEnqueueWorker
from .memory_replay import SqlAlchemyMemoryReplayStore
from .memory_supervision import MemoryRetryPolicy
from .memory_worker import MemoryWorker
from .settings import AgentServiceSettings
from .worker import AgentWorker, ObservableAgentRuntime


def activity_workers(
    broker: RedisStreamBroker, model: StructuredOutputModel | None
) -> tuple[ActivityPublisher, NarrationWorker]:
    return (
        ActivityPublisher(
            broker.transport_client,
            capacity=int(os.getenv("RETURN_AGENT_ACTIVITY_QUEUE_SIZE", "1024")),
        ),
        NarrationWorker(
            broker.transport_client,
            model,
            timeout=float(os.getenv("RETURN_AGENT_NARRATION_TIMEOUT_SECONDS", "20")),
            concurrency=int(os.getenv("RETURN_AGENT_NARRATION_CONCURRENCY", "2")),
        ),
    )


def compose_service(
    *,
    settings: AgentServiceSettings,
    runtime: ObservableAgentRuntime,
) -> FastAPI:
    """Compose transport around an injected runtime.

    The in-memory journal is deliberately restricted to the demo profile.
    Production composition must inject durable checkpoint/journal/provider
    implementations in a later integration owned by their respective teams.
    """

    if settings.profile not in {"demo", "demo-qwen"}:
        raise RuntimeError(
            "production Agent service composition requires durable adapters"
        )
    broker = RedisStreamBroker.from_url(settings.redis_url)
    narration_model = None if settings.profile == "demo" else runtime.dependencies.model
    publisher, narrator = activity_workers(broker, narration_model)
    worker = AgentWorker(
        activity_sink=publisher.submit,
        runtime=runtime,
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name=settings.consumer_name,
        block_ms=settings.block_ms,
        reclaim_idle_ms=settings.reclaim_idle_ms,
    )
    return create_health_app(worker=worker, broker=broker, activity_publisher=publisher, narration_worker=narrator)


def compose_integrated_service(
    *,
    settings: AgentServiceSettings,
    model: object,
) -> FastAPI:
    """Compose Qwen with API-backed Providers and Agent-owned persistence."""

    token = settings.internal_service_token
    if not token or not token.strip():
        raise RuntimeError("integrated service requires an internal service token")
    if not settings.agent_database_url.strip() or not settings.api_base_url.strip():
        raise RuntimeError("integrated service requires Agent DB and API URLs")
    memory_retry = MemoryRetryPolicy(
        settings.memory_retry_initial_seconds, settings.memory_retry_max_seconds
    )

    @asynccontextmanager
    async def resources():
        client = httpx.Client(timeout=settings.provider_timeout_seconds)
        broker = RedisStreamBroker.from_url(settings.redis_url)
        journal = PostgresCommandJournal(
            settings.agent_database_url,
            owner=settings.consumer_name,
            lease_seconds=settings.command_lease_seconds,
        )
        replay_engine = create_engine(
            make_url(settings.agent_database_url).set(drivername="postgresql+psycopg"),
            pool_pre_ping=True,
        )
        replay_store = SqlAlchemyMemoryReplayStore(replay_engine)
        try:
            await asyncio.to_thread(replay_store.migrate)
            await journal.setup()
            async with AsyncPostgresSaver.from_conn_string(
                settings.agent_database_url,
                serde=create_checkpoint_serializer(),
            ) as checkpointer:
                await checkpointer.setup()
                provider_args = {
                    "base_url": settings.api_base_url,
                    "service_token": token,
                    "timeout_seconds": settings.provider_timeout_seconds,
                    "client": client,
                }
                dependencies = AgentDependencies(
                    reviewer_gate_config=load_reviewer_gate_config(os.environ.get("RETURN_AGENT_REVIEW_GATE_CONFIG")),
                    model=model,
                    case_context_provider=HttpCaseContextProvider(**provider_args),
                    policy_provider=HttpPolicyProvider(**provider_args),
                    verification_provider=HttpVerificationProvider(**provider_args),
                    human_review_provider=HttpHumanReviewProvider(**provider_args),
                    operational_memory_store=HttpOperationalMemoryStore(
                        **provider_args
                    ),
                    evidence_provider=HttpEvidenceProvider(**provider_args),
                )
                runtime = ReturnAgentRuntime(dependencies, checkpointer)
                publisher, narrator = activity_workers(broker, model)
                worker = AgentWorker(
                    activity_sink=publisher.submit,
                    runtime=runtime,
                    broker=broker,
                    journal=journal,
                    consumer_name=settings.consumer_name,
                    block_ms=settings.block_ms,
                    reclaim_idle_ms=settings.reclaim_idle_ms,
                )
                memory_enqueue_worker = MemoryEnqueueWorker(
                    activity_sink=publisher.submit,
                    input_provider=runtime,
                    broker=broker,
                    consumer_name=f"{settings.consumer_name}-memory-enqueue",
                    block_ms=settings.block_ms,
                    reclaim_idle_ms=settings.reclaim_idle_ms,
                    retry_policy=memory_retry,
                )
                memory_worker = MemoryWorker(
                    activity_sink=publisher.submit,
                    distiller=MemoryDistiller(model=ObservedProvider(model, "model", "model")),
                    store=ObservedProvider(dependencies.operational_memory_store, "operational_memory_store"),
                    broker=broker,
                    journal=journal,
                    replay_store=replay_store,
                    consumer_name=f"{settings.consumer_name}-memory",
                    block_ms=settings.block_ms,
                    reclaim_idle_ms=settings.reclaim_idle_ms,
                    retry_policy=memory_retry,
                )
                yield ServiceResources(
                    activity_publisher=publisher, narration_worker=narrator,
                    worker=worker,
                    broker=broker,
                    memory_enqueue_worker=memory_enqueue_worker,
                    memory_worker=memory_worker,
                    ready=journal.ping,
                )
        finally:
            client.close()
            await journal.close()
            await asyncio.to_thread(replay_engine.dispose)

    return create_health_app(resource_factory=resources)
