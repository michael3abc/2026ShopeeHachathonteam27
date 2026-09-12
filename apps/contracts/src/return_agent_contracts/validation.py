"""Context-dependent safety checks. Model shape validation alone is insufficient."""
from typing import Literal

from pydantic import TypeAdapter

from .domain import (
    CaseContext, ClaimFinding, ClaimId, CorrectedDecision, EvidenceAssessment, EvidenceItem,
    EvidenceRequest, HumanReviewDossier, OrderSnapshot, PolicyBundle, ProposedDecisionDraft,
    ProposedDecisionHandoff, ReviewResult, ReviewerGateConfig, AgentReturnDecision,
    DraftReturnDecision, HumanReviewReturnDecision, refund_amount,
)
from .gates import evaluate_gate
from .primitives import unique
from .registry import REGISTRY, REGISTRY_VERSION

Pair = tuple[ClaimId, str]


def validate_policy(context: CaseContext, snapshot: OrderSnapshot, policy: PolicyBundle, reason: str, claimed: list[str]) -> None:
    if policy.retrieval_status != "OK" or not policy.clauses:
        raise ValueError("Policy is unavailable or ambiguous")
    if context.order_ref != snapshot.order_ref or context.snapshot_version != snapshot.snapshot_version:
        raise ValueError("Context and order version mismatch")
    unique(claimed, "claimed item")
    lines = {item.line_item_id: item for item in snapshot.line_items}
    if not claimed or not set(claimed) <= lines.keys():
        raise ValueError("Claimed items must come from the trusted order")
    categories = {lines[item].category_ref for item in claimed}
    for clause in policy.clauses:
        if context.case_opened_at < clause.effective_from or (clause.effective_to is not None and context.case_opened_at > clause.effective_to):
            raise ValueError("Policy does not cover the case date")
        scope = clause.applicable_conditions
        if (scope.markets and context.market not in scope.markets) or (scope.reason_codes and reason not in scope.reason_codes) or (scope.categories and not categories.intersection(scope.categories)):
            raise ValueError("Policy does not cover the case scope")
    allowed_actions(policy)
    effective_return_policy(policy)


def allowed_actions(policy: PolicyBundle) -> set[str]:
    if policy.retrieval_status != "OK" or not policy.clauses:
        raise ValueError("A usable policy is required")
    actions = set.intersection(*(set(clause.allowed_actions) for clause in policy.clauses))
    if not actions:
        raise ValueError("Policy actions conflict")
    return actions


def effective_return_policy(policy: PolicyBundle) -> Literal["REQUIRED", "NOT_REQUIRED", "MODEL_JUDGMENT"]:
    requirements = {clause.return_policy for clause in policy.clauses}
    fixed = requirements - {"MODEL_JUDGMENT"}
    if len(fixed) > 1 or not requirements:
        raise ValueError("Policy return requirements conflict or are missing")
    return next(iter(fixed)) if fixed else "MODEL_JUDGMENT"


def expected_pairs(policy: PolicyBundle, snapshot: OrderSnapshot, claimed: list[str]) -> set[Pair]:
    unique(claimed, "claimed item")
    if not claimed or not set(claimed) <= {item.line_item_id for item in snapshot.line_items}:
        raise ValueError("Unknown or empty original claim scope")
    claims = {claim for clause in policy.clauses for claim in clause.required_claim_ids}
    return {(claim, subject) for claim in claims for subject in ([snapshot.order_ref] if REGISTRY[claim].subject_scope == "ORDER" else claimed)}


def validate_findings(findings: list[ClaimFinding], policy: PolicyBundle, snapshot: OrderSnapshot, claimed: list[str], evidence: list[EvidenceItem]) -> None:
    pairs = [(f.claim_id, f.subject) for f in findings]
    unique(pairs, "claim finding pair")
    if set(pairs) != expected_pairs(policy, snapshot, claimed):
        raise ValueError("Claim findings must cover exactly all required subject pairs")
    unique([item.evidence_id for item in evidence], "evidence ID")
    by_ref = {item.evidence_id: item for item in evidence}
    for finding in findings:
        unique(finding.supporting_evidence_refs, "supporting evidence reference")
        if not set(finding.supporting_evidence_refs) <= by_ref.keys():
            raise ValueError("Finding references unknown evidence")
        for ref in finding.supporting_evidence_refs:
            item = by_ref[ref]
            definition = REGISTRY[finding.claim_id]
            if item.subject != finding.subject:
                raise ValueError("Evidence subject differs from the finding")
            if item.source == "USER" and ("USER_EVIDENCE" not in definition.satisfiable_by or item.type not in definition.accepted_evidence_types):
                raise ValueError("Evidence type or source cannot establish this claim")


def eligible_items(findings: list[ClaimFinding], snapshot: OrderSnapshot, claimed: list[str]) -> tuple[list[str], bool]:
    approved: list[str] = []
    declined: list[str] = []
    for item in claimed:
        statuses = [f.status for f in findings if f.subject in (item, snapshot.order_ref)]
        if statuses and all(status == "SUPPORTED" for status in statuses):
            approved.append(item)
        if "CONTRADICTED" in statuses:
            declined.append(item)
    return approved, len(declined) == len(claimed)


def evidence_status(findings: list[ClaimFinding], snapshot: OrderSnapshot, claimed: list[str]) -> str:
    approved, declined = eligible_items(findings, snapshot, claimed)
    return "SUFFICIENT_FOR_APPROVAL" if approved else "SUFFICIENT_FOR_DECLINE" if declined else "INSUFFICIENT"


def validate_evidence_request(request: EvidenceRequest, findings: list[ClaimFinding], policy: PolicyBundle) -> None:
    unresolved = {(f.claim_id, f.subject) for f in findings if f.status == "UNSUPPORTED" and "USER_EVIDENCE" in REGISTRY[f.claim_id].satisfiable_by}
    requested = [(claim.claim_id, claim.subject) for claim in request.missing_claims]
    unique(requested, "missing claim pair")
    if set(requested) != unresolved:
        raise ValueError("Evidence request must contain every unresolved user-evidence pair only")
    types = {kind for claim, _ in unresolved for kind in REGISTRY[claim].accepted_evidence_types}
    unique(request.accepted_evidence_types, "accepted evidence type")
    if set(request.accepted_evidence_types) != types:
        raise ValueError("Accepted evidence types differ from the registry union")
    validate_refs(request.policy_refs, [clause.clause_id for clause in policy.clauses], "policy")


def validate_assessment(assessment: EvidenceAssessment, policy: PolicyBundle, snapshot: OrderSnapshot, claimed: list[str], evidence: list[EvidenceItem]) -> None:
    assessment = TypeAdapter(EvidenceAssessment).validate_python(assessment)
    if assessment.claim_registry_version != REGISTRY_VERSION:
        raise ValueError("Unknown assessment registry version")
    validate_findings(assessment.claim_findings, policy, snapshot, claimed, evidence)
    if assessment.evidence_status != evidence_status(assessment.claim_findings, snapshot, claimed):
        raise ValueError("Assessment status does not follow claim findings")
    if assessment.evidence_status == "INSUFFICIENT":
        validate_evidence_request(assessment.missing_evidence_request, assessment.claim_findings, policy)


def validate_refs(refs: list[str], known: list[str], label: str) -> None:
    unique(refs, label + " reference")
    if not set(refs) <= set(known):
        raise ValueError(f"Unknown {label} reference")


def validate_resolved_evidence(requested_ref: str, item: EvidenceItem, subjects: set[str], *, source: str | None = None) -> None:
    item = EvidenceItem.model_validate(item)
    if item.artifact_ref != requested_ref or item.subject not in subjects or (source is not None and item.source != source):
        raise ValueError("Resolved evidence does not match the requested artifact, subject or source")


def validate_return(decision: AgentReturnDecision | DraftReturnDecision | HumanReviewReturnDecision, policy: PolicyBundle, *, human: bool = False, draft: bool = False) -> None:
    rule = effective_return_policy(policy)
    expected_source = "HUMAN_REVIEW" if human else "MODEL_JUDGMENT" if rule == "MODEL_JUDGMENT" else "POLICY"
    if decision.source != expected_source:
        raise ValueError("Return decision source does not match policy authority")
    if draft and decision.source == "POLICY":
        from .domain import RequiredReturnReasonCode
        from typing import get_args
        required = decision.reason_code in get_args(RequiredReturnReasonCode)
    else:
        required = decision.requirement.required
    if (rule == "REQUIRED" and not required) or (rule == "NOT_REQUIRED" and required):
        raise ValueError("Return decision conflicts with a fixed policy")


def validate_draft(draft: ProposedDecisionDraft, assessment: EvidenceAssessment, policy: PolicyBundle, snapshot: OrderSnapshot, claimed: list[str], evidence: list[EvidenceItem]) -> None:
    draft = TypeAdapter(ProposedDecisionDraft).validate_python(draft)
    validate_assessment(assessment, policy, snapshot, claimed, evidence)
    if draft.action not in allowed_actions(policy):
        raise ValueError("Policy does not allow this action")
    validate_refs(draft.policy_refs, [c.clause_id for c in policy.clauses], "policy")
    validate_refs(draft.evidence_refs, [e.evidence_id for e in evidence], "evidence")
    approved, declined = eligible_items(assessment.claim_findings, snapshot, claimed)
    if draft.action == "FULL_REFUND":
        if not set(draft.refund_scope.line_item_ids) <= set(approved):
            raise ValueError("Refund scope is not supported by the assessed claims")
        refund_amount(snapshot, draft.refund_scope.line_item_ids)
        validate_return(draft.return_decision, policy, draft=True)
    elif not declined:
        raise ValueError("DECLINE requires contradictory claims for every requested item")


def validate_handoff(handoff: ProposedDecisionHandoff, context: CaseContext, snapshot: OrderSnapshot, policy: PolicyBundle, claimed: list[str]) -> None:
    handoff = ProposedDecisionHandoff.model_validate(handoff)
    decision = handoff.proposed_decision
    validate_policy(context, snapshot, policy, decision.reason_code, claimed)
    if (handoff.case_ref != context.case_ref or handoff.order_snapshot_ref != snapshot.order_snapshot_ref or handoff.policy_bundle_version != policy.policy_bundle_version or handoff.claim_registry_version != REGISTRY_VERSION):
        raise ValueError("Handoff identity or version does not match trusted context")
    unique([e.evidence_id for e in handoff.evidence_bundle], "evidence ID")
    validate_refs(handoff.policy_refs, [c.clause_id for c in policy.clauses], "policy")
    validate_refs(decision.policy_refs, handoff.policy_refs, "decision policy")
    validate_refs(decision.evidence_refs, [e.evidence_id for e in handoff.evidence_bundle], "evidence")
    if decision.action not in allowed_actions(policy):
        raise ValueError("Action is not permitted by all applicable policy clauses")
    if not set(decision.refund_scope.line_item_ids) <= set(claimed):
        raise ValueError("Handoff expands the original claim scope")
    if decision.currency != snapshot.currency or decision.amount != refund_amount(snapshot, decision.refund_scope.line_item_ids):
        raise ValueError("Handoff amount or currency differs from the trusted scope total")
    needs_user = any("USER_EVIDENCE" in REGISTRY[claim].satisfiable_by for clause in policy.clauses for claim in clause.required_claim_ids)
    if needs_user and not handoff.evidence_bundle:
        raise ValueError("The policy requires an evidence bundle")
    if decision.action == "FULL_REFUND":
        validate_return(decision.return_decision, policy)


def validate_review(review: ReviewResult, handoff: ProposedDecisionHandoff, snapshot: OrderSnapshot, policy: PolicyBundle, claimed: list[str]) -> None:
    review = TypeAdapter(ReviewResult).validate_python(review)
    validate_findings(review.reviewer_claim_findings, policy, snapshot, claimed, handoff.evidence_bundle)
    if review.verdict == "REVISE":
        for reason in review.revision_reasons:
            if not reason.message.strip() or not reason.required_change.strip():
                raise ValueError("Reviewer objections must request a concrete change")
            validate_refs(reason.evidence_refs, [e.evidence_id for e in handoff.evidence_bundle], "revision evidence")
            validate_refs(reason.policy_refs, [c.clause_id for c in policy.clauses], "revision policy")
        return
    approved, declined = eligible_items(review.reviewer_claim_findings, snapshot, claimed)
    decision = handoff.proposed_decision
    if decision.action == "FULL_REFUND" and not set(decision.refund_scope.line_item_ids) <= set(approved):
        raise ValueError("Reviewer findings do not support the refund scope")
    if decision.action == "DECLINE" and not declined:
        raise ValueError("Reviewer findings do not establish decline for all requested items")


def validate_dossier(dossier: HumanReviewDossier, handoff: ProposedDecisionHandoff, review: ReviewResult, context: CaseContext, config: ReviewerGateConfig) -> None:
    dossier = HumanReviewDossier.model_validate(dossier)
    proposals, reviews, events = dossier.proposal_history, dossier.review_history, dossier.revision_events
    if len(proposals) != len(reviews) or len(events) != len(proposals) - 1:
        raise ValueError("Dossier must contain every reviewed proposal and completed revision")
    unique([p.handoff_id for p in proposals], "proposal ID")
    unique([e.event_id for e in events], "revision event ID")
    unique(dossier.claimed_line_item_ids, "original claimed item")
    if dossier.claim_registry_version != REGISTRY_VERSION:
        raise ValueError("Dossier registry mismatch")
    if proposals[-1] != handoff or reviews[-1] != review:
        raise ValueError("Dossier does not end at the submitted proposal and review")
    for index, (proposal, result) in enumerate(zip(proposals, reviews, strict=True)):
        if proposal.revision_round != index:
            raise ValueError("Reviewer rounds must start at zero and be contiguous")
        validate_handoff(proposal, context, dossier.order_snapshot, dossier.policy_bundle, dossier.claimed_line_item_ids)
        validate_review(result, proposal, dossier.order_snapshot, dossier.policy_bundle, dossier.claimed_line_item_ids)
        if index < len(events):
            event = events[index]
            if (event.case_ref != context.case_ref or event.handoff_before_ref != proposal.handoff_id or event.revision_round != index + 1 or event.review_result != result or result.verdict != "REVISE"):
                raise ValueError("Revision event does not match its preceding reviewed proposal")
    if dossier.routing_reason == "REVISION_BUDGET_EXCEEDED":
        if len(proposals) != 4 or review.verdict != "REVISE" or dossier.review_gate is not None:
            raise ValueError("Revision entry requires four REVISE reviews and no monetary gate")
    else:
        decision = handoff.proposed_decision
        gate = evaluate_gate(decision.action, decision.amount, decision.currency, config)
        if review.verdict != "APPROVE" or gate.status != "HUMAN_REQUIRED" or gate != dossier.review_gate or dossier.routing_reason != gate.reason:
            raise ValueError("Human monetary entry does not match the current verified gate")


def validate_human_decision(decision: CorrectedDecision, dossier: HumanReviewDossier, current: OrderSnapshot, policy: PolicyBundle) -> None:
    decision = TypeAdapter(CorrectedDecision).validate_python(decision)
    if current.order_ref != dossier.order_snapshot.order_ref or current.currency != dossier.order_snapshot.currency:
        raise ValueError("Human review cannot change the order or currency")
    if policy != dossier.policy_bundle or policy.retrieval_status != "OK":
        raise ValueError("Human review must retain the exact persisted policy")
    if decision.action not in allowed_actions(policy):
        raise ValueError("Human review action is not allowed by policy")
    if not set(decision.refund_scope.line_item_ids) <= set(dossier.claimed_line_item_ids):
        raise ValueError("Human review cannot expand original claim scope")
    refund_amount(current, decision.refund_scope.line_item_ids)
    if decision.action == "FULL_REFUND":
        validate_return(decision.return_decision, policy, human=True)
        if any("USER_EVIDENCE" in REGISTRY[claim].satisfiable_by for clause in policy.clauses for claim in clause.required_claim_ids) and not dossier.proposal_history[-1].evidence_bundle:
            raise ValueError("Human refund lacks the required evidence bundle")
