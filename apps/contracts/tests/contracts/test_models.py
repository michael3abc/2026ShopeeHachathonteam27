from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.enums import ClaimId, MemoryStatus
from return_agent_contracts.models import (
    AccumulatedEscalationContext,
    AgentFullRefundFinalDecision,
    ApprovedHumanReviewResult,
    ApprovedMemory,
    ApprovedReviewResult,
    ClarificationRequest,
    CorrectedDeclineDecision,
    CorrectedFullRefundDecision,
    DecisionRevisionEvent,
    DeclineFinalDecision,
    EditedHumanReviewResult,
    EvidenceAssessment,
    FailedVerificationResult,
    HumanReviewResult,
    HumanReviewReturnDecision,
    IntakeResult,
    ManualEscalationHandoff,
    MemoryCandidate,
    MemoryCandidateOutput,
    MemoryDistillationOutput,
    MemoryScope,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    RequiredReturnRequirement,
    ResolutionHandoff,
    ResolverConflictOutput,
    ResolverEvidenceRequestOutput,
    ResolverOutput,
    ReviewerApprovedResolutionHandoff,
    RevisedReviewResult,
    RevisionConflictReport,
    RevisionReason,
    UserTurn,
    VerificationIssue,
    WaivedReturnRequirement,
)

from .fixtures import (
    TIME,
    approved_review,
    case_context,
    evidence_item,
    evidence_request,
    memory_candidate,
    order_snapshot,
    policy_bundle,
    proposed_decision_draft,
    proposed_handoff,
    supported_assessment,
)


def _validate(contract: object, payload: object) -> object:
    return TypeAdapter(contract).validate_python(payload)


def test_money_is_decimal_in_python_and_decimal_string_on_wire() -> None:
    snapshot = order_snapshot()
    assert snapshot.line_items[1].refundable_amount == Decimal(1200)
    assert snapshot.model_dump(mode="json")["refundable_amount_max"] == "1900"

    payload = snapshot.model_dump(mode="json")
    payload["line_items"][0]["refundable_amount"] = 700
    with pytest.raises(ValidationError):
        type(snapshot).model_validate(payload)
    for invalid in ("-1", "1e3", "01", 12.5):
        payload = snapshot.model_dump(mode="json")
        payload["refundable_amount_max"] = invalid
        with pytest.raises(ValidationError):
            type(snapshot).model_validate(payload)


def test_unknown_fields_currency_and_non_utc_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _validate(
            type(proposed_decision_draft()),
            {**proposed_decision_draft().model_dump(), "amount": "1200"},
        )
    for currency in ("twD", "TWD1", "TW"):
        payload = order_snapshot().model_dump(mode="json")
        payload["currency"] = currency
        with pytest.raises(ValidationError):
            type(order_snapshot()).model_validate(payload)
    payload = order_snapshot().model_dump(mode="json")
    payload["captured_at"] = "2026-09-01T18:00:00+08:00"
    with pytest.raises(ValidationError):
        type(order_snapshot()).model_validate(payload)


def test_contract_examples_round_trip_as_json() -> None:
    review = RevisedReviewResult(
        verdict="REVISE",
        reviewer_claim_findings=supported_assessment().claim_findings,
        revision_reasons=[
            RevisionReason(
                code="EVIDENCE_INSUFFICIENT",
                message="A clearer image is needed.",
                subject="LI-002",
                required_change="Provide a clearer image of the package.",
            )
        ],
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at=TIME,
    )
    candidate = memory_candidate()
    values = [
        UserTurn(
            turn_id="TURN-001",
            role="USER",
            text="The speaker arrived damaged.",
            attached_artifact_refs=["artifact://evidence/EV-002"],
            received_at=TIME,
        ),
        case_context(),
        order_snapshot(),
        policy_bundle(),
        evidence_item(),
        supported_assessment(),
        evidence_request(),
        IntakeResult(
            completeness="COMPLETE",
            order_ref="ORDER-001",
            reason_code="ITEM_DAMAGED",
            reason_summary="Damaged on arrival.",
            requested_action="REFUND",
            claimed_line_item_ids=["LI-002"],
        ),
        ClarificationRequest(
            request_id="CREQ-001",
            missing_fields=["order_ref"],
            clarification_question="Please provide the order reference.",
            clarification_round=1,
        ),
        proposed_decision_draft(),
        RevisionConflictReport(
            conflicting_reason_codes=["POLICY_MISMATCH", "SCOPE_UNSUPPORTED"],
            conflicting_review_refs=["REV-001", "REV-002"],
            explanation="The requested changes cannot both be applied.",
        ),
        proposed_handoff(),
        FailedVerificationResult(
            status="FAIL",
            issues=[
                VerificationIssue(
                    code="RETURN_WINDOW_EXCEEDED",
                    message="The return window is exceeded.",
                    field_path="proposed_decision.action",
                )
            ],
            verification_version="verification:1.0",
        ),
        review,
        DecisionRevisionEvent(
            event_id="REV-001",
            case_ref="CASE-001",
            handoff_before_ref="HANDOFF-001",
            review_result=review,
            revision_round=1,
            created_at=TIME,
        ),
        CorrectedDeclineDecision(action="DECLINE", refund_scope={"line_item_ids": []}),
        EditedHumanReviewResult(
            decision="EDIT",
            review_note="Evidence did not establish the claim.",
            corrected_decision=CorrectedDeclineDecision(
                action="DECLINE", refund_scope={"line_item_ids": []}
            ),
            correction_reason_code="CLAIM_NOT_ESTABLISHED",
            final_resolution_ref="RESOLUTION-001",
            reviewed_at=TIME,
        ),
        ReviewerApprovedResolutionHandoff(
            case_ref="CASE-001",
            handoff_id="HANDOFF-001",
            outcome_source="REVIEWER_APPROVE",
            final_decision=AgentFullRefundFinalDecision(
                action="FULL_REFUND",
                refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
                amount="1200",
                currency="TWD",
                return_decision=ModelJudgmentReturnDecision(
                    source="MODEL_JUDGMENT",
                    requirement=WaivedReturnRequirement(
                        required=False, reason_code="ITEM_UNSALVAGEABLE"
                    ),
                ),
                reason_code="ITEM_DAMAGED",
            ),
            review_result=approved_review(),
            execution_blocked=False,
            emitted_at=TIME,
        ),
        AccumulatedEscalationContext(
            clarification_round=0,
            evidence_round=1,
            verification_round=0,
            revision_round=1,
            review_history_refs=["REV-001"],
        ),
        ManualEscalationHandoff(
            case_ref="CASE-001",
            thread_id="THREAD-001",
            escalation_reason="REVISION_BUDGET_EXCEEDED",
            last_known_handoff_ref="HANDOFF-001",
            accumulated_context=AccumulatedEscalationContext(
                clarification_round=0,
                evidence_round=1,
                verification_round=0,
                revision_round=1,
                review_history_refs=["REV-001"],
            ),
            created_at=TIME,
        ),
        candidate,
        ApprovedMemory(
            memory_id=candidate.memory_id,
            retrieval_summary=candidate.retrieval_summary,
            status="APPROVED",
            recommended_behavior=candidate.recommended_behavior,
            trigger_conditions=candidate.trigger_conditions,
            policy_version=candidate.policy_version,
            claim_registry_version=candidate.claim_registry_version,
            scope=candidate.scope,
            confidence=candidate.confidence,
            approved_at=TIME,
        ),
    ]
    for value in values:
        type(value).model_validate(value.model_dump(mode="json"))


def test_evidence_and_resolver_discriminated_unions() -> None:
    assert (
        _validate(
            EvidenceAssessment, supported_assessment().model_dump(mode="json")
        ).evidence_status
        == "SUFFICIENT_FOR_APPROVAL"
    )
    assert (
        _validate(
            ResolverOutput,
            {
                "result_type": "DRAFT",
                "draft": proposed_decision_draft().model_dump(mode="json"),
            },
        ).result_type
        == "DRAFT"
    )
    assert (
        _validate(
            ResolverOutput,
            ResolverEvidenceRequestOutput(
                result_type="REQUEST_EVIDENCE", evidence_request=evidence_request()
            ).model_dump(mode="json"),
        ).result_type
        == "REQUEST_EVIDENCE"
    )
    assert (
        _validate(
            ResolverOutput,
            ResolverConflictOutput(
                result_type="CONFLICTING_REVISIONS",
                conflict=RevisionConflictReport(
                    conflicting_reason_codes=["POLICY_MISMATCH", "SCOPE_UNSUPPORTED"],
                    conflicting_review_refs=["REV-001", "REV-002"],
                    explanation="The requested changes conflict.",
                ),
            ).model_dump(mode="json"),
        ).result_type
        == "CONFLICTING_REVISIONS"
    )
    invalid = supported_assessment().model_dump(mode="json")
    invalid["evidence_status"] = "INSUFFICIENT"
    with pytest.raises(ValidationError):
        _validate(EvidenceAssessment, invalid)


def test_decision_return_reason_and_action_shapes_are_schema_visible() -> None:
    invalid_refund = proposed_handoff().proposed_decision.model_dump(mode="json")
    invalid_refund.pop("return_decision")
    with pytest.raises(ValidationError):
        _validate(type(proposed_handoff().proposed_decision), invalid_refund)

    invalid_reason = proposed_handoff().proposed_decision.model_dump(mode="json")
    invalid_reason["return_decision"]["requirement"] = {
        "required": True,
        "reason_code": "ITEM_UNSALVAGEABLE",
    }
    with pytest.raises(ValidationError):
        _validate(type(proposed_handoff().proposed_decision), invalid_reason)

    decline = DeclineFinalDecision(
        action="DECLINE",
        refund_scope={"line_item_ids": []},
        amount="0",
        currency="TWD",
        reason_code="ITEM_DAMAGED",
    )
    with pytest.raises(ValidationError):
        type(decline).model_validate(
            {**decline.model_dump(mode="json"), "return_decision": {}}
        )

    corrected = CorrectedFullRefundDecision(
        action="FULL_REFUND",
        refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
        return_decision=HumanReviewReturnDecision(
            source="HUMAN_REVIEW",
            requirement=RequiredReturnRequirement(
                required=True, reason_code="RETURN_REQUIRED_FOR_INSPECTION"
            ),
        ),
    )
    assert corrected.return_decision.source == "HUMAN_REVIEW"


def test_review_human_and_resolution_unions_reject_wrong_branch_fields() -> None:
    approve = ApprovedReviewResult(
        verdict="APPROVE",
        reviewer_claim_findings=supported_assessment().claim_findings,
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at=TIME,
    )
    with pytest.raises(ValidationError):
        _validate(
            type(approve),
            {**approve.model_dump(mode="json"), "revision_reasons": [{}]},
        )

    with pytest.raises(ValidationError):
        _validate(
            HumanReviewResult,
            {
                "decision": "EDIT",
                "review_note": "Needs correction.",
                "final_resolution_ref": "RES-001",
                "reviewed_at": TIME,
            },
        )
    approved_human = ApprovedHumanReviewResult(
        decision="APPROVE",
        review_note="Reviewed and approved.",
        final_resolution_ref="RES-001",
        reviewed_at=TIME,
    )
    assert approved_human.review_note == "Reviewed and approved."

    blocked = {
        "case_ref": "CASE-001",
        "handoff_id": "H-1",
        "outcome_source": "RISK_BLOCK",
        "final_decision": DeclineFinalDecision(
            action="DECLINE",
            refund_scope={"line_item_ids": []},
            amount="0",
            currency="TWD",
            reason_code="ITEM_DAMAGED",
        ).model_dump(mode="json"),
        "risk_reason_codes": ["HIGH_VALUE_ITEM"],
        "execution_blocked": True,
        "emitted_at": TIME,
    }
    with pytest.raises(ValidationError):
        _validate(ResolutionHandoff, blocked)


def test_memory_candidate_union_is_candidate_only() -> None:
    candidate = MemoryCandidate(
        memory_id="MEM-001",
        retrieval_summary="Damaged-item evidence is incomplete; request the required evidence together.",
        trigger_conditions=["Two evidence requirements are missing."],
        recommended_behavior="Ask for both in one request.",
        rationale="A correction established this is more efficient.",
        source_case_refs=["CASE-001"],
        source_revision_event_refs=["REV-001"],
        policy_version="POLICY-12:v3",
        claim_registry_version="claim-registry:1.0",
        scope=MemoryScope(market="TW", claim_ids=[ClaimId.DAMAGE_PRESENT_ON_ARRIVAL]),
        confidence=0.72,
        status=MemoryStatus.CANDIDATE,
    )
    assert (
        _validate(
            MemoryDistillationOutput,
            MemoryCandidateOutput(
                result_type="CREATE_CANDIDATE", candidate=candidate
            ).model_dump(mode="json"),
        ).result_type
        == "CREATE_CANDIDATE"
    )
    with pytest.raises(ValidationError):
        candidate.model_validate({**candidate.model_dump(), "status": "APPROVED"})


def test_reviewer_model_cannot_supply_budget_routing_or_a_third_verdict() -> None:
    payload = approved_review().model_dump(mode="json")
    for change in (
        {"verdict": "ESCALATE"},
        {"retry_limit": True},
        {"routing_reason": "REVISION_BUDGET_EXCEEDED"},
    ):
        with pytest.raises(ValidationError):
            ApprovedReviewResult.model_validate({**payload, **change})
