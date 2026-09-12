from pydantic import TypeAdapter
from sqlalchemy import select

from return_agent_contracts.primitives import payload_hash
from return_agent_contracts.providers import ContractConflict, ExecuteRefundRequest, SubmitHumanReviewParams
from return_agent_contracts.public import AgentEvent, EvidenceRequestView, HumanReviewPayload
from return_agent_contracts.workflow import AgentServiceEvent

from .capabilities import CapabilityStore
from .cases import CaseStore, CaseStateConflict
from .db import CommandOutboxRow, HumanReviewRow, ProcessedAgentEventRow, ProjectionCursorRow, ResolutionJobRow
from .refunds import AuthorizationRejected, RefundService, SimulatedRefundApplication


class EventOutOfOrder(RuntimeError):
    pass


class EventProjector:
    def __init__(self, cases: CaseStore):
        self.cases, self.sessions = cases, cases.sessions
        self.capabilities = CapabilityStore(cases)

    def emit(self, session, case, node, event_type, payload, timestamp):
        event = TypeAdapter(AgentEvent).validate_python({"case_ref": case.case_ref, "node": node, "seq": self.cases.next_seq(session, case.case_ref), "ts": timestamp, "type": event_type, "payload": payload})
        self.cases.append_event(session, case, event)

    def escalate(self, session, case, code, terminal_ref, timestamp):
        self.emit(session, case, "terminate_automation", "error", {"code": code, "message": "Automation stopped; manual follow-up is required", "retryable": False}, timestamp)
        self.cases.transition(session, case, "ESCALATED", code, "terminate_automation")
        self.emit(session, case, "terminate_automation", "done", {"status": "ESCALATED", "terminal_ref": terminal_ref}, timestamp)

    def project(self, event: AgentServiceEvent) -> bool:
        event = TypeAdapter(AgentServiceEvent).validate_python(event)
        with self.sessions.begin() as session:
            case = self.cases.locked_case(session, event.case_ref)
            command = session.get(CommandOutboxRow, event.command_id)
            if command is None or command.case_ref != case.case_ref or case.thread_id != event.thread_id or command.payload["thread_id"] != event.thread_id:
                raise ContractConflict("Event is not bound to a canonical command")
            existing = session.get(ProcessedAgentEventRow, event.event_id)
            if existing:
                if existing.payload_hash != payload_hash(event):
                    raise ContractConflict("Event ID reused with different content")
                return False
            cursor = session.get(ProjectionCursorRow, event.command_id)
            if cursor is None:
                cursor = ProjectionCursorRow(command_id=event.command_id, case_ref=case.case_ref, event_index=0)
                session.add(cursor)
            if cursor.terminal_event_id or event.event_index <= cursor.event_index:
                raise ContractConflict("Event conflicts with a projected command position")
            if event.event_index != cursor.event_index + 1:
                raise EventOutOfOrder("Earlier command events must be projected first")
            if case.status != "OBSERVING":
                raise CaseStateConflict("Command events require an observing case")
            if event.event_type == "NODE_OBSERVED":
                observation = event.payload.observation
                if observation.phase in ("ENTER", "EXIT"):
                    self.emit(session, case, observation.node, "node_enter" if observation.phase == "ENTER" else "node_exit", {"review_gate": observation.review_gate}, event.occurred_at)
                else:
                    self.emit(session, case, observation.node, "error", {"code": "NODE_CONTRACT_FAILURE", "message": "Node validation or provider failed", "retryable": False}, event.occurred_at)
                if observation.memory_retrieval is not None:
                    self.emit(session, case, observation.node, "memory_retrieval", observation.memory_retrieval, event.occurred_at)
            elif event.event_type == "INTERRUPTED":
                pending = event.payload.result.interrupt_payload
                if pending.kind == "CLARIFICATION":
                    case.clarification_request = pending.request.model_dump(mode="json")
                    node, status = "request_clarification", "AWAITING_CLARIFICATION"
                    public = {"interrupt_kind": "CLARIFICATION", "case_ref": case.case_ref, "request": pending.request}
                elif pending.kind == "EVIDENCE_REQUEST":
                    view = EvidenceRequestView(case_ref=case.case_ref, **pending.request.model_dump(mode="python"))
                    case.evidence_request = view.model_dump(mode="json")
                    node, status = "request_evidence", "AWAITING_EVIDENCE"
                    public = {"interrupt_kind": "EVIDENCE_REQUEST", "request": view}
                else:
                    row = session.get(HumanReviewRow, pending.review_ref)
                    if row is None or pending.dossier is None or row.case_ref != case.case_ref or row.handoff_id != pending.handoff_id or row.result is not None:
                        raise ContractConflict("Human interrupt has no matching pending persisted dossier")
                    submission = SubmitHumanReviewParams(handoff=pending.handoff, review=pending.review_result, dossier=pending.dossier)
                    if row.payload_hash != payload_hash(submission) or pending.policy_bundle != pending.dossier.policy_bundle:
                        raise ContractConflict("Human interrupt altered its persisted dossier")
                    proposal = pending.handoff.proposed_decision
                    values = proposal.model_dump(mode="python", exclude={"reason_code", "policy_refs", "evidence_refs"})
                    values.update(case_ref=case.case_ref, handoff_id=pending.handoff_id, dossier=pending.dossier, rationale_summary=pending.handoff.rationale_summary, review_result=pending.review_result, routing_reason=pending.routing_reason, memories_used=pending.memory_ids, evidence_refs=[{"evidence_id": e.evidence_id, "artifact_ref": e.artifact_ref, "caption": e.extracted_summary, "subject": e.subject, "type": e.type} for e in pending.handoff.evidence_bundle], policy_hits=[{"clause_id": c.clause_id, "excerpt": c.text, "policy_version": c.policy_version} for c in pending.policy_bundle.clauses])
                    view = TypeAdapter(HumanReviewPayload).validate_python(values)
                    case.human_review = view.model_dump(mode="json")
                    node, status = "await_human_review", "AWAITING_HUMAN_REVIEW"
                    public = {"interrupt_kind": "HUMAN_REVIEW", "review": view}
                self.cases.transition(session, case, status, "Agent requested input", node)
                self.emit(session, case, node, "interrupt", public, event.occurred_at)
            elif event.event_type == "RESOLVED":
                request = ExecuteRefundRequest(resolution_handoff=event.payload.result.resolution_handoff)
                try:
                    RefundService(self.capabilities, SimulatedRefundApplication(self.capabilities)).authorize(session, request)
                except AuthorizationRejected:
                    self.escalate(session, case, "REFUND_AUTHORIZATION_REJECTED", request.resolution_handoff.handoff_id, event.occurred_at)
                else:
                    case.final_resolution = request.resolution_handoff.model_dump(mode="json")
                    self.cases.transition(session, case, "EXECUTING", "Authorized resolution queued", "emit_resolution_handoff")
                    session.add(ResolutionJobRow(handoff_id=request.resolution_handoff.handoff_id, case_ref=case.case_ref, request=request.model_dump(mode="json"), status="PENDING", attempts=0, next_attempt_at=self.cases.clock()))
            elif event.event_type == "ESCALATED":
                result = event.payload.result.manual_escalation
                self.escalate(session, case, result.escalation_reason, event.event_id, event.occurred_at)
            else:
                self.escalate(session, case, event.payload.code, event.event_id, event.occurred_at)
            cursor.event_index = event.event_index
            if event.event_type != "NODE_OBSERVED":
                cursor.terminal_event_id = event.event_id
            session.add(ProcessedAgentEventRow(event_id=event.event_id, case_ref=case.case_ref, command_id=event.command_id, event_index=event.event_index, payload_hash=payload_hash(event), processed_at=self.cases.clock()))
            return True
