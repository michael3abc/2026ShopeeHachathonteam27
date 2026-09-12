"""Each integration test owns a fresh, explicitly named PostgreSQL schema."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from return_agent.cases import CaseStore
from return_agent.db import make_engine, make_sessions
from return_agent.settings import Settings
from datetime import datetime, timezone
from decimal import Decimal
from return_agent_contracts.domain import ApprovedReviewResult, ClaimFinding, EvidenceItem, FullRefundProposedDecision, HumanReviewDossier, ModelJudgmentReturnDecision, NonEmptyRefundScope, OrderLineItem, OrderSnapshot, PolicyClause, ApplicableConditions, ProposedDecisionHandoff, RequiredReturnRequirement
from return_agent_contracts.gates import evaluate_gate
from return_agent_contracts.providers import LoadCaseContextParams, RetrievePolicyParams
from return_agent_contracts.public import CreateCaseRequest
from return_agent_contracts.registry import REGISTRY_VERSION
from return_agent.capabilities import CapabilityStore
from return_agent.db import EvidenceRow, PolicyClauseRow, TrustedOrderRow


@pytest.fixture
def database():
    url = os.getenv("TEST_API_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_API_DATABASE_URL to an isolated local test database")
    settings = Settings(profile="integrated-demo", database_url=url)
    schema = f"team27_test_{uuid4().hex}"
    admin = make_engine(settings)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = make_engine(settings, schema=schema)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            # Public may already be at head; that must never skip this schema's migration.
            assert connection.exec_driver_sql("SELECT current_schema()").scalar_one() == schema
            assert {"cases", "case_events", "agent_command_outbox", "alembic_version"} <= set(inspect(connection).get_table_names(schema=schema))
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def store(database):
    return CaseStore(make_sessions(database[0]))


@pytest.fixture
def trusted(store):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    order = OrderSnapshot(order_ref="synthetic-order", order_snapshot_ref="synthetic-snapshot", snapshot_version=1, currency="TWD", captured_at=now, delivered_at=now, refundable_amount_max="9000", already_refunded_amount="0", line_items=[OrderLineItem(line_item_id="item-one", sku_ref="sku-speaker", category_ref="audio", title="測試音箱", quantity=1, refundable_amount="6200"), OrderLineItem(line_item_id="item-two", sku_ref="sku-cable", category_ref="audio", title="測試線材", quantity=1, refundable_amount="1200")])
    clause = PolicyClause(clause_id="damage-policy", policy_version="demo:1", text="送達後若品項外觀損壞可退款；退回需求依個案判斷。", required_claim_ids=["DELIVERY_CONFIRMED", "ITEM_PHYSICALLY_DAMAGED"], allowed_actions=["FULL_REFUND", "DECLINE"], return_policy="MODEL_JUDGMENT", applicable_conditions=ApplicableConditions(markets=["TW"], reason_codes=["ITEM_DAMAGED"]), effective_from=now)
    evidence = [EvidenceItem(evidence_id=f"evidence-{item}", artifact_ref=f"artifact-{item}", type="IMAGE", source="USER", subject=item, extracted_summary="合成測試描述：物件外殼表面有裂痕。", collected_at=now) for item in ("item-one", "item-two")]
    with store.sessions.begin() as session:
        session.add(TrustedOrderRow(order_ref=order.order_ref, market="TW", snapshot=order.model_dump(mode="json")))
        session.add(PolicyClauseRow(clause_id=clause.clause_id, policy_version=clause.policy_version, payload=clause.model_dump(mode="json")))
        for item in evidence:
            session.add(EvidenceRow(artifact_ref=item.artifact_ref, payload=item.model_dump(mode="json")))
    ref = store.create(CreateCaseRequest(order_ref=order.order_ref, user_ref="synthetic-user", initial_message="音箱與線材外殼有裂痕", attached_artifact_refs=[item.artifact_ref for item in evidence]))
    capabilities = CapabilityStore(store)
    loaded = capabilities.load_case_context(LoadCaseContextParams(case_ref=ref))
    params = RetrievePolicyParams(case_context=loaded.case_context, order_snapshot=loaded.order_snapshot, reason_code="ITEM_DAMAGED", claimed_line_item_ids=["item-one", "item-two"])
    policy = capabilities.retrieve_policy(params)
    handoff = ProposedDecisionHandoff(handoff_id="proposal-one", handoff_version="1.0", case_ref=ref, agent_prompt_version="resolver:1", claim_registry_version=REGISTRY_VERSION, order_snapshot_ref=order.order_snapshot_ref, policy_bundle_version=policy.policy_bundle_version, policy_refs=[clause.clause_id], evidence_bundle=evidence, rationale_summary="依可見損壞評估退款", revision_round=0, proposed_decision=FullRefundProposedDecision(action="FULL_REFUND", amount="6200", currency="TWD", reason_code="ITEM_DAMAGED", policy_refs=[clause.clause_id], evidence_refs=[evidence[0].evidence_id], refund_scope=NonEmptyRefundScope(line_item_ids=["item-one"]), return_decision=ModelJudgmentReturnDecision(source="MODEL_JUDGMENT", requirement=RequiredReturnRequirement(required=True, reason_code="RETURN_REQUIRED_FOR_INSPECTION"))))
    review = ApprovedReviewResult(verdict="APPROVE", reviewed_at=store.clock(), reviewer_prompt_version="reviewer:1", reviewer_claim_findings=[ClaimFinding(claim_id="DELIVERY_CONFIRMED", subject=order.order_ref, status="SUPPORTED", explanation="訂單含送達日期"), *[ClaimFinding(claim_id="ITEM_PHYSICALLY_DAMAGED", subject=item.subject, status="SUPPORTED", explanation="表面有裂痕", supporting_evidence_refs=[item.evidence_id]) for item in evidence]])
    dossier = HumanReviewDossier(claim_registry_version=REGISTRY_VERSION, claimed_line_item_ids=params.claimed_line_item_ids, order_snapshot=order, policy_bundle=policy, proposal_history=[handoff], review_history=[review], review_gate=evaluate_gate("FULL_REFUND", Decimal("6200"), "TWD", capabilities.gates), routing_reason="HIGH_VALUE_ITEM")
    return capabilities, params, handoff, review, dossier


@pytest.fixture
def agent_database():
    from return_agent_service.db import make_engine as agent_engine
    from return_agent_service.checkpoint import checkpoint_saver
    url = os.getenv("TEST_AGENT_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_AGENT_DATABASE_URL for durable Agent integration")
    schema = f"team27_agent_test_{uuid4().hex}"
    admin = agent_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = agent_engine(url, schema=schema)
    config = Config(str(Path(__file__).parents[2] / "agent_service" / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with checkpoint_saver(url, schema=schema, setup=True):
            pass
        yield engine, url, schema
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def test_redis():
    from redis import Redis
    from return_agent_contracts.messages import COMMAND_STREAM, EVENT_STREAM, COMMAND_DLQ
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TEST_REDIS_URL to an empty, test-only Redis database")
    client = Redis.from_url(url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
    assert client.dbsize() == 0, "Test Redis database must be empty; no data was removed"
    try:
        yield client
    finally:
        # Delete only the three streams these integration tests own.
        client.delete(COMMAND_STREAM, EVENT_STREAM, COMMAND_DLQ)
        client.close()
