"""Activity persistence and independent read-only internal-demo HTTP surface."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from time import monotonic

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from return_agent_contracts.activity import (
    ActivityEmission,
    ActivityEvent,
    ActivityPage,
    Narration,
    NarrationJob,
    NodeSummary,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .db.activity import ActivityRecord, NarrationOutboxRecord
from .db.case import CaseRecord


class ActivityRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def append(self, emission: ActivityEmission) -> ActivityEvent:
        with self.sessions.begin() as session:
            case = session.scalar(
                select(CaseRecord)
                .where(CaseRecord.case_ref == emission.case_ref)
                .with_for_update()
            )
            if case is None:
                raise LookupError("activity case not found")
            existing = session.get(ActivityRecord, emission.event_id)
            raw = emission.model_dump(mode="json")
            if existing:
                if {k: v for k, v in existing.payload.items() if k != "seq"} != raw:
                    raise ValueError("activity identity collision")
                return ActivityEvent.model_validate(existing.payload)
            narration_source = None
            if isinstance(emission.payload, Narration):
                narration_source = session.get(
                    NarrationOutboxRecord, emission.payload.source_event_id
                )
                if narration_source is None:
                    raise ValueError("unknown narration source")
                source = NarrationJob.model_validate(narration_source.payload).source
                for key in (
                    "case_ref",
                    "run_id",
                    "scope",
                    "job_id",
                    "node",
                    "operation_id",
                    "attempt_id",
                    "parent_operation_id",
                ):
                    if getattr(source, key) != getattr(emission, key):
                        raise ValueError("narration source correlation mismatch")
                if narration_source.result_event_id:
                    return ActivityEvent.model_validate(
                        session.get(
                            ActivityRecord, narration_source.result_event_id
                        ).payload
                    )
            highest = (
                session.scalar(
                    select(func.max(ActivityRecord.seq)).where(
                        ActivityRecord.case_ref == emission.case_ref
                    )
                )
                or 0
            )
            event = ActivityEvent(**raw, seq=highest + 1)
            session.add(
                ActivityRecord(
                    event_id=event.event_id,
                    case_ref=event.case_ref,
                    seq=event.seq,
                    payload=event.model_dump(mode="json"),
                )
            )
            session.flush()
            if isinstance(emission.payload, NodeSummary):
                session.add(
                    NarrationOutboxRecord(
                        source_event_id=event.event_id,
                        payload=NarrationJob(
                            job_id=f"narration:{event.event_id}",
                            source=emission.model_copy(
                                update={
                                    "payload": NodeSummary(facts=emission.payload.facts)
                                }
                            ),
                        ).model_dump(mode="json"),
                        dispatched=False,
                    )
                )
            if narration_source:
                narration_source.result_event_id = event.event_id
            return event

    def page(self, case_ref: str, after: int, limit: int) -> ActivityPage:
        with self.sessions() as session:
            if session.get(CaseRecord, case_ref) is None:
                raise LookupError("case not found")
            rows = session.scalars(
                select(ActivityRecord)
                .where(ActivityRecord.case_ref == case_ref, ActivityRecord.seq > after)
                .order_by(ActivityRecord.seq)
                .limit(limit + 1)
            ).all()
            events = [ActivityEvent.model_validate(row.payload) for row in rows[:limit]]
            return ActivityPage(
                events=events,
                next_cursor=events[-1].seq if events else after,
                has_more=len(rows) > limit,
            )


router = APIRouter()


@router.get("/cases/{case_ref}/activities", response_model=ActivityPage)
async def get_activities(
    request: Request,
    case_ref: str,
    after_seq: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> ActivityPage:
    try:
        return await asyncio.to_thread(
            ActivityRepository(request.app.state.session_factory).page,
            case_ref,
            after_seq,
            limit,
        )
    except LookupError:
        raise HTTPException(404, "case not found") from None


async def stream_activities(
    repository: ActivityRepository,
    request: Request,
    case_ref: str,
    cursor: int,
    *,
    poll: float = 0.25,
    heartbeat: float = 15.0,
) -> AsyncIterator[str]:
    last = monotonic()
    while not await request.is_disconnected():
        page = await asyncio.to_thread(repository.page, case_ref, cursor, 100)
        for event in page.events:
            cursor = event.seq
            yield f"id: {cursor}\nevent: activity\ndata: {event.model_dump_json()}\n\n"
            last = monotonic()
        if page.has_more:
            continue
        if monotonic() - last >= heartbeat:
            yield ": keep-alive\n\n"
            last = monotonic()
        await asyncio.sleep(poll)


@router.get("/cases/{case_ref}/activities/stream")
async def activity_stream(
    request: Request,
    case_ref: str,
    after_seq: int = Query(0, ge=0),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    if last_event_id is not None:
        if not last_event_id.isascii() or not last_event_id.isdecimal():
            raise HTTPException(400, "Last-Event-ID must be nonnegative integer")
        after_seq = int(last_event_id)
    repository = ActivityRepository(request.app.state.session_factory)
    try:
        await asyncio.to_thread(repository.page, case_ref, after_seq, 1)
    except LookupError:
        raise HTTPException(404, "case not found") from None
    return StreamingResponse(
        stream_activities(repository, request, case_ref, after_seq),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
