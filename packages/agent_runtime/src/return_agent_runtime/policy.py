"""Deterministic v2 policy nodes and explicit buyer consent."""
import logging
from langgraph.types import interrupt
from return_agent_contracts.policy_v2 import (
    PolicyPathId, PolicySelection, PolicyConfirmationRequest, content_hash, evaluate_policy,
    policy_confirmation_request_ref, validate_policy_confirmation_request,
)
from return_agent_contracts.runtime import PolicyConfirmationResume
from return_agent_contracts.enums import EscalationReason
from .dependencies import AgentDependencies
from .state import AgentState

LOGGER = logging.getLogger(__name__)


def evaluate_state(state: AgentState, dependencies: AgentDependencies, findings=None):
    return evaluate_policy(context=state["case_context"],order=state["order_snapshot"],bundle=state["policy_bundle"],
        claimed_line_item_ids=state["claimed_line_item_ids"],
        findings=state["evidence_assessment"].claim_findings if findings is None else findings,
        evidence=state["evidence_bundle"],selection=state["policy_selection"],evaluated_at=dependencies.clock.now())


def confirmation_request(state: AgentState, path: PolicyPathId, required: bool, requirement_hash: str | None = None):
    selection = state["policy_selection"]
    version = selection.selection_version + 1
    requirement_hash = requirement_hash or content_hash({"required":required,"reason_code":"POLICY_RETURN_REQUIRED" if required else "ITEM_NOT_RECEIVED"})
    payload = dict(case_ref=state["case_ref"],original_scope_hash=content_hash(state["claimed_line_item_ids"]),
        original_path_id=selection.selected_path_id,path_id=path,selection_version=version,
        return_required=required,return_requirement_hash=requirement_hash)
    return PolicyConfirmationRequest(request_ref=policy_confirmation_request_ref(payload,state["policy_bundle"]),**payload)


def evaluate_policy_node(dependencies: AgentDependencies):
    def node(state: AgentState):
        try:
            evaluation = evaluate_state(state,dependencies)
        except ValueError:
            return {"escalation_reason":EscalationReason.CONTRACT_VIOLATION,"_route":"terminate_automation"}
        selected = [x for x in evaluation.item_evaluations if x.path_id is evaluation.selection.selected_path_id]
        update = {"policy_evaluation":evaluation}
        if all(x.status == "ELIGIBLE" for x in selected):
            return update | {"_route":"propose_decision"}
        alternative = [x for x in evaluation.item_evaluations if x.path_id is PolicyPathId.COOLING_OFF]
        if evaluation.selection.selected_path_id is PolicyPathId.DAMAGED_ON_ARRIVAL and all(x.status == "ELIGIBLE" for x in alternative):
            return update | {"pending_policy_confirmation":confirmation_request(state,PolicyPathId.COOLING_OFF,True),
                "_route":"confirm_policy_path"}
        if all(x.status == "NEEDS_INFORMATION" for x in selected) and state["evidence_round"] < 2:
            request = getattr(state["evidence_assessment"],"missing_evidence_request",None)
            if request is not None:
                return update | {"pending_evidence_request":request,"evidence_round":state["evidence_round"]+1,
                    "_route":"request_evidence"}
        if all(x.reason_codes == ["CLAIM_CONTRADICTED"] for x in selected) and not any(x.status == "ELIGIBLE" for x in evaluation.item_evaluations):
            return update | {"_route":"propose_decision"}
        return update | {"escalation_reason":EscalationReason.SPECIALIST_REQUIRED,"_route":"terminate_automation"}
    return node


def confirm_policy_path_node(state: AgentState):
    request = state["pending_policy_confirmation"]
    try:
        validate_policy_confirmation_request(request, state["policy_bundle"])
    except ValueError:
        LOGGER.warning("Policy confirmation rejected: unbound or changed versioned rule package")
        return {"escalation_reason":EscalationReason.CONTRACT_VIOLATION,"_route":"terminate_automation"}
    resume = PolicyConfirmationResume.model_validate(interrupt({"kind":"POLICY_CONFIRMATION",
        "case_ref":state["case_ref"],"request":request.model_dump(mode="json")}))
    confirmation = resume.confirmation
    if confirmation.request != request:
        return {"escalation_reason":EscalationReason.CONTRACT_VIOLATION,"_route":"terminate_automation"}
    if not confirmation.accepted:
        # Keep the original evidence budget; a declined alternative is not a denial.
        evidence_request = getattr(state.get("evidence_assessment"),"missing_evidence_request",None)
        if request.path_id is not request.original_path_id and evidence_request and state["evidence_round"] < 2:
            return {"pending_policy_confirmation":None,"pending_evidence_request":evidence_request,
                "evidence_round":state["evidence_round"]+1,"_route":"request_evidence"}
        return {"escalation_reason":EscalationReason.POLICY_CONFIRMATION_DECLINED,"_route":"terminate_automation"}
    selection = PolicySelection(selected_path_id=request.path_id,selection_version=request.selection_version,
        original_requested_action=state["policy_selection"].original_requested_action,confirmation_ref=confirmation.confirmation_ref)
    return {"policy_confirmation":confirmation,"policy_selection":selection,"pending_policy_confirmation":None,
        "operational_memory":[],"memory_retrieval":None,"policy_evaluation":None,"_route":"retrieve_policy"}
