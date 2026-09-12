from __future__ import annotations

import pytest
from return_agent_contracts.enums import (
    ClaimId,
    ClaimStatus,
    EvidenceStatus,
    EvidenceType,
    ReturnPolicy,
)
from return_agent_contracts.models import (
    ApprovalEvidenceAssessment,
    ApprovedReviewResult,
    ClaimFinding,
    DeclineEvidenceAssessment,
    DeclineProposedDecision,
    DeclineProposedDecisionDraft,
    EvidenceRequest,
    FullRefundProposedDecision,
    FullRefundProposedDecisionDraft,
    InsufficientEvidenceAssessment,
    MissingClaim,
    NonEmptyRefundScope,
    PolicyBundle,
    PolicyReturnDecision,
    PolicyReturnDecisionDraft,
    RequiredReturnRequirement,
    RevisedReviewResult,
    RevisionReason,
)
from return_agent_contracts.registry import CLAIM_REGISTRY_V1, validate_claim_registry
from return_agent_contracts.validation import (
    ContractInvariantError,
    derive_memory_categories,
    expected_claim_pairs,
    validate_applicable_policy_bundle,
    validate_case_context_load_result,
    validate_evidence_assessment,
    validate_evidence_request,
    validate_memory_candidate,
    validate_proposed_decision_draft,
    validate_proposed_decision_handoff,
    validate_resolved_evidence_item,
    validate_review_result,
)

from .fixtures import (
    case_context_load_result,
    evidence_item,
    evidence_request,
    memory_candidate,
    order_snapshot,
    policy_bundle,
    proposed_decision_draft,
    proposed_handoff,
    supported_assessment,
)


@pytest.mark.parametrize(
    "leaked_text",
    [
        "Contact buyer at customer@example.com before requesting evidence.",
        "Call 0912-345-678 to confirm the package condition.",
        "收件人：王小明，請一次索取全部照片。",
        "Reuse artifact://evidence/EV-002 for future cases.",
    ],
)
def test_memory_candidate_rejects_pii_and_raw_artifact_references(
    leaked_text: str,
) -> None:
    candidate = memory_candidate().model_copy(
        update={"recommended_behavior": leaked_text}
    )

    with pytest.raises(ContractInvariantError):
        validate_memory_candidate(candidate)


def test_claim_pairs_and_supported_assessment_are_valid() -> None:
    policy = policy_bundle()
    assessment = supported_assessment()
    assert expected_claim_pairs(policy, ["LI-002"]) == {
        (ClaimId.DELIVERY_CONFIRMED.value, "ORDER"),
        (ClaimId.ORDER_WITHIN_RETURN_WINDOW.value, "ORDER"),
        (ClaimId.ITEM_PHYSICALLY_DAMAGED.value, "LI-002"),
        (ClaimId.DAMAGE_PRESENT_ON_ARRIVAL.value, "LI-002"),
    }
    validate_evidence_assessment(assessment, policy, order_snapshot(), ["LI-002"])
    validate_proposed_decision_draft(
        proposed_decision_draft(), assessment, policy, order_snapshot(), ["LI-002"]
    )
    validate_proposed_decision_handoff(proposed_handoff(), policy, order_snapshot())


def test_evidence_request_must_equal_all_unresolved_user_claims() -> None:
    findings = [
        finding.model_copy(
            update={"status": ClaimStatus.UNSUPPORTED, "supporting_evidence_refs": []}
        )
        if finding.claim_id
        in {ClaimId.ITEM_PHYSICALLY_DAMAGED, ClaimId.DAMAGE_PRESENT_ON_ARRIVAL}
        else finding
        for finding in supported_assessment().claim_findings
    ]
    complete_request = EvidenceRequest(
        request_id="EREQ-ALL",
        missing_claims=[
            MissingClaim(claim_id=ClaimId.ITEM_PHYSICALLY_DAMAGED, subject="LI-002"),
            MissingClaim(claim_id=ClaimId.DAMAGE_PRESENT_ON_ARRIVAL, subject="LI-002"),
        ],
        accepted_evidence_types=[EvidenceType.IMAGE, EvidenceType.VIDEO],
        user_message="Provide one clear set of photos for all missing claims.",
        policy_refs=["POLICY-12:v3#4.2"],
    )
    assessment = InsufficientEvidenceAssessment(
        evidence_status="INSUFFICIENT",
        claim_registry_version="claim-registry:1.0",
        claim_findings=findings,
        missing_evidence_request=complete_request,
    )
    validate_evidence_assessment(
        assessment, policy_bundle(), order_snapshot(), ["LI-002"]
    )

    omitted = complete_request.model_copy(
        update={"missing_claims": complete_request.missing_claims[:1]}
    )
    with pytest.raises(ContractInvariantError):
        validate_evidence_request(
            omitted, findings, policy_bundle(), order_snapshot(), ["LI-002"]
        )

    already_supported = complete_request.model_copy(
        update={
            "missing_claims": [
                MissingClaim(
                    claim_id=ClaimId.DELIVERY_CONFIRMED,
                    subject="ORDER",
                )
            ],
            "accepted_evidence_types": [EvidenceType.DOCUMENT],
        }
    )
    with pytest.raises(ContractInvariantError):
        validate_evidence_request(
            already_supported,
            findings,
            policy_bundle(),
            order_snapshot(),
            ["LI-002"],
        )


def test_system_facts_only_gap_fails_closed_instead_of_requesting_user() -> None:
    findings = [
        finding.model_copy(
            update={"status": ClaimStatus.UNSUPPORTED, "supporting_evidence_refs": []}
        )
        if finding.claim_id is ClaimId.ORDER_WITHIN_RETURN_WINDOW
        else finding
        for finding in supported_assessment().claim_findings
    ]
    with pytest.raises(ContractInvariantError):
        validate_evidence_request(
            evidence_request(), findings, policy_bundle(), order_snapshot(), ["LI-002"]
        )


def _multi_item_findings(*, second_item_supported: bool) -> list[ClaimFinding]:
    base = supported_assessment().claim_findings
    findings = [base[0], base[1]]
    for line_item_id, contradicted in (
        ("LI-001", True),
        ("LI-002", not second_item_supported),
    ):
        for finding in base[2:]:
            findings.append(
                finding.model_copy(
                    update={
                        "subject": line_item_id,
                        "status": (
                            ClaimStatus.CONTRADICTED
                            if contradicted
                            else ClaimStatus.SUPPORTED
                        ),
                    }
                )
            )
    return findings


def test_decline_requires_every_claimed_item_to_be_decline_eligible() -> None:
    mixed = ApprovalEvidenceAssessment(
        evidence_status=EvidenceStatus.SUFFICIENT_FOR_APPROVAL,
        claim_registry_version="claim-registry:1.0",
        claim_findings=_multi_item_findings(second_item_supported=True),
    )
    decline = DeclineProposedDecisionDraft(
        action="DECLINE",
        refund_scope={"line_item_ids": []},
        reason_code="ITEM_DAMAGED",
        policy_refs=["POLICY-12:v3#4.2"],
        evidence_refs=["EV-002"],
        rationale_summary="At least one item is contradicted.",
    )
    with pytest.raises(ContractInvariantError):
        validate_proposed_decision_draft(
            decline, mixed, policy_bundle(), order_snapshot(), ["LI-001", "LI-002"]
        )

    all_contradicted = DeclineEvidenceAssessment(
        evidence_status=EvidenceStatus.SUFFICIENT_FOR_DECLINE,
        claim_registry_version="claim-registry:1.0",
        claim_findings=_multi_item_findings(second_item_supported=False),
    )
    validate_proposed_decision_draft(
        decline,
        all_contradicted,
        policy_bundle(),
        order_snapshot(),
        ["LI-001", "LI-002"],
    )
    decline_handoff = proposed_handoff().model_copy(
        update={
            "proposed_decision": DeclineProposedDecision(
                action="DECLINE",
                refund_scope={"line_item_ids": []},
                amount="0",
                currency="TWD",
                reason_code="ITEM_DAMAGED",
                policy_refs=["POLICY-12:v3#4.2"],
                evidence_refs=["EV-002"],
            )
        }
    )
    decline_approval = ApprovedReviewResult(
        verdict="APPROVE",
        reviewer_claim_findings=all_contradicted.claim_findings,
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at="2026-09-01T10:45:00Z",
    )
    validate_review_result(
        decline_approval,
        decline_handoff,
        policy_bundle(),
        order_snapshot(),
        ["LI-001", "LI-002"],
    )


def test_policy_and_model_return_decision_sources_are_enforced() -> None:
    static_policy = policy_bundle(ReturnPolicy.REQUIRED)
    static_draft = FullRefundProposedDecisionDraft(
        action="FULL_REFUND",
        refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
        reason_code="ITEM_DAMAGED",
        return_decision=PolicyReturnDecisionDraft(
            source="POLICY", reason_code="RETURN_REQUIRED_FOR_INSPECTION"
        ),
        policy_refs=["POLICY-12:v3#4.2"],
        evidence_refs=["EV-002"],
        rationale_summary="Claims are supported and Policy requires return.",
    )
    validate_proposed_decision_draft(
        static_draft,
        supported_assessment(),
        static_policy,
        order_snapshot(),
        ["LI-002"],
    )
    with pytest.raises(ContractInvariantError):
        validate_proposed_decision_draft(
            proposed_decision_draft(),
            supported_assessment(),
            static_policy,
            order_snapshot(),
            ["LI-002"],
        )

    policy_decision = FullRefundProposedDecision(
        action="FULL_REFUND",
        refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
        amount="1200",
        currency="TWD",
        reason_code="ITEM_DAMAGED",
        return_decision=PolicyReturnDecision(
            source="POLICY",
            requirement=RequiredReturnRequirement(
                required=True, reason_code="RETURN_REQUIRED_FOR_INSPECTION"
            ),
        ),
        policy_refs=["POLICY-12:v3#4.2"],
        evidence_refs=["EV-002"],
    )
    handoff = proposed_handoff().model_copy(
        update={"proposed_decision": policy_decision}
    )
    validate_proposed_decision_handoff(handoff, static_policy, order_snapshot())


def test_handoff_amount_scope_and_currency_are_recomputed() -> None:
    handoff = proposed_handoff()
    for update in ({"amount": "1"}, {"currency": "USD"}):
        invalid = handoff.model_copy(
            update={
                "proposed_decision": handoff.proposed_decision.model_copy(update=update)
            }
        )
        with pytest.raises(ContractInvariantError):
            validate_proposed_decision_handoff(
                invalid, policy_bundle(), order_snapshot()
            )


def test_reviewer_approve_must_support_reviewed_handoff() -> None:
    approved = ApprovedReviewResult(
        verdict="APPROVE",
        reviewer_claim_findings=supported_assessment().claim_findings,
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at="2026-09-01T10:45:00Z",
    )
    validate_review_result(
        approved,
        proposed_handoff(),
        policy_bundle(),
        order_snapshot(),
        ["LI-002"],
    )

    unsupported_findings = [
        finding.model_copy(
            update={"status": ClaimStatus.UNSUPPORTED, "supporting_evidence_refs": []}
        )
        if finding.claim_id is ClaimId.DAMAGE_PRESENT_ON_ARRIVAL
        else finding
        for finding in supported_assessment().claim_findings
    ]
    bad_approve = approved.model_copy(
        update={"reviewer_claim_findings": unsupported_findings}
    )
    with pytest.raises(ContractInvariantError):
        validate_review_result(
            bad_approve,
            proposed_handoff(),
            policy_bundle(),
            order_snapshot(),
            ["LI-002"],
        )

    decline_handoff = proposed_handoff().model_copy(
        update={
            "proposed_decision": DeclineProposedDecision(
                action="DECLINE",
                refund_scope={"line_item_ids": []},
                amount="0",
                currency="TWD",
                reason_code="ITEM_DAMAGED",
                policy_refs=["POLICY-12:v3#4.2"],
                evidence_refs=["EV-002"],
            )
        }
    )
    with pytest.raises(ContractInvariantError):
        validate_review_result(
            approved,
            decline_handoff,
            policy_bundle(),
            order_snapshot(),
            ["LI-002"],
        )


def test_revision_references_and_evidence_resolution_are_validated() -> None:
    review = RevisedReviewResult(
        verdict="REVISE",
        reviewer_claim_findings=supported_assessment().claim_findings,
        revision_reasons=[
            RevisionReason(
                code="EVIDENCE_INSUFFICIENT",
                message="Evidence must be clarified.",
                policy_refs=["POLICY-12:v3#4.2"],
                evidence_refs=["EV-002"],
                subject="LI-002",
                required_change="Provide a clear package image.",
            )
        ],
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at="2026-09-01T10:45:00Z",
    )
    validate_review_result(
        review,
        proposed_handoff(),
        policy_bundle(),
        order_snapshot(),
        ["LI-002"],
    )
    unknown = review.model_copy(
        update={
            "revision_reasons": [
                review.revision_reasons[0].model_copy(
                    update={"evidence_refs": ["EV-UNKNOWN"]}
                )
            ]
        }
    )
    with pytest.raises(ContractInvariantError):
        validate_review_result(
            unknown,
            proposed_handoff(),
            policy_bundle(),
            order_snapshot(),
            ["LI-002"],
        )

    validate_resolved_evidence_item(
        evidence_item(), evidence_item().artifact_ref, evidence_request()
    )
    with pytest.raises(ContractInvariantError):
        validate_resolved_evidence_item(
            evidence_item().model_copy(update={"subject": "LI-001"}),
            evidence_item().artifact_ref,
            evidence_request(),
        )


def test_policy_dates_registry_context_and_memory_categories() -> None:
    validate_applicable_policy_bundle(
        case_context_load_result().case_context, policy_bundle()
    )
    expired_clause = type(policy_bundle().clauses[0]).model_validate(
        {
            **policy_bundle().clauses[0].model_dump(mode="json"),
            "effective_to": "2026-08-31T23:59:59Z",
        }
    )
    expired_bundle = PolicyBundle.model_validate(
        {**policy_bundle().model_dump(mode="json"), "clauses": [expired_clause]}
    )
    with pytest.raises(ContractInvariantError):
        validate_applicable_policy_bundle(
            case_context_load_result().case_context, expired_bundle
        )

    broken_registry = dict(CLAIM_REGISTRY_V1)
    damaged = broken_registry[ClaimId.ITEM_PHYSICALLY_DAMAGED]
    broken_registry[ClaimId.ITEM_PHYSICALLY_DAMAGED] = damaged.model_copy(
        update={"distinguish_from": (ClaimId.ITEM_FUNCTIONALLY_IMPAIRED,)}
    )
    with pytest.raises(ValueError):
        validate_claim_registry(broken_registry)

    validate_case_context_load_result("CASE-001", case_context_load_result())
    with pytest.raises(ContractInvariantError):
        validate_case_context_load_result("CASE-OTHER", case_context_load_result())
    assert derive_memory_categories(order_snapshot(), ["LI-002"]) == [
        "CAT-AUDIO-SPEAKERS"
    ]


@pytest.mark.parametrize("private", [
    "private@example.com", "0912-345-678", "4111 1111 1111 1111",
    "收件人：王小明", "地址：台北市測試路123號",
    "https://private.test/path?secret=yes", "artifact://bucket/private",
    "sk-secret-abcdef", "Bearer abc.def-token",
])
def test_learning_dialogue_redacts_sensitive_spans(private):
    from return_agent_contracts.validation import redact_learning_dialogue
    text, redacted = redact_learning_dialogue(f"補拍的照片。 {private}\n請確認損壞範圍")
    assert redacted and private not in text
    assert "補拍的照片" in text and "請確認損壞範圍" in text


def test_learning_dialogue_rejects_oversize_without_truncation():
    from return_agent_contracts.validation import redact_learning_dialogue
    assert redact_learning_dialogue("a" * 2000) == ("a" * 2000, False)
    with pytest.raises(OverflowError):
        redact_learning_dialogue("a" * 2001)
