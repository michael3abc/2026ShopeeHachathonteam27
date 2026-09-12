"""New synthetic examples; no imported reference fixtures or source data."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from return_agent_contracts.domain import (
    ApplicableConditions, ApprovedReviewResult, CaseContext, ClaimFinding,
    EvidenceItem, FullRefundProposedDecision, ModelJudgmentReturnDecision,
    NonEmptyRefundScope, OrderLineItem, OrderSnapshot, PolicyBundle, PolicyClause,
    ProposedDecisionHandoff, RequiredReturnRequirement,
)
from return_agent_contracts.registry import REGISTRY_VERSION


@pytest.fixture
def scenario():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    context = CaseContext(case_ref="case-test", order_ref="order-test", market="TW", case_opened_at=now, snapshot_version=1)
    order = OrderSnapshot(
        order_ref=context.order_ref, order_snapshot_ref="snapshot-test", snapshot_version=1,
        currency="TWD", captured_at=now, delivered_at=now, refundable_amount_max=Decimal("10000"),
        already_refunded_amount=Decimal("0"),
        line_items=[OrderLineItem(line_item_id=item, sku_ref=f"sku-{item}", category_ref="audio", title="合成測試品項", quantity=1, refundable_amount=Decimal(amount)) for item, amount in [("LI-001", "6200"), ("LI-002", "1200")]],
    )
    policy = PolicyBundle(policy_bundle_version="bundle-test", retrieval_status="OK", retrieved_at=now, clauses=[PolicyClause(
        clause_id="clause-test", policy_version="policy-test:1", text="需確認送達與品項損壞，可依案件判斷是否退回。",
        required_claim_ids=["DELIVERY_CONFIRMED", "ITEM_PHYSICALLY_DAMAGED"], allowed_actions=["FULL_REFUND", "DECLINE"],
        return_policy="MODEL_JUDGMENT", applicable_conditions=ApplicableConditions(markets=["TW"]), effective_from=now,
    )])
    evidence = [EvidenceItem(evidence_id=f"evidence-{item}", artifact_ref=f"artifact-{item}", type="IMAGE", source="USER", subject=item, extracted_summary="合成圖像的外殼可見裂痕；不包含到貨時間結論。", collected_at=now) for item in ("LI-001", "LI-002")]
    findings = [ClaimFinding(claim_id="DELIVERY_CONFIRMED", subject=order.order_ref, status="SUPPORTED", explanation="可信訂單含送達紀錄")]
    findings += [ClaimFinding(claim_id="ITEM_PHYSICALLY_DAMAGED", subject=item, status="SUPPORTED", explanation="外殼裂痕", supporting_evidence_refs=[f"evidence-{item}"]) for item in ("LI-001", "LI-002")]
    handoff = ProposedDecisionHandoff(
        handoff_id="proposal-test-0", handoff_version="1.0", case_ref=context.case_ref,
        agent_prompt_version="reconstruction-resolver:1", claim_registry_version=REGISTRY_VERSION,
        order_snapshot_ref=order.order_snapshot_ref, policy_bundle_version=policy.policy_bundle_version,
        policy_refs=["clause-test"], evidence_bundle=evidence, rationale_summary="依品項判斷全額退款", revision_round=0,
        proposed_decision=FullRefundProposedDecision(action="FULL_REFUND", amount=Decimal("1200"), currency="TWD", reason_code="ITEM_DAMAGED", policy_refs=["clause-test"], evidence_refs=["evidence-LI-002"], refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]), return_decision=ModelJudgmentReturnDecision(source="MODEL_JUDGMENT", requirement=RequiredReturnRequirement(required=True, reason_code="RETURN_REQUIRED_FOR_INSPECTION"))),
    )
    review = ApprovedReviewResult(verdict="APPROVE", reviewed_at=now, reviewer_prompt_version="reconstruction-reviewer:1", reviewer_claim_findings=findings)
    return {"now": now, "context": context, "order": order, "policy": policy, "evidence": evidence, "findings": findings, "claimed": ["LI-001", "LI-002"], "handoff": handoff, "review": review}
