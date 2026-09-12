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
