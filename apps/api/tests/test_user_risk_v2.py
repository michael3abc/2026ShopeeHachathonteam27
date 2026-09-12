from datetime import timedelta
from dataclasses import replace
import pytest
from sqlalchemy import select
from pydantic import TypeAdapter
from return_agent.capabilities.user_risk import SqlAlchemyUserRiskProvider, append_risk_event
from return_agent.capabilities.human_review import SqlAlchemyHumanReviewProvider
from return_agent.db.models import UserRiskProfileRecord, UserRiskEventRecord, HumanReviewRecord
from return_agent_contracts.models import HumanReviewDossier, HumanApproveResolutionHandoff, HumanEditResolutionHandoff, ExecuteRefundRequest
from return_agent_contracts.ui import ReviewDecision
from .test_policy_v2_fulfillment import setup_case, authorize, release, NOW, CaseProvider, FulfillmentWorker


@pytest.mark.parametrize("persona,score,level",[("NORMAL",0,"LOW"),("WATCH",40,"MEDIUM"),("HIGH-RISK",65,"HIGH")])
def test_persisted_personas_and_current_case_exclusion(persona,score,level):
    env=setup_case(damaged=True,persona=persona)
    assert env.resolution.user_risk_gate.score == score
    assert env.resolution.user_risk_gate.risk_level == level
    provider=SqlAlchemyUserRiskProvider(env.sessions,CaseProvider(env.context))
    before=env.snapshot
    with env.sessions.begin() as session:
        # New writes after the first snapshot cannot change persisted facts.
        session.get(UserRiskProfileRecord,env.case.user_ref).orders_90d=100
        for name,at in [("cutoff",NOW),("future",NOW+timedelta(days=1)),("backfill",NOW-timedelta(days=1))]:
            append_risk_event(session,user_ref=env.case.user_ref,case_ref=name,order_ref=name,event_type="CLAIM_REGISTERED",reason_code="ITEM_DAMAGED",occurred_at=at)
    assert provider.prepare_snapshot(env.case.case_ref,env.handoff.proposed_decision.reason_code,NOW) == before
    with pytest.raises(ValueError):
        provider.prepare_snapshot(env.case.case_ref,env.handoff.proposed_decision.reason_code,NOW+timedelta(seconds=1))


def human(env, decision, *, dossier_snapshot=None):
    resolution=env.resolution
    dossier=HumanReviewDossier(claimed_line_item_ids=env.handoff.proposed_decision.refund_scope.line_item_ids,
        claim_registry_version="claim-registry:2.0",routing_reason="HIGH_USER_RISK",review_gate=resolution.review_gate,
        user_risk_snapshot=dossier_snapshot or env.snapshot,user_risk_gate=resolution.user_risk_gate,reviewer_evaluations=[resolution.policy_evaluation],
        order_snapshot=env.context.order_snapshot,policy_bundle=env.bundle,policy_bundle_history=[env.bundle],
        proposal_history=[env.handoff],review_history=[resolution.review_result])
    provider=SqlAlchemyHumanReviewProvider(env.sessions,CaseProvider(env.context))
    provider.submit_for_review(env.handoff,resolution.review_result,dossier)
    raw=dict(decision=decision,handoff_id=env.handoff.handoff_id,reviewer_id="REVIEWER",review_note="Verified the scoped request and required return.")
    if decision == "EDIT":
        raw.update(correction_reason_code="RETURN_REQUIREMENT_INCORRECT",corrected_decision=dict(action="FULL_REFUND",
            refund_scope={"line_item_ids":["LI-DEMO-SPEAKER"]},return_decision=dict(source="HUMAN_REVIEW",
                requirement=dict(required=True,reason_code="RETURN_REQUIRED_FOR_INSPECTION")),
            policy_findings=[f.model_dump(mode="json") for f in resolution.review_result.reviewer_claim_findings]))
    with env.sessions.begin() as session:
        result=provider.complete_for_case(session,case_ref=env.case.case_ref,decision=TypeAdapter(ReviewDecision).validate_python(raw))
    return result


@pytest.mark.parametrize("decision",["APPROVE","EDIT","REJECT"])
def test_high_risk_human_authorization_still_requires_inspection(decision):
    env=setup_case(damaged=True,persona="HIGH-RISK")
    with pytest.raises(ValueError,match="risk authorization"):
        authorize(env)
    result=human(env,decision)
    if decision == "REJECT":
        assert result.decision == "REJECT"
        assert env.application.calls == []
        return
    raw=env.resolution.model_dump(mode="json")
    raw.update(outcome_source="HUMAN_"+decision,policy_evaluation=result.policy_evaluation.model_dump(mode="json"))
    if decision == "EDIT":
        raw["final_decision"]["return_decision"]=result.corrected_decision.return_decision.model_dump(mode="json")
    env.resolution=(HumanApproveResolutionHandoff if decision == "APPROVE" else HumanEditResolutionHandoff).model_validate(raw)
    env.request=ExecuteRefundRequest(resolution_handoff=env.resolution)
    assert authorize(env).state == "AWAITING_RETURN_CONFIRMATION"
    assert not FulfillmentWorker(env.sessions,env.executor).run_once()
    assert env.application.calls == []
    release(env)
    assert FulfillmentWorker(env.sessions,env.executor).run_once()
    assert len(env.application.calls) == 1


def test_forged_low_gate_does_not_authorize_high_snapshot():
    env=setup_case(damaged=True,persona="HIGH-RISK")
    gate=env.resolution.user_risk_gate.model_copy(update={"status":"PASS","risk_level":"LOW","score":0,"tags":[],"matched_rules":[],"reason":None})
    env.resolution=env.resolution.model_copy(update={"user_risk_gate":gate})
    with pytest.raises(ValueError,match="risk authorization"):
        authorize(env)
    assert env.application.calls == []


def test_human_dossier_cannot_replace_persisted_facts_even_with_same_gate():
    env = setup_case(damaged=True, persona="HIGH-RISK")
    # An older account gives the same HIGH score; recalculating the gate alone
    # cannot detect the fabricated input. The immutable snapshot must match.
    forged = env.snapshot.model_copy(update={"account_age_days": 9999})
    with pytest.raises(ValueError, match="persisted risk snapshot"):
        human(env, "APPROVE", dossier_snapshot=forged)
    with env.sessions() as session:
        assert session.scalar(select(HumanReviewRecord)) is None
    assert env.application.calls == []


def test_snapshot_http_requires_service_token_and_pinned_cutoff(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from return_agent.app import app, get_provider_bundle

    env = setup_case(damaged=True)
    provider = SqlAlchemyUserRiskProvider(env.sessions, CaseProvider(env.context))
    monkeypatch.setattr(app.state, "internal_service_token", "risk-test-token")
    monkeypatch.setitem(app.dependency_overrides, get_provider_bundle,
        lambda: SimpleNamespace(user_risk_provider=provider))
    body = {"method": "UserRiskProvider.prepare_snapshot",
        "params": {"case_ref": env.case.case_ref, "reason_code": "ITEM_DAMAGED",
        "as_of": NOW.isoformat()}}
    client = TestClient(app, raise_server_exceptions=True)
    try:
        url = "/internal/v1/user-risk/snapshot"
        assert client.post(url, json=body).status_code == 401
        headers = {"Authorization": "Bearer risk-test-token"}
        response = client.post(url, json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"] == env.snapshot.model_dump(mode="json")
        assert client.post(url, json=body, headers=headers).json() == response.json()
        body["params"]["as_of"] = (NOW + timedelta(seconds=1)).isoformat()
        assert client.post(url, json=body, headers=headers).status_code == 409
    finally:
        client.close()
