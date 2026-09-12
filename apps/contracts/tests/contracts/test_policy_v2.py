from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from return_agent_contracts.models import CaseContext, OrderSnapshot, PolicyBundle, ClaimFinding, EvidenceItem
from return_agent_contracts.policy_v2 import (PolicySelection, PolicyConfirmationRequest, evaluate_policy, content_hash,
    policy_confirmation_request_ref, validate_policy_confirmation_request)

NOW = datetime(2026,9,12,tzinfo=UTC)

def inputs(path="COOLING_OFF", **facts):
    document = json.loads((Path(__file__).resolve().parents[4]/"data/policy-v2.json.example").read_text())[0]
    bundle = PolicyBundle(schema_version="v2",policy_bundle_version="DEMO-TW-RETURNS:v2.0:bundle:test",
        retrieved_at=NOW,retrieval_status="OK",paths=document["paths"],selected_path_id=path,
        clauses=[dict(c,policy_version="DEMO-TW-RETURNS:v2.0") for c in document["clauses"]])
    context = CaseContext(case_ref="C1",order_ref="O1",market="TW",case_opened_at=NOW,
        snapshot_version=1,policy_schema_version="v2",first_valid_submitted_at=NOW)
    item_facts = dict(line_item_id="L1",source_ref="order-facts:1",transaction_version="transaction:1",
        purchased_spec={"sku":"SKU1","specification":"blue"},delivery_status="RECEIVED",received_at=NOW-timedelta(days=10),
        shipment_refs=["shipment:1"],pending_split_delivery=False,returnable_quantity=1,exception="NONE_CONFIRMED",
        exception_source_ref="exception:1",is_bundle=False,cancelled=False,refunded=False,
        deadlines=[dict(policy_path_id=p["path_id"],deadline_at=NOW,rule_source_ref="deadline:1",rule_source_version="1") for p in document["paths"]]) | facts
    order = OrderSnapshot(order_snapshot_ref="O1@1",order_ref="O1",snapshot_version=1,captured_at=NOW,currency="TWD",
        delivered_at=NOW-timedelta(days=10),refundable_amount_max="100",already_refunded_amount="0",
        line_items=[dict(line_item_id="L1",sku_ref="SKU1",category_ref="CAT",title="Item",quantity=1,refundable_amount="100")],
        policy_facts=dict(platform="SHOPEE_TW",seller_type="BUSINESS",product_type="GENERAL_PHYSICAL",cross_border=False,source_ref="order:1",items=[item_facts]))
    return dict(context=context,order=order,bundle=bundle,claimed_line_item_ids=["L1"],findings=[],evidence=[],
        selection=PolicySelection(selected_path_id=path,selection_version=1,original_requested_action="REFUND"),evaluated_at=NOW)


def status(result, path):
    return next(item.status for item in result.item_evaluations if item.path_id == path)


def test_p01_empty_claims_is_not_vacuous_approval():
    result = evaluate_policy(**inputs())
    assert status(result,"COOLING_OFF") == "ELIGIBLE"
    assert status(result,"DAMAGED_ON_ARRIVAL") == "NEEDS_INFORMATION"
    assert status(evaluate_policy(**inputs(exception="UNKNOWN")),"COOLING_OFF") == "SPECIALIST_REQUIRED"
    assert status(evaluate_policy(**inputs(returnable_quantity=0)),"COOLING_OFF") == "SPECIALIST_REQUIRED"


def test_deadline_inclusive_and_provider_specific():
    values = inputs()
    assert status(evaluate_policy(**values),"COOLING_OFF") == "ELIGIBLE"
    values["context"].first_valid_submitted_at = NOW + timedelta(microseconds=1)
    result = evaluate_policy(**values)
    assert status(result,"COOLING_OFF") == "INELIGIBLE"
    assert status(result,"DAMAGED_ON_ARRIVAL") == "SPECIALIST_REQUIRED"


def test_p04_requires_trusted_investigation_and_no_pending_delivery():
    result = evaluate_policy(**inputs("UNDELIVERED_ITEM",delivery_status="CONFIRMED_UNDELIVERED",received_at=None,investigation_ref="investigation:1"))
    assert status(result,"UNDELIVERED_ITEM") == "ELIGIBLE"
    for overrides in ({"delivery_status":"UNKNOWN"},{"delivery_status":"IN_TRANSIT"},{"pending_split_delivery":True},{"cancelled":True},{"refunded":True},{"reservation_case_ref":"other"}):
        result = evaluate_policy(**inputs("UNDELIVERED_ITEM",investigation_ref="investigation:1",**overrides))
        assert status(result,"UNDELIVERED_ITEM") == "SPECIALIST_REQUIRED"


def test_p03_backend_missing_is_not_user_evidence_request():
    assert status(evaluate_policy(**inputs("WRONG_ITEM",purchased_spec={})),"WRONG_ITEM") == "SPECIALIST_REQUIRED"
    assert status(evaluate_policy(**inputs("WRONG_ITEM")),"WRONG_ITEM") == "NEEDS_INFORMATION"


def test_evaluation_tampering_and_empty_scope_rejected():
    result = evaluate_policy(**inputs())
    payload = result.model_dump(mode="json")
    payload["case_ref"] = "forged"
    with pytest.raises(ValidationError):
        type(result).model_validate(payload)
    values = inputs()
    values["claimed_line_item_ids"] = []
    with pytest.raises(ValueError):
        evaluate_policy(**values)
    assert content_hash({"a":1,"b":2}) == content_hash({"b":2,"a":1})


@pytest.mark.parametrize("days,status_value", [(7, "INELIGIBLE"), (15, "ELIGIBLE")])
def test_provider_deadline_and_first_submission_survive_later_assessment(days, status_value):
    values = inputs()
    for deadline in values["order"].policy_facts.items[0].deadlines:
        deadline.deadline_at = NOW - timedelta(days=10) + timedelta(days=days)
    values["evaluated_at"] = NOW + timedelta(days=30)
    assert status(evaluate_policy(**values), "COOLING_OFF") == status_value


def test_damage_without_arrival_timing_keeps_independent_cooling_off_alternative():
    values = inputs("DAMAGED_ON_ARRIVAL")
    values["evidence"] = [EvidenceItem(evidence_id="EV-DAMAGE", type="IMAGE", source="USER",
        subject="L1", artifact_ref="artifact://damage", extracted_summary="Visible crack.", collected_at=NOW)]
    values["findings"] = [ClaimFinding(claim_id="ITEM_PHYSICALLY_DAMAGED", subject="L1",
        status="SUPPORTED", supporting_evidence_refs=["EV-DAMAGE"], explanation="Visible crack.")]
    evaluation = evaluate_policy(**values)
    assert status(evaluation, "DAMAGED_ON_ARRIVAL") == "NEEDS_INFORMATION"
    assert status(evaluation, "COOLING_OFF") == "ELIGIBLE"


@pytest.mark.parametrize("field,value", [("seller_type", "UNKNOWN"), ("seller_type", "PERSONAL"),
    ("product_type", "SPECIAL"), ("platform", "OTHER"), ("cross_border", True)])
def test_unknown_or_outside_transaction_is_specialist_on_all_paths(field, value):
    values = inputs()
    setattr(values["order"].policy_facts, field, value)
    assert {x.status for x in evaluate_policy(**values).item_evaluations} == {"SPECIALIST_REQUIRED"}


@pytest.mark.parametrize("facts", [{"deadlines": []}, {"exception": "ESTABLISHED"},
    {"exception": "DISPUTED"}, {"exception_source_ref": None}, {"is_bundle": True}])
def test_missing_deadline_or_exception_facts_never_approve_empty_claims(facts):
    assert status(evaluate_policy(**inputs(**facts)), "COOLING_OFF") == "SPECIALIST_REQUIRED"


def test_undelivered_system_claim_rejects_photo_as_investigation():
    values = inputs("UNDELIVERED_ITEM", delivery_status="CONFIRMED_UNDELIVERED",
        received_at=None, investigation_ref="INV-TRUSTED")
    values["findings"] = [ClaimFinding(claim_id="ITEM_CONFIRMED_UNDELIVERED", subject="L1",
        status="SUPPORTED", supporting_evidence_refs=["BUYER-PHOTO"], explanation="Empty package.")]
    with pytest.raises(ValueError, match="system-only"):
        evaluate_policy(**values)


@pytest.mark.parametrize("versioned_input", ["context", "bundle"])
def test_v2_evaluation_rejects_cross_version_input(versioned_input):
    values = inputs()
    field = "policy_schema_version" if versioned_input == "context" else "schema_version"
    values[versioned_input] = values[versioned_input].model_copy(update={field: "v1"})
    with pytest.raises(ValueError, match="explicit v2"):
        evaluate_policy(**values)


def bound_confirmation_request(bundle):
    payload = dict(case_ref="C1", original_scope_hash=content_hash(["L1"]),
        original_path_id="DAMAGED_ON_ARRIVAL", path_id="COOLING_OFF", selection_version=2,
        return_required=True, return_requirement_hash=content_hash({"required": True}))
    return PolicyConfirmationRequest(request_ref=policy_confirmation_request_ref(payload, bundle), **payload)


def test_confirmation_binding_survives_identical_package_retrieval_and_path_selection():
    bundle = inputs()["bundle"]
    request = bound_confirmation_request(bundle)
    reselected = bundle.model_copy(deep=True)
    reselected.policy_bundle_version = "DEMO-TW-RETURNS:v2.0:bundle:new-retrieval"
    reselected.retrieved_at = NOW + timedelta(hours=1)
    reselected.selected_path_id = "DAMAGED_ON_ARRIVAL"
    reselected.clauses.reverse()
    reselected.paths.reverse()
    validate_policy_confirmation_request(request, reselected)


@pytest.mark.parametrize("changed", ["clause", "path", "common_constraints", "legacy_digest", "scope", "requirement"])
def test_confirmation_binding_rejects_rule_changes_and_legacy_unbound_consent(changed):
    bundle = inputs()["bundle"]
    request = bound_confirmation_request(bundle)
    bundle.policy_bundle_version = "DEMO-TW-RETURNS:v2.0:bundle:new-retrieval"
    if changed == "clause": bundle.clauses[0].text = "Changed rule."
    if changed == "path": bundle.paths[0].interpretation_hash = "f" * 64
    if changed == "common_constraints": bundle.common_constraints = ["Changed scope."]
    if changed == "scope": request.original_scope_hash = content_hash(["L2"])
    if changed == "requirement": request.return_requirement_hash = content_hash({"required": False})
    if changed == "legacy_digest":
        request.request_ref = f"policy-confirmation:{content_hash(request.model_dump(mode='json', exclude={'request_ref'}))}"
        assert PolicyConfirmationRequest.model_validate(request.model_dump(mode="json")) == request
    with pytest.raises(ValueError, match="current versioned rule package"):
        validate_policy_confirmation_request(request, bundle)
