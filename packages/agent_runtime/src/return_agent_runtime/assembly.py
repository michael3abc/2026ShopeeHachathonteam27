"""Deterministic decision, handoff, and terminal assembly."""

from __future__ import annotations
from return_agent_contracts.policy_v2 import active_clauses, REGISTRY_V2_VERSION

from collections.abc import Iterable
from decimal import Decimal

from return_agent_contracts.enums import (
    ClaimStatus,
    EscalationReason,
    OutcomeSource,
    ResolutionAction,
    ReturnDecisionSource,
    ReturnPolicy,
    ReviewVerdict,
    SubjectScope,
)
from return_agent_contracts.models import (
    AccumulatedEscalationContext,
    AgentFullRefundFinalDecision,
    ApprovedHumanReviewResult,
    DecisionRevisionEvent,
    DeclineFinalDecision,
    DeclineProposedDecision,
    DeclineProposedDecisionDraft,
    EditedHumanReviewResult,
    FullRefundProposedDecision,
    FullRefundProposedDecisionDraft,
    HumanApproveResolutionHandoff,
    HumanEditedFullRefundFinalDecision,
    HumanEditResolutionHandoff,
    HumanRejectResolutionHandoff,
    HumanReviewDossier,
    HumanReviewResult,
    ManualEscalationHandoff,
    MemoryDistillationInput,
    ModelJudgmentReturnDecision,
    OrderSnapshot,
    PolicyBundle,
    PolicyReturnDecision,
    PolicyReturnDecisionDraft,
    ProposedDecisionDraft,
    ProposedDecisionHandoff,
    RejectedHumanReviewResult,
    RequiredReturnRequirement,
    ResolutionHandoff,
    ReviewerApprovedResolutionHandoff,
    ReviewResult,
    WaivedReturnRequirement,
)
from return_agent_contracts.registry import CLAIM_REGISTRY_VERSION, get_claim_definition
from return_agent_contracts.validation import (
    ContractInvariantError,
    derive_memory_categories,
    validate_proposed_decision_draft,
    validate_proposed_decision_handoff,
)

from .dependencies import AgentDependencies
from .prompts import RESOLVER_PROMPT_VERSION
from .state import AgentState


def _effective_return_policy(policy_bundle: PolicyBundle) -> ReturnPolicy:
    policies = {clause.return_policy for clause in active_clauses(policy_bundle)}
    if {ReturnPolicy.REQUIRED, ReturnPolicy.NOT_REQUIRED}.issubset(policies):
        raise ContractInvariantError("applicable clauses disagree on return policy")
    if ReturnPolicy.REQUIRED in policies:
        return ReturnPolicy.REQUIRED
    if ReturnPolicy.NOT_REQUIRED in policies:
        return ReturnPolicy.NOT_REQUIRED
    return ReturnPolicy.MODEL_JUDGMENT


def _complete_return_decision(
    draft: FullRefundProposedDecisionDraft,
    policy_bundle: PolicyBundle,
) -> PolicyReturnDecision | ModelJudgmentReturnDecision:
    if isinstance(draft.return_decision, ModelJudgmentReturnDecision):
        return draft.return_decision
    if not isinstance(draft.return_decision, PolicyReturnDecisionDraft):
        raise ContractInvariantError("unsupported resolver return decision")
    policy = _effective_return_policy(policy_bundle)
    if policy is ReturnPolicy.REQUIRED:
        requirement = RequiredReturnRequirement(
            required=True,
            reason_code=draft.return_decision.reason_code,
        )
    elif policy is ReturnPolicy.NOT_REQUIRED:
        requirement = WaivedReturnRequirement(
            required=False,
            reason_code=draft.return_decision.reason_code,
        )
    else:
        raise ContractInvariantError(
            "MODEL_JUDGMENT policy cannot use a POLICY return-decision draft"
        )
    return PolicyReturnDecision(
        source=ReturnDecisionSource.POLICY,
        requirement=requirement,
    )


def _scope_amount(
    order_snapshot: OrderSnapshot, line_item_ids: Iterable[str]
) -> Decimal:
    items = {item.line_item_id: item for item in order_snapshot.line_items}
    ids = tuple(line_item_ids)
    unknown = set(ids) - set(items)
    if unknown:
        raise ContractInvariantError(f"unknown refund line items: {sorted(unknown)}")
    return sum((items[item_id].refundable_amount for item_id in ids), Decimal(0))


def _graph_owned_policy_refs(policy_bundle: PolicyBundle) -> list[str]:
    """Cite the complete set of clauses already selected as applicable."""

    return list(dict.fromkeys(clause.clause_id for clause in active_clauses(policy_bundle)))


def _graph_owned_evidence_refs(
    state: AgentState, draft: ProposedDecisionDraft
) -> list[str]:
    """Derive decision citations from validated findings, never model free text."""

    assessment = state["evidence_assessment"]
    if assessment is None:
        raise ContractInvariantError("decision citations require an assessment")
    target_status = (
        ClaimStatus.SUPPORTED
        if draft.action is ResolutionAction.FULL_REFUND
        else ClaimStatus.CONTRADICTED
    )
    target_items = (
        draft.refund_scope.line_item_ids
        if draft.action is ResolutionAction.FULL_REFUND
        else state["claimed_line_item_ids"]
    )
    required_claim_ids = {
        claim_id
        for clause in active_clauses(state["policy_bundle"])
        for claim_id in clause.required_claim_ids
    }
    relevant_pairs = {
        (
            claim_id,
            "ORDER"
            if get_claim_definition(claim_id).subject_scope is SubjectScope.ORDER
            else line_item_id,
        )
        for claim_id in required_claim_ids
        for line_item_id in target_items
    }
    cited = {
        evidence_ref
        for finding in assessment.claim_findings
        if (finding.claim_id, finding.subject) in relevant_pairs
        and finding.status is target_status
        for evidence_ref in finding.supporting_evidence_refs
    }
    return [
        evidence.evidence_id
        for evidence in state.get("evidence_bundle", [])
        if evidence.evidence_id in cited
    ]


def _graph_owned_draft(
    state: AgentState, draft: ProposedDecisionDraft
) -> ProposedDecisionDraft:
    return draft.model_copy(
        update={
            "policy_refs": _graph_owned_policy_refs(state["policy_bundle"]),
            "evidence_refs": _graph_owned_evidence_refs(state, draft),
        }
    )


def build_proposed_handoff(
    *,
    state: AgentState,
    draft: ProposedDecisionDraft,
    dependencies: AgentDependencies,
) -> ProposedDecisionHandoff:
    """Validate an LLM draft, derive graph-owned fields, and validate again."""

    draft = _graph_owned_draft(state, draft)
    assessment = state["evidence_assessment"]
    policy_bundle = state["policy_bundle"]
    order_snapshot = state["order_snapshot"]
    claimed_ids = state["claimed_line_item_ids"]
    validate_proposed_decision_draft(
        draft,
        assessment,
        policy_bundle,
        order_snapshot,
        claimed_ids,
    )

    if isinstance(draft, FullRefundProposedDecisionDraft):
        decision = FullRefundProposedDecision(
            action=ResolutionAction.FULL_REFUND,
            refund_scope=draft.refund_scope,
            amount=_scope_amount(order_snapshot, draft.refund_scope.line_item_ids),
            currency=order_snapshot.currency,
            reason_code=draft.reason_code,
            return_decision=_complete_return_decision(draft, policy_bundle),
            policy_refs=list(draft.policy_refs),
            evidence_refs=list(draft.evidence_refs),
        )
    elif isinstance(draft, DeclineProposedDecisionDraft):
        decision = DeclineProposedDecision(
            action=ResolutionAction.DECLINE,
            refund_scope=draft.refund_scope,
            amount="0",
            currency=order_snapshot.currency,
            reason_code=draft.reason_code,
            policy_refs=list(draft.policy_refs),
            evidence_refs=list(draft.evidence_refs),
        )
    else:
        raise ContractInvariantError("unknown ProposedDecisionDraft variant")

    handoff = ProposedDecisionHandoff(
        handoff_version="2.0" if policy_bundle.schema_version == "v2" else "1.0",
        policy_evaluation=state.get("policy_evaluation"),
        policy_selection=state.get("policy_selection"),
        policy_confirmation=state.get("policy_confirmation"),
        assessment_findings=assessment.claim_findings if policy_bundle.schema_version == "v2" else None,
        handoff_id=dependencies.id_factory.make(
            "handoff",
            state["thread_id"],
            state["propose_round"],
        ),
        case_ref=state["case_ref"],
        order_snapshot_ref=order_snapshot.order_snapshot_ref,
        policy_bundle_version=policy_bundle.policy_bundle_version,
        claim_registry_version=REGISTRY_V2_VERSION if policy_bundle.schema_version == "v2" else CLAIM_REGISTRY_VERSION,
        proposed_decision=decision,
        evidence_bundle=list(state.get("evidence_bundle", [])),
        policy_refs=list(dict.fromkeys(draft.policy_refs)),
        rationale_summary=draft.rationale_summary,
        revision_round=state["revision_round"],
        agent_prompt_version=RESOLVER_PROMPT_VERSION,
    )
    validate_proposed_decision_handoff(handoff, policy_bundle, order_snapshot)
    return handoff


def build_revision_event(
    *,
    state: AgentState,
    review_result: ReviewResult,
    dependencies: AgentDependencies,
) -> DecisionRevisionEvent:
    next_round = state["revision_round"] + 1
    handoff = state["current_handoff"]
    return DecisionRevisionEvent(
        event_id=dependencies.id_factory.make(
            "revision",
            state["thread_id"],
            handoff.handoff_id,
            next_round,
        ),
        case_ref=state["case_ref"],
        handoff_before_ref=handoff.handoff_id,
        review_result=review_result,
        revision_round=next_round,
        created_at=dependencies.clock.now(),
    )


def _agent_final_decision(handoff: ProposedDecisionHandoff):
    decision = handoff.proposed_decision
    if isinstance(decision, FullRefundProposedDecision):
        return AgentFullRefundFinalDecision(
            action=decision.action,
            refund_scope=decision.refund_scope,
            amount=decision.amount,
            currency=decision.currency,
            reason_code=decision.reason_code,
            return_decision=decision.return_decision,
        )
    return DeclineFinalDecision(
        action=decision.action,
        refund_scope=decision.refund_scope,
        amount=decision.amount,
        currency=decision.currency,
        reason_code=decision.reason_code,
    )


def _human_edited_final_decision(
    *,
    human_result: EditedHumanReviewResult,
    handoff: ProposedDecisionHandoff,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
):
    correction = human_result.corrected_decision
    scope = list(correction.refund_scope.line_item_ids)
    if not set(scope).issubset(set(claimed_line_item_ids)):
        raise ContractInvariantError(
            "human correction scope must stay within claimed line items"
        )
    if correction.action is ResolutionAction.FULL_REFUND:
        amount = _scope_amount(order_snapshot, scope)
        if amount > order_snapshot.refundable_amount_max:
            raise ContractInvariantError("human correction exceeds refundable maximum")
        return HumanEditedFullRefundFinalDecision(
            action=ResolutionAction.FULL_REFUND,
            refund_scope=correction.refund_scope,
            amount=amount,
            currency=order_snapshot.currency,
            return_decision=correction.return_decision,
            reason_code=handoff.proposed_decision.reason_code,
        )
    return DeclineFinalDecision(
        action=ResolutionAction.DECLINE,
        refund_scope=correction.refund_scope,
        amount="0",
        currency=order_snapshot.currency,
        reason_code=handoff.proposed_decision.reason_code,
    )


def build_resolution_handoff(
    *,
    state: AgentState,
    dependencies: AgentDependencies,
) -> ResolutionHandoff:
    handoff = state["current_handoff"]
    review = state["review_history"][-1]
    common = {
        "case_ref": state["case_ref"],
        "handoff_id": handoff.handoff_id,
        "review_gate": state.get("review_gate"),
        "user_risk_gate": state.get("user_risk_gate"),
        "policy_evaluation": (state.get("reviewer_evaluations") or [None])[-1],
        "emitted_at": dependencies.clock.now(),
        "review_result": review,
    }
    if handoff.handoff_version == "2.0":
        human = state.get("human_review_result")
        if human is not None and human.policy_evaluation is not None:
            common["policy_evaluation"] = human.policy_evaluation
        decision = human.corrected_decision if isinstance(human,EditedHumanReviewResult) else handoff.proposed_decision
        if decision.action is ResolutionAction.FULL_REFUND and not isinstance(human,RejectedHumanReviewResult):
            common["refund_release_condition"] = "RETURN_INSPECTION_PASSED" if decision.return_decision.requirement.required else "AUTHORIZED_NO_RETURN"
    if review.verdict is ReviewVerdict.APPROVE and state.get("human_review_result") is None:
        return ReviewerApprovedResolutionHandoff(
            **common,
            outcome_source=OutcomeSource.REVIEWER_APPROVE,
            final_decision=_agent_final_decision(handoff),
            execution_blocked=False,
        )
    human_result: HumanReviewResult = state["human_review_result"]
    if isinstance(human_result, ApprovedHumanReviewResult):
        return HumanApproveResolutionHandoff(
            **common,
            outcome_source=OutcomeSource.HUMAN_APPROVE,
            final_decision=_agent_final_decision(handoff),
            execution_blocked=False,
        )
    if isinstance(human_result, EditedHumanReviewResult):
        return HumanEditResolutionHandoff(
            **common,
            outcome_source=OutcomeSource.HUMAN_EDIT,
            final_decision=_human_edited_final_decision(
                human_result=human_result,
                handoff=handoff,
                order_snapshot=state["order_snapshot"],
                claimed_line_item_ids=state["claimed_line_item_ids"],
            ),
            execution_blocked=False,
        )
    if isinstance(human_result, RejectedHumanReviewResult):
        return HumanRejectResolutionHandoff(
            **common,
            outcome_source=OutcomeSource.HUMAN_REJECT,
            final_decision=DeclineFinalDecision(
                action=ResolutionAction.DECLINE,
                refund_scope={"line_item_ids": []},
                amount="0",
                currency=state["order_snapshot"].currency,
                reason_code=handoff.proposed_decision.reason_code,
            ),
            execution_blocked=False,
        )
    raise ContractInvariantError("unknown HumanReviewResult variant")


def build_memory_distillation_input(state: AgentState) -> MemoryDistillationInput:
    """Assemble the closed correction trace without adding transport concerns."""

    resolution = state.get("resolution_handoff")
    assessment = state.get("evidence_assessment")
    proposals = state.get("proposal_history", [])
    if resolution is None or assessment is None or not proposals:
        raise ContractInvariantError("memory distillation trace is incomplete")
    return MemoryDistillationInput(
        case_context=state["case_context"],
        policy_bundle=state["policy_bundle"],
        evidence_assessment=assessment,
        proposal_history=list(proposals),
        revision_events=list(state.get("revision_events", [])),
        human_review_result=state.get("human_review_result"),
        final_resolution=resolution,
        claimed_categories=derive_memory_categories(
            state["order_snapshot"], state["claimed_line_item_ids"]
        ),
    )


def build_human_review_dossier(state: AgentState) -> HumanReviewDossier:
    reviewed_ids = {event.handoff_before_ref for event in state.get("revision_events", [])}
    reviewed_ids.add(state["current_handoff"].handoff_id)
    return HumanReviewDossier(
        claim_registry_version=state["current_handoff"].claim_registry_version,
        routing_reason=state["review_routing_reason"],
        review_gate=state.get("review_gate"),
        user_risk_gate=state.get("user_risk_gate"),
        user_risk_snapshot=state.get("user_risk_snapshot"),
        reviewer_evaluations=state.get("reviewer_evaluations", []),
        policy_bundle_history=state.get("policy_bundle_history", []),
        claimed_line_item_ids=state["claimed_line_item_ids"],
        order_snapshot=state["order_snapshot"], policy_bundle=state["policy_bundle"],
        proposal_history=[p for p in state["proposal_history"] if p.handoff_id in reviewed_ids],
        review_history=state["review_history"],
        revision_events=state.get("revision_events", []),
    )


def build_manual_escalation(
    *,
    state: AgentState,
    reason: EscalationReason,
    dependencies: AgentDependencies,
) -> ManualEscalationHandoff:
    current = state.get("current_handoff")
    return ManualEscalationHandoff(
        case_ref=state["case_ref"],
        thread_id=state["thread_id"],
        escalation_reason=reason,
        last_known_handoff_ref=current.handoff_id if current is not None else None,
        accumulated_context=AccumulatedEscalationContext(
            clarification_round=state.get("clarification_round", 0),
            evidence_round=state.get("evidence_round", 0),
            verification_round=state.get("verification_round", 0),
            revision_round=state.get("revision_round", 0),
            review_history_refs=[
                event.event_id for event in state.get("revision_events", [])
            ],
            verification_issues=list(state.get("verification_feedback", [])),
        ),
        created_at=dependencies.clock.now(),
    )
