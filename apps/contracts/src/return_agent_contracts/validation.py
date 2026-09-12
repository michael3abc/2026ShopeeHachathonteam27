"""Deterministic validation that needs more than one contract DTO."""

from __future__ import annotations

from .review_gates import ReviewerGateConfig, evaluate_review_gate
from .models import REVIEW_REVISION_LIMIT

import re
from collections.abc import Iterable
from decimal import Decimal

from .enums import (
    ClaimId,
    ClaimStatus,
    EvidenceStatus,
    RequiredReturnReasonCode,
    ResolutionAction,
    RetrievalStatus,
    ReturnDecisionSource,
    ReturnPolicy,
    ReviewVerdict,
    SatisfiableBy,
    SubjectScope,
    WaivedReturnReasonCode,
)
from .models import (
    CaseContext,
    CaseContextLoadResult,
    ClaimFinding,
    CorrectedDecision,
    EvidenceAssessment,
    EvidenceItem,
    EvidenceRequest,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryCandidate,
    OrderSnapshot,
    PolicyBundle,
    ProposedDecisionDraft,
    ProposedDecisionHandoff,
    ReviewResult,
)
from .registry import get_claim_definition


class ContractInvariantError(ValueError):
    """A relationship between individually-valid DTOs is invalid."""


ClaimSubjectPair = tuple[str, str]
_CANDIDATE_PII_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)(?:\+?886[-\s]?)?0?9\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    re.compile(r"(?:姓名|收件人|聯絡人)\s*[:：]?\s*[\w\u3400-\u9fff]{2,}"),
    re.compile(r"(?:地址|住址)\s*[:：]?\s*[^\s,，。]{4,}"),
    re.compile(r"(?:artifact|https?)://", re.IGNORECASE),
)


def validate_memory_summary(summary: str) -> None:
    """Reject obvious PII and raw references before text reaches embeddings."""
    if not summary.strip() or len(summary) > 2000:
        raise ContractInvariantError("memory summary must contain 1 to 2000 characters")
    if any(pattern.search(summary) for pattern in _CANDIDATE_PII_PATTERNS):
        raise ContractInvariantError("memory summary contains PII or a raw reference")


def validate_memory_candidate(candidate: MemoryCandidate) -> None:
    """Reject duplicate scope metadata and obvious PII/raw artifact leakage."""

    validate_memory_summary(candidate.retrieval_summary)
    unique_lists = {
        "source_case_refs": candidate.source_case_refs,
        "source_event_refs": candidate.source_event_refs,
        "scope.reason_codes": candidate.scope.reason_codes,
        "scope.claim_ids": candidate.scope.claim_ids,
        "scope.categories": candidate.scope.categories,
    }
    for field_name, values in unique_lists.items():
        if len(values) != len(set(values)):
            raise ContractInvariantError(f"{field_name} must contain unique values")

    natural_language = [
        *candidate.trigger_conditions,
        candidate.recommended_behavior,
        candidate.rationale,
        *candidate.applicability_limits,
        *candidate.prohibited_inferences,
    ]
    for text in natural_language:
        if any(pattern.search(text) for pattern in _CANDIDATE_PII_PATTERNS):
            raise ContractInvariantError(
                "memory candidate contains PII or a raw artifact reference"
            )


def validate_applicable_policy_bundle(
    case_context: CaseContext, policy_bundle: PolicyBundle
) -> None:
    """Ensure the Policy provider returned usable clauses for this case instant."""

    if policy_bundle.retrieval_status is not RetrievalStatus.OK:
        raise ContractInvariantError(
            "a non-OK PolicyBundle must follow its fail-closed graph route"
        )
    for clause in policy_bundle.clauses:
        if clause.effective_from > case_context.case_opened_at or (
            clause.effective_to is not None
            and clause.effective_to < case_context.case_opened_at
        ):
            raise ContractInvariantError(
                "policy clause effective range does not cover case_opened_at"
            )


def validate_case_context_load_result(
    expected_case_ref: str, result: CaseContextLoadResult
) -> None:
    """Validate the part of a case load result that is not self-contained."""

    if result.case_context.case_ref != expected_case_ref:
        raise ContractInvariantError(
            "CaseContextLoadResult.case_context.case_ref does not match request"
        )
    if result.case_context.order_ref != result.order_snapshot.order_ref:
        raise ContractInvariantError(
            "CaseContextLoadResult case_context and order_snapshot order_ref differ"
        )


def _claimed_items(
    order_snapshot: OrderSnapshot, claimed_line_item_ids: Iterable[str]
) -> tuple[str, ...]:
    claimed = tuple(claimed_line_item_ids)
    known = {item.line_item_id for item in order_snapshot.line_items}
    if not claimed:
        raise ContractInvariantError("claimed_line_item_ids must not be empty")
    if len(claimed) != len(set(claimed)):
        raise ContractInvariantError("claimed_line_item_ids must be unique")
    unknown = set(claimed) - known
    if unknown:
        raise ContractInvariantError(f"unknown claimed line items: {sorted(unknown)}")
    return claimed


def expected_claim_pairs(
    policy_bundle: PolicyBundle, claimed_line_item_ids: Iterable[str]
) -> set[ClaimSubjectPair]:
    """Return the exact `(claim_id, subject)` set required by the policy."""

    if not policy_bundle.clauses:
        raise ContractInvariantError("assessment requires a non-empty PolicyBundle")
    expected: set[ClaimSubjectPair] = set()
    for clause in policy_bundle.clauses:
        for claim_id in clause.required_claim_ids:
            definition = get_claim_definition(claim_id)
            if definition.subject_scope is SubjectScope.ORDER:
                expected.add((claim_id.value, "ORDER"))
            else:
                expected.update(
                    (claim_id.value, line_item_id)
                    for line_item_id in claimed_line_item_ids
                )
    return expected


def _findings_by_pair(
    findings: Iterable[ClaimFinding],
) -> dict[ClaimSubjectPair, ClaimFinding]:
    return {(finding.claim_id.value, finding.subject): finding for finding in findings}


def validate_claim_findings(
    findings: Iterable[ClaimFinding],
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
) -> None:
    """Validate completeness and subject scope of an assessment/review."""

    items = _claimed_items(order_snapshot, claimed_line_item_ids)
    all_findings = tuple(findings)
    expected = expected_claim_pairs(policy_bundle, items)
    actual = {(finding.claim_id.value, finding.subject) for finding in all_findings}
    if len(actual) != len(all_findings):
        raise ContractInvariantError("claim findings must not contain duplicate pairs")
    if actual != expected:
        raise ContractInvariantError(
            f"claim finding pairs differ; expected {sorted(expected)}, got {sorted(actual)}"
        )


def expected_evidence_status(
    findings: Iterable[ClaimFinding],
    policy_bundle: PolicyBundle,
    claimed_line_item_ids: Iterable[str],
) -> EvidenceStatus:
    """Apply the documented three-valued evidence decision rule."""

    by_pair = _findings_by_pair(findings)
    required_claim_ids = {
        claim_id
        for clause in policy_bundle.clauses
        for claim_id in clause.required_claim_ids
    }
    order_claims = [
        claim_id
        for claim_id in required_claim_ids
        if get_claim_definition(claim_id).subject_scope is SubjectScope.ORDER
    ]
    line_item_claims = [
        claim_id
        for claim_id in required_claim_ids
        if get_claim_definition(claim_id).subject_scope is SubjectScope.LINE_ITEM
    ]

    per_item_statuses: list[list[ClaimStatus]] = []
    for line_item_id in claimed_line_item_ids:
        statuses = [
            by_pair[(claim_id.value, "ORDER")].status for claim_id in order_claims
        ]
        statuses.extend(
            by_pair[(claim_id.value, line_item_id)].status
            for claim_id in line_item_claims
        )
        per_item_statuses.append(statuses)

    if any(
        all(status is ClaimStatus.SUPPORTED for status in statuses)
        for statuses in per_item_statuses
    ):
        return EvidenceStatus.SUFFICIENT_FOR_APPROVAL
    if all(ClaimStatus.CONTRADICTED in statuses for statuses in per_item_statuses):
        return EvidenceStatus.SUFFICIENT_FOR_DECLINE
    return EvidenceStatus.INSUFFICIENT


def validate_evidence_request(
    request: EvidenceRequest,
    claim_findings: Iterable[ClaimFinding],
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
) -> None:
    items = _claimed_items(order_snapshot, claimed_line_item_ids)
    all_findings = tuple(claim_findings)
    validate_claim_findings(all_findings, policy_bundle, order_snapshot, items)
    unresolved_user_pairs = {
        (finding.claim_id.value, finding.subject)
        for finding in all_findings
        if finding.status is ClaimStatus.UNSUPPORTED
        and SatisfiableBy.USER_EVIDENCE
        in get_claim_definition(finding.claim_id).satisfiable_by
    }
    missing_pairs = {
        (entry.claim_id.value, entry.subject) for entry in request.missing_claims
    }
    if len(missing_pairs) != len(request.missing_claims):
        raise ContractInvariantError("missing_claims must not contain duplicate pairs")
    if missing_pairs != unresolved_user_pairs:
        raise ContractInvariantError(
            "missing_claims must equal all unresolved USER_EVIDENCE claim pairs"
        )

    accepted_types = set()
    for claim_id, _ in missing_pairs:
        definition = get_claim_definition(ClaimId(claim_id))
        if definition.satisfiable_by == (SatisfiableBy.SYSTEM_FACTS,):
            raise ContractInvariantError("SYSTEM_FACTS-only claims cannot be requested")
        accepted_types.update(definition.accepted_evidence_types)
    if set(request.accepted_evidence_types) != accepted_types:
        raise ContractInvariantError(
            "accepted_evidence_types must equal the registry union"
        )


def validate_evidence_assessment(
    assessment: EvidenceAssessment,
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
) -> None:
    items = _claimed_items(order_snapshot, claimed_line_item_ids)
    validate_claim_findings(
        assessment.claim_findings, policy_bundle, order_snapshot, items
    )
    actual_status = expected_evidence_status(
        assessment.claim_findings, policy_bundle, items
    )
    if assessment.evidence_status is not actual_status:
        raise ContractInvariantError(
            f"evidence_status must be {actual_status.value}, got {assessment.evidence_status.value}"
        )
    missing_evidence_request = getattr(assessment, "missing_evidence_request", None)
    if missing_evidence_request is not None:
        validate_evidence_request(
            missing_evidence_request,
            assessment.claim_findings,
            policy_bundle,
            order_snapshot,
            items,
        )


def validate_resolved_evidence_item(
    evidence_item: EvidenceItem, artifact_ref: str, pending_request: EvidenceRequest
) -> None:
    """Validate the deterministic merge after ``EvidenceProvider.resolve``."""

    if evidence_item.artifact_ref != artifact_ref:
        raise ContractInvariantError(
            "resolved evidence artifact_ref does not match the provider request"
        )
    pending_subjects = {entry.subject for entry in pending_request.missing_claims}
    if evidence_item.subject not in pending_subjects:
        raise ContractInvariantError(
            "resolved evidence subject is not in the pending evidence request"
        )


def _validate_action_against_policy(
    action: ResolutionAction, policy_bundle: PolicyBundle
) -> ReturnPolicy:
    if not policy_bundle.clauses:
        raise ContractInvariantError("decision requires a non-empty PolicyBundle")
    if any(action not in clause.allowed_actions for clause in policy_bundle.clauses):
        raise ContractInvariantError("action is not allowed by every applicable clause")
    return_policies = {clause.return_policy for clause in policy_bundle.clauses}
    if {ReturnPolicy.REQUIRED, ReturnPolicy.NOT_REQUIRED}.issubset(return_policies):
        raise ContractInvariantError("applicable clauses disagree on return policy")
    if ReturnPolicy.REQUIRED in return_policies:
        return ReturnPolicy.REQUIRED
    if ReturnPolicy.NOT_REQUIRED in return_policies:
        return ReturnPolicy.NOT_REQUIRED
    return ReturnPolicy.MODEL_JUDGMENT


def _supported_item_ids(
    findings: Iterable[ClaimFinding],
    policy_bundle: PolicyBundle,
    claimed_line_item_ids: Iterable[str],
) -> set[str]:
    by_pair = _findings_by_pair(findings)
    required_claim_ids = {
        claim_id
        for clause in policy_bundle.clauses
        for claim_id in clause.required_claim_ids
    }
    supported: set[str] = set()
    for line_item_id in claimed_line_item_ids:
        statuses = []
        for claim_id in required_claim_ids:
            subject = (
                "ORDER"
                if get_claim_definition(claim_id).subject_scope is SubjectScope.ORDER
                else line_item_id
            )
            statuses.append(by_pair[(claim_id.value, subject)].status)
        if all(status is ClaimStatus.SUPPORTED for status in statuses):
            supported.add(line_item_id)
    return supported


def validate_proposed_decision_draft(
    draft: ProposedDecisionDraft,
    assessment: EvidenceAssessment,
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
) -> None:
    items = _claimed_items(order_snapshot, claimed_line_item_ids)
    validate_evidence_assessment(assessment, policy_bundle, order_snapshot, items)
    return_policy = _validate_action_against_policy(draft.action, policy_bundle)
    _validate_policy_refs(draft.policy_refs, policy_bundle)
    _validate_rationale_has_no_amount(draft.rationale_summary, order_snapshot.currency)
    if not set(draft.refund_scope.line_item_ids).issubset(
        _supported_item_ids(assessment.claim_findings, policy_bundle, items)
    ):
        raise ContractInvariantError(
            "refund_scope includes items without supported claims"
        )
    if draft.action is ResolutionAction.DECLINE:
        if assessment.evidence_status is not EvidenceStatus.SUFFICIENT_FOR_DECLINE:
            raise ContractInvariantError(
                "DECLINE requires SUFFICIENT_FOR_DECLINE for every claimed item"
            )
        return

    return_decision = draft.return_decision
    if return_policy is ReturnPolicy.MODEL_JUDGMENT:
        if return_decision.source is not ReturnDecisionSource.MODEL_JUDGMENT:
            raise ContractInvariantError(
                "MODEL_JUDGMENT policy requires a model-authored return decision"
            )
        return
    if return_decision.source is not ReturnDecisionSource.POLICY:
        raise ContractInvariantError(
            "static return policy requires a POLICY return-decision draft"
        )
    if return_policy is ReturnPolicy.REQUIRED and not isinstance(
        return_decision.reason_code, RequiredReturnReasonCode
    ):
        raise ContractInvariantError(
            "REQUIRED policy requires a return-required reason"
        )
    if return_policy is ReturnPolicy.NOT_REQUIRED and not isinstance(
        return_decision.reason_code, WaivedReturnReasonCode
    ):
        raise ContractInvariantError(
            "NOT_REQUIRED policy requires a return-waived reason"
        )


def validate_review_result(
    review_result: ReviewResult,
    reviewed_handoff: ProposedDecisionHandoff,
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
    claimed_line_item_ids: Iterable[str],
) -> None:
    """Validate Reviewer findings and the references carried by a revision."""

    validate_claim_findings(
        review_result.reviewer_claim_findings,
        policy_bundle,
        order_snapshot,
        claimed_line_item_ids,
    )
    evidence_ids = {item.evidence_id for item in reviewed_handoff.evidence_bundle}
    for reason in review_result.revision_reasons:
        _validate_policy_refs(reason.policy_refs, policy_bundle)
        if not set(reason.evidence_refs).issubset(evidence_ids):
            raise ContractInvariantError(
                "revision reason evidence_refs must exist in evidence_bundle"
            )

    if review_result.verdict is not ReviewVerdict.APPROVE:
        return
    decision = reviewed_handoff.proposed_decision
    if decision.action is ResolutionAction.FULL_REFUND:
        supported_items = _supported_item_ids(
            review_result.reviewer_claim_findings,
            policy_bundle,
            claimed_line_item_ids,
        )
        if not set(decision.refund_scope.line_item_ids).issubset(supported_items):
            raise ContractInvariantError(
                "Reviewer APPROVE refund scope includes unsupported items"
            )
    elif (
        expected_evidence_status(
            review_result.reviewer_claim_findings,
            policy_bundle,
            claimed_line_item_ids,
        )
        is not EvidenceStatus.SUFFICIENT_FOR_DECLINE
    ):
        raise ContractInvariantError(
            "Reviewer APPROVE decline requires complete decline eligibility"
        )


def validate_proposed_decision_handoff(
    handoff: ProposedDecisionHandoff,
    policy_bundle: PolicyBundle,
    order_snapshot: OrderSnapshot,
) -> None:
    if handoff.order_snapshot_ref != order_snapshot.order_snapshot_ref:
        raise ContractInvariantError(
            "handoff order_snapshot_ref does not match snapshot"
        )
    if handoff.policy_bundle_version != policy_bundle.policy_bundle_version:
        raise ContractInvariantError(
            "handoff policy bundle version does not match bundle"
        )
    return_policy = _validate_action_against_policy(
        handoff.proposed_decision.action, policy_bundle
    )
    _validate_policy_refs(handoff.policy_refs, policy_bundle)
    _validate_rationale_has_no_amount(
        handoff.rationale_summary, order_snapshot.currency
    )
    decision = handoff.proposed_decision
    if decision.action is ResolutionAction.FULL_REFUND:
        return_decision = decision.return_decision
        if return_policy is ReturnPolicy.MODEL_JUDGMENT:
            if return_decision.source is not ReturnDecisionSource.MODEL_JUDGMENT:
                raise ContractInvariantError(
                    "MODEL_JUDGMENT policy requires MODEL_JUDGMENT return decision"
                )
        else:
            if return_decision.source is not ReturnDecisionSource.POLICY:
                raise ContractInvariantError(
                    "static return policy requires POLICY return decision"
                )
            required = return_decision.requirement.required
            if return_policy is ReturnPolicy.REQUIRED and not required:
                raise ContractInvariantError("REQUIRED policy requires return")
            if return_policy is ReturnPolicy.NOT_REQUIRED and required:
                raise ContractInvariantError("NOT_REQUIRED policy waives return")

    line_items = {item.line_item_id: item for item in order_snapshot.line_items}
    scope = handoff.proposed_decision.refund_scope.line_item_ids
    if not set(scope).issubset(line_items):
        raise ContractInvariantError("handoff refund scope contains unknown line items")
    expected_amount = sum(
        (line_items[line_item_id].refundable_amount for line_item_id in scope),
        Decimal(0),
    )
    if handoff.proposed_decision.amount != expected_amount:
        raise ContractInvariantError("handoff amount must equal the refund scope total")
    if handoff.proposed_decision.amount > order_snapshot.refundable_amount_max:
        raise ContractInvariantError("handoff amount exceeds refundable_amount_max")
    if handoff.proposed_decision.currency != order_snapshot.currency:
        raise ContractInvariantError("handoff currency must match order snapshot")

    requires_user_evidence = any(
        SatisfiableBy.USER_EVIDENCE in get_claim_definition(claim_id).satisfiable_by
        for clause in policy_bundle.clauses
        for claim_id in clause.required_claim_ids
    )
    if requires_user_evidence and not handoff.evidence_bundle:
        raise ContractInvariantError(
            "user-evidence policy requires a non-empty evidence bundle"
        )


def validate_human_review_entry(handoff: ProposedDecisionHandoff, review: ReviewResult, dossier: HumanReviewDossier, config: ReviewerGateConfig) -> None:
    if dossier.proposal_history[-1] != handoff or dossier.review_history[-1] != review:
        raise ContractInvariantError("human dossier does not match final proposal and review")
    if dossier.routing_reason == "REVISION_BUDGET_EXCEEDED":
        if review.verdict is not ReviewVerdict.REVISE or handoff.revision_round < REVIEW_REVISION_LIMIT or dossier.review_gate is not None:
            raise ContractInvariantError("revision entry requires exhausted REVISE without monetary gate")
        return
    decision = handoff.proposed_decision
    expected = evaluate_review_gate(decision.action, decision.amount, decision.currency, config)
    if (review.verdict is not ReviewVerdict.APPROVE or expected.status != "HUMAN_REQUIRED"
        or dossier.review_gate != expected or dossier.routing_reason != expected.reason):
        raise ContractInvariantError("human amount-gate entry is invalid or configuration changed")


def validate_human_decision(
    decision: CorrectedDecision,
    dossier: HumanReviewDossier,
    order_snapshot: OrderSnapshot,
    policy_bundle: PolicyBundle,
) -> Decimal:
    """Human owns evidence judgment; deterministic policy and money still bind."""
    if order_snapshot.order_ref != dossier.order_snapshot.order_ref:
        raise ContractInvariantError("human review order mismatch")
    if policy_bundle != dossier.policy_bundle:
        raise ContractInvariantError("human review policy changed or unavailable")
    return_policy = _validate_action_against_policy(decision.action, policy_bundle)
    scope = decision.refund_scope.line_item_ids
    if not set(scope).issubset(dossier.claimed_line_item_ids):
        raise ContractInvariantError("refund scope exceeds original claimed items")
    items = {item.line_item_id: item for item in order_snapshot.line_items}
    if not set(scope).issubset(items):
        raise ContractInvariantError("refund scope is no longer available")
    if order_snapshot.currency != dossier.order_snapshot.currency:
        raise ContractInvariantError("order currency changed")
    amount = sum((items[item].refundable_amount for item in scope), Decimal(0))
    if amount > order_snapshot.refundable_amount_max:
        raise ContractInvariantError("refund exceeds current refundable maximum")
    if decision.action is ResolutionAction.FULL_REFUND:
        required = decision.return_decision.requirement.required
        if return_policy is ReturnPolicy.REQUIRED and not required:
            raise ContractInvariantError("Policy requires return")
        if return_policy is ReturnPolicy.NOT_REQUIRED and required:
            raise ContractInvariantError("Policy waives return")
        if not dossier.proposal_history[-1].evidence_bundle and any(
            SatisfiableBy.USER_EVIDENCE in get_claim_definition(claim).satisfiable_by
            for clause in policy_bundle.clauses for claim in clause.required_claim_ids
        ):
            raise ContractInvariantError("required user evidence is absent")
    return amount


def human_corrected_decision(
    result: HumanReviewResult, handoff: ProposedDecisionHandoff
) -> CorrectedDecision:
    """Normalize the public review actions without reversing REJECT semantics."""
    from .models import CorrectedDeclineDecision, CorrectedFullRefundDecision

    if result.decision.value == "EDIT":
        return result.corrected_decision
    if result.decision.value == "REJECT" or handoff.proposed_decision.action is ResolutionAction.DECLINE:
        return CorrectedDeclineDecision(action="DECLINE", refund_scope={"line_item_ids": []})
    proposal = handoff.proposed_decision
    return CorrectedFullRefundDecision(
        action="FULL_REFUND", refund_scope=proposal.refund_scope,
        return_decision={"source": "HUMAN_REVIEW", "requirement": proposal.return_decision.requirement},
    )


def derive_memory_categories(
    order_snapshot: OrderSnapshot, claimed_line_item_ids: Iterable[str]
) -> list[str]:
    """Derive the only categories allowed in a memory query."""

    claimed = set(_claimed_items(order_snapshot, claimed_line_item_ids))
    return sorted(
        {
            item.category_ref
            for item in order_snapshot.line_items
            if item.line_item_id in claimed
        }
    )


def _validate_policy_refs(refs: Iterable[str], policy_bundle: PolicyBundle) -> None:
    clause_ids = {clause.clause_id for clause in policy_bundle.clauses}
    unknown = set(refs) - clause_ids
    if unknown:
        raise ContractInvariantError(f"unknown policy references: {sorted(unknown)}")


def _validate_rationale_has_no_amount(rationale: str, currency: str) -> None:
    escaped_currency = re.escape(currency)
    prohibited = re.compile(
        rf"(?:\b{escaped_currency}\s*\d+|\b\d+\s*{escaped_currency}\b|"
        r"\b(?:refund|amount)\s*[:：]?\s*\d+|(?:退款|金額)\s*(?:為|是|[:：])?\s*\d+|\d+\s*[元塊])",
        re.IGNORECASE,
    )
    if prohibited.search(rationale):
        raise ContractInvariantError(
            "rationale_summary must not contain a refund amount"
        )
