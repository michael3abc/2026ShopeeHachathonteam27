"""Database-backed Server-Sent Events stream for Agent UI projections."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import monotonic

from fastapi import Request
from return_agent_contracts.ui import CaseStatus
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db.case import AGENT_EVENT, CaseEventRecord, CaseRecord


@dataclass(frozen=True, slots=True)
class EventStreamSettings:
    poll_interval_seconds: float = 0.25
    heartbeat_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if self.heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")


class CaseEventStream:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: EventStreamSettings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def iterate(
        self,
        request: Request,
        *,
        case_ref: str,
        after_seq: int,
    ) -> AsyncIterator[str]:
        cursor = after_seq
        last_output = monotonic()
        while True:
            records, status = await asyncio.to_thread(
                self._read_after, case_ref, cursor
            )
            for record in records:
                cursor = record.seq
                last_output = monotonic()
                event_type = record.payload["type"]
                body = json.dumps(
                    record.payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"id: {record.seq}\nevent: {event_type}\ndata: {body}\n\n"

            if status in (CaseStatus.RESOLVED, CaseStatus.ESCALATED):
                return
            if await request.is_disconnected():
                return

            now = monotonic()
            if now - last_output >= self._settings.heartbeat_seconds:
                last_output = now
                yield ": keep-alive\n\n"
            await asyncio.sleep(self._settings.poll_interval_seconds)

    def _read_after(
        self,
        case_ref: str,
        after_seq: int,
    ) -> tuple[list[CaseEventRecord], CaseStatus]:
        with self._session_factory() as session:
            case = session.get(CaseRecord, case_ref)
            if case is None:
                raise LookupError(f"unknown case {case_ref}")
            records = list(
                session.scalars(
                    select(CaseEventRecord)
                    .where(
                        CaseEventRecord.case_ref == case_ref,
                        CaseEventRecord.kind == AGENT_EVENT,
                        CaseEventRecord.seq > after_seq,
                    )
                    .order_by(CaseEventRecord.seq)
                )
            )
            for record in records:
                session.expunge(record)
            return records, CaseStatus(case.status)
