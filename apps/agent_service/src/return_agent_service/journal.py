"""Command idempotency port; production must provide a durable implementation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from psycopg_pool import AsyncConnectionPool


class CommandClaim(StrEnum):
    CLAIMED = "CLAIMED"
    BUSY = "BUSY"
    TERMINAL = "TERMINAL"


class CommandJournal(Protocol):
    async def claim(self, command_id: str) -> CommandClaim: ...

    async def complete(self, command_id: str) -> None: ...

    async def fail(self, command_id: str) -> None: ...

    async def abandon(self, command_id: str) -> None: ...


class InMemoryCommandJournal:
    """Development-only journal; state is lost when the process restarts."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def claim(self, command_id: str) -> CommandClaim:
        async with self._lock:
            state = self._states.get(command_id)
            if state in {"COMPLETED", "FAILED"}:
                return CommandClaim.TERMINAL
            if state == "RUNNING":
                return CommandClaim.BUSY
            self._states[command_id] = "RUNNING"
            return CommandClaim.CLAIMED

    async def complete(self, command_id: str) -> None:
        await self._finish(command_id, "COMPLETED")

    async def fail(self, command_id: str) -> None:
        await self._finish(command_id, "FAILED")

    async def abandon(self, command_id: str) -> None:
        async with self._lock:
            if self._states.get(command_id) == "RUNNING":
                del self._states[command_id]

    async def _finish(self, command_id: str, state: str) -> None:
        async with self._lock:
            if self._states.get(command_id) != "RUNNING":
                raise RuntimeError(f"command {command_id} is not claimed")
            self._states[command_id] = state


class PostgresCommandJournal:
    """Lease-based durable command idempotency for Agent Service replicas."""

    def __init__(
        self,
        conninfo: str,
        *,
        owner: str,
        lease_seconds: int = 900,
    ) -> None:
        if not conninfo.strip() or not owner.strip():
            raise ValueError("conninfo and owner must be non-empty")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._owner = owner
        self._lease_seconds = lease_seconds
        self._pool = AsyncConnectionPool(conninfo, open=False)

    async def setup(self) -> None:
        await self._pool.open()
        async with self._pool.connection() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_command_journal (
                    command_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL CHECK (
                        state IN ('RUNNING', 'COMPLETED', 'FAILED')
                    ),
                    claimed_by TEXT,
                    claimed_until TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    async def close(self) -> None:
        await self._pool.close()

    async def ping(self) -> bool:
        try:
            async with self._pool.connection() as connection:
                await connection.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - readiness reports false
            return False

    async def claim(self, command_id: str) -> CommandClaim:
        now = datetime.now(UTC)
        claimed_until = now + timedelta(seconds=self._lease_seconds)
        async with self._pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    SELECT state, claimed_by, claimed_until
                    FROM agent_command_journal
                    WHERE command_id = %s
                    FOR UPDATE
                    """,
                    (command_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    await connection.execute(
                        """
                        INSERT INTO agent_command_journal (
                            command_id, state, claimed_by, claimed_until, updated_at
                        ) VALUES (%s, 'RUNNING', %s, %s, %s)
                        """,
                        (command_id, self._owner, claimed_until, now),
                    )
                    return CommandClaim.CLAIMED
                state, _claimed_by, existing_until = row
                if state in {"COMPLETED", "FAILED"}:
                    return CommandClaim.TERMINAL
                if existing_until is not None and existing_until > now:
                    return CommandClaim.BUSY
                await connection.execute(
                    """
                    UPDATE agent_command_journal
                    SET claimed_by = %s, claimed_until = %s, updated_at = %s
                    WHERE command_id = %s
                    """,
                    (self._owner, claimed_until, now, command_id),
                )
                return CommandClaim.CLAIMED

    async def complete(self, command_id: str) -> None:
        await self._finish(command_id, "COMPLETED")

    async def fail(self, command_id: str) -> None:
        await self._finish(command_id, "FAILED")

    async def abandon(self, command_id: str) -> None:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                DELETE FROM agent_command_journal
                WHERE command_id = %s AND state = 'RUNNING' AND claimed_by = %s
                """,
                (command_id, self._owner),
            )
            if cursor.rowcount not in {0, 1}:
                raise RuntimeError("unexpected command journal abandon count")

    async def _finish(self, command_id: str, state: str) -> None:
        now = datetime.now(UTC)
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE agent_command_journal
                SET state = %s, claimed_by = NULL, claimed_until = NULL, updated_at = %s
                WHERE command_id = %s AND state = 'RUNNING' AND claimed_by = %s
                """,
                (state, now, command_id, self._owner),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"command {command_id} is not owned and running")
