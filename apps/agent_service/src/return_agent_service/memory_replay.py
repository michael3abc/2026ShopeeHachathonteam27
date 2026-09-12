"""Durable first-result and terminal-event storage in the Agent database."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from alembic import command
from alembic.config import Config
from pydantic import TypeAdapter
from return_agent_contracts.models import MemoryDistillationOutput
from return_agent_contracts.service import MemoryDistillationJob, MemoryServiceEvent
from sqlalchemy import JSON, Column, Engine, MetaData, String, Table, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

_OUTPUT = TypeAdapter(MemoryDistillationOutput)
_EVENT = TypeAdapter(MemoryServiceEvent)
METADATA = MetaData()
RESULTS = Table(
    "memory_job_results",
    METADATA,
    Column("job_id", String(256), primary_key=True),
    Column("input_hash", String(64), nullable=False),
    Column("prompt_version", String(256), nullable=False),
    Column("result", JSON(none_as_null=True)),
    Column("terminal_event", JSON(none_as_null=True)),
)


@dataclass(frozen=True)
class MemoryReplay:
    prompt_version: str
    result: MemoryDistillationOutput | None
    terminal_event: MemoryServiceEvent | None


class MemoryReplayConflictError(ValueError):
    """The same job ID was delivered with different semantic input."""


class SqlAlchemyMemoryReplayStore:
    """Persist output before submission and the exact event before publication."""

    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name not in {"postgresql", "sqlite"}:
            raise ValueError("memory replay requires PostgreSQL or test SQLite")
        self._engine = engine

    def migrate(self) -> None:
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).with_name("migrations"))
        )
        with self._engine.begin() as connection:
            # Serialize startup migrations across replicas, independent of the
            # API and LangGraph migration histories.
            if connection.dialect.name == "postgresql":
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(180018)")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    async def load(
        self, job: MemoryDistillationJob, prompt_version: str
    ) -> MemoryReplay:
        return await asyncio.to_thread(self._load, job, prompt_version)

    async def save_result(
        self, job: MemoryDistillationJob, result: MemoryDistillationOutput
    ) -> MemoryReplay:
        return await asyncio.to_thread(
            self._save, job, "result", _OUTPUT.dump_python(result, mode="json")
        )

    async def save_event(
        self, job: MemoryDistillationJob, event: MemoryServiceEvent
    ) -> MemoryReplay:
        return await asyncio.to_thread(
            self._save, job, "terminal_event", _EVENT.dump_python(event, mode="json")
        )

    @staticmethod
    def _hash(job: MemoryDistillationJob) -> str:
        # Enqueue redelivery may have a new issued_at; everything else must match.
        payload = job.model_dump(mode="json", exclude={"issued_at"})
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _decode(
        row: Mapping[str, Any] | None, job: MemoryDistillationJob
    ) -> MemoryReplay:
        if row is None or row["input_hash"] != SqlAlchemyMemoryReplayStore._hash(job):
            raise MemoryReplayConflictError("memory job ID has conflicting input")
        return MemoryReplay(
            prompt_version=row["prompt_version"],
            result=_OUTPUT.validate_python(row["result"])
            if row["result"] is not None
            else None,
            terminal_event=_EVENT.validate_python(row["terminal_event"])
            if row["terminal_event"] is not None
            else None,
        )

    def _load(self, job: MemoryDistillationJob, prompt_version: str) -> MemoryReplay:
        with self._engine.begin() as connection:
            insert = (
                pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
            )
            connection.execute(
                insert(RESULTS)
                .values(
                    job_id=job.job_id,
                    input_hash=self._hash(job),
                    prompt_version=prompt_version,
                )
                .on_conflict_do_nothing(index_elements=["job_id"])
            )
            row = (
                connection.execute(
                    select(RESULTS).where(RESULTS.c.job_id == job.job_id)
                )
                .mappings()
                .one()
            )
            replay = self._decode(row, job)
            if replay.result is None and replay.terminal_event is None and replay.prompt_version != prompt_version:
                raise MemoryReplayConflictError("pending memory job belongs to a different prompt version")
            return replay

    def _save(
        self,
        job: MemoryDistillationJob,
        field: Literal["result", "terminal_event"],
        payload: object,
    ) -> MemoryReplay:
        with self._engine.begin() as connection:
            # First successful writer wins. Never overwrite an earlier model
            # output or event, including after an ambiguous database response.
            connection.execute(
                update(RESULTS)
                .where(
                    RESULTS.c.job_id == job.job_id,
                    RESULTS.c.input_hash == self._hash(job),
                    RESULTS.c[field].is_(None),
                )
                .values({field: payload})
            )
            row = (
                connection.execute(
                    select(RESULTS).where(RESULTS.c.job_id == job.job_id)
                )
                .mappings()
                .one_or_none()
            )
            return self._decode(row, job)
