import hashlib
from datetime import timedelta

from pydantic import TypeAdapter, ValidationError
from redis import Redis
from redis.exceptions import ResponseError
from sqlalchemy import or_, select

from return_agent_contracts.messages import COMMAND_STREAM, EVENT_STREAM
from return_agent_contracts.providers import ContractConflict, ExecuteRefundRequest, ProviderUnavailable
from return_agent_contracts.workflow import AgentServiceEvent

from .cases import CaseNotFound, CaseStateConflict, CaseStore
from .db import CommandOutboxRow, RejectedAgentEventRow, ResolutionJobRow
from .projection import EventOutOfOrder, EventProjector
from .refunds import AuthorizationRejected, RefundService

EVENT_GROUP = "return-agent-api-v1"


class CommandDispatcher:
    def __init__(self, cases: CaseStore, redis: Redis):
        self.cases, self.redis = cases, redis

    def tick(self) -> int:
        now, claims = self.cases.clock(), []
        with self.cases.sessions.begin() as session:
            rows = session.scalars(select(CommandOutboxRow).where(CommandOutboxRow.published_at.is_(None), or_(CommandOutboxRow.claimed_until.is_(None), CommandOutboxRow.claimed_until < now)).order_by(CommandOutboxRow.created_at).limit(10).with_for_update(skip_locked=True))
            for row in rows:
                row.lease_token, row.claimed_until = self.cases.ids("lease"), now + timedelta(seconds=30)
                row.attempts += 1
                claims.append((row.command_id, row.lease_token, row.payload))
        for command_id, token, payload in claims:
            import json
            self.redis.xadd(COMMAND_STREAM, {"body": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))})
            with self.cases.sessions.begin() as session:
                row = session.get(CommandOutboxRow, command_id, with_for_update=True)
                if row.lease_token == token:
                    row.published_at, row.claimed_until = self.cases.clock(), None
        return len(claims)


class EventConsumer:
    def __init__(self, cases: CaseStore, redis: Redis, *, consumer: str, min_idle_ms: int = 1000):
        self.cases, self.redis, self.consumer, self.min_idle_ms = cases, redis, consumer, min_idle_ms
        self.projector = EventProjector(cases)
        try:
            redis.xgroup_create(EVENT_STREAM, EVENT_GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def process(self, message_id: str, body: str) -> bool:
        try:
            event = TypeAdapter(AgentServiceEvent).validate_json(body)
            self.projector.project(event)
        except EventOutOfOrder:
            return False
        except (ValidationError, ContractConflict, CaseStateConflict, CaseNotFound, ValueError):
            with self.cases.sessions.begin() as session:
                if session.get(RejectedAgentEventRow, message_id) is None:
                    session.add(RejectedAgentEventRow(source_message_id=message_id, payload_hash=hashlib.sha256(body.encode()).hexdigest(), error_code="INVALID_AGENT_EVENT", rejected_at=self.cases.clock()))
        self.redis.xack(EVENT_STREAM, EVENT_GROUP, message_id)
        return True

    def tick(self) -> int:
        reclaimed = self.redis.xautoclaim(EVENT_STREAM, EVENT_GROUP, self.consumer, self.min_idle_ms, "0-0", count=20)[1]
        batches = self.redis.xreadgroup(EVENT_GROUP, self.consumer, {EVENT_STREAM: ">"}, count=20, block=1 if reclaimed else 250)
        entries = [*reclaimed, *(entry for _, batch in batches for entry in batch)]
        for message_id, fields in entries:
            self.process(message_id, fields.get("body", ""))
        return len(entries)


class ResolutionWorker:
    def __init__(self, cases: CaseStore, refunds: RefundService):
        self.cases, self.refunds = cases, refunds
        self.projector = EventProjector(cases)

    def tick(self) -> bool:
        now = self.cases.clock()
        with self.cases.sessions.begin() as session:
            row = session.scalar(select(ResolutionJobRow).where(ResolutionJobRow.status == "PENDING", ResolutionJobRow.next_attempt_at <= now, or_(ResolutionJobRow.claimed_until.is_(None), ResolutionJobRow.claimed_until < now)).order_by(ResolutionJobRow.next_attempt_at).limit(1).with_for_update(skip_locked=True))
            if row is None:
                return False
            row.lease_token, row.claimed_until = self.cases.ids("lease"), now + timedelta(seconds=900)
            row.attempts += 1
            token, handoff_id, case_ref, attempts = row.lease_token, row.handoff_id, row.case_ref, row.attempts
            request = ExecuteRefundRequest.model_validate(row.request)
        error, result = None, None
        try:
            if request.resolution_handoff.final_decision.action == "FULL_REFUND":
                result = self.refunds.execute(request)
            else:
                with self.cases.sessions() as session:
                    self.refunds.authorize(session, request)
        except ProviderUnavailable:
            error = "REFUND_OUTCOME_UNAVAILABLE"
        except (AuthorizationRejected, ContractConflict, ValueError):
            error = "REFUND_AUTHORIZATION_REJECTED"
        with self.cases.sessions.begin() as session:
            case = self.cases.locked_case(session, case_ref)
            row = session.get(ResolutionJobRow, handoff_id, with_for_update=True)
            if row.lease_token != token or row.status != "PENDING":
                return True
            row.claimed_until, row.error_code = None, error
            if error == "REFUND_OUTCOME_UNAVAILABLE" and attempts < 5:
                row.next_attempt_at = self.cases.clock() + timedelta(seconds=min(30, 2 ** attempts))
                return True
            if error or (result is not None and result.status == "REJECTED"):
                row.status = "FAILED"
                if result:
                    case.refund_execution = result.model_dump(mode="json")
                self.projector.escalate(session, case, error or "REFUND_APPLICATION_REJECTED", result.execution_ref if result else handoff_id, self.cases.clock())
            else:
                row.status = "COMPLETED"
                case.refund_execution = result.model_dump(mode="json") if result else None
                self.cases.transition(session, case, "RESOLVED", "Refund applied" if result else "Decline decision completed without payment", "emit_resolution_handoff")
                self.projector.emit(session, case, "emit_resolution_handoff", "done", {"status": "RESOLVED", "terminal_ref": result.execution_ref if result else handoff_id}, self.cases.clock())
        return True
