"""Health-only HTTP surface for the queue-driven Agent service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException

from .broker import AgentStreamBroker
from .memory_enqueue_worker import MemoryEnqueueWorker
from .memory_worker import MemoryWorker
from .worker import AgentWorker


@dataclass(frozen=True, slots=True)
class ServiceResources:
    worker: AgentWorker
    broker: AgentStreamBroker
    memory_enqueue_worker: MemoryEnqueueWorker | None = None
    memory_worker: MemoryWorker | None = None
    ready: Callable[[], object] | None = None
    activity_publisher: object | None = None
    narration_worker: object | None = None


ResourceFactory = Callable[[], AbstractAsyncContextManager[ServiceResources]]


def create_health_app(
    *,
    worker: AgentWorker | None = None,
    broker: AgentStreamBroker | None = None,
    resource_factory: ResourceFactory | None = None,
    activity_publisher=None,
    narration_worker=None,
) -> FastAPI:
    if resource_factory is None and (worker is None or broker is None):
        raise ValueError("worker and broker are required without resource_factory")
    state: dict[str, object] = {}

    @asynccontextmanager
    async def static_resources() -> AsyncIterator[ServiceResources]:
        assert worker is not None and broker is not None
        yield ServiceResources(worker=worker, broker=broker, activity_publisher=activity_publisher, narration_worker=narration_worker)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        factory = resource_factory or static_resources
        async with factory() as resources:
            active_worker = resources.worker
            active_broker = resources.broker
            stop = asyncio.Event()
            agent_task = asyncio.create_task(
                active_worker.run_forever(stop), name="agent-worker"
            )
            tasks = [agent_task]
            for name, background in (("activity-publisher", resources.activity_publisher), ("narration-worker", resources.narration_worker)):
                if background is not None:
                    tasks.append(asyncio.create_task(background.run_forever(stop), name=name))
            if resources.memory_enqueue_worker is not None:
                tasks.append(
                    asyncio.create_task(
                        resources.memory_enqueue_worker.run_forever(stop),
                        name="memory-enqueue-worker",
                    )
                )
            if resources.memory_worker is not None:
                tasks.append(
                    asyncio.create_task(
                        resources.memory_worker.run_forever(stop),
                        name="memory-worker",
                    )
                )
            state.update(
                stop=stop,
                tasks=tasks,
                broker=active_broker,
                ready=resources.ready,
            )
            try:
                yield
            finally:
                stop.set()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await active_broker.close()

    app = FastAPI(title="Return Agent Service", lifespan=lifespan)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        tasks = state.get("tasks")
        if (
            not isinstance(tasks, list)
            or not tasks
            or any(not isinstance(task, asyncio.Task) or task.done() for task in tasks)
        ):
            raise HTTPException(status_code=503, detail="Agent workers are not running")
        active_broker = state.get("broker")
        if active_broker is None or not await active_broker.ping():
            raise HTTPException(status_code=503, detail="Redis is unavailable")
        ready_check = state.get("ready")
        if callable(ready_check):
            outcome = ready_check()
            if asyncio.iscoroutine(outcome):
                outcome = await outcome
            if not outcome:
                raise HTTPException(
                    status_code=503,
                    detail="Agent persistence is unavailable",
                )
        return {"status": "ready"}

    return app
