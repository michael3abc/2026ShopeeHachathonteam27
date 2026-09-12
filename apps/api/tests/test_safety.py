from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from return_agent.app import (
    app,
    require_internal_service,
    verify_handoff,
)
from return_agent.capabilities.safety import (
    SafetyConflictError,
    SafetyProviders,
    SqlAlchemyPolicyBundleRepository,
    SqlAlchemySafetyRepository,
    SqlAlchemyVerificationProvider,
)
from return_agent.db.models import (
    Base,
    HandoffVerificationRecord,
    PolicyRetrievalRecord,
)
from return_agent_contracts.enums import ClaimId, ReasonCode, ResolutionAction
from return_agent_contracts.models import (
    ApplicableConditions,
    CaseContext,
    CaseContextLoadResult,
    EvidenceItem,
    FullRefundProposedDecision,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    OrderLineItem,
    OrderSnapshot,
    PolicyBundle,
    PolicyClause,
    ProposedDecisionHandoff,
    WaivedReturnRequirement,
)
from return_agent_contracts.transport import (
    VerifyHandoffRequest,
    VerifyHandoffResponse,
)
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@dataclass
class CaseProvider:
    result: CaseContextLoadResult
    error: Exception | None = None

    def load_case_context(self, case_ref: str) -> CaseContextLoadResult:
        if self.error is not None:
            raise self.error
        if case_ref != self.result.case_context.case_ref:
            raise LookupError(case_ref)
        return self.result


@dataclass
class EvidenceProvider:
    item: EvidenceItem

    def resolve(self, artifact_ref: str) -> EvidenceItem:
        if artifact_ref != self.item.artifact_ref:
            raise LookupError(artifact_ref)
        return self.item


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _context(*, already_refunded_amount: str = "0") -> CaseContextLoadResult:
    order = OrderSnapshot(
        order_snapshot_ref="ORDER-001@1",
        order_ref="ORDER-001",
        snapshot_version=1,
        captured_at="2026-09-01T10:00:00Z",
        currency="TWD",
        delivered_at="2026-08-30T10:00:00Z",
        line_items=[
            OrderLineItem(
                line_item_id="LI-001",
                sku_ref="SKU-001",
                category_ref="CAT-AUDIO-SPEAKERS",
                title="Speaker",
                quantity=1,
                refundable_amount="1200",
            )
        ],
        refundable_amount_max="1200",
        already_refunded_amount=already_refunded_amount,
    )
    return CaseContextLoadResult(
        case_context=CaseContext(
            case_ref="CASE-001",
            order_ref="ORDER-001",
            market="TW",
            case_opened_at="2026-09-01T10:00:00Z",
            snapshot_version=1,
        ),
        order_snapshot=order,
    )


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="EV-001",
        type="IMAGE",
        source="USER",
        subject="LI-001",
        artifact_ref="artifact://evidence/EV-001",
        extracted_summary="The carton and the cracked speaker are visible.",
        collected_at="2026-09-01T10:05:00Z",
    )


def _bundle() -> PolicyBundle:
    return PolicyBundle(
        policy_bundle_version="bundle:POLICY-001",
        retrieval_status="OK",
        retrieved_at="2026-09-01T10:00:00Z",
        clauses=[
            PolicyClause(
                clause_id="POLICY-001#damaged",
                policy_version="POLICY-001:v1",
                effective_from="2026-01-01T00:00:00Z",
                effective_to=None,
                applicable_conditions=ApplicableConditions(
                    markets=["TW"],
                    reason_codes=[ReasonCode.ITEM_DAMAGED],
                    categories=["CAT-AUDIO-SPEAKERS"],
                ),
                required_claim_ids=[ClaimId.ITEM_PHYSICALLY_DAMAGED],
                allowed_actions=[ResolutionAction.FULL_REFUND],
                return_policy="MODEL_JUDGMENT",
                text="Damaged products may receive a full refund.",
            )
        ],
    )


def _handoff(handoff_id: str = "HANDOFF-001") -> ProposedDecisionHandoff:
    evidence = _evidence()
    return ProposedDecisionHandoff(
        handoff_version="1.0",
        handoff_id=handoff_id,
        case_ref="CASE-001",
        order_snapshot_ref="ORDER-001@1",
        policy_bundle_version="bundle:POLICY-001",
        claim_registry_version="claim-registry:1.0",
        proposed_decision=FullRefundProposedDecision(
            action="FULL_REFUND",
            refund_scope=NonEmptyRefundScope(line_item_ids=["LI-001"]),
            amount="1200",
            currency="TWD",
            reason_code="ITEM_DAMAGED",
            return_decision=ModelJudgmentReturnDecision(
                source="MODEL_JUDGMENT",
                requirement=WaivedReturnRequirement(
                    required=False,
                    reason_code="ITEM_UNSALVAGEABLE",
                ),
            ),
            policy_refs=["POLICY-001#damaged"],
            evidence_refs=[evidence.evidence_id],
        ),
        evidence_bundle=[evidence],
        policy_refs=["POLICY-001#damaged"],
        rationale_summary="The observed damage supports the requested refund.",
        revision_round=0,
        agent_prompt_version="resolver:1.0",
    )


def _providers(
    session_factory: sessionmaker[Session],
    case_provider: CaseProvider,
    *,
    thresholds: dict[str, str] | None = None,
    evidence_provider: EvidenceProvider | None = None,
) -> SafetyProviders:
    repository = SqlAlchemySafetyRepository(session_factory)
    verification = SqlAlchemyVerificationProvider(
        repository,
        case_provider,
        SqlAlchemyPolicyBundleRepository(session_factory),
        evidence_provider or EvidenceProvider(_evidence()),
    )
    return SafetyProviders(verification)


def _store_bundle(session_factory: sessionmaker[Session]) -> None:
    bundle = _bundle()
    with session_factory.begin() as session:
        session.add(
            PolicyRetrievalRecord(
                retrieval_id="policy-retrieval:001",
                request_hash="a" * 64,
                bundle_version=bundle.policy_bundle_version,
                retrieval_status=bundle.retrieval_status.value,
                bundle_payload=bundle.model_dump(mode="json"),
                retrieved_at=datetime(2026, 9, 1, 10, tzinfo=UTC),
            )
        )


def test_verification_is_idempotent_and_recovers_from_unavailable() -> None:
    session_factory = _session_factory()
    _store_bundle(session_factory)
    case_provider = CaseProvider(_context())
    providers = _providers(session_factory, case_provider)
    handoff = _handoff()

    assert providers.verification_provider.verify(handoff).status.value == "PASS"
    assert providers.verification_provider.verify(handoff).status.value == "PASS"
    with session_factory() as session:
        assert len(session.scalars(select(HandoffVerificationRecord)).all()) == 1

    changed = handoff.model_copy(update={"agent_prompt_version": "resolver:2.0"})
    with pytest.raises(SafetyConflictError):
        providers.verification_provider.verify(changed)

    unavailable_handoff = _handoff("HANDOFF-UNAVAILABLE")
    case_provider.error = ConnectionError("context service down")
    assert (
        providers.verification_provider.verify(unavailable_handoff).status.value
        == "UNAVAILABLE"
    )
    case_provider.error = None
    assert (
        providers.verification_provider.verify(unavailable_handoff).status.value
        == "PASS"
    )


def test_verification_fails_for_evidence_or_handoff_violations() -> None:
    session_factory = _session_factory()
    _store_bundle(session_factory)
    mismatched_evidence = _evidence().model_copy(
        update={"extracted_summary": "A different persisted summary."}
    )
    providers = _providers(
        session_factory,
        CaseProvider(_context()),
        evidence_provider=EvidenceProvider(mismatched_evidence),
    )

    evidence_failure = providers.verification_provider.verify(
        _handoff("HANDOFF-EVIDENCE-MISMATCH")
    )
    assert evidence_failure.status.value == "FAIL"
    assert evidence_failure.issues[0].code == "EVIDENCE_METADATA_MISMATCH"

    invalid_handoff = _handoff("HANDOFF-INVALID-AMOUNT").model_copy(
        update={
            "proposed_decision": _handoff()
            .proposed_decision.model_copy(update={"amount": Decimal(1)})
        }
    )
    amount_failure = providers.verification_provider.verify(invalid_handoff)
    assert amount_failure.status.value == "FAIL"
    assert amount_failure.issues[0].code == "HANDOFF_INVALID"

    missing_policy = _handoff("HANDOFF-MISSING-POLICY").model_copy(
        update={"policy_bundle_version": "bundle:MISSING"}
    )
    missing_policy_result = providers.verification_provider.verify(missing_policy)
    assert missing_policy_result.status.value == "FAIL"
    assert missing_policy_result.issues[0].code == "POLICY_BUNDLE_NOT_FOUND"


def test_internal_safety_routes_require_a_token_and_return_contract_envelopes() -> None:
    session_factory = _session_factory()
    _store_bundle(session_factory)
    providers = _providers(session_factory, CaseProvider(_context()))
    original_providers = app.state.safety_providers
    original_token = app.state.internal_service_token
    app.state.safety_providers = providers
    app.state.internal_service_token = "test-service-token"
    request = VerifyHandoffRequest(
        method="VerificationProvider.verify", params={"handoff": _handoff()}
    )
    try:
        request_context = SimpleNamespace(app=app)
        with pytest.raises(HTTPException) as error:
            require_internal_service(request_context, None)  # type: ignore[arg-type]
        assert error.value.status_code == 401

        require_internal_service(  # type: ignore[arg-type]
            request_context,
            "Bearer test-service-token",
        )
        response = verify_handoff(request, None, providers)
        assert response.result.status.value == "PASS"
        assert "/internal/v1/risk" not in app.openapi()["paths"]
    finally:
        app.state.safety_providers = original_providers
        app.state.internal_service_token = original_token


@pytest.mark.asyncio
@pytest.mark.parametrize("path,method", [
    ("/internal/v1/verification", "VerificationProvider.verify"),
])
@pytest.mark.parametrize("token,credential,expected", [
    (None, None, 503),
    ("", "Bearer ", 503),
    ("   ", "Bearer    ", 503),
    ("\t", None, 503),
    ("test-service-token", None, 401),
    ("test-service-token", "Bearer ", 401),
    ("test-service-token", "Bearer wrong", 401),
    ("test-service-token", "Bearer test-service-token ", 401),
    ("test-service-token", "Bearer test-service-token", 200),
])
async def test_safety_http_credentials(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    method: str,
    token: str | None,
    credential: str | None,
    expected: int,
) -> None:
    from return_agent_contracts.models import PassedVerificationResult

    calls: list[str] = []

    class RecordingProviders:
        def verify(self, handoff: ProposedDecisionHandoff):
            calls.append("verify")
            return PassedVerificationResult(
                status="PASS", issues=[], verification_version="test:v1"
            )

    provider = RecordingProviders()
    monkeypatch.setattr(app.state, "internal_service_token", token)
    monkeypatch.setattr(app.state, "safety_providers", SafetyProviders(provider))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            path,
            headers={} if credential is None else {"Authorization": credential},
            json={"method": method, "params": {"handoff": _handoff().model_dump(mode="json")}},
        )
    assert response.status_code == expected
    if expected == 200:
        assert len(calls) == 1
        if method == "VerificationProvider.verify":
            VerifyHandoffResponse.model_validate(response.json())
    else:
        assert calls == []


def test_safety_migration_upgrades_and_downgrades_fresh_sqlite(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'safety.db'}")

    command.upgrade(config, "head")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    assert {"handoff_verifications", "risk_evaluations"}.issubset(
        inspect(engine).get_table_names()
    )
    command.downgrade(config, "base")
    assert not {"handoff_verifications", "risk_evaluations"}.intersection(
        inspect(engine).get_table_names()
    )
