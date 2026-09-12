from __future__ import annotations

import asyncio

import pytest
from redis.exceptions import AuthenticationError, ConnectionError, ResponseError
from return_agent_service.memory_supervision import (
    MemoryRetryPolicy,
    is_transient_transport_error,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ValueError("invalid contract"),
        AuthenticationError("auth"),
        ResponseError("WRONGTYPE"),
    ],
)
async def test_permanent_errors_exit_without_retry(error) -> None:
    calls = 0

    async def initialize():
        pass

    async def run_once():
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(type(error)):
        await MemoryRetryPolicy(0.001, 0.002).run(
            stop=asyncio.Event(),
            initialize=initialize,
            run_once=run_once,
            worker_name="test-worker",
        )
    assert calls == 1
    assert not is_transient_transport_error(error)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_stop_and_cancellation_interrupt_backoff(cancel) -> None:
    attempted = asyncio.Event()
    stop = asyncio.Event()

    async def initialize():
        pass

    async def run_once():
        attempted.set()
        raise ConnectionError("temporary")

    task = asyncio.create_task(
        MemoryRetryPolicy(30, 30).run(
            stop=stop,
            initialize=initialize,
            run_once=run_once,
            worker_name="test-worker",
        )
    )
    await asyncio.wait_for(attempted.wait(), timeout=1)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        stop.set()
        await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_backoff_is_capped_and_resets_after_success(monkeypatch) -> None:
    delays = []
    stop = asyncio.Event()
    attempts = 0

    async def initialize():
        pass

    async def run_once():
        nonlocal attempts
        attempts += 1
        if attempts == 4:
            return True
        if attempts == 6:
            stop.set()
            return False
        raise ConnectionError("temporary")

    async def wait_for(awaitable, *, timeout):
        awaitable.close()
        delays.append(timeout)
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", wait_for)
    await MemoryRetryPolicy(0.5, 1).run(
        stop=stop,
        initialize=initialize,
        run_once=run_once,
        worker_name="test-worker",
    )
    assert delays == [0.5, 1, 1, 0.5]


@pytest.mark.parametrize(
    "initial,maximum", [(0, 1), (-1, 1), (2, 1), (1, float("inf")), (float("nan"), 1)]
)
def test_invalid_retry_settings_are_rejected(initial, maximum) -> None:
    with pytest.raises(ValueError):
        MemoryRetryPolicy(initial, maximum)
