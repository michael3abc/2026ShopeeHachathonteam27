import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from redis import Redis
from redis.exceptions import ResponseError
from sqlalchemy import or_, select

from return_agent_contracts.messages import AgentCommand, AgentResumeRequest, AgentStartRequest, COMMAND_DLQ, COMMAND_GROUP, COMMAND_STREAM, EVENT_STREAM
from return_agent_contracts.providers import ContractConflict

from .db import EventOutboxRow
from .journal import CommandJournal


class JournalObserver:
    def __init__(self, journal, command):
        self.journal, self.command = journal, command
    def observe(self, observation):
        self.journal.observe(self.command, observation)
    def paused(self, node, task_ref):
        # The durable INTERRUPTED result is published after LangGraph saves the pause.
        pass


class CommandWorker:
    def __init__(self, engine, journal: CommandJournal, redis: Redis, runtime_factory, *, consumer: str, min_idle_ms: int = 1000):
        self.engine, self.journal, self.redis, self.runtime_factory = engine, journal, redis, runtime_factory
        self.consumer, self.min_idle_ms = consumer, min_idle_ms
        try:
            redis.xgroup_create(COMMAND_STREAM, COMMAND_GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def dead_letter(self, message_id: str, body: str, code: str):
        self.redis.xadd(COMMAND_DLQ, {"body": json.dumps({"source_message_id": message_id, "error_code": code, "payload_hash": hashlib.sha256(body.encode()).hexdigest()})})
        self.redis.xack(COMMAND_STREAM, COMMAND_GROUP, message_id)

    def process(self, message_id: str, body: str) -> bool:
        try:
            command = TypeAdapter(AgentCommand).validate_json(body)
        except ValidationError:
            self.dead_letter(message_id, body, "INVALID_COMMAND")
            return True
        lock_name = "runtime-thread:" + command.thread_id
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock_connection:
            acquired = lock_connection.exec_driver_sql("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (lock_name,)).scalar_one()
            if not acquired:
                return False
            try:
                with self.runtime_factory(JournalObserver(self.journal, command)) as runtime:
                    snapshot = runtime.graph.get_state(runtime.config(command.thread_id))
                    checkpoint = snapshot.config.get("configurable", {}).get("checkpoint_id") if snapshot.config else None
                    try:
                        status, initial_checkpoint = self.journal.claim(command, self.consumer, checkpoint)
                    except ContractConflict:
                        self.dead_letter(message_id, body, "COMMAND_IDENTITY_CONFLICT")
                        return True
                    if status == "BUSY":
                        return False
                    if status != "TERMINAL":
                        try:
                            if command.command_type == "START":
                                result = runtime.continue_run(command.thread_id) if snapshot.values else runtime.start(AgentStartRequest(case_ref=command.case_ref, thread_id=command.thread_id, order_ref=command.payload.order_ref, initial_turn=command.payload.initial_turn))
                            elif checkpoint != initial_checkpoint:
                                result = runtime.continue_run(command.thread_id)
                            else:
                                result = runtime.resume(AgentResumeRequest(thread_id=command.thread_id, payload=command.payload.resume))
                        except ValueError:
                            self.journal.fail(command, self.consumer)
                        else:
                            state = runtime.state(command.thread_id)
                            self.journal.complete(command, self.consumer, result, state.memory_distillation_input)
                self.redis.xack(COMMAND_STREAM, COMMAND_GROUP, message_id)
                return True
            finally:
                lock_connection.exec_driver_sql("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (lock_name,))

    def tick(self) -> int:
        entries = self.redis.xautoclaim(COMMAND_STREAM, COMMAND_GROUP, self.consumer, self.min_idle_ms, "0-0", count=5)[1]
        batches = self.redis.xreadgroup(COMMAND_GROUP, self.consumer, {COMMAND_STREAM: ">"}, count=5, block=1 if entries else 250)
        entries = [*entries, *(entry for _, batch in batches for entry in batch)]
        for message_id, fields in entries:
            self.process(message_id, fields.get("body", ""))
        return len(entries)


class EventPublisher:
    def __init__(self, journal: CommandJournal, redis: Redis):
        self.journal, self.redis = journal, redis

    def tick(self) -> int:
        now, claims = self.journal.clock(), []
        with self.journal.sessions.begin() as session:
            rows = session.scalars(select(EventOutboxRow).where(EventOutboxRow.published_at.is_(None), or_(EventOutboxRow.claimed_until.is_(None), EventOutboxRow.claimed_until < now)).order_by(EventOutboxRow.command_id, EventOutboxRow.event_index).limit(50).with_for_update(skip_locked=True))
            for row in rows:
                row.lease_token, row.claimed_until = uuid4().hex, now + timedelta(seconds=30)
                claims.append((row.event_id, row.lease_token, row.payload))
        for event_id, token, payload in claims:
            self.redis.xadd(EVENT_STREAM, {"body": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))})
            with self.journal.sessions.begin() as session:
                row = session.get(EventOutboxRow, event_id, with_for_update=True)
                if row.lease_token == token:
                    row.published_at, row.claimed_until = self.journal.clock(), None
        return len(claims)
