from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from return_agent_contracts.messages import AgentCommand, AgentResumeCommand, AgentResumePayload, AgentStartCommand, AgentStartPayload, AgentUserTurn, ClarificationResume, EvidenceResume
from return_agent_contracts.primitives import ContractModel, payload_hash
from return_agent_contracts.public import AgentEvent, CASE_TRANSITIONS, CaseDetail, CreateCaseRequest, SendMessageRequest, StateChangeEvent, StateChangePayload
from return_agent_contracts.workflow import GraphNodeName

from .db import CaseEventRow, CaseRow, CommandOutboxRow


class CaseNotFound(LookupError):
    pass


class CaseStateConflict(ValueError):
    pass


class MissingEvidence(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(kind: str) -> str:
    return f"{kind.upper()}-{uuid4().hex}"


class CaseStore:
    def __init__(self, sessions: sessionmaker[Session], *, clock: Callable[[], datetime] = utc_now, ids: Callable[[str], str] = new_ref):
        self.sessions, self.clock, self.ids = sessions, clock, ids

    def locked_case(self, session: Session, case_ref: str) -> CaseRow:
        case = session.scalar(select(CaseRow).where(CaseRow.case_ref == case_ref).with_for_update())
        if case is None:
            raise CaseNotFound(case_ref)
        return case

    def next_seq(self, session: Session, case_ref: str) -> int:
        session.flush()
        return (session.scalar(select(func.max(CaseEventRow.seq)).where(CaseEventRow.case_ref == case_ref)) or 0) + 1

    def append_event(self, session: Session, case: CaseRow, event: AgentEvent) -> None:
        event = TypeAdapter(AgentEvent).validate_python(event)
        if event.case_ref != case.case_ref:
            raise ValueError("Event belongs to a different case")
        session.add(CaseEventRow(event_id=self.ids("event"), case_ref=case.case_ref, seq=event.seq, kind="agent_event", payload=event.model_dump(mode="json"), created_at=event.ts))

    def transition(self, session: Session, case: CaseRow, to_status: str, reason: str, node: GraphNodeName) -> None:
        if to_status not in CASE_TRANSITIONS[case.status]:
            raise CaseStateConflict(f"Cannot transition {case.status} to {to_status}")
        previous = case.status
        case.status, case.updated_at = to_status, self.clock()
        event = StateChangeEvent(case_ref=case.case_ref, node=node, seq=self.next_seq(session, case.case_ref), ts=case.updated_at, type="state_change", payload=StateChangePayload(from_status=previous, to_status=to_status, reason=reason))
        self.append_event(session, case, event)

    def enqueue(self, session: Session, command: AgentCommand) -> None:
        command = TypeAdapter(AgentCommand).validate_python(command)
        session.add(CommandOutboxRow(command_id=command.command_id, case_ref=command.case_ref, payload=command.model_dump(mode="json"), payload_hash=payload_hash(command), created_at=command.issued_at, attempts=0))

    def create(self, request: CreateCaseRequest) -> str:
        now, case_ref, thread_id = self.clock(), self.ids("case"), self.ids("thread")
        turn = AgentUserTurn(turn_id=self.ids("turn"), role="USER", text=request.initial_message, received_at=now, attached_artifact_refs=request.attached_artifact_refs)
        with self.sessions.begin() as session:
            case = CaseRow(case_ref=case_ref, thread_id=thread_id, order_ref=request.order_ref, user_ref=request.user_ref, status="OBSERVING", created_at=now, updated_at=now)
            session.add(case)
            session.flush()
            session.add(CaseEventRow(event_id=turn.turn_id, case_ref=case_ref, seq=1, kind="user_turn", payload={"message": turn.text, "attached_artifact_refs": turn.attached_artifact_refs}, created_at=now))
            command = AgentStartCommand(command_type="START", command_id=self.ids("command"), case_ref=case_ref, thread_id=thread_id, issued_at=now, payload=AgentStartPayload(order_ref=request.order_ref, initial_turn=turn))
            self.enqueue(session, command)
        return case_ref

    def detail(self, case_ref: str) -> CaseDetail:
        with self.sessions() as session:
            case = session.get(CaseRow, case_ref)
            if case is None:
                raise CaseNotFound(case_ref)
            return CaseDetail.model_validate({key: getattr(case, key) for key in CaseDetail.model_fields})

    def message(self, case_ref: str, request: SendMessageRequest) -> CaseDetail:
        with self.sessions.begin() as session:
            case = self.locked_case(session, case_ref)
            if case.status not in ("AWAITING_CLARIFICATION", "AWAITING_EVIDENCE"):
                raise CaseStateConflict("Case is not waiting for a customer response")
            if case.status == "AWAITING_EVIDENCE" and not request.attached_artifact_refs:
                raise MissingEvidence("An artifact is required for an evidence response")
            now = self.clock()
            turn = AgentUserTurn(turn_id=self.ids("turn"), role="USER", text=request.message, received_at=now, attached_artifact_refs=request.attached_artifact_refs)
            resume = ClarificationResume(kind="CLARIFICATION", turn=turn) if case.status == "AWAITING_CLARIFICATION" else EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=request.attached_artifact_refs)
            session.add(CaseEventRow(event_id=turn.turn_id, case_ref=case_ref, seq=self.next_seq(session, case_ref), kind="user_turn", payload={"message": turn.text, "attached_artifact_refs": turn.attached_artifact_refs}, created_at=now))
            self.transition(session, case, "OBSERVING", "Customer response accepted", "parse_request" if resume.kind == "CLARIFICATION" else "request_evidence")
            case.clarification_request, case.evidence_request = None, None
            self.enqueue(session, AgentResumeCommand(command_type="RESUME", command_id=self.ids("command"), case_ref=case_ref, thread_id=case.thread_id, issued_at=now, payload=AgentResumePayload(resume=resume)))
        return self.detail(case_ref)

    def events(self, case_ref: str, after_seq: int = 0, limit: int = 100) -> list[AgentEvent]:
        with self.sessions() as session:
            if session.get(CaseRow, case_ref) is None:
                raise CaseNotFound(case_ref)
            rows = session.scalars(select(CaseEventRow).where(CaseEventRow.case_ref == case_ref, CaseEventRow.kind == "agent_event", CaseEventRow.seq > after_seq).order_by(CaseEventRow.seq).limit(limit))
            return [TypeAdapter(AgentEvent).validate_python(row.payload) for row in rows]
