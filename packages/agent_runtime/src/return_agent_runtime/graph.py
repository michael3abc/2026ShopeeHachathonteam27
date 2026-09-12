"""Sixteen deterministic graph nodes; all external capabilities are injected ports."""
from decimal import Decimal
from typing import Any

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import TypeAdapter

from return_agent_contracts.distillation import MemoryDistillationInput
from return_agent_contracts.domain import CaseContextLoadResult, DecisionRevisionEvent, EvidenceAssessment, EvidenceItem, EvidenceRequest, HumanReviewDossier, PolicyBundle, ProposedDecision, ProposedDecisionHandoff, ReviewResult, VerificationResult, refund_amount
from return_agent_contracts.gates import gate_after_review
from return_agent_contracts.human import HumanReviewResult, ResolutionHandoff
from return_agent_contracts.memory import MemoryQuerySummary, MemoryRetrievalObservation, MemorySearchHit
from return_agent_contracts.messages import AgentResumeRequest, AgentStartRequest, ClarificationRequest, IntakeResult, ResolverOutput, ResumePayload
from return_agent_contracts.providers import FetchHumanReviewParams, LoadCaseContextParams, QueryApprovedMemoryParams, ResolveEvidenceParams, RetrievePolicyParams, SubmitHumanReviewParams, VerifyHandoffParams
from return_agent_contracts.registry import REGISTRY_VERSION
from return_agent_contracts.validation import effective_return_policy, validate_assessment, validate_dossier, validate_draft, validate_evidence_request, validate_handoff, validate_human_decision, validate_policy, validate_resolved_evidence, validate_review
from return_agent_contracts.workflow import AccumulatedEscalationContext, AgentRunResult, ClarificationInterruptPayload, EvidenceInterruptPayload, HumanReviewInterruptPayload, InterruptedAgentRunResult, ManualEscalationAgentRunResult, ManualEscalationHandoff, NodeExecutionObservation, ResolutionAgentRunResult

from .inputs import PROMPT_VERSIONS, intake_input, memory_query_input, resolver_input, reviewer_input
from .ports import RuntimeDependencies
from .state import RuntimeState

NODES = ("parse_request", "request_clarification", "load_case_context", "retrieve_policy", "prepare_memory_query", "retrieve_memory", "assess_case", "request_evidence", "propose_decision", "external_verification", "reviewer", "record_revision_event", "await_human_review", "emit_resolution_handoff", "enqueue_memory_distillation", "terminate_automation")


class ReturnRuntime:
    def __init__(self, dependencies: RuntimeDependencies, checkpointer):
        self.deps = dependencies
        builder = StateGraph(RuntimeState)
        for node in NODES:
            builder.add_node(node, self.wrapped(node))
        builder.add_edge(START, "parse_request")
        for node in NODES:
            if node in ("enqueue_memory_distillation", "terminate_automation"):
                builder.add_edge(node, END)
            else:
                builder.add_conditional_edges(node, lambda state: state.route, {name: name for name in NODES})
        self.graph = builder.compile(checkpointer=checkpointer)

    def config(self, thread_id: str):
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    def wrapped(self, node: str):
        def invoke(state: RuntimeState):
            state = RuntimeState.model_validate(state.checkpoint_values())
            attempt = state.node_attempts.get(node, 0) + 1
            state.node_attempts = {**state.node_attempts, node: attempt}
            task_ref = self.deps.ids("task", state.thread_id, node, attempt)
            observer = self.deps.observer
            if observer:
                observer.observe(NodeExecutionObservation(node=node, phase="ENTER", task_ref=task_ref))
            try:
                getattr(self, node)(state)
            except GraphInterrupt:
                if observer:
                    observer.paused(node, task_ref)
                raise
            except Exception:
                state.escalation_reason, state.route = "CONTRACT_VIOLATION", "terminate_automation"
                state.resolution, state.memory_distillation_input = None, None
                if node in ("enqueue_memory_distillation", "terminate_automation"):
                    self.terminate_automation(state)
                if observer:
                    observer.observe(NodeExecutionObservation(node=node, phase="ERROR", task_ref=task_ref, error_message="Node contract or provider failed"))
                return state.checkpoint_values()
            if observer:
                observer.observe(NodeExecutionObservation(node=node, phase="EXIT", task_ref=task_ref, memory_retrieval=state.memory_retrieval if node in ("prepare_memory_query", "retrieve_memory") else None, review_gate=state.review_gate if node == "reviewer" else None))
            return RuntimeState.model_validate(state.checkpoint_values()).checkpoint_values()
        return invoke

    def generate(self, task: str, payload: dict[str, Any], output_type):
        return TypeAdapter(output_type).validate_python(self.deps.model.generate(task, payload, output_type))

    def stop(self, state: RuntimeState, reason: str):
        state.escalation_reason, state.route = reason, "terminate_automation"

    def start(self, request: AgentStartRequest) -> AgentRunResult:
        request = AgentStartRequest.model_validate(request)
        config = self.config(request.thread_id)
        if self.graph.get_state(config).values:
            raise ValueError("Thread already exists; use its durable command journal")
        initial = RuntimeState(case_ref=request.case_ref, thread_id=request.thread_id, trusted_order_ref=request.order_ref, conversation_turns=[request.initial_turn])
        result = self.graph.invoke(initial.checkpoint_values(), config)
        return self.result(result)

    def resume(self, request: AgentResumeRequest) -> AgentRunResult:
        config = self.config(request.thread_id)
        snapshot = self.graph.get_state(config)
        pending = [item for task in snapshot.tasks for item in task.interrupts]
        if len(pending) != 1 or pending[0].value["kind"] != request.payload.kind:
            raise ValueError("Resume does not match the current interrupt")
        state = RuntimeState.model_validate(snapshot.values)
        if request.payload.kind == "CLARIFICATION" and request.payload.turn.turn_id in {turn.turn_id for turn in state.conversation_turns}:
            raise ValueError("Duplicate user turn")
        return self.result(self.graph.invoke(Command(resume=request.payload.model_dump(mode="json")), config))

    def continue_run(self, thread_id: str) -> AgentRunResult:
        """Resume interrupted execution after a worker crash, without inventing user input."""
        snapshot = self.graph.get_state(self.config(thread_id))
        pending = [item for task in snapshot.tasks for item in task.interrupts]
        if pending:
            return InterruptedAgentRunResult(result_type="INTERRUPTED", status="INTERRUPTED", interrupt_payload=pending[0].value)
        if not snapshot.values:
            raise ValueError("Unknown thread")
        return self.result(self.graph.invoke(None, self.config(thread_id))) if snapshot.next else self.result(snapshot.values)

    def result(self, values: dict[str, Any]) -> AgentRunResult:
        if values.get("__interrupt__"):
            return InterruptedAgentRunResult(result_type="INTERRUPTED", status="INTERRUPTED", interrupt_payload=values["__interrupt__"][0].value)
        state = RuntimeState.model_validate({key: value for key, value in values.items() if key != "__interrupt__"})
        if state.resolution:
            return ResolutionAgentRunResult(result_type="RESOLUTION", status="COMPLETED", resolution_handoff=state.resolution)
        return ManualEscalationAgentRunResult(result_type="MANUAL_ESCALATION", status="COMPLETED", manual_escalation=state.escalation)

    def state(self, thread_id: str) -> RuntimeState:
        return RuntimeState.model_validate(self.graph.get_state(self.config(thread_id)).values)

    def parse_request(self, state: RuntimeState):
        intent = self.generate("INTAKE", intake_input(state), IntakeResult)
        if intent.order_ref and state.trusted_order_ref and intent.order_ref != state.trusted_order_ref:
            raise ValueError("Intake cannot replace the trusted order")
        if intent.completeness == "INCOMPLETE":
            if state.clarification_round >= 2:
                return self.stop(state, "CLARIFICATION_BUDGET_EXCEEDED")
            state.clarification_round += 1
            state.clarification_request = ClarificationRequest(request_id=self.deps.ids("clarification", state.case_ref, state.clarification_round), clarification_round=state.clarification_round, missing_fields=intent.missing_fields, clarification_question=intent.clarification_question)
            state.normalized_intent, state.route = intent, "request_clarification"
            return
        if intent.reason_code is None or not intent.reason_summary or intent.requested_action not in ("REFUND", "RETURN_AND_REFUND"):
            raise ValueError("Complete intake lacks a supported request and reason")
        state.normalized_intent = intent
        if state.order_snapshot is None:
            state.route = "load_case_context"
            return
        claimed = intent.claimed_line_item_ids
        if not claimed or len(set(claimed)) != len(claimed) or not set(claimed) <= {item.line_item_id for item in state.order_snapshot.line_items}:
            raise ValueError("Intake items do not identify trusted order lines")
        state.claimed_line_item_ids, state.route = claimed, "retrieve_policy"

    def request_clarification(self, state: RuntimeState):
        payload = ClarificationInterruptPayload(kind="CLARIFICATION", case_ref=state.case_ref, request=state.clarification_request)
        response = TypeAdapter(ResumePayload).validate_python(interrupt(payload.model_dump(mode="json")))
        if response.kind != "CLARIFICATION" or response.turn.turn_id in {turn.turn_id for turn in state.conversation_turns}:
            raise ValueError("Wrong or repeated clarification response")
        state.conversation_turns = [*state.conversation_turns, response.turn]
        state.clarification_request, state.route = None, "parse_request"

    def load_case_context(self, state: RuntimeState):
        loaded = CaseContextLoadResult.model_validate(self.deps.context.load_case_context(LoadCaseContextParams(case_ref=state.case_ref)))
        if loaded.case_context.case_ref != state.case_ref or (state.trusted_order_ref and loaded.case_context.order_ref != state.trusted_order_ref):
            raise ValueError("Provider changed case or order identity")
        state.case_context, state.order_snapshot = loaded.case_context, loaded.order_snapshot
        state.trusted_order_ref = loaded.case_context.order_ref
        # Intake needs trusted item identifiers before it can select claim scope.
        state.route = "parse_request"

    def retrieve_policy(self, state: RuntimeState):
        policy = PolicyBundle.model_validate(self.deps.policy.retrieve_policy(RetrievePolicyParams(case_context=state.case_context, order_snapshot=state.order_snapshot, reason_code=state.normalized_intent.reason_code, claimed_line_item_ids=state.claimed_line_item_ids)))
        state.policy_bundle = policy
        if policy.retrieval_status != "OK":
            return self.stop(state, "POLICY_" + policy.retrieval_status)
        validate_policy(state.case_context, state.order_snapshot, policy, state.normalized_intent.reason_code, state.claimed_line_item_ids)
        state.route = "prepare_memory_query"

    def resolve_artifacts(self, state: RuntimeState, refs: list[str]):
        existing = {item.artifact_ref: item for item in state.evidence_bundle}
        subjects = {state.order_snapshot.order_ref, *(item.line_item_id for item in state.order_snapshot.line_items)}
        for ref in dict.fromkeys(refs):
            if ref not in existing:
                item = EvidenceItem.model_validate(self.deps.evidence.resolve(ResolveEvidenceParams(artifact_ref=ref)))
                validate_resolved_evidence(ref, item, subjects)
                if item.evidence_id in {known.evidence_id for known in existing.values()}:
                    raise ValueError("Evidence identity reused for another artifact")
                existing[ref] = item
        state.evidence_bundle = list(existing.values())

    def prepare_memory_query(self, state: RuntimeState):
        # Artifact failure is fatal; it is outside the optional-memory failure boundary.
        self.resolve_artifacts(state, [ref for turn in state.conversation_turns for ref in turn.attached_artifact_refs])
        try:
            summary = self.generate("MEMORY_QUERY_SUMMARY", memory_query_input(state), MemoryQuerySummary)
            state.memory_retrieval = MemoryRetrievalObservation(status="OK", query_summary=summary.query_summary)
            state.route = "retrieve_memory"
        except Exception:
            state.memory_retrieval = MemoryRetrievalObservation(status="UNAVAILABLE", error_code="SUMMARY_UNAVAILABLE")
            state.route = "assess_case"

    def retrieve_memory(self, state: RuntimeState):
        query = QueryApprovedMemoryParams(query_summary=state.memory_retrieval.query_summary, market=state.case_context.market, reason_code=state.normalized_intent.reason_code, required_claim_ids=sorted({claim for clause in state.policy_bundle.clauses for claim in clause.required_claim_ids}), categories=sorted({item.category_ref for item in state.order_snapshot.line_items if item.line_item_id in state.claimed_line_item_ids}), policy_versions=sorted({clause.policy_version for clause in state.policy_bundle.clauses}), claim_registry_major=1, top_k=3)
        try:
            hits = TypeAdapter(list[MemorySearchHit]).validate_python(self.deps.memory.query_approved(query))
            state.memory_retrieval = MemoryRetrievalObservation(status="OK", query_summary=query.query_summary, hits=hits)
        except Exception:
            state.memory_retrieval = MemoryRetrievalObservation(status="UNAVAILABLE", query_summary=query.query_summary, error_code="RETRIEVAL_UNAVAILABLE")
        state.route = "assess_case"

    def request_more_evidence(self, state: RuntimeState, request: EvidenceRequest):
        if state.evidence_round >= 2:
            return self.stop(state, "EVIDENCE_BUDGET_EXCEEDED")
        state.evidence_round += 1
        values = request.model_dump(mode="python")
        values["request_id"] = self.deps.ids("evidence-request", state.case_ref, state.evidence_round)
        state.evidence_request = EvidenceRequest.model_validate(values)
        state.route = "request_evidence"

    def assess_case(self, state: RuntimeState):
        assessment = self.generate("ASSESS", resolver_input(state), EvidenceAssessment)
        values = assessment.model_dump(mode="python")
        values["claim_registry_version"] = REGISTRY_VERSION
        assessment = TypeAdapter(EvidenceAssessment).validate_python(values)
        validate_assessment(assessment, state.policy_bundle, state.order_snapshot, state.claimed_line_item_ids, state.evidence_bundle)
        state.evidence_assessment = assessment
        if assessment.evidence_status == "INSUFFICIENT":
            self.request_more_evidence(state, assessment.missing_evidence_request)
        else:
            state.route = "propose_decision"

    def request_evidence(self, state: RuntimeState):
        payload = EvidenceInterruptPayload(kind="EVIDENCE_REQUEST", case_ref=state.case_ref, request=state.evidence_request)
        response = TypeAdapter(ResumePayload).validate_python(interrupt(payload.model_dump(mode="json")))
        if response.kind != "EVIDENCE_REQUEST":
            raise ValueError("Wrong evidence resume")
        self.resolve_artifacts(state, response.artifact_refs)
        state.evidence_request, state.route = None, "prepare_memory_query"

    def propose_decision(self, state: RuntimeState):
        if state.propose_round >= 6:
            return self.stop(state, "PROPOSE_BUDGET_EXCEEDED")
        state.propose_round += 1
        output = self.generate("PROPOSE_OR_REVISE", resolver_input(state), ResolverOutput)
        if output.result_type == "CONFLICTING_REVISIONS":
            return self.stop(state, "CONFLICTING_REVISIONS")
        if output.result_type == "REQUEST_EVIDENCE":
            findings = state.pending_review_result.reviewer_claim_findings if state.pending_review_result else state.evidence_assessment.claim_findings
            validate_evidence_request(output.evidence_request, findings, state.policy_bundle)
            return self.request_more_evidence(state, output.evidence_request)
        draft = output.draft
        validate_draft(draft, state.evidence_assessment, state.policy_bundle, state.order_snapshot, state.claimed_line_item_ids, state.evidence_bundle)
        values = draft.model_dump(mode="python", exclude={"rationale_summary"})
        values.update(amount=refund_amount(state.order_snapshot, draft.refund_scope.line_item_ids), currency=state.order_snapshot.currency)
        if draft.action == "FULL_REFUND" and draft.return_decision.source == "POLICY":
            values["return_decision"] = {"source": "POLICY", "requirement": {"required": effective_return_policy(state.policy_bundle) == "REQUIRED", "reason_code": draft.return_decision.reason_code}}
        decision = TypeAdapter(ProposedDecision).validate_python(values)
        if state.pending_review_result and state.current_handoff and decision == state.current_handoff.proposed_decision and draft.rationale_summary == state.current_handoff.rationale_summary:
            raise ValueError("Revision ignored the pending reviewer objections")
        handoff = ProposedDecisionHandoff(handoff_id=self.deps.ids("handoff", state.case_ref, state.propose_round), handoff_version="1.0", case_ref=state.case_ref, agent_prompt_version=PROMPT_VERSIONS["PROPOSE_OR_REVISE"], claim_registry_version=REGISTRY_VERSION, order_snapshot_ref=state.order_snapshot.order_snapshot_ref, policy_bundle_version=state.policy_bundle.policy_bundle_version, policy_refs=draft.policy_refs, evidence_bundle=state.evidence_bundle, proposed_decision=decision, rationale_summary=draft.rationale_summary, revision_round=state.revision_round)
        validate_handoff(handoff, state.case_context, state.order_snapshot, state.policy_bundle, state.claimed_line_item_ids)
        state.current_handoff = handoff
        state.pending_review_result, state.review_gate = None, None
        state.route = "external_verification"

    def external_verification(self, state: RuntimeState):
        result = TypeAdapter(VerificationResult).validate_python(self.deps.verification.verify(VerifyHandoffParams(handoff=state.current_handoff)))
        if result.status == "UNAVAILABLE":
            return self.stop(state, "VERIFICATION_UNAVAILABLE")
        if result.status == "FAIL":
            state.verification_feedback = result.issues
            if state.verification_round >= 2:
                return self.stop(state, "VERIFICATION_BUDGET_EXCEEDED")
            state.verification_round += 1
            state.route = "propose_decision"
            return
        state.proposal_history = [*state.proposal_history, state.current_handoff]
        state.verification_feedback, state.route = [], "reviewer"

    def reviewer(self, state: RuntimeState):
        now = self.deps.clock()
        result = self.generate("REVIEW", reviewer_input(state, now), ReviewResult)
        values = result.model_dump(mode="python")
        values.update(reviewed_at=now, reviewer_prompt_version=PROMPT_VERSIONS["REVIEW"])
        result = TypeAdapter(ReviewResult).validate_python(values)
        validate_review(result, state.current_handoff, state.order_snapshot, state.policy_bundle, state.claimed_line_item_ids)
        state.review_history = [*state.review_history, result]
        state.reviewed_proposal_ids = [*state.reviewed_proposal_ids, state.current_handoff.handoff_id]
        state.pending_review_result = result
        decision = state.current_handoff.proposed_decision
        state.review_gate = gate_after_review(result, decision.action, decision.amount, decision.currency, self.deps.gates)
        if result.verdict == "REVISE":
            if state.revision_round >= 3:
                state.routing_reason, state.route = "REVISION_BUDGET_EXCEEDED", "await_human_review"
            else:
                state.route = "record_revision_event"
        elif state.review_gate.status == "HUMAN_REQUIRED":
            state.routing_reason, state.route = state.review_gate.reason, "await_human_review"
        else:
            state.route = "emit_resolution_handoff"

    def record_revision_event(self, state: RuntimeState):
        state.revision_round += 1
        state.revision_events = [*state.revision_events, DecisionRevisionEvent(event_id=self.deps.ids("revision", state.case_ref, state.revision_round), case_ref=state.case_ref, handoff_before_ref=state.current_handoff.handoff_id, review_result=state.pending_review_result, revision_round=state.revision_round, created_at=self.deps.clock())]
        state.route = "propose_decision"

    def await_human_review(self, state: RuntimeState):
        proposals = {item.handoff_id: item for item in state.proposal_history}
        dossier = HumanReviewDossier(claim_registry_version=REGISTRY_VERSION, claimed_line_item_ids=state.claimed_line_item_ids, order_snapshot=state.order_snapshot, policy_bundle=state.policy_bundle, proposal_history=[proposals[ref] for ref in state.reviewed_proposal_ids], review_history=state.review_history, revision_events=state.revision_events, review_gate=state.review_gate, routing_reason=state.routing_reason)
        validate_dossier(dossier, state.current_handoff, state.pending_review_result, state.case_context, self.deps.gates)
        state.human_dossier = dossier
        ref = self.deps.human.submit_for_review(SubmitHumanReviewParams(handoff=state.current_handoff, review=state.pending_review_result, dossier=dossier))
        state.human_review_ref = ref
        result = self.deps.human.fetch_result(FetchHumanReviewParams(review_ref=ref))
        if result is None:
            payload = HumanReviewInterruptPayload(kind="HUMAN_REVIEW", case_ref=state.case_ref, handoff_id=state.current_handoff.handoff_id, review_ref=ref, handoff=state.current_handoff, review_result=state.pending_review_result, policy_bundle=state.policy_bundle, dossier=dossier, memory_ids=[hit.memory.memory_id for hit in state.memory_retrieval.hits] if state.memory_retrieval else [], routing_reason=state.routing_reason)
            response = TypeAdapter(ResumePayload).validate_python(interrupt(payload.model_dump(mode="json")))
            if response.kind != "HUMAN_REVIEW":
                raise ValueError("Wrong human review resume")
            result = self.deps.human.fetch_result(FetchHumanReviewParams(review_ref=ref))
        if result is None:
            state.route = "await_human_review"
        else:
            state.human_review_result = TypeAdapter(HumanReviewResult).validate_python(result)
            state.route = "emit_resolution_handoff"

    def emit_resolution_handoff(self, state: RuntimeState):
        proposal = state.current_handoff.proposed_decision
        final = proposal.model_dump(mode="python", exclude={"policy_refs", "evidence_refs"})
        source = "REVIEWER_APPROVE"
        human = state.human_review_result
        if human:
            source = "HUMAN_" + human.decision
            if human.decision == "EDIT":
                validate_human_decision(human.corrected_decision, state.human_dossier, state.order_snapshot, state.policy_bundle)
                final = human.corrected_decision.model_dump(mode="python")
                final.update(amount=refund_amount(state.order_snapshot, human.corrected_decision.refund_scope.line_item_ids), currency=proposal.currency, reason_code=proposal.reason_code)
            elif human.decision == "REJECT":
                final = {"action": "DECLINE", "amount": Decimal("0"), "currency": proposal.currency, "reason_code": proposal.reason_code, "refund_scope": {"line_item_ids": []}}
        state.resolution = TypeAdapter(ResolutionHandoff).validate_python({"handoff_id": state.current_handoff.handoff_id, "case_ref": state.case_ref, "emitted_at": self.deps.clock(), "execution_blocked": False, "review_gate": state.review_gate, "outcome_source": source, "final_decision": final, "review_result": state.review_history[-1]})
        state.route = "enqueue_memory_distillation"

    def enqueue_memory_distillation(self, state: RuntimeState):
        human = state.human_review_result
        corrected = bool(state.revision_events) or (human is not None and human.decision in ("EDIT", "REJECT"))
        if corrected and (human is None or human.generalizable is not False):
            state.memory_distillation_input = MemoryDistillationInput(case_context=state.case_context, claimed_categories=sorted({item.category_ref for item in state.order_snapshot.line_items if item.line_item_id in state.claimed_line_item_ids}), evidence_assessment=state.evidence_assessment, final_resolution=state.resolution, human_review_result=human, policy_bundle=state.policy_bundle, proposal_history=state.proposal_history, revision_events=state.revision_events)

    def terminate_automation(self, state: RuntimeState):
        state.escalation = ManualEscalationHandoff(case_ref=state.case_ref, thread_id=state.thread_id, created_at=self.deps.clock(), escalation_reason=state.escalation_reason or "CONTRACT_VIOLATION", last_known_handoff_ref=state.current_handoff.handoff_id if state.current_handoff else None, accumulated_context=AccumulatedEscalationContext(clarification_round=state.clarification_round, evidence_round=state.evidence_round, verification_round=state.verification_round, revision_round=state.revision_round, review_history_refs=state.reviewed_proposal_ids, verification_issues=state.verification_feedback))
