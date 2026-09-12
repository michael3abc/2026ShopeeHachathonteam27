"""Reliable Redis bridge between the Case API and Agent Service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from return_agent_contracts.adapters import (
    UIAdapterError,
    to_clarification_interrupt_payload,
    to_evidence_request_view,
    to_human_review_payload,
)
from return_agent_contracts.enums import (
    RefundExecutionStatus,
    ResolutionAction,
)
from return_agent_contracts.interfaces import RefundExecutionProvider
from return_agent_contracts.models import ExecuteRefundRequest, RefundExecutionRecord
from return_agent_contracts.runtime import (
    AgentInterruptKind,
    GraphNodeName,
    NodeExecutionPhase,
)
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    REDIS_BODY_FIELD,
    AgentEscalatedEvent,
    AgentInterruptedEvent,
    AgentNodeObservedEvent,
    AgentResolvedEvent,
    AgentRunFailedEvent,
    AgentServiceEvent,
)
from return_agent_contracts.ui import CaseStatus
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from .db.agent_bridge import (
    AgentCommandOutboxRecord,
    AgentEventProjectionCursorRecord,
    ProcessedAgentEventRecord,
    RejectedAgentEventRecord,
)
from .db.case import CaseRecord, append_agent_event
from .store import CaseNotFoundError, CaseStore, IllegalTransitionError

LOGGER = logging.getLogger(__name__)
EVENT_ADAPTER = TypeAdapter(AgentServiceEvent)
API_EVENT_CONSUMER_GROUP = "return-agent-api-v1"
PUBLIC_AGENT_FAILURE_MESSAGE = (
    "The automated review could not complete. A specialist will review this case."
)
PUBLIC_NODE_FAILURE_MESSAGE = "An automated review step failed."
PUBLIC_REJECTED_EVENT_MESSAGE = "The automated review returned an invalid update. A specialist will review this case."
PUBLIC_REFUND_REJECTED_MESSAGE = (
    "The authorized refund could not be applied. A specialist will review this case."
)


class InvalidAgentEventError(ValueError):
    """A valid wire event that cannot apply to its referenced case."""


class AgentEventGapError(RuntimeError):
    """An event arrived before an earlier event for the same command."""


class RefundExecutionUnavailableError(RuntimeError):
    """A refund handoff must remain pending until an executor is configured."""


@dataclass(frozen=True, slots=True)
class AgentBridgeSettings:
    redis_url: str
    event_consumer_name: str
    outbox_dispatcher_name: str | None = None
    outbox_claim_seconds: int = 30
    event_block_ms: int = 1_000
    event_reclaim_idle_ms: int = 60_000
    event_reclaim_every: int = 4
    idle_poll_seconds: float = 1.0

    def __post_init__(self) -> None:
        if (
            self.outbox_claim_seconds < 1
            or self.event_block_ms < 1
            or self.event_reclaim_idle_ms < 1
            or self.event_reclaim_every < 1
        ):
            raise ValueError("Redis timing values must be positive")
        if self.idle_poll_seconds <= 0:
            raise ValueError("idle_poll_seconds must be positive")

    @classmethod
    def from_env(cls) -> AgentBridgeSettings:
        return cls(
            redis_url=os.environ.get(
                "RETURN_AGENT_REDIS_URL", "redis://localhost:6379/0"
            ),
            event_consumer_name=os.environ.get(
                "RETURN_AGENT_API_EVENT_CONSUMER",
                f"api-{socket.gethostname()}",
            ),
            outbox_dispatcher_name=os.environ.get(
                "RETURN_AGENT_API_OUTBOX_DISPATCHER",
                f"api-{socket.gethostname()}-{os.getpid()}",
            ),
            outbox_claim_seconds=int(
                os.environ.get("RETURN_AGENT_API_OUTBOX_CLAIM_SECONDS", "30")
            ),
            event_block_ms=int(
                os.environ.get("RETURN_AGENT_API_EVENT_BLOCK_MS", "1000")
            ),
            event_reclaim_idle_ms=int(
                os.environ.get("RETURN_AGENT_API_EVENT_RECLAIM_IDLE_MS", "60000")
            ),
            event_reclaim_every=int(
                os.environ.get("RETURN_AGENT_API_EVENT_RECLAIM_EVERY", "4")
            ),
            idle_poll_seconds=float(
                os.environ.get("RETURN_AGENT_API_BRIDGE_POLL_SECONDS", "1.0")
            ),
        )


@dataclass(frozen=True, slots=True)
class RedisEventMessage:
    message_id: str
    body: str


class AgentEventProjector:
    """Atomically project one service event into Case state and UI events."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        refund_execution_provider: RefundExecutionProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._refund_execution_provider = refund_execution_provider

    def project(self, event: AgentServiceEvent) -> bool:
        pending_refund = False
        payload_hash = _event_payload_hash(event)
        with self._session_factory.begin() as session:
            store = CaseStore(session)
            try:
                case = store.lock(event.case_ref)
                processed = session.get(ProcessedAgentEventRecord, event.event_id)
                if processed is not None:
                    if (
                        processed.case_ref == event.case_ref
                        and processed.command_id == event.command_id
                        and processed.event_index == event.event_index
                        and processed.payload_hash == payload_hash
                    ):
                        return False
                    raise InvalidAgentEventError(
                        f"event_id {event.event_id} collides with a different event"
                    )
                if case.thread_id != event.thread_id:
                    raise InvalidAgentEventError(
                        f"event thread {event.thread_id} does not own "
                        f"case {event.case_ref}"
                    )
                cursor = session.get(AgentEventProjectionCursorRecord, event.command_id)
                if cursor is not None and cursor.case_ref != event.case_ref:
                    raise InvalidAgentEventError(
                        f"command {event.command_id} belongs to case "
                        f"{cursor.case_ref}, not {event.case_ref}"
                    )
                if cursor is not None and cursor.terminated_at is not None:
                    raise InvalidAgentEventError(
                        f"command {event.command_id} projection is terminated"
                    )
                expected_index = 1 if cursor is None else cursor.last_event_index + 1
                if event.event_index > expected_index:
                    raise AgentEventGapError(
                        f"event {event.event_id} has index {event.event_index}; "
                        f"expected {expected_index}"
                    )
                if event.event_index < expected_index:
                    raise InvalidAgentEventError(
                        f"event {event.event_id} reuses projected index "
                        f"{event.event_index}"
                    )
                pending_refund = self._apply(session, store, case, event)
            except AgentEventGapError:
                raise
            except InvalidAgentEventError:
                raise
            except (
                CaseNotFoundError,
                IllegalTransitionError,
                UIAdapterError,
                LookupError,
                ValueError,
            ) as error:
                raise InvalidAgentEventError(str(error)) from error

            if not pending_refund:
                self._record_processed(session, event, payload_hash, cursor)
        if pending_refund:
            if self._refund_execution_provider is None:
                raise RefundExecutionUnavailableError(
                    f"refund event {event.event_id} has no configured executor"
                )
            assert isinstance(event, AgentResolvedEvent)
            handoff = event.payload.result.resolution_handoff
            from uuid import uuid4

            from return_agent_contracts.activity_observer import (
                CURRENT_ACTIVITY,
                ActivityContext,
                facts_from,
                span,
            )

            from .activities import ActivityRepository
            activity_context = ActivityContext(case_ref=event.case_ref, run_id=event.command_id,
                scope="REFUND", node="execute_refund", attempt_id=uuid4().hex,
                sink=ActivityRepository(self._session_factory).append)
            activity_token = CURRENT_ACTIVITY.set(activity_context)
            try:
                with span("node", "execute_refund") as step:
                    with span("tool", "refund_execution_provider.execute") as operation:
                        result = self._refund_execution_provider.execute(
                            ExecuteRefundRequest(resolution_handoff=handoff)
                        )
                        operation["facts"] = facts_from(result)
                    step["facts"] = facts_from(result)
            except Exception as error:
                raise RefundExecutionUnavailableError(
                    f"refund execution for {event.event_id} is unavailable"
                ) from error
            finally:
                CURRENT_ACTIVITY.reset(activity_token)
            self._complete_refund(event, result, payload_hash)
        return True

    @staticmethod
    def _record_processed(
        session: Session,
        event: AgentServiceEvent,
        payload_hash: str,
        cursor: AgentEventProjectionCursorRecord | None,
    ) -> None:
        session.add(
            ProcessedAgentEventRecord(
                event_id=event.event_id,
                case_ref=event.case_ref,
                command_id=event.command_id,
                event_index=event.event_index,
                payload_hash=payload_hash,
            )
        )
        if cursor is None:
            session.add(
                AgentEventProjectionCursorRecord(
                    command_id=event.command_id,
                    case_ref=event.case_ref,
                    last_event_index=event.event_index,
                )
            )
        else:
            cursor.last_event_index = event.event_index
            cursor.updated_at = datetime.now(UTC)

    def _complete_refund(
        self,
        event: AgentResolvedEvent,
        result: RefundExecutionRecord,
        payload_hash: str,
    ) -> None:
        with self._session_factory.begin() as session:
            store = CaseStore(session)
            case = store.lock(event.case_ref)
            if session.get(ProcessedAgentEventRecord, event.event_id) is not None:
                return
            cursor = session.get(AgentEventProjectionCursorRecord, event.command_id)
            if cursor is not None and cursor.last_event_index + 1 != event.event_index:
                raise AgentEventGapError(
                    f"refund event {event.event_id} cannot complete out of order"
                )
            occurred_at = datetime.now(UTC)
            node = GraphNodeName.EMIT_RESOLUTION_HANDOFF
            if result.status is RefundExecutionStatus.SUCCEEDED:
                self._transition(
                    session,
                    store,
                    case,
                    CaseStatus.RESOLVED,
                    node=node,
                    occurred_at=occurred_at,
                    reason="Authorized refund execution completed.",
                )
                terminal_status = CaseStatus.RESOLVED
            else:
                append_agent_event(
                    session,
                    case.case_ref,
                    {
                        "type": "error",
                        "ts": occurred_at,
                        "node": node,
                        "payload": {
                            "code": "REFUND_EXECUTION_REJECTED",
                            "message": PUBLIC_REFUND_REJECTED_MESSAGE,
                            "retryable": False,
                        },
                    },
                )
                self._transition(
                    session,
                    store,
                    case,
                    CaseStatus.ESCALATED,
                    node=node,
                    occurred_at=occurred_at,
                    reason="Authorized refund execution was rejected.",
                )
                terminal_status = CaseStatus.ESCALATED
            self._done(
                session,
                case.case_ref,
                node=node,
                occurred_at=occurred_at,
                terminal_ref=result.execution_ref,
                status=terminal_status,
            )
            self._record_processed(session, event, payload_hash, cursor)

    def reject(
        self,
        *,
        source_message_id: str,
        raw_body: str,
        error_code: str,
        error: Exception,
        event_id: str | None = None,
        command_id: str | None = None,
        case_ref: str | None = None,
    ) -> None:
        """Durably reject a poison event and fail its active case closed."""

        with self._session_factory.begin() as session:
            if session.get(RejectedAgentEventRecord, source_message_id) is not None:
                return
            session.add(
                RejectedAgentEventRecord(
                    source_message_id=source_message_id,
                    event_id=event_id,
                    case_ref=case_ref,
                    raw_body=raw_body,
                    error_code=error_code,
                    error_message=f"{type(error).__name__}: {error}"[:2_000],
                )
            )
            if case_ref is None:
                return
            case = session.scalar(
                select(CaseRecord)
                .where(CaseRecord.case_ref == case_ref)
                .with_for_update()
            )
            if case is None:
                return
            occurred_at = datetime.now(UTC)
            termination_event_id = event_id or f"rejected:{source_message_id}"
            cursor = (
                session.get(AgentEventProjectionCursorRecord, command_id)
                if command_id is not None
                else None
            )
            if command_id is not None and cursor is None:
                session.add(
                    AgentEventProjectionCursorRecord(
                        command_id=command_id,
                        case_ref=case_ref,
                        last_event_index=0,
                        terminated_at=occurred_at,
                        termination_event_id=termination_event_id,
                    )
                )
            elif (
                cursor is not None
                and cursor.case_ref == case_ref
                and cursor.terminated_at is None
            ):
                cursor.terminated_at = occurred_at
                cursor.termination_event_id = termination_event_id
                cursor.updated_at = occurred_at
            if CaseStatus(case.status) in {
                CaseStatus.RESOLVED,
                CaseStatus.ESCALATED,
            }:
                return
            node = GraphNodeName.TERMINATE_AUTOMATION
            append_agent_event(
                session,
                case_ref,
                {
                    "type": "error",
                    "ts": occurred_at,
                    "node": node,
                    "payload": {
                        "code": "AGENT_EVENT_REJECTED",
                        "message": PUBLIC_REJECTED_EVENT_MESSAGE,
                        "retryable": False,
                    },
                },
            )
            self._transition(
                session,
                CaseStore(session),
                case,
                CaseStatus.ESCALATED,
                node=node,
                occurred_at=occurred_at,
                reason="Agent event failed validation.",
            )
            self._done(
                session,
                case_ref,
                node=node,
                occurred_at=occurred_at,
                terminal_ref=termination_event_id,
                status=CaseStatus.ESCALATED,
            )

    def _apply(
        self,
        session: Session,
        store: CaseStore,
        case: CaseRecord,
        event: AgentServiceEvent,
    ) -> bool:
        if isinstance(event, AgentNodeObservedEvent):
            self._project_node(session, event)
            return False
        if isinstance(event, AgentInterruptedEvent):
            self._project_interrupt(session, store, case, event)
            return False
        if isinstance(event, AgentResolvedEvent):
            return self._project_resolution(session, store, case, event)
        if isinstance(event, AgentEscalatedEvent):
            node = GraphNodeName.TERMINATE_AUTOMATION
            self._transition(
                session,
                store,
                case,
                CaseStatus.ESCALATED,
                node=node,
                occurred_at=event.occurred_at,
                reason="Agent requested manual escalation.",
            )
            self._done(
                session,
                case.case_ref,
                node=node,
                occurred_at=event.occurred_at,
                terminal_ref=event.event_id,
                status=CaseStatus.ESCALATED,
            )
            return False
        if isinstance(event, AgentRunFailedEvent):
            node = event.payload.failed_node or GraphNodeName.PARSE_REQUEST
            append_agent_event(
                session,
                case.case_ref,
                {
                    "type": "error",
                    "ts": event.occurred_at,
                    "node": node,
                    "payload": {
                        "code": "AGENT_RUN_FAILED",
                        "message": PUBLIC_AGENT_FAILURE_MESSAGE,
                        "retryable": event.payload.retryable,
                    },
                },
            )
            self._transition(
                session,
                store,
                case,
                CaseStatus.ESCALATED,
                node=node,
                occurred_at=event.occurred_at,
                reason="Agent run failed.",
            )
            self._done(
                session,
                case.case_ref,
                node=node,
                occurred_at=event.occurred_at,
                terminal_ref=event.event_id,
                status=CaseStatus.ESCALATED,
            )
            return False
        raise InvalidAgentEventError(f"unsupported Agent event {type(event).__name__}")

    def _project_node(self, session: Session, event: AgentNodeObservedEvent) -> None:
        observation = event.payload.observation
        if observation.phase is NodeExecutionPhase.ERROR:
            append_agent_event(
                session,
                event.case_ref,
                {
                    "type": "error",
                    "ts": event.occurred_at,
                    "node": observation.node,
                    "payload": {
                        "code": "AGENT_NODE_ERROR",
                        "message": PUBLIC_NODE_FAILURE_MESSAGE,
                        "retryable": False,
                    },
                },
            )
            return
        append_agent_event(
            session,
            event.case_ref,
            {
                "type": (
                    "node_enter"
                    if observation.phase is NodeExecutionPhase.ENTER
                    else "node_exit"
                ),
                "ts": event.occurred_at,
                "node": observation.node,
                "payload": {"detail": f"task_ref={observation.task_ref}",
                    **({"review_gate": observation.review_gate.model_dump(mode="json")} if observation.review_gate else {})},
            },
        )

        if observation.memory_retrieval is not None:
            append_agent_event(
                session,
                event.case_ref,
                {
                    "type": "memory_retrieval",
                    "ts": event.occurred_at,
                    "node": observation.node,
                    "payload": observation.memory_retrieval.model_dump(mode="json"),
                },
            )

    def _project_interrupt(
        self,
        session: Session,
        store: CaseStore,
        case: CaseRecord,
        event: AgentInterruptedEvent,
    ) -> None:
        interrupt = event.payload.result.interrupt_payload
        if interrupt.kind is AgentInterruptKind.POLICY_CONFIRMATION:
            from .db.models import PolicyConfirmationRecord
            request = interrupt.request
            if request.case_ref != case.case_ref or case.policy_schema_version != "v2":
                raise ValueError("policy confirmation case binding mismatch")
            record = session.get(PolicyConfirmationRecord,request.request_ref)
            if record is not None and record.request_payload != request.model_dump(mode="json"):
                raise ValueError("policy confirmation request changed")
            if record is None:
                session.add(PolicyConfirmationRecord(request_ref=request.request_ref,case_ref=case.case_ref,request_payload=request.model_dump(mode="json")))
            node = GraphNodeName.CONFIRM_POLICY_PATH
            target = CaseStatus.AWAITING_POLICY_CONFIRMATION
            view = {"interrupt_kind":"POLICY_CONFIRMATION","request":request.model_dump(mode="json")}
        elif interrupt.kind is AgentInterruptKind.CLARIFICATION:
            node = GraphNodeName.REQUEST_CLARIFICATION
            target = CaseStatus.AWAITING_CLARIFICATION
            view = to_clarification_interrupt_payload(event.case_ref, interrupt.request)
        elif interrupt.kind is AgentInterruptKind.EVIDENCE_REQUEST:
            node = GraphNodeName.REQUEST_EVIDENCE
            target = CaseStatus.AWAITING_EVIDENCE
            view = {
                "interrupt_kind": AgentInterruptKind.EVIDENCE_REQUEST,
                "request": to_evidence_request_view(event.case_ref, interrupt.request),
            }
        else:
            node = GraphNodeName.AWAIT_HUMAN_REVIEW
            target = CaseStatus.AWAITING_HUMAN_REVIEW
            view = {
                "interrupt_kind": AgentInterruptKind.HUMAN_REVIEW,
                "review": to_human_review_payload(
                    interrupt.handoff,
                    interrupt.review_result,
                    interrupt.policy_bundle,
                    interrupt.memory_ids,
                    interrupt.dossier,
                ),
            }

        payload = view.model_dump(mode="json") if hasattr(view, "model_dump") else view
        append_agent_event(
            session,
            case.case_ref,
            {
                "type": "interrupt",
                "ts": event.occurred_at,
                "node": node,
                "payload": payload,
            },
        )
        self._transition(
            session,
            store,
            case,
            target,
            node=node,
            occurred_at=event.occurred_at,
            reason=f"Agent awaits {interrupt.kind.value.lower()} input.",
        )

    def _project_resolution(
        self,
        session: Session,
        store: CaseStore,
        case: CaseRecord,
        event: AgentResolvedEvent,
    ) -> bool:
        handoff = event.payload.result.resolution_handoff
        if case.policy_schema_version == "v2" and handoff.final_decision.action is ResolutionAction.FULL_REFUND:
            from .capabilities.fulfillment import register_authorization
            register_authorization(session,case,handoff,self._refund_execution_provider)
            return False
        if (
            handoff.final_decision.action is ResolutionAction.FULL_REFUND
            and not handoff.execution_blocked
        ):
            current = CaseStatus(case.status)
            if current is CaseStatus.OBSERVING:
                self._transition(
                    session,
                    store,
                    case,
                    CaseStatus.EXECUTING,
                    node=GraphNodeName.EMIT_RESOLUTION_HANDOFF,
                    occurred_at=event.occurred_at,
                    reason="Agent emitted a refund resolution handoff.",
                )
            elif current is not CaseStatus.EXECUTING:
                raise InvalidAgentEventError(
                    f"refund event cannot execute while case is {current.value}"
                )
            return True

        node = GraphNodeName.EMIT_RESOLUTION_HANDOFF
        self._transition(
            session,
            store,
            case,
            CaseStatus.EXECUTING,
            node=node,
            occurred_at=event.occurred_at,
            reason="Agent emitted a final resolution handoff.",
        )
        self._transition(
            session,
            store,
            case,
            CaseStatus.RESOLVED,
            node=node,
            occurred_at=event.occurred_at,
            reason="Final decision does not require a refund mutation.",
        )
        self._done(
            session,
            case.case_ref,
            node=node,
            occurred_at=event.occurred_at,
            terminal_ref=handoff.handoff_id,
            status=CaseStatus.RESOLVED,
        )
        return False

    def _transition(
        self,
        session: Session,
        store: CaseStore,
        case: CaseRecord,
        target: CaseStatus,
        *,
        node: GraphNodeName,
        occurred_at: datetime,
        reason: str,
    ) -> None:
        current = CaseStatus(case.status)
        store.transition(case.case_ref, target)
        append_agent_event(
            session,
            case.case_ref,
            {
                "type": "state_change",
                "ts": occurred_at,
                "node": node,
                "payload": {
                    "from_status": current,
                    "to_status": target,
                    "reason": reason,
                },
            },
        )

    @staticmethod
    def _done(
        session: Session,
        case_ref: str,
        *,
        node: GraphNodeName,
        occurred_at: datetime,
        terminal_ref: str,
        status: CaseStatus,
    ) -> None:
        append_agent_event(
            session,
            case_ref,
            {
                "type": "done",
                "ts": occurred_at,
                "node": node,
                "payload": {"terminal_ref": terminal_ref, "status": status},
            },
        )


class AgentBridge:
    """Run the outbox dispatcher and Agent event consumer."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        redis: Redis,
        settings: AgentBridgeSettings,
        refund_execution_provider: RefundExecutionProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._settings = settings
        self._projector = AgentEventProjector(
            session_factory,
            refund_execution_provider,
        )
        from .capabilities.fulfillment import FulfillmentWorker
        self._fulfillment = FulfillmentWorker(session_factory,refund_execution_provider)
        self._outbox_owner = (
            settings.outbox_dispatcher_name
            or f"{settings.event_consumer_name}-{id(self)}"
        )
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._event_reads_since_reclaim = 0
        self._event_reclaim_cursor = "0-0"

    @classmethod
    def from_settings(
        cls,
        session_factory: sessionmaker[Session],
        settings: AgentBridgeSettings,
        refund_execution_provider: RefundExecutionProvider | None = None,
    ) -> AgentBridge:
        return cls(
            session_factory=session_factory,
            redis=Redis.from_url(settings.redis_url, decode_responses=True),
            settings=settings,
            refund_execution_provider=refund_execution_provider,
        )

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._run_outbox(), name="agent-command-outbox"),
            asyncio.create_task(self._run_events(), name="agent-event-consumer"),
        ]

    async def close(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._redis.aclose()

    async def dispatch_outbox_once(self) -> bool:
        pending = await asyncio.to_thread(self._claim_next_outbox_command)
        if pending is None:
            return False
        command_id, payload, lease_token = pending
        try:
            await self._redis.xadd(
                AGENT_COMMAND_STREAM,
                {REDIS_BODY_FIELD: _json(payload)},
            )
        except Exception as error:
            await asyncio.to_thread(
                self._record_publish_failure,
                command_id,
                lease_token,
                error,
            )
            raise
        await asyncio.to_thread(
            self._record_publish_success,
            command_id,
            lease_token,
        )
        return True

    async def consume_event_once(self) -> bool:
        message = await self._read_event()
        if message is None:
            return False
        try:
            event = EVENT_ADAPTER.validate_json(message.body)
        except (ValidationError, ValueError, TypeError) as error:
            event_id, command_id, case_ref = _event_references(message.body)
            await asyncio.to_thread(
                self._projector.reject,
                source_message_id=message.message_id,
                raw_body=message.body,
                error_code="INVALID_AGENT_EVENT",
                error=error,
                event_id=event_id,
                command_id=command_id,
                case_ref=case_ref,
            )
            LOGGER.error(
                "Rejected invalid Agent event %s: %s",
                message.message_id,
                error,
            )
            await self._ack_event(message.message_id)
            return True

        try:
            await asyncio.to_thread(self._projector.project, event)
        except AgentEventGapError as error:
            LOGGER.info("Deferring out-of-order Agent event: %s", error)
            return False
        except InvalidAgentEventError as error:
            await asyncio.to_thread(
                self._projector.reject,
                source_message_id=message.message_id,
                raw_body=message.body,
                error_code="INAPPLICABLE_AGENT_EVENT",
                error=error,
                event_id=event.event_id,
                command_id=event.command_id,
                case_ref=event.case_ref,
            )
            LOGGER.error(
                "Rejected inapplicable Agent event %s: %s",
                event.event_id,
                error,
            )
            await self._ack_event(message.message_id)
            return True
        except RefundExecutionUnavailableError:
            LOGGER.info(
                "Leaving refund event %s pending for an executor", event.event_id
            )
            return False

        await self._ack_event(message.message_id)
        return True

    async def _run_outbox(self) -> None:
        while not self._stop.is_set():
            try:
                worked = await self.dispatch_outbox_once()
                worked = await self.dispatch_completion_once() or worked
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Agent command publication failed")
                worked = False
            if not worked:
                await self._wait_when_idle()

    async def dispatch_completion_once(self) -> bool:
        from return_agent_contracts.completion import REFUND_COMPLETION_STREAM
        from return_agent.db.models import RefundCompletionOutboxRecord
        def pending():
            with self._session_factory() as session:
                row = session.scalar(select(RefundCompletionOutboxRecord).where(
                    RefundCompletionOutboxRecord.published.is_(False)).order_by(RefundCompletionOutboxRecord.resolution_ref).limit(1))
                return (row.resolution_ref,row.payload) if row else None
        record = await asyncio.to_thread(pending)
        if record is None:
            return False
        ref,payload = record
        # Delivery may repeat after publish/commit failure. Agent joins by ref/hash.
        await self._redis.xadd(REFUND_COMPLETION_STREAM,{REDIS_BODY_FIELD:_json(payload)})
        def mark():
            with self._session_factory.begin() as session:
                session.get(RefundCompletionOutboxRecord,ref).published = True
        await asyncio.to_thread(mark)
        return True

    async def _run_events(self) -> None:
        group_ready = False
        while not self._stop.is_set():
            try:
                if not group_ready:
                    await self._ensure_event_group()
                    group_ready = True
                await asyncio.to_thread(self._fulfillment.run_once)
                await self.consume_event_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Agent event consumption failed")
                group_ready = False
                await self._wait_when_idle()

    async def _wait_when_idle(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop.wait(), timeout=self._settings.idle_poll_seconds
            )
        except TimeoutError:
            pass

    def _claim_next_outbox_command(
        self,
    ) -> tuple[str, dict[str, Any], str] | None:
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(AgentCommandOutboxRecord)
                .where(
                    AgentCommandOutboxRecord.published_at.is_(None),
                    or_(
                        AgentCommandOutboxRecord.claimed_until.is_(None),
                        AgentCommandOutboxRecord.claimed_until <= now,
                    ),
                )
                .order_by(AgentCommandOutboxRecord.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if record is None:
                return None
            lease_token = uuid4().hex
            record.claimed_by = self._outbox_owner
            record.claimed_until = now + timedelta(
                seconds=self._settings.outbox_claim_seconds
            )
            record.lease_token = lease_token
            return record.command_id, dict(record.payload), lease_token

    def _record_publish_success(self, command_id: str, lease_token: str) -> None:
        with self._session_factory.begin() as session:
            record = session.get(AgentCommandOutboxRecord, command_id)
            if (
                record is None
                or record.published_at is not None
                or record.claimed_by != self._outbox_owner
                or record.lease_token != lease_token
            ):
                return
            record.attempt_count += 1
            record.published_at = datetime.now(UTC)
            record.last_error = None
            record.claimed_by = None
            record.claimed_until = None
            record.lease_token = None

    def _record_publish_failure(
        self,
        command_id: str,
        lease_token: str,
        error: Exception,
    ) -> None:
        with self._session_factory.begin() as session:
            record = session.get(AgentCommandOutboxRecord, command_id)
            if (
                record is None
                or record.published_at is not None
                or record.claimed_by != self._outbox_owner
                or record.lease_token != lease_token
            ):
                return
            record.attempt_count += 1
            record.last_error = f"{type(error).__name__}: {error}"[:2_000]
            record.claimed_by = None
            record.claimed_until = None
            record.lease_token = None

    async def _ensure_event_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                AGENT_EVENT_STREAM,
                API_EVENT_CONSUMER_GROUP,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def _read_event(self) -> RedisEventMessage | None:
        self._event_reads_since_reclaim += 1
        if self._event_reads_since_reclaim >= self._settings.event_reclaim_every:
            self._event_reads_since_reclaim = 0
            reclaimed = await self._reclaim_event()
            if reclaimed is not None:
                return reclaimed

        streams = await self._redis.xreadgroup(
            API_EVENT_CONSUMER_GROUP,
            self._settings.event_consumer_name,
            streams={AGENT_EVENT_STREAM: ">"},
            count=1,
            block=self._settings.event_block_ms,
        )
        if streams:
            return _redis_event_message(streams[0][1][0])

        return await self._reclaim_event()

    async def _reclaim_event(self) -> RedisEventMessage | None:
        claimed = await self._redis.xautoclaim(
            AGENT_EVENT_STREAM,
            API_EVENT_CONSUMER_GROUP,
            self._settings.event_consumer_name,
            min_idle_time=self._settings.event_reclaim_idle_ms,
            start_id=self._event_reclaim_cursor,
            count=1,
        )
        claimed_messages = claimed[1] if len(claimed) > 1 else []
        if claimed:
            next_cursor = _text(claimed[0])
            if claimed_messages:
                message_id = _text(claimed_messages[-1][0])
                if next_cursor == "0-0" or _stream_id_key(
                    next_cursor
                ) <= _stream_id_key(message_id):
                    next_cursor = _stream_id_after(message_id)
            self._event_reclaim_cursor = next_cursor
        return _redis_event_message(claimed_messages[0]) if claimed_messages else None

    async def _ack_event(self, message_id: str) -> None:
        await self._redis.xack(
            AGENT_EVENT_STREAM,
            API_EVENT_CONSUMER_GROUP,
            message_id,
        )


def _redis_event_message(
    entry: tuple[object, dict[object, object]],
) -> RedisEventMessage:
    message_id, fields = entry
    body = fields.get(REDIS_BODY_FIELD)
    if body is None:
        body = fields.get(REDIS_BODY_FIELD.encode())
    return RedisEventMessage(message_id=_text(message_id), body=_text(body or ""))


def _stream_id_key(message_id: str) -> tuple[int, int]:
    milliseconds, sequence = message_id.split("-", maxsplit=1)
    return int(milliseconds), int(sequence)


def _stream_id_after(message_id: str) -> str:
    milliseconds, sequence = _stream_id_key(message_id)
    return f"{milliseconds}-{sequence + 1}"


def _event_references(
    body: str,
) -> tuple[str | None, str | None, str | None]:
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None, None, None
    if not isinstance(value, dict):
        return None, None, None

    def reference(key: str) -> str | None:
        candidate = value.get(key)
        return candidate if isinstance(candidate, str) and candidate.strip() else None

    return (
        reference("event_id"),
        reference("command_id"),
        reference("case_ref"),
    )


def _event_payload_hash(event: AgentServiceEvent) -> str:
    payload = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _text(value: object) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)
