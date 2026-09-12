from datetime import UTC,datetime,timedelta
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from return_agent_contracts.models import PolicyBundle,CaseContextLoadResult
from return_agent_contracts.policy_v2 import PolicyConfirmation, PolicyConfirmationRequest, PolicySelection
from return_agent_contracts.runtime import PolicyConfirmationResume
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.user_risk import UserRiskSnapshot
from return_agent_runtime import ReturnAgentRuntime
from return_agent_runtime.model import ModelTask
from .conftest import make_runtime,case_load,user_turn
from .fakes import QueuedModel,FrozenClock

NOW=datetime(2026,9,12,tzinfo=UTC)


def inputs(undelivered=False):
    raw=case_load().model_dump(mode="json")
    raw["case_context"].update(policy_schema_version="v2",case_opened_at=NOW,first_valid_submitted_at=NOW)
    document=json.loads((Path(__file__).resolve().parents[3]/"data/policy-v2.json.example").read_text())[0]
    item=dict(line_item_id="LI-002",source_ref="facts",transaction_version="transaction",
        purchased_spec={"sku":"SKU-B","specification":"blue"},delivery_status="CONFIRMED_UNDELIVERED" if undelivered else "RECEIVED",
        received_at=None if undelivered else NOW-timedelta(days=10),investigation_ref="investigation" if undelivered else None,
        shipment_refs=["shipment"],pending_split_delivery=False,returnable_quantity=1,exception="NONE_CONFIRMED",exception_source_ref="exception",
        is_bundle=False,cancelled=False,refunded=False,
        deadlines=[dict(policy_path_id=p["path_id"],deadline_at=NOW+timedelta(days=5),rule_source_ref="deadline",rule_source_version="v1") for p in document["paths"]])
    raw["order_snapshot"]["policy_facts"]=dict(platform="SHOPEE_TW",seller_type="MALL",product_type="GENERAL_PHYSICAL",cross_border=False,source_ref="facts",items=[item])
    path="UNDELIVERED_ITEM" if undelivered else "COOLING_OFF"
    bundle=PolicyBundle(schema_version="v2",policy_bundle_version="DEMO-TW-RETURNS:v2.0:bundle:runtime",retrieved_at=NOW,
        retrieval_status="OK",selected_path_id=path,paths=document["paths"],clauses=[dict(c,policy_version="DEMO-TW-RETURNS:v2.0") for c in document["clauses"]])
    return CaseContextLoadResult.model_validate(raw),bundle


@pytest.mark.parametrize("risk",["LOW","MEDIUM","HIGH","UNKNOWN"])
@pytest.mark.parametrize("undelivered",[False,True])
@pytest.mark.parametrize("high_amount", [False, True])
def test_v2_empty_claims_or_system_facts_independent_review_and_risk(risk,undelivered,high_amount):
    context,bundle=inputs(undelivered)
    reason="MISSING_ITEM" if undelivered else "CHANGED_MIND"
    findings=[dict(claim_id="ITEM_CONFIRMED_UNDELIVERED",subject="LI-002",status="SUPPORTED",supporting_evidence_refs=["investigation"],explanation="Trusted investigation.")] if undelivered else []
    model=QueuedModel()
    model.queue(ModelTask.INTAKE,dict(completeness="COMPLETE",order_ref="ORDER-001",reason_code=reason,reason_summary="Requested return.",
        requested_action="REFUND",claimed_line_item_ids=[],missing_fields=[],clarification_question=None))
    assessment=dict(evidence_status="SUFFICIENT_FOR_APPROVAL",claim_registry_version="claim-registry:2.0",claim_findings=findings)
    model.queue(ModelTask.ASSESS,assessment,assessment)
    refs=next(p.clause_refs for p in bundle.paths if p.path_id==bundle.selected_path_id)
    draft=dict(result_type="DRAFT",draft=dict(action="FULL_REFUND",refund_scope={"line_item_ids":["LI-002"]},reason_code=reason,
        return_decision=dict(source="POLICY",reason_code="ITEM_NOT_RECEIVED" if undelivered else "POLICY_RETURN_REQUIRED"),
        policy_refs=refs,evidence_refs=[],rationale_summary="Selected path permits this scoped request."))
    model.queue(ModelTask.PROPOSE_OR_REVISE,draft,draft)
    model.queue(ModelTask.REVIEW,dict(verdict="APPROVE",reviewer_claim_findings=findings,revision_reasons=[],reviewer_prompt_version="reviewer:test",reviewed_at=NOW))
    runtime,providers=make_runtime(model=model,case_result=context,policy_result=bundle,
        reviewer_gate_config=ReviewerGateConfig(thresholds={"TWD": "100" if high_amount else "5000"}))
    snapshots=[]
    def snapshot(case_ref,reason_code,as_of):
        snapshots.append(case_ref)
        if risk=="UNKNOWN":raise LookupError("unavailable")
        return UserRiskSnapshot(snapshot_ref="snapshot",case_ref=case_ref,user_ref="user",reason_code=reason_code,as_of=as_of,created_at=NOW,
            account_age_days=180,orders_90d=8,same_reason_claims_90d=3 if risk in {"MEDIUM","HIGH"} else 1,refunded_orders_90d=4 if risk=="HIGH" else 1)
    class Policy:
        def retrieve_policy(self,*args,**kwargs):
            return bundle
    class Memory:
        calls=[]
        def query_approved(self,**kwargs):
            self.calls.append(kwargs)
            return []
    memory=Memory()
    runtime=ReturnAgentRuntime(replace(runtime.dependencies,clock=FrozenClock(NOW),policy_provider=Policy(),
        operational_memory_store=memory,user_risk_provider=SimpleNamespace(prepare_snapshot=snapshot)),runtime.checkpointer)
    result=runtime.start(thread_id="thread",case_ref="CASE-001",initial_turn=user_turn())
    if not undelivered:
        assert result.result_type == "INTERRUPTED", result
        pending=result.interrupt_payload.request
        assert isinstance(pending,PolicyConfirmationRequest)
        assert snapshots == []
        result=runtime.resume(thread_id="thread",payload=PolicyConfirmationResume(kind="POLICY_CONFIRMATION",
            confirmation=PolicyConfirmation(confirmation_ref="consent",request=pending,accepted=True,confirmed_at=NOW)))
    assert len(snapshots)==1,result
    assert memory.calls[-1]["claim_registry_major"]==2
    assert memory.calls[-1]["policy_path_id"]==bundle.selected_path_id
    if not undelivered:assert memory.calls[-1]["required_claim_ids"]==[]
    reviewer=next(call for call in model.calls if call.task is ModelTask.REVIEW)
    rendered=json.dumps(reviewer.payload,default=str)
    assert all(key not in rendered for key in ["assessment_findings","policy_evaluation","operational_memory","user_risk"])
    if high_amount or risk in {"HIGH","UNKNOWN"}:
        assert result.result_type=="INTERRUPTED",result
        assert result.interrupt_kind=="HUMAN_REVIEW"
        dossier = result.interrupt_payload.dossier
        assert dossier.user_risk_gate.risk_level == risk
        if high_amount:
            assert result.interrupt_payload.routing_reason == "HIGH_VALUE_ITEM"
            assert dossier.review_gate.status == "HUMAN_REQUIRED"
    else:
        assert result.result_type=="RESOLUTION",result
        assert result.resolution_handoff.user_risk_gate.risk_level==risk
    if not undelivered and risk == "LOW" and not high_amount:
        from return_agent_contracts.validation import ContractInvariantError, validate_proposed_decision_handoff
        handoff = runtime.graph.get_state({"configurable": {"thread_id": "thread"}}).values["current_handoff"]
        validate_proposed_decision_handoff(handoff, bundle, context.order_snapshot)
        changed_bundle = bundle.model_copy(deep=True)
        changed_bundle.clauses[0].text = "Changed rule under an existing consent."
        with pytest.raises(ContractInvariantError, match="current versioned rule package"):
            validate_proposed_decision_handoff(handoff, changed_bundle, context.order_snapshot)


@pytest.mark.parametrize("tamper", ["selected_path", "immutable_bundle", "case_version"])
def test_policy_provider_cannot_replace_persisted_selection_or_bundle(tamper):
    from return_agent_runtime.graph import _retrieve_policy_node
    from .test_interrupt_resume import complete_intake
    from return_agent_contracts.models import IntakeResult
    context, bundle = inputs()
    changed = bundle.model_copy(deep=True)
    if tamper == "selected_path":
        changed.selected_path_id = "WRONG_ITEM"
    elif tamper == "immutable_bundle":
        changed.clauses[0].text = "Changed policy under the same reference."
    else:
        context.case_context.policy_schema_version = "v1"
    runtime, _ = make_runtime(model=QueuedModel())
    dependencies = replace(runtime.dependencies, policy_provider=SimpleNamespace(retrieve_policy=lambda *a, **k: changed))
    update = _retrieve_policy_node(dependencies)({"case_context": context.case_context,
        "order_snapshot": context.order_snapshot, "claimed_line_item_ids": ["LI-002"],
        "normalized_intent": IntakeResult.model_validate(complete_intake()),
        "policy_selection": PolicySelection(selected_path_id="COOLING_OFF", selection_version=2,
            original_requested_action="REFUND", confirmation_ref="consent"),
        "policy_bundle_history": [bundle]})
    assert update["_route"] == "terminate_automation"
    assert update["escalation_reason"] == "CONTRACT_VIOLATION"


def test_path_confirmation_preserves_objections_budgets_and_clears_prior_memory(monkeypatch):
    from return_agent_runtime.policy import confirmation_request, confirm_policy_path_node
    _, bundle = inputs()
    state = dict(case_ref="CASE-001", claimed_line_item_ids=["LI-002"],
        policy_bundle=bundle,
        policy_selection=PolicySelection(selected_path_id="DAMAGED_ON_ARRIVAL",
            selection_version=2, original_requested_action="REFUND"),
        revision_round=2, evidence_round=1, propose_round=4, verification_round=1,
        revision_events=["persisted-objection"], review_history=["prior-review"],
        operational_memory=["old-path-hit"], memory_retrieval="old-observation")
    request = confirmation_request(state, "COOLING_OFF", True)
    state["pending_policy_confirmation"] = request
    confirmation = PolicyConfirmation(confirmation_ref="consent", request=request, accepted=True, confirmed_at=NOW)
    monkeypatch.setattr("return_agent_runtime.policy.interrupt", lambda _: {"kind": "POLICY_CONFIRMATION",
        "confirmation": confirmation.model_dump(mode="json")})
    resumed = state | confirm_policy_path_node(state)
    assert resumed["_route"] == "retrieve_policy"
    assert resumed["policy_selection"].selected_path_id == "COOLING_OFF"
    assert resumed["policy_selection"].selection_version == 3
    assert resumed["operational_memory"] == [] and resumed["memory_retrieval"] is None
    for key in ["revision_round", "evidence_round", "propose_round", "verification_round", "revision_events", "review_history"]:
        assert resumed[key] == state[key]


@pytest.mark.parametrize("changed", ["legacy_digest", "new_rule_package"])
def test_confirmation_checkpoint_rejects_unbound_or_changed_package_before_interrupt(monkeypatch, changed):
    from return_agent_runtime.policy import confirmation_request, confirm_policy_path_node
    from return_agent_contracts.policy_v2 import content_hash
    _, bundle = inputs()
    state = dict(case_ref="CASE-001", claimed_line_item_ids=["LI-002"], policy_bundle=bundle,
        policy_selection=PolicySelection(selected_path_id="COOLING_OFF",
            selection_version=1, original_requested_action="REFUND"))
    request = confirmation_request(state, "COOLING_OFF", True)
    if changed == "legacy_digest":
        request.request_ref = f"policy-confirmation:{content_hash(request.model_dump(mode='json', exclude={'request_ref'}))}"
    else:
        bundle.policy_bundle_version = "DEMO-TW-RETURNS:v2.0:bundle:changed"
        bundle.clauses[0].text = "Different requirements under the same policy major."
    state["pending_policy_confirmation"] = request
    def forbidden_interrupt(_):
        raise AssertionError("unbound consent must fail before accepting a resume")
    monkeypatch.setattr("return_agent_runtime.policy.interrupt", forbidden_interrupt)
    update = confirm_policy_path_node(state)
    assert update["_route"] == "terminate_automation"
    assert update["escalation_reason"] == "CONTRACT_VIOLATION"


@pytest.mark.parametrize("changed", ["none", "policy", "registry", "path", "market", "reason", "category"])
def test_cooling_off_memory_requires_exact_path_policy_registry_scope(changed):
    from return_agent_runtime.graph import _memory_matches
    from return_agent_contracts.models import ApprovedMemory
    memory = ApprovedMemory(memory_id="MEM", retrieval_summary="Confirm required return consent.",
        status="APPROVED", recommended_behavior="Explain return inspection.", trigger_conditions=["Cooling off."],
        policy_version="DEMO-TW-RETURNS:v2.0", claim_registry_version="claim-registry:2.0",
        scope=dict(market="TW", policy_path_id="COOLING_OFF", reason_codes=["CHANGED_MIND"],
            claim_ids=[], categories=["CAT"]), confidence=0.8, approved_at=NOW)
    if changed == "policy": memory.policy_version = "POLICY-12:v3"
    if changed == "registry": memory.claim_registry_version = "claim-registry:2.1"
    if changed == "path": memory.scope.policy_path_id = "DAMAGED_ON_ARRIVAL"
    if changed == "market": memory.scope.market = "SG"
    if changed == "reason": memory.scope.reason_codes = ["ITEM_DAMAGED"]
    if changed == "category": memory.scope.categories = ["OTHER"]
    assert _memory_matches(memory, market="TW", reason_code="CHANGED_MIND", required_claim_ids=set(),
        categories={"CAT"}, policy_versions={"DEMO-TW-RETURNS:v2.0"}, registry_version="claim-registry:2.0",
        policy_path_id="COOLING_OFF") is (changed == "none")
