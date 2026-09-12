"""Install the small, original synthetic order and metadata set for local demos."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from return_agent_contracts.domain import ApplicableConditions, EvidenceItem, OrderLineItem, OrderSnapshot, PolicyClause

from .db import EvidenceRow, PolicyClauseRow, TrustedOrderRow, make_engine, make_sessions
from .settings import Settings


def seed_demo(sessions, *, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    delivered = now - timedelta(days=2)
    clause = PolicyClause(clause_id="audio-arrival-damage", policy_version="returns-tw:1", text="台灣音訊商品在送達七日內申請，到貨時已存在可觀察外觀損壞，得依申請品項全額退款。外觀損壞與功能故障分別認定；退回需求須判斷實際檢測或回收價值。", required_claim_ids=["DELIVERY_CONFIRMED", "ORDER_WITHIN_RETURN_WINDOW", "ITEM_PHYSICALLY_DAMAGED", "DAMAGE_PRESENT_ON_ARRIVAL"], allowed_actions=["FULL_REFUND", "DECLINE"], return_policy="MODEL_JUDGMENT", applicable_conditions=ApplicableConditions(markets=["TW"], categories=["audio"], reason_codes=["ITEM_DAMAGED"]), effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with sessions.begin() as session:
        if session.get(PolicyClauseRow, (clause.clause_id, clause.policy_version)) is None:
            session.add(PolicyClauseRow(clause_id=clause.clause_id, policy_version=clause.policy_version, payload=clause.model_dump(mode="json")))
        for label, amount in (("A", "1200"), ("B", "6200"), ("C", "6800")):
            order_ref, item_ref = f"DEMO-{label}", f"DEMO-{label}-ITEM"
            if session.get(TrustedOrderRow, order_ref) is not None:
                continue
            order = OrderSnapshot(order_ref=order_ref, order_snapshot_ref=f"DEMO-{label}-SNAPSHOT-1", snapshot_version=1, currency="TWD", captured_at=now, delivered_at=delivered, refundable_amount_max=Decimal(amount), already_refunded_amount=Decimal("0"), line_items=[OrderLineItem(line_item_id=item_ref, sku_ref=f"DEMO-{label}-SKU", category_ref="audio", title=f"合成音箱 {label}", quantity=1, refundable_amount=Decimal(amount))])
            session.add(TrustedOrderRow(order_ref=order_ref, market="TW", snapshot=order.model_dump(mode="json")))
            summaries = {
                "closeup": "合成影像人工標註：音箱外殼側面有細長裂痕，未顯示拍攝或拆封時點；畫面無功能測試。",
                "unboxing": "合成影像人工標註：送達當日的連續拆封序列，未開封箱體、取出音箱與外殼同一裂痕出現在連續畫面。未測試內部電路。",
                "overview": "合成影像人工標註：音箱完整外觀與裂痕位置可對照，音箱主體仍完整；没有明顯液體、燃燒或粉碎痕跡。",
                "inspection": "合成影像人工標註：裂痕旁可見可拆卸的外殼螺絲與檢測接點。畫面只能辨識外觀結構，無法確認電路功能、維修費或殘值。",
            }
            for kind, summary in summaries.items():
                ref = f"DEMO-{label}-{kind.upper()}"
                evidence = EvidenceItem(evidence_id=f"EV-{ref}", artifact_ref=ref, type="IMAGE", source="USER", subject=item_ref, extracted_summary=summary, collected_at=delivered)
                session.add(EvidenceRow(artifact_ref=ref, payload=evidence.model_dump(mode="json")))


def main():
    settings = Settings.from_env()
    engine = make_engine(settings)
    try:
        seed_demo(make_sessions(engine))
        print("Synthetic demo orders A/B/C and neutral evidence metadata are installed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
