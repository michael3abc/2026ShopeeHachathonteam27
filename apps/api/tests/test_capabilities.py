from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from return_agent_contracts.domain import ApprovedReviewResult, CaseContext, ClaimFinding, EvidenceItem, FullRefundProposedDecision, HumanReviewDossier, ModelJudgmentReturnDecision, NonEmptyRefundScope, OrderLineItem, OrderSnapshot, PolicyClause, ApplicableConditions, ProposedDecisionHandoff, RequiredReturnRequirement
from return_agent_contracts.gates import evaluate_gate
from return_agent_contracts.providers import ContractConflict, LoadCaseContextParams, ResolveEvidenceParams, RetrievePolicyParams, SubmitHumanReviewParams, VerifyHandoffParams
from return_agent_contracts.public import CreateCaseRequest
from return_agent_contracts.registry import REGISTRY_VERSION

from return_agent.capabilities import CapabilityNotFound, CapabilityStore
from return_agent.db import EvidenceRow, HumanReviewRow, PolicyClauseRow, PolicyRetrievalRow, TrustedOrderRow, VerificationRow
from return_agent.main import create_app
from return_agent.settings import Settings


@pytest.fixture
def trusted(store):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    order = OrderSnapshot(order_ref="synthetic-order", order_snapshot_ref="synthetic-snapshot", snapshot_version=1, currency="TWD", captured_at=now, delivered_at=now, refundable_amount_max="9000", already_refunded_amount="0", line_items=[OrderLineItem(line_item_id="item-one", sku_ref="sku-speaker", category_ref="audio", title="測試音箱", quantity=1, refundable_amount="6200"), OrderLineItem(line_item_id="item-two", sku_ref="sku-cable", category_ref="audio", title="測試線材", quantity=1, refundable_amount="1200")])
    clause = PolicyClause(clause_id="damage-policy", policy_version="demo:1", text="送達後若品項外觀損壞可退款；退回需求依個案判斷。", required_claim_ids=["DELIVERY_CONFIRMED", "ITEM_PHYSICALLY_DAMAGED"], allowed_actions=["FULL_REFUND", "DECLINE"], return_policy="MODEL_JUDGMENT", applicable_conditions=ApplicableConditions(markets=["TW"], reason_codes=["ITEM_DAMAGED"]), effective_from=now)
    evidence = [EvidenceItem(evidence_id=f"evidence-{item}", artifact_ref=f"artifact-{item}", type="IMAGE", source="USER", subject=item, extracted_summary="合成測試描述：物件外殼表面有裂痕。", collected_at=now) for item in ("item-one", "item-two")]
    with store.sessions.begin() as session:
        session.add(TrustedOrderRow(order_ref=order.order_ref, market="TW", snapshot=order.model_dump(mode="json")))
        session.add(PolicyClauseRow(clause_id=clause.clause_id, policy_version=clause.policy_version, payload=clause.model_dump(mode="json")))
        for item in evidence:
            session.add(EvidenceRow(artifact_ref=item.artifact_ref, payload=item.model_dump(mode="json")))
    ref = store.create(CreateCaseRequest(order_ref=order.order_ref, user_ref="synthetic-user", initial_message="音箱與線材外殼有裂痕", attached_artifact_refs=[item.artifact_ref for item in evidence]))
    capabilities = CapabilityStore(store)
    loaded = capabilities.load_case_context(LoadCaseContextParams(case_ref=ref))
    params = RetrievePolicyParams(case_context=loaded.case_context, order_snapshot=loaded.order_snapshot, reason_code="ITEM_DAMAGED", claimed_line_item_ids=["item-one", "item-two"])
    policy = capabilities.retrieve_policy(params)
    handoff = ProposedDecisionHandoff(handoff_id="proposal-one", handoff_version="1.0", case_ref=ref, agent_prompt_version="resolver:1", claim_registry_version=REGISTRY_VERSION, order_snapshot_ref=order.order_snapshot_ref, policy_bundle_version=policy.policy_bundle_version, policy_refs=[clause.clause_id], evidence_bundle=evidence, rationale_summary="依可見損壞評估退款", revision_round=0, proposed_decision=FullRefundProposedDecision(action="FULL_REFUND", amount="6200", currency="TWD", reason_code="ITEM_DAMAGED", policy_refs=[clause.clause_id], evidence_refs=[evidence[0].evidence_id], refund_scope=NonEmptyRefundScope(line_item_ids=["item-one"]), return_decision=ModelJudgmentReturnDecision(source="MODEL_JUDGMENT", requirement=RequiredReturnRequirement(required=True, reason_code="RETURN_REQUIRED_FOR_INSPECTION"))))
    review = ApprovedReviewResult(verdict="APPROVE", reviewed_at=store.clock(), reviewer_prompt_version="reviewer:1", reviewer_claim_findings=[ClaimFinding(claim_id="DELIVERY_CONFIRMED", subject=order.order_ref, status="SUPPORTED", explanation="訂單含送達日期"), *[ClaimFinding(claim_id="ITEM_PHYSICALLY_DAMAGED", subject=item.subject, status="SUPPORTED", explanation="表面有裂痕", supporting_evidence_refs=[item.evidence_id]) for item in evidence]])
    dossier = HumanReviewDossier(claim_registry_version=REGISTRY_VERSION, claimed_line_item_ids=params.claimed_line_item_ids, order_snapshot=order, policy_bundle=policy, proposal_history=[handoff], review_history=[review], review_gate=evaluate_gate("FULL_REFUND", Decimal("6200"), "TWD", capabilities.gates), routing_reason="HIGH_VALUE_ITEM")
    return capabilities, params, handoff, review, dossier


def test_canonical_order_binding_and_neutral_evidence(trusted):
    caps, params, handoff, _, _ = trusted
    assert params.case_context.case_ref == handoff.case_ref
    actual = caps.resolve(ResolveEvidenceParams(artifact_ref="artifact-item-one"))
    assert "claim" not in actual.model_dump() and "eligible" not in actual.model_dump()
    with pytest.raises(CapabilityNotFound):
        caps.resolve(ResolveEvidenceParams(artifact_ref="https://example.invalid/arbitrary"))
    forged = params.model_copy(update={"case_context": params.case_context.model_copy(update={"market": "SG"})})
    with pytest.raises(ContractConflict):
        caps.retrieve_policy(forged)


def test_verification_replay_concurrent_conflict(trusted):
    caps, _, handoff, _, _ = trusted
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: caps.verify(VerifyHandoffParams(handoff=handoff)), range(2)))
    assert [r.status for r in results] == ["PASS", "PASS"]
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(VerificationRow)) == 1
    changed = handoff.model_copy(update={"rationale_summary": "changed"})
    with pytest.raises(ContractConflict):
        caps.verify(VerifyHandoffParams(handoff=changed))


@pytest.mark.parametrize("tamper", ["amount", "evidence", "missing_policy", "changed_snapshot"])
def test_verification_fails_closed(trusted, tamper):
    caps, _, handoff, _, _ = trusted
    if tamper == "amount":
        handoff = handoff.model_copy(update={"proposed_decision": handoff.proposed_decision.model_copy(update={"amount": Decimal("1")})})
    elif tamper == "evidence":
        item = handoff.evidence_bundle[0].model_copy(update={"extracted_summary": "forged observation"})
        handoff = handoff.model_copy(update={"evidence_bundle": [item, handoff.evidence_bundle[1]]})
    elif tamper == "missing_policy":
        with caps.sessions.begin() as session:
            session.delete(session.get(PolicyRetrievalRow, handoff.policy_bundle_version))
    else:
        with caps.sessions.begin() as session:
            row = session.get(TrustedOrderRow, "synthetic-order")
            row.snapshot = {**row.snapshot, "snapshot_version": 2}
    assert caps.verify(VerifyHandoffParams(handoff=handoff)).status == "FAIL"


def test_policy_exact_version_survives_catalog_change(trusted):
    caps, _, handoff, _, _ = trusted
    with caps.sessions.begin() as session:
        session.delete(session.get(PolicyClauseRow, ("damage-policy", "demo:1")))
    assert caps.verify(VerifyHandoffParams(handoff=handoff)).status == "PASS"


def test_human_review_requires_verified_immutable_dossier(trusted):
    caps, _, handoff, review, dossier = trusted
    request = SubmitHumanReviewParams(handoff=handoff, review=review, dossier=dossier)
    with pytest.raises(ValueError):
        caps.submit_for_review(request)
    assert caps.verify(VerifyHandoffParams(handoff=handoff)).status == "PASS"
    ref = caps.submit_for_review(request)
    assert caps.submit_for_review(request) == ref
    with pytest.raises(ValueError):
        caps.submit_for_review(SubmitHumanReviewParams(handoff=handoff, review=review))
    changed = dossier.model_copy(update={"claimed_line_item_ids": ["item-one"]})
    with pytest.raises(ContractConflict):
        caps.submit_for_review(request.model_copy(update={"dossier": changed}))
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(HumanReviewRow)) == 1


def test_internal_http_authorization_and_typed_wire(trusted):
    caps, params, _, _, _ = trusted
    request = {"method": "CaseContextProvider.load_case_context", "params": {"case_ref": params.case_context.case_ref}}
    client = TestClient(create_app(Settings(internal_service_token=SecretStr("synthetic-token")), store=caps.cases))
    assert client.post("/internal/v1/case-context", json=request).status_code == 401
    assert client.post("/internal/v1/case-context", json=request, headers={"Authorization": "Bearer wrong"}).status_code == 401
    headers = {"Authorization": "Bearer synthetic-token"}
    result = client.post("/internal/v1/case-context", json=request, headers=headers)
    assert result.status_code == 200 and result.json()["result"]["case_context"]["case_ref"] == params.case_context.case_ref
    assert client.post("/internal/v1/case-context", json={**request, "method": "wrong"}, headers=headers).status_code == 422
    unconfigured = TestClient(create_app(Settings(), store=caps.cases))
    assert unconfigured.post("/internal/v1/case-context", json=request, headers=headers).status_code == 503
