from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from return_agent_contracts.domain import ApplicableConditions, CaseContext, CaseContextLoadResult, EvidenceItem, OrderLineItem, OrderSnapshot, PassedVerificationResult, PolicyBundle, PolicyClause, ReviewerGateConfig
from return_agent_contracts.messages import AgentStartRequest, AgentUserTurn
from return_agent_service.fake_model import TypedFakeModel
from return_agent_runtime.graph import ReturnRuntime
from return_agent_runtime.ports import RuntimeDependencies


@pytest.fixture
def runtime_scenario():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    order = OrderSnapshot(order_ref="runtime-order", order_snapshot_ref="runtime-snapshot", snapshot_version=1, captured_at=now, delivered_at=now, currency="TWD", refundable_amount_max="1200", already_refunded_amount="0", line_items=[OrderLineItem(line_item_id="runtime-item", sku_ref="runtime-sku", category_ref="audio", title="合成音箱", quantity=1, refundable_amount="1200")])
    context = CaseContext(case_ref="runtime-case", order_ref=order.order_ref, market="TW", case_opened_at=now, snapshot_version=1)
    policy = PolicyBundle(policy_bundle_version="runtime-policy", retrieval_status="OK", retrieved_at=now, clauses=[PolicyClause(clause_id="runtime-clause", policy_version="demo:1", text="送達後品項損壞可全額退款，依情況要求退回檢測。", required_claim_ids=["DELIVERY_CONFIRMED", "ITEM_PHYSICALLY_DAMAGED"], allowed_actions=["FULL_REFUND", "DECLINE"], return_policy="MODEL_JUDGMENT", applicable_conditions=ApplicableConditions(markets=["TW"]), effective_from=now)])
    evidence = EvidenceItem(evidence_id="runtime-evidence", artifact_ref="runtime-artifact", type="IMAGE", source="USER", subject="runtime-item", extracted_summary="合成案例：音箱外殼可見裂痕。", collected_at=now)

    class Providers:
        human_result = None
        submitted = None
        query_calls = 0
        def load_case_context(self, params):
            return CaseContextLoadResult(case_context=context, order_snapshot=self.order)
        def retrieve_policy(self, params):
            return policy
        def resolve(self, params):
            if params.artifact_ref != evidence.artifact_ref:
                raise ValueError("Unknown artifact")
            return evidence
        def verify(self, params):
            return PassedVerificationResult(status="PASS", verification_version="verification:1.0")
        def submit_for_review(self, params):
            self.submitted = params
            return "runtime-human-review"
        def fetch_result(self, params):
            return self.human_result
        def query_approved(self, params):
            self.query_calls += 1
            return []
    providers = Providers()
    providers.order = order
    model = TypedFakeModel()
    deps = RuntimeDependencies(model=model, context=providers, policy=providers, evidence=providers, verification=providers, human=providers, memory=providers, clock=lambda: now, gates=ReviewerGateConfig())
    saver = InMemorySaver()
    runtime = ReturnRuntime(deps, saver)
    request = AgentStartRequest(case_ref=context.case_ref, thread_id="runtime-thread", order_ref=order.order_ref, initial_turn=AgentUserTurn(turn_id="runtime-turn", role="USER", text="音箱外殼有裂痕，希望退款。", received_at=now, attached_artifact_refs=[evidence.artifact_ref]))
    return SimpleNamespace(runtime=runtime, deps=deps, saver=saver, request=request, model=model, providers=providers, now=now, order=order, context=context, policy=policy, evidence=evidence)
