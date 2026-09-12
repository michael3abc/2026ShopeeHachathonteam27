from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest
from pydantic import TypeAdapter, ValidationError

from return_agent_contracts.domain import (
    ApprovalEvidenceAssessment, ClaimFinding, CorrectedFullRefundDecision,
    DecisionRevisionEvent, DeclineProposedDecision, EvidenceAssessment, EvidenceRequest,
    FullRefundProposedDecisionDraft, HumanReviewDossier, HumanReviewReturnDecision,
    InsufficientEvidenceAssessment, NonEmptyRefundScope, OrderSnapshot,
    PolicyReturnDecisionDraft, ProposedDecisionHandoff, RequiredReturnRequirement,
    ReviewGateResult, ReviewResult, ReviewerGateConfig, RevisedReviewResult,
    RevisionReason, WaivedReturnRequirement, refund_amount,
)
from return_agent_contracts.gates import evaluate_gate, gate_after_review, gate_fingerprint
from return_agent_contracts.primitives import Amount, UTCDateTime
from return_agent_contracts.registry import REGISTRY, REGISTRY_VERSION, validate_registry
from return_agent_contracts.validation import (
    evidence_status, expected_pairs, validate_assessment, validate_dossier, validate_draft,
    validate_evidence_request, validate_findings, validate_handoff, validate_human_decision,
    validate_policy, validate_resolved_evidence, validate_review,
)


def revised(s):
    return RevisedReviewResult(verdict="REVISE", reviewer_prompt_version="reviewer:1", reviewed_at=s["now"], reviewer_claim_findings=s["findings"], revision_reasons=[RevisionReason(code="RETURN_REQUIREMENT_INCONSISTENT", subject="LI-002", message="應重新評估實體退回的必要性", required_change="依退回成本修正退回要求", policy_refs=["clause-test"])])


def dossier(s, *, budget=False):
    if budget:
        proposals = [s["handoff"].model_copy(deep=True, update={"handoff_id": f"proposal-{i}", "revision_round": i}) for i in range(4)]
        reviews = [revised(s) for _ in range(4)]
        events = [DecisionRevisionEvent(event_id=f"revision-{i}", case_ref=s["context"].case_ref, handoff_before_ref=proposals[i].handoff_id, review_result=reviews[i], revision_round=i+1, created_at=s["now"]) for i in range(3)]
        gate, routing = None, "REVISION_BUDGET_EXCEEDED"
    else:
        h = s["handoff"].model_copy(deep=True)
        h.proposed_decision.refund_scope = NonEmptyRefundScope(line_item_ids=["LI-001"])
        h.proposed_decision.amount = Decimal("6200")
        proposals, reviews, events = [h], [s["review"]], []
        gate = evaluate_gate("FULL_REFUND", Decimal("6200"), "TWD", ReviewerGateConfig())
        routing = "HIGH_VALUE_ITEM"
    return HumanReviewDossier(claim_registry_version=REGISTRY_VERSION, claimed_line_item_ids=s["claimed"], order_snapshot=s["order"], policy_bundle=s["policy"], proposal_history=proposals, review_history=reviews, revision_events=events, review_gate=gate, routing_reason=routing)


@pytest.mark.parametrize("value", [1.2, 1200, True, "-1", "01", "1e3", "NaN", Decimal("NaN"), Decimal("Infinity"), Decimal("-0")])
def test_money_rejects_ambiguous_or_lossy_input(value):
    with pytest.raises((ValueError, ValidationError)):
        TypeAdapter(Amount).validate_python(value)


def test_money_has_exact_string_roundtrip_and_sum(scenario):
    value = "123456789012345678901234567890.0000000000000001"
    adapter = TypeAdapter(Amount)
    assert adapter.dump_json(adapter.validate_python(value)) == f'"{value}"'.encode()
    with localcontext() as context:
        context.prec = 2
        assert refund_amount(scenario["order"], ["LI-001", "LI-002"]) == Decimal("7400")


@pytest.mark.parametrize("value", ["2026-09-10T08:00:00+08:00", "2026-09-10T00:00:00", datetime(2026, 9, 10), datetime(2026, 9, 10, tzinfo=timezone(timedelta(hours=8)))])
def test_utc_rejects_non_utc_input(value):
    with pytest.raises(ValueError):
        TypeAdapter(UTCDateTime).validate_python(value)


def test_extra_fields_and_duplicate_order_items_are_rejected(scenario):
    data = scenario["order"].model_dump(mode="json")
    with pytest.raises(ValidationError):
        OrderSnapshot.model_validate({**data, "trusted": True})
    data["line_items"].append(deepcopy(data["line_items"][0]))
    with pytest.raises(ValidationError):
        OrderSnapshot.model_validate(data)


def test_registry_is_complete_and_symmetric():
    validate_registry(REGISTRY)
    assert len(REGISTRY) == 10
    broken = {k: v.model_copy(deep=True) for k, v in REGISTRY.items()}
    broken["ITEM_PHYSICALLY_DAMAGED"].distinguish_from = []
    with pytest.raises(ValueError):
        validate_registry(broken)


def test_c01_valid_scope_amount_and_review(scenario):
    s = scenario
    validate_handoff(s["handoff"], s["context"], s["order"], s["policy"], s["claimed"])
    validate_review(s["review"], s["handoff"], s["order"], s["policy"], s["claimed"])
    assert s["handoff"].proposed_decision.amount == Decimal("1200")
    assert len(expected_pairs(s["policy"], s["order"], s["claimed"])) == 3


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra"])
def test_c02_findings_require_exact_pairs(scenario, mutation):
    s = scenario
    findings = deepcopy(s["findings"])
    if mutation == "missing": findings.pop()
    elif mutation == "duplicate": findings.append(findings[0])
    else: findings.append(ClaimFinding(claim_id="ITEM_UNUSED", subject="LI-002", status="UNSUPPORTED", explanation="待補證據"))
    with pytest.raises(ValueError):
        validate_findings(findings, s["policy"], s["order"], s["claimed"], s["evidence"])


def test_c02_unsupported_is_insufficient_not_decline(scenario):
    s = scenario
    for finding in s["findings"]: finding.status = "UNSUPPORTED"
    assert evidence_status(s["findings"], s["order"], s["claimed"]) == "INSUFFICIENT"


def test_c03_decline_requires_every_item_contradicted(scenario):
    s = scenario
    s["findings"][1].status = "CONTRADICTED"
    assert evidence_status(s["findings"], s["order"], s["claimed"]) == "SUFFICIENT_FOR_APPROVAL"
    s["findings"][2].status = "CONTRADICTED"
    assert evidence_status(s["findings"], s["order"], s["claimed"]) == "SUFFICIENT_FOR_DECLINE"
    old = s["handoff"].proposed_decision
    s["handoff"].proposed_decision = DeclineProposedDecision(action="DECLINE", amount="0", currency="TWD", reason_code=old.reason_code, policy_refs=old.policy_refs, evidence_refs=old.evidence_refs, refund_scope={"line_item_ids": []})
    s["review"].reviewer_claim_findings = s["findings"]
    validate_review(s["review"], s["handoff"], s["order"], s["policy"], s["claimed"])
    with pytest.raises(ValidationError):
        DeclineProposedDecision.model_validate({**s["handoff"].proposed_decision.model_dump(mode="json"), "return_decision": old.return_decision.model_dump(mode="json")})


def test_c04_request_is_exact_unresolved_user_union(scenario):
    s = scenario
    s["findings"][0].status = "UNSUPPORTED"
    s["findings"][1].status = "UNSUPPORTED"
    request = EvidenceRequest(request_id="request-test", missing_claims=[{"claim_id": "ITEM_PHYSICALLY_DAMAGED", "subject": "LI-001"}], accepted_evidence_types=["IMAGE", "VIDEO"], policy_refs=["clause-test"], user_message="請提供該品項的損壞照片")
    validate_evidence_request(request, s["findings"], s["policy"])
    for patch in [{"missing_claims": [{"claim_id": "DELIVERY_CONFIRMED", "subject": "order-test"}]}, {"accepted_evidence_types": ["IMAGE"]}, {"policy_refs": ["unknown"]}]:
        with pytest.raises(ValueError):
            validate_evidence_request(EvidenceRequest.model_validate({**request.model_dump(), **patch}), s["findings"], s["policy"])


@pytest.mark.parametrize("ref,subjects,source", [("unknown", {"LI-001"}, None), ("artifact-LI-001", {"LI-002"}, None), ("artifact-LI-001", {"LI-001"}, "SYSTEM")])
def test_c04_evidence_resolution_identity_is_checked(scenario, ref, subjects, source):
    with pytest.raises(ValueError):
        validate_resolved_evidence(ref, scenario["evidence"][0], subjects, source=source)


@pytest.mark.parametrize("field,value", [("amount", Decimal("1201")), ("currency", "SGD"), ("refund_scope", NonEmptyRefundScope(line_item_ids=["other"]))])
def test_c05_tampered_money_scope_and_currency_fail(scenario, field, value):
    s = scenario
    setattr(s["handoff"].proposed_decision, field, value)
    with pytest.raises(ValueError):
        validate_handoff(s["handoff"], s["context"], s["order"], s["policy"], s["claimed"])


def test_c05_static_policy_cannot_be_overridden(scenario):
    s = scenario
    s["policy"].clauses[0].return_policy = "REQUIRED"
    with pytest.raises(ValueError):
        validate_handoff(s["handoff"], s["context"], s["order"], s["policy"], s["claimed"])


@pytest.mark.parametrize("currency,amount,expected", [("TWD", "4999.99", "PASS"), ("TWD", "5000", "PASS"), ("TWD", "5000.01", "HUMAN_REQUIRED"), ("SGD", "199.99", "PASS"), ("SGD", "200", "PASS"), ("SGD", "200.01", "HUMAN_REQUIRED"), ("USD", "1", "HUMAN_REQUIRED")])
def test_c10_c11_decimal_thresholds(currency, amount, expected):
    gate = evaluate_gate("FULL_REFUND", Decimal(amount), currency, ReviewerGateConfig())
    assert gate.status == expected
    if currency == "USD": assert gate.reason == "CURRENCY_THRESHOLD_UNCONFIGURED"


def test_c11_revise_has_no_gate_and_decline_is_not_applicable(scenario):
    assert gate_after_review(revised(scenario), "FULL_REFUND", Decimal("6200"), "TWD", ReviewerGateConfig()) is None
    assert evaluate_gate("DECLINE", Decimal("0"), "TWD", ReviewerGateConfig()).status == "NOT_APPLICABLE"


def test_gate_hash_normalizes_decimal_text_without_precision_loss():
    a = ReviewerGateConfig(thresholds={"TWD": "5000.000", "SGD": "200.0"})
    b = ReviewerGateConfig(thresholds={"SGD": "200", "TWD": "5000"})
    assert gate_fingerprint(a) == gate_fingerprint(b)
    assert gate_fingerprint(a) != gate_fingerprint(ReviewerGateConfig(version="reviewer-gates:2"))


@pytest.mark.parametrize("budget", [False, True])
def test_c13_both_human_entries_validate(scenario, budget):
    d = dossier(scenario, budget=budget)
    validate_dossier(d, d.proposal_history[-1], d.review_history[-1], scenario["context"], ReviewerGateConfig())


@pytest.mark.parametrize("mutation", ["case", "policy", "snapshot", "registry", "round", "missing_event", "reversed_events", "event_ref", "event_review", "event_case", "duplicate_id"])
def test_c06_entire_revision_history_is_bound(scenario, mutation):
    d = dossier(scenario, budget=True)
    if mutation in ("case", "policy", "snapshot", "registry", "round"):
        field = {"case": "case_ref", "policy": "policy_bundle_version", "snapshot": "order_snapshot_ref", "registry": "claim_registry_version", "round": "revision_round"}[mutation]
        setattr(d.proposal_history[0], field, 1 if mutation == "round" else "wrong")
    elif mutation == "missing_event": d.revision_events.pop()
    elif mutation == "reversed_events": d.revision_events.reverse()
    elif mutation == "event_ref": d.revision_events[0].handoff_before_ref = "wrong"
    elif mutation == "event_review": d.revision_events[0].review_result = scenario["review"]
    elif mutation == "event_case": d.revision_events[0].case_ref = "wrong"
    else: d.proposal_history[0].handoff_id = d.proposal_history[1].handoff_id
    with pytest.raises(ValueError):
        validate_dossier(d, d.proposal_history[-1], d.review_history[-1], scenario["context"], ReviewerGateConfig())


def test_c12_gate_recomputed_against_current_configuration(scenario):
    d = dossier(scenario)
    with pytest.raises(ValueError):
        validate_dossier(d, d.proposal_history[-1], d.review_history[-1], scenario["context"], ReviewerGateConfig(version="new-version"))
    d.review_gate.config_hash = "0" * 64
    with pytest.raises(ValueError):
        validate_dossier(d, d.proposal_history[-1], d.review_history[-1], scenario["context"], ReviewerGateConfig())


def test_c13_human_can_rejudge_original_scope_but_not_expand_it(scenario):
    d = dossier(scenario)
    decision = CorrectedFullRefundDecision(action="FULL_REFUND", refund_scope={"line_item_ids": ["LI-002"]}, return_decision=HumanReviewReturnDecision(source="HUMAN_REVIEW", requirement=WaivedReturnRequirement(required=False, reason_code="RETURN_UNECONOMICAL")))
    validate_human_decision(decision, d, scenario["order"], scenario["policy"])
    decision.refund_scope = NonEmptyRefundScope(line_item_ids=["unknown"])
    with pytest.raises(ValueError):
        validate_human_decision(decision, d, scenario["order"], scenario["policy"])


def test_c13_human_cannot_exceed_latest_order_maximum(scenario):
    d = dossier(scenario)
    current = scenario["order"].model_copy(deep=True)
    current.already_refunded_amount = Decimal("9500")
    decision = CorrectedFullRefundDecision(action="FULL_REFUND", refund_scope={"line_item_ids": ["LI-002"]}, return_decision={"source": "HUMAN_REVIEW", "requirement": {"required": True, "reason_code": "RETURN_REQUIRED_FOR_INSPECTION"}})
    with pytest.raises(ValueError):
        validate_human_decision(decision, d, current, scenario["policy"])


def test_reviewer_approve_does_not_borrow_resolver_findings(scenario):
    s = scenario
    s["review"].reviewer_claim_findings[-1].status = "UNSUPPORTED"
    with pytest.raises(ValueError):
        validate_review(s["review"], s["handoff"], s["order"], s["policy"], s["claimed"])


def test_revise_needs_structured_nonempty_objection(scenario):
    review = revised(scenario).model_dump(mode="json")
    review["revision_reasons"] = []
    with pytest.raises(ValidationError):
        TypeAdapter(ReviewResult).validate_python(review)


def test_policy_effective_interval_and_scope(scenario):
    s = scenario
    s["context"].case_opened_at -= timedelta(days=1)
    with pytest.raises(ValueError):
        validate_policy(s["context"], s["order"], s["policy"], "ITEM_DAMAGED", s["claimed"])


def test_assessment_cannot_claim_approval_from_unsupported_findings(scenario):
    s = scenario
    for finding in s["findings"][1:]: finding.status = "UNSUPPORTED"
    assessment = ApprovalEvidenceAssessment(evidence_status="SUFFICIENT_FOR_APPROVAL", claim_registry_version=REGISTRY_VERSION, claim_findings=s["findings"])
    with pytest.raises(ValueError):
        validate_assessment(assessment, s["policy"], s["order"], s["claimed"], s["evidence"])


def test_draft_uses_policy_authority_and_never_model_amount(scenario):
    s = scenario
    s["policy"].clauses[0].return_policy = "REQUIRED"
    assessment = ApprovalEvidenceAssessment(evidence_status="SUFFICIENT_FOR_APPROVAL", claim_registry_version=REGISTRY_VERSION, claim_findings=s["findings"])
    draft = FullRefundProposedDecisionDraft(action="FULL_REFUND", refund_scope={"line_item_ids": ["LI-002"]}, reason_code="ITEM_DAMAGED", rationale_summary="按適用條款處理", policy_refs=["clause-test"], evidence_refs=["evidence-LI-002"], return_decision=PolicyReturnDecisionDraft(source="POLICY", reason_code="RETURN_REQUIRED_FOR_INSPECTION"))
    validate_draft(draft, assessment, s["policy"], s["order"], s["claimed"], s["evidence"])
    with pytest.raises(ValueError):
        FullRefundProposedDecisionDraft.model_validate({**draft.model_dump(), "amount": "1"})
    draft.return_decision = PolicyReturnDecisionDraft(source="POLICY", reason_code="RETURN_UNECONOMICAL")
    with pytest.raises(ValueError):
        validate_draft(draft, assessment, s["policy"], s["order"], s["claimed"], s["evidence"])


def test_draft_scope_must_be_supported_by_assessment(scenario):
    s = scenario
    s["findings"][2].status = "UNSUPPORTED"
    assessment = ApprovalEvidenceAssessment(evidence_status="SUFFICIENT_FOR_APPROVAL", claim_registry_version=REGISTRY_VERSION, claim_findings=s["findings"])
    draft = FullRefundProposedDecisionDraft(action="FULL_REFUND", refund_scope={"line_item_ids": ["LI-002"]}, reason_code="ITEM_DAMAGED", rationale_summary="錯誤退款範圍", policy_refs=["clause-test"], return_decision=s["handoff"].proposed_decision.return_decision)
    with pytest.raises(ValueError):
        validate_draft(draft, assessment, s["policy"], s["order"], s["claimed"], s["evidence"])


def test_evidence_request_cannot_omit_an_unresolved_item(scenario):
    s = scenario
    for finding in s["findings"][1:]: finding.status = "UNSUPPORTED"
    request = EvidenceRequest(request_id="request-test", missing_claims=[{"claim_id": "ITEM_PHYSICALLY_DAMAGED", "subject": "LI-001"}], accepted_evidence_types=["IMAGE", "VIDEO"], policy_refs=["clause-test"], user_message="請補證據")
    with pytest.raises(ValueError): validate_evidence_request(request, s["findings"], s["policy"])
