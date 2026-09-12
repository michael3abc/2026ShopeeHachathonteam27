"""Retry only safe transport operations with capped, interruptible backoff."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import psycopg
from redis import exceptions as redis_errors
from return_agent_contracts.http_adapters import ProviderTransportError
from sqlalchemy.exc import DBAPIError

LOGGER = logging.getLogger(__name__)


def is_transient_transport_error(error: Exception) -> bool:
    if isinstance(
        error, (redis_errors.AuthenticationError, redis_errors.AuthorizationError)
    ):
        return False
    if isinstance(
        error,
        (
            ConnectionError,
            TimeoutError,
            redis_errors.ConnectionError,
            redis_errors.TimeoutError,
            redis_errors.BusyLoadingError,
        ),
    ):
        return True
    if isinstance(error, DBAPIError):
        return is_transient_transport_error(error.orig)
    if isinstance(error, (psycopg.OperationalError, psycopg.InterfaceError)):
        code = error.sqlstate
        return (
            code is None
            or code.startswith("08")
            or code
            in {
                "57P01",
                "57P02",
                "57P03",
                "40001",
                "40P01",
            }
        )
    if isinstance(error, ProviderTransportError):
        return isinstance(error.__cause__, (httpx.NetworkError, httpx.TimeoutException))
    return False


@dataclass(frozen=True)
class MemoryRetryPolicy:
    initial_seconds: float = 0.25
    max_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not (
            math.isfinite(self.initial_seconds)
            and math.isfinite(self.max_seconds)
            and 0 < self.initial_seconds <= self.max_seconds
        ):
            raise ValueError(
                "memory retry delays must be finite and 0 < initial <= max"
            )

    async def run(
        self,
        *,
        stop: asyncio.Event,
        initialize: Callable[[], Awaitable[None]],
        run_once: Callable[[], Awaitable[bool]],
        worker_name: str,
    ) -> None:
        initialized = False
        delay = self.initial_seconds
        while not stop.is_set():
            try:
                if not initialized:
                    await initialize()
                    initialized = True
                await run_once()
            except Exception as error:
                if not is_transient_transport_error(error):
                    raise
                LOGGER.warning(
                    "%s transport failure (%s); retrying in %.3fs",
                    worker_name,
                    type(error).__name__,
                    delay,
                )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
                delay = min(delay * 2, self.max_seconds)
            else:
                delay = self.initial_seconds
