"""Exercise real authorization, reservation and payment boundaries on v2 cases."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from return_agent.capabilities.fulfillment import (
    register_authorization, accept_return_event, transition, FulfillmentWorker, RETURN_EVENT,
)
from return_agent.capabilities.policy_v2_demo import DemoScenarios, initialize_v2_case, seed_user_risk
from return_agent.capabilities.refund import SqlAlchemyRefundExecutionProvider, RefundExecutionUnavailableError
from return_agent.capabilities.user_risk import SqlAlchemyUserRiskProvider
from return_agent.db.case import CaseRecord
from return_agent.db.models import (
    HandoffVerificationRecord, PolicyRetrievalRecord, ReturnAuthorizationRecord,
    RefundExecutionRecord, RefundItemReservation, UserRiskEventRecord,
)
from return_agent_contracts.models import (
    CaseContextLoadResult, PolicyBundle, ProposedDecisionHandoff,
    ReviewerApprovedResolutionHandoff, ExecuteRefundRequest,
)
from return_agent_contracts.policy_v2 import PolicySelection, evaluate_policy, content_hash
from return_agent_contracts.review_gates import evaluate_review_gate
from return_agent_contracts.user_risk import evaluate_user_risk
from .test_refund_execution import _session_factory, ApplicationProvider, CaseProvider

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def setup_case(*, undelivered=False, persona="NORMAL", damaged=False, sessions=None, case_ref="CASE-PV2"):
    sessions = sessions or _session_factory()
    scenario = "F" if undelivered else "HIGH" if persona == "HIGH-RISK" else persona
    case = CaseRecord(case_ref=case_ref, thread_id="thread:"+case_ref,
        order_ref=f"ORDER-PV2-{scenario}-test", user_ref=f"USER-{persona}",
        status="OBSERVING", created_at=NOW, updated_at=NOW)
    initialize_v2_case(case, DemoScenarios.model_validate_json((ROOT/"data/policy-v2-cases.json.example").read_text()))
    with sessions.begin() as session:
        session.add(case)
    seed_user_risk(sessions, ROOT/"data/user-risk.json.example")
    context = CaseContextLoadResult.model_validate(case.v2_context_payload)
    provider = CaseProvider(context)
    application = ApplicationProvider()
    executor = SqlAlchemyRefundExecutionProvider(sessions, provider, application)
    path = "UNDELIVERED_ITEM" if undelivered else "DAMAGED_ON_ARRIVAL" if damaged else "COOLING_OFF"
    document = json.loads((ROOT/"data/policy-v2.json.example").read_text())[0]
    bundle = PolicyBundle(schema_version="v2",policy_bundle_version=f"DEMO-TW-RETURNS:v2.0:bundle:{case_ref}",
        retrieval_status="OK",retrieved_at=NOW,selected_path_id=path,paths=document["paths"],
        clauses=[dict(c,policy_version="DEMO-TW-RETURNS:v2.0") for c in document["clauses"]])
    selection = PolicySelection(selected_path_id=path,selection_version=1,original_requested_action="REFUND")
    scope = ["LI-DEMO-SPEAKER"]
    from return_agent_contracts.models import ClaimFinding, EvidenceItem
    evidence = [EvidenceItem(evidence_id="EV-ARRIVAL",type="IMAGE",source="USER",subject=scope[0],
        artifact_ref="artifact://synthetic/arrival",extracted_summary="The package and item are visibly damaged immediately on arrival.",collected_at=NOW)] if damaged else []
    assessment = [ClaimFinding(claim_id=claim,subject=scope[0],status="SUPPORTED",supporting_evidence_refs=["EV-ARRIVAL"],explanation="Arrival evidence supports the claim.")
        for claim in ["ITEM_PHYSICALLY_DAMAGED","DAMAGE_PRESENT_ON_ARRIVAL"]] if damaged else []
    evaluation = evaluate_policy(context=context.case_context,order=context.order_snapshot,bundle=bundle,
        claimed_line_item_ids=scope,findings=assessment,evidence=evidence,selection=selection,evaluated_at=NOW)
    refs = next(p.clause_refs for p in bundle.paths if p.path_id == path)
    requirement = dict(required=not undelivered,reason_code="ITEM_NOT_RECEIVED" if undelivered else "RETURN_REQUIRED_FOR_INSPECTION" if damaged else "POLICY_RETURN_REQUIRED")
    reason = "MISSING_ITEM" if undelivered else "ITEM_DAMAGED" if damaged else "CHANGED_MIND"
    proposal = dict(action="FULL_REFUND",refund_scope={"line_item_ids":scope},amount="1200",currency="TWD",
        reason_code=reason,return_decision=dict(source="MODEL_JUDGMENT" if damaged else "POLICY",requirement=requirement),policy_refs=refs)
    handoff = ProposedDecisionHandoff(handoff_version="2.0",handoff_id=f"handoff:{case_ref}",case_ref=case_ref,
        order_snapshot_ref=context.order_snapshot.order_snapshot_ref,policy_bundle_version=bundle.policy_bundle_version,
        claim_registry_version="claim-registry:2.0",policy_evaluation=evaluation,policy_selection=selection,
        assessment_findings=assessment,evidence_bundle=evidence,proposed_decision=proposal,policy_refs=refs,rationale_summary="Selected policy path is eligible.",
        revision_round=0,agent_prompt_version="resolver:2.0")
    with sessions.begin() as session:
        session.add(PolicyRetrievalRecord(retrieval_id=f"retrieval:{case_ref}",request_hash=content_hash(case_ref),
            bundle_version=bundle.policy_bundle_version,retrieval_status="OK",bundle_payload=bundle.model_dump(mode="json"),retrieved_at=NOW))
        session.add(HandoffVerificationRecord(verification_id=f"verification:{case_ref}",handoff_id=handoff.handoff_id,
            payload_hash=content_hash(handoff),handoff_payload=handoff.model_dump(mode="json"),verification_status="PASS",
            result_payload=dict(status="PASS",issues=[],verification_version="verification:2.0"),
            verification_version="verification:2.0",created_at=NOW,updated_at=NOW))
    risk_provider = SqlAlchemyUserRiskProvider(sessions,provider)
    snapshot = risk_provider.prepare_snapshot(case_ref,handoff.proposed_decision.reason_code,NOW)
    findings = [] if not undelivered else [dict(claim_id="ITEM_CONFIRMED_UNDELIVERED",subject=scope[0],status="SUPPORTED",
        supporting_evidence_refs=[context.order_snapshot.policy_facts.items[0].investigation_ref],explanation="Trusted non-delivery investigation.")]
    from return_agent_contracts.models import ClaimFinding
    if damaged:
        findings = [f.model_dump(mode="json") for f in assessment]
    review_evaluation = evaluate_policy(context=context.case_context,order=context.order_snapshot,bundle=bundle,
        claimed_line_item_ids=scope,findings=[ClaimFinding.model_validate(f) for f in findings],evidence=evidence,selection=selection,evaluated_at=NOW)
    resolution = ReviewerApprovedResolutionHandoff(case_ref=case_ref,handoff_id=handoff.handoff_id,emitted_at=NOW,
        outcome_source="REVIEWER_APPROVE",execution_blocked=False,final_decision={k:v for k,v in proposal.items() if k != "policy_refs"},
        review_result=dict(verdict="APPROVE",reviewer_claim_findings=findings,reviewer_prompt_version="reviewer:2.0",reviewed_at=NOW),
        policy_evaluation=review_evaluation,refund_release_condition="AUTHORIZED_NO_RETURN" if undelivered else "RETURN_INSPECTION_PASSED",
        review_gate=evaluate_review_gate("FULL_REFUND",handoff.proposed_decision.amount,"TWD",executor._reviewer_gate_config),
        user_risk_gate=evaluate_user_risk("FULL_REFUND",snapshot,executor._user_risk_config))
    return SimpleNamespace(sessions=sessions,case=case,context=context,executor=executor,application=application,
        handoff=handoff,bundle=bundle,resolution=resolution,request=ExecuteRefundRequest(resolution_handoff=resolution),snapshot=snapshot)


def authorize(env):
    with env.sessions.begin() as session:
        return register_authorization(session,session.get(CaseRecord,env.case.case_ref),env.resolution,env.executor)


def consent(env):
    with env.sessions.begin() as session:
        record = session.scalar(select(ReturnAuthorizationRecord))
        record.confirmation_payload = dict(input=dict(accept=True,authorization_ref=record.authorization_ref,
            return_requirement_hash=record.payload["requirement_hash"],idempotency_key="consent"))
        transition(session,record,"AWAITING_RETURN","Buyer accepted the return requirement.")


def event(env, kind="RETURN_ARRIVED", **changes):
    with env.sessions() as session:
        record = session.scalar(select(ReturnAuthorizationRecord))
        raw = dict(event_id=kind,producer_id="test-producer",case_ref=env.case.case_ref,
            authorization_ref=record.authorization_ref,line_item_id="LI-DEMO-SPEAKER",occurred_at=datetime.now(UTC),
            event_type=kind,payload={"tracking_ref":"tracking"} if kind == "RETURN_ARRIVED" else
            {"arrived_event_id":"RETURN_ARRIVED","inspection_ref":"inspection"}) | changes
    return RETURN_EVENT.validate_python(dict(raw,payload_hash=content_hash(raw)))


def accept(env, ev):
    with env.sessions.begin() as session:
        return accept_return_event(session,ev)


def release(env):
    consent(env)
    accept(env,event(env))
    accept(env,event(env,"INSPECTION_PASSED"))


def test_approval_is_not_payment_and_inspection_releases_once():
    env = setup_case()
    record = authorize(env)
    assert record.state == "AWAITING_RETURN_CONFIRMATION"
    with pytest.raises(RefundExecutionUnavailableError):
        env.executor.execute(env.request)
    consent(env)
    assert not FulfillmentWorker(env.sessions,env.executor).run_once()
    arrival = event(env)
    receipt = accept(env,arrival)
    assert accept(env,arrival) == receipt
    assert not FulfillmentWorker(env.sessions,env.executor).run_once()
    assert env.application.calls == []
    accept(env,event(env,"INSPECTION_PASSED"))
    assert FulfillmentWorker(env.sessions,env.executor).run_once()
    assert not FulfillmentWorker(env.sessions,env.executor).run_once()
    assert env.executor.execute(env.request).status == "SUCCEEDED"
    assert len(env.application.calls) == 1
    with env.sessions() as session:
        assert session.get(CaseRecord,env.case.case_ref).status == "RESOLVED"
        assert len(list(session.scalars(select(UserRiskEventRecord).where(UserRiskEventRecord.case_ref == env.case.case_ref,
            UserRiskEventRecord.event_type == "REFUND_SUCCEEDED")))) == 1


def test_undelivered_waiver_still_requires_authorization():
    env = setup_case(undelivered=True)
    assert authorize(env).state == "EXECUTING"
    assert FulfillmentWorker(env.sessions,env.executor).run_once()
    assert len(env.application.calls) == 1


@pytest.mark.parametrize("change", [{"line_item_id":"other"},{"case_ref":"other"},{"authorization_ref":"other"},
    {"occurred_at":NOW-timedelta(days=1)}])
def test_bad_event_cannot_release_payment(change):
    env = setup_case()
    authorize(env)
    consent(env)
    with pytest.raises(ValueError):
        accept(env,event(env,**change))
    assert env.application.calls == []


def test_inspection_before_arrival_and_changed_replay_rejected():
    env = setup_case()
    authorize(env)
    consent(env)
    with pytest.raises(ValueError):
        accept(env,event(env,"INSPECTION_PASSED"))
    arrival = event(env)
    accept(env,arrival)
    with pytest.raises(ValueError):
        accept(env,event(env,payload={"tracking_ref":"changed"}))
    assert env.application.calls == []


def test_config_change_stops_payment():
    env = setup_case()
    authorize(env)
    release(env)
    env.executor._user_risk_config = env.executor._user_risk_config.model_copy(update={"version":"changed"})
    assert FulfillmentWorker(env.sessions,env.executor).run_once()
    assert env.application.calls == []
    with env.sessions() as session:
        assert session.get(CaseRecord,env.case.case_ref).status == "ESCALATED"


def test_unknown_payment_keeps_reservation_and_resumes_original_key():
    env = setup_case()
    authorize(env)
    release(env)
    env.application.timeout_once = True
    with pytest.raises(RefundExecutionUnavailableError):
        env.executor.execute(env.request)
    with env.sessions() as session:
        assert session.scalar(select(RefundItemReservation)) is not None
        assert session.scalar(select(RefundExecutionRecord)).state == "IN_PROGRESS"
    assert FulfillmentWorker(env.sessions,env.executor).run_once()
    assert len({r.execution_ref for r in env.application.calls}) == 1
    assert len(env.application.applied_effects) == 1
