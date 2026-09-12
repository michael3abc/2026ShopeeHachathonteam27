"""Independent activity consumer and transactional narration outbox delivery."""

import asyncio
import logging
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from return_agent_contracts.activity import (
    ACTIVITY_GROUP,
    ACTIVITY_STREAM,
    NARRATION_STREAM,
    ActivityEmission,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .activities import ActivityRepository
from .db.activity import NarrationOutboxRecord

LOGGER = logging.getLogger(__name__)


class ActivityBridge:
    def __init__(
        self, sessions: sessionmaker[Session], redis: Redis, consumer: str | None = None
    ) -> None:
        self.repository = ActivityRepository(sessions)
        self.redis, self.consumer = redis, consumer or f"activity-api-{uuid4().hex}"

    async def setup(self) -> None:
        try:
            await self.redis.xgroup_create(
                ACTIVITY_STREAM, ACTIVITY_GROUP, id="0-0", mkstream=True
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def consume_once(self) -> bool:
        claimed = await self.redis.xautoclaim(
            ACTIVITY_STREAM,
            ACTIVITY_GROUP,
            self.consumer,
            min_idle_time=10000,
            start_id="0-0",
            count=100,
        )
        entries = claimed[1]
        if not entries:
            batches = await self.redis.xreadgroup(
                ACTIVITY_GROUP,
                self.consumer,
                {ACTIVITY_STREAM: ">"},
                count=100,
                block=100,
            )
            entries = batches[0][1] if batches else []
        for message_id, fields in entries:
            try:
                event = ActivityEmission.model_validate_json(fields["body"])
                await asyncio.to_thread(self.repository.append, event)
            except (ValueError, KeyError, LookupError):
                # Do not copy the rejected body (which may contain secrets) to a DLQ.
                await self.redis.xadd(
                    ACTIVITY_STREAM + ".rejected",
                    {"message_id": message_id, "code": "INVALID_ACTIVITY"},
                )
                LOGGER.error("activity rejected: %s", message_id)
            await self.redis.xack(ACTIVITY_STREAM, ACTIVITY_GROUP, message_id)
        return bool(entries)

    def _pending(self):
        with self.repository.sessions() as session:
            return [
                (r.source_event_id, r.payload)
                for r in session.scalars(
                    select(NarrationOutboxRecord)
                    .where(NarrationOutboxRecord.dispatched.is_(False))
                    .limit(100)
                )
            ]

    def _mark_sent(self, source):
        with self.repository.sessions.begin() as session:
            session.get(NarrationOutboxRecord, source).dispatched = True

    async def dispatch_once(self) -> bool:
        import json

        rows = await asyncio.to_thread(self._pending)
        for source, payload in rows:
            await self.redis.xadd(NARRATION_STREAM, {"body": json.dumps(payload)})
            await asyncio.to_thread(self._mark_sent, source)
        return bool(rows)

    async def run_forever(self) -> None:
        while True:
            try:
                await self.setup()
                while True:
                    await self.consume_once()
                    await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - isolated transport boundary retries without ACK
                LOGGER.error(
                    "activity bridge unavailable; unacked events/outbox will retry"
                )
                await asyncio.sleep(1)
