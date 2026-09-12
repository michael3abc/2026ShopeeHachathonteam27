"""Explicit synthetic order scenarios, pinned once at case creation."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from pydantic import Field
from return_agent_contracts.base import ContractModel, Money, NonNegativeInt, OpaqueRef, UTCDateTime
from return_agent_contracts.models import CaseContextLoadResult
from return_agent_contracts.policy_v2 import PolicyPathId
from return_agent.db.models import UserRiskProfileRecord
from .user_risk import utc, append_risk_event


class DemoScenario(ContractModel):
    id: OpaqueRef
    order_prefix: OpaqueRef
    user_ref: OpaqueRef
    amount: Money
    delivery: Literal["RECEIVED","CONFIRMED_UNDELIVERED"]


class DemoScenarios(ContractModel):
    version: Literal["synthetic-policy-v2-cases:1"]
    scenarios: list[DemoScenario]


class RiskPersona(ContractModel):
    user_ref: OpaqueRef
    account_age_days: NonNegativeInt
    orders_90d: NonNegativeInt
    registered_claims: NonNegativeInt
    refunded_orders: NonNegativeInt


class RiskSeed(ContractModel):
    reference_at: UTCDateTime
    synthetic: Literal[True]
    profiles: list[RiskPersona]


def initialize_v2_case(case, scenarios: DemoScenarios) -> bool:
    matches = [s for s in scenarios.scenarios if case.order_ref.startswith(s.order_prefix)]
    if not matches:
        if case.order_ref.startswith("ORDER-PV2-"):
            raise ValueError("unknown v2 Demo scenario")
        return False
    if len(matches) != 1 or matches[0].user_ref != case.user_ref:
        raise ValueError("synthetic order scenario owner mismatch")
    scenario = matches[0]
    now = utc(case.created_at)
    received = now-timedelta(days=10) if scenario.delivery == "RECEIVED" else None
    ref = f"synthetic:{case.order_ref}"
    item = "LI-DEMO-SPEAKER"
    context = CaseContextLoadResult(
        case_context=dict(case_ref=case.case_ref,order_ref=case.order_ref,market="TW",case_opened_at=now,
            first_valid_submitted_at=now,snapshot_version=1,policy_schema_version="v2"),
        order_snapshot=dict(order_snapshot_ref=f"{case.order_ref}@1",order_ref=case.order_ref,snapshot_version=1,
            captured_at=now,currency="TWD",delivered_at=received,refundable_amount_max=scenario.amount,already_refunded_amount="0",
            line_items=[dict(line_item_id=item,sku_ref="SKU-DEMO-SPEAKER",category_ref="CAT-AUDIO-SPEAKERS",
                title="Demo Bluetooth Speaker",quantity=1,refundable_amount=scenario.amount)],
            policy_facts=dict(platform="SHOPEE_TW",seller_type="MALL",product_type="GENERAL_PHYSICAL",cross_border=False,
                source_ref=ref,items=[dict(line_item_id=item,source_ref=ref,transaction_version="synthetic-transaction:1",
                purchased_spec={"sku":"SKU-DEMO-SPEAKER","specification":"Blue Bluetooth speaker"},
                delivery_status=scenario.delivery,received_at=received,shipment_refs=[ref+":shipment"],
                investigation_ref=ref+":investigation" if received is None else None,pending_split_delivery=False,
                returnable_quantity=1,exception="NONE_CONFIRMED",exception_source_ref=ref+":exception",is_bundle=False,
                cancelled=False,refunded=False,deadlines=[dict(policy_path_id=path,deadline_at=now+timedelta(days=5),
                    rule_source_ref=ref+":deadline:"+path.value,rule_source_version="synthetic-deadline:1") for path in PolicyPathId])]))
    )
    case.policy_schema_version = "v2"
    case.v2_context_payload = context.model_dump(mode="json")
    return True


def seed_user_risk(sessions, path: Path):
    seed = RiskSeed.model_validate_json(path.read_text())
    with sessions.begin() as session:
        for persona in seed.profiles:
            created = seed.reference_at-timedelta(days=persona.account_age_days)
            profile = session.get(UserRiskProfileRecord,persona.user_ref)
            if profile is None:
                session.add(UserRiskProfileRecord(user_ref=persona.user_ref,account_created_at=created,
                    orders_90d=persona.orders_90d,updated_at=seed.reference_at))
            elif utc(profile.account_created_at) != created or profile.orders_90d != persona.orders_90d:
                raise ValueError("synthetic risk profile changed; use a new version/identity")
            for kind,count in [("CLAIM_REGISTERED",persona.registered_claims),("REFUND_SUCCEEDED",persona.refunded_orders)]:
                for i in range(count):
                    ref = f"synthetic:{persona.user_ref}:{i}"
                    append_risk_event(session,user_ref=persona.user_ref,case_ref=ref,order_ref=ref+":order",event_type=kind,
                        reason_code="ITEM_DAMAGED",occurred_at=seed.reference_at-timedelta(days=i+1))
