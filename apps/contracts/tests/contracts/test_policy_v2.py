from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from return_agent_contracts.models import CaseContext, OrderSnapshot, PolicyBundle, ClaimFinding, EvidenceItem
from return_agent_contracts.policy_v2 import PolicySelection, evaluate_policy, content_hash

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
