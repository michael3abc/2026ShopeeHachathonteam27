from __future__ import annotations
from return_agent_contracts.review_gates import evaluate_review_gate, ReviewerGateConfig

import json
import os
import runpy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from pathlib import Path
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from return_agent.capabilities.refund import (
    RefundExecutionConflictError,
    RefundExecutionUnavailableError,
    SqlAlchemyRefundExecutionProvider,
)
from return_agent.db.models import (
    Base,
    HandoffVerificationRecord,
    HumanReviewRecord,
    PolicyRetrievalRecord,
    RefundExecutionItemRecord,
    RefundExecutionRecord,
    RefundItemReservation,
)
from return_agent_contracts.enums import (
    OutcomeSource,
    ReasonCode,
    RefundApplicationStatus,
    ResolutionAction,
    VerificationStatus,
)
from return_agent_contracts.models import (
    AgentFullRefundFinalDecision,
    AppliedRefundApplicationResult,
    ApplyRefundRequest,
    ApprovedReviewResult,
    CaseContext,
    CaseContextLoadResult,
    DeclineFinalDecision,
    EmptyRefundScope,
    EvidenceItem,
    ExecuteRefundRequest,
    FullRefundProposedDecision,
    HumanApproveResolutionHandoff,
    HumanEditedFullRefundFinalDecision,
    HumanEditResolutionHandoff,
    HumanRejectResolutionHandoff,
    HumanReviewDossier,
    HumanReviewReturnDecision,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    OrderLineItem,
    OrderSnapshot,
    PassedVerificationResult,
    PolicyBundle,
    ProposedDecisionHandoff,
    RejectedRefundApplicationResult,
    ReviewerApprovedResolutionHandoff,
    RevisedReviewResult,
    WaivedReturnRequirement,
)
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema

TIME = datetime(2026, 9, 8, 10, tzinfo=UTC)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _file_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    postgres_url = os.environ.get("REFUND_TEST_POSTGRES_URL")
    if postgres_url:
        # Dedicated test DB only: each case gets an isolated schema.
        schema = f"refund_test_{uuid4().hex}"
        engine = create_engine(postgres_url)
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine.dispose()
        engine = create_engine(
            postgres_url, connect_args={"options": f"-csearch_path={schema}"}
        )
        Base.metadata.create_all(engine, tables=[
            HandoffVerificationRecord.__table__, HumanReviewRecord.__table__,
            PolicyRetrievalRecord.__table__,
            RefundExecutionRecord.__table__, RefundExecutionItemRecord.__table__,
            RefundItemReservation.__table__,
        ])
        return sessionmaker(bind=engine, expire_on_commit=False)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'refund-concurrency.db'}",
        connect_args={"timeout": 5},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _context() -> CaseContextLoadResult:
    return CaseContextLoadResult(
        case_context=CaseContext(
            case_ref="CASE-001",
            order_ref="ORDER-001",
            market="TW",
            case_opened_at=TIME,
            snapshot_version=1,
        ),
        order_snapshot=OrderSnapshot(
            order_snapshot_ref="ORDER-001@1",
            order_ref="ORDER-001",
            snapshot_version=1,
            captured_at=TIME,
            currency="TWD",
            delivered_at="2026-09-01T10:00:00Z",
            line_items=[
                OrderLineItem(
                    line_item_id="LI-001",
                    sku_ref="SKU-001",
                    category_ref="CAT-AUDIO-HEADPHONES",
                    title="Headphones",
                    quantity=1,
                    refundable_amount="700",
                ),
                OrderLineItem(
                    line_item_id="LI-002",
                    sku_ref="SKU-002",
                    category_ref="CAT-AUDIO-SPEAKERS",
                    title="Speaker",
                    quantity=1,
                    refundable_amount="1200",
                ),
            ],
            refundable_amount_max="1900",
            already_refunded_amount="0",
        ),
    )


def _handoff(handoff_id: str) -> ProposedDecisionHandoff:
    return ProposedDecisionHandoff(
        handoff_version="1.0",
        handoff_id=handoff_id,
        case_ref="CASE-001",
        order_snapshot_ref="ORDER-001@1",
        policy_bundle_version="bundle:POLICY-001",
        claim_registry_version="claim-registry:1.0",
        proposed_decision=FullRefundProposedDecision(
            action=ResolutionAction.FULL_REFUND,
            refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
            amount="1200",
            currency="TWD",
            reason_code=ReasonCode.ITEM_DAMAGED,
            return_decision=ModelJudgmentReturnDecision(
                source="MODEL_JUDGMENT",
                requirement=WaivedReturnRequirement(
                    required=False,
                    reason_code="ITEM_UNSALVAGEABLE",
                ),
            ),
            policy_refs=["POLICY-001#damaged"],
        ),
        policy_refs=["POLICY-001#damaged"],
        evidence_bundle=[EvidenceItem(evidence_id="EV-002", type="IMAGE", source="USER",
            subject="LI-002", artifact_ref="artifact://EV-002", extracted_summary="Visible damage.",
            collected_at=TIME)],
        rationale_summary="The persisted proposal is authorized for refund.",
        revision_round=3,
        agent_prompt_version="resolver:1.0",
    )


def _agent_final(handoff: ProposedDecisionHandoff) -> AgentFullRefundFinalDecision:
    decision = handoff.proposed_decision
    assert isinstance(decision, FullRefundProposedDecision)
    return AgentFullRefundFinalDecision(
        action=decision.action,
        refund_scope=decision.refund_scope,
        amount=decision.amount,
        currency=decision.currency,
        return_decision=decision.return_decision,
        reason_code=decision.reason_code,
    )


def _review(handoff, approved):
    payload = dict(
        verdict="APPROVE" if approved else "REVISE",
        reviewer_claim_findings=[dict(claim_id="ITEM_PHYSICALLY_DAMAGED",
            subject=item, status="SUPPORTED", supporting_evidence_refs=[],
            explanation="Damage is visible.")
            for item in (handoff.proposed_decision.refund_scope.line_item_ids if approved else ["LI-001", "LI-002"])],
        revision_reasons=[] if approved else [dict(code="DECISION_INCONSISTENT",
            subject="LI-002", message="Return rationale needs correction.",
            required_change="Support the return rationale with facts.",
            policy_refs=["POLICY-001#damaged"], evidence_refs=[])],
        reviewer_prompt_version="reviewer:2.0", reviewed_at=TIME,
    )
    return (ApprovedReviewResult if approved else RevisedReviewResult).model_validate(payload)


def _reviewer_approve(handoff: ProposedDecisionHandoff) -> ExecuteRefundRequest:
    return ExecuteRefundRequest(
        resolution_handoff=ReviewerApprovedResolutionHandoff(
            case_ref=handoff.case_ref,
            handoff_id=handoff.handoff_id,
            emitted_at=TIME,
            outcome_source=OutcomeSource.REVIEWER_APPROVE,
            review_gate=evaluate_review_gate(handoff.proposed_decision.action, handoff.proposed_decision.amount, handoff.proposed_decision.currency, ReviewerGateConfig()),
            review_result=_review(handoff, True),
            final_decision=_agent_final(handoff),
            execution_blocked=False,
        )
    )


def _human_approve(handoff: ProposedDecisionHandoff) -> ExecuteRefundRequest:
    return ExecuteRefundRequest(
        resolution_handoff=HumanApproveResolutionHandoff(
            case_ref=handoff.case_ref,
            handoff_id=handoff.handoff_id,
            emitted_at=TIME,
            outcome_source=OutcomeSource.HUMAN_APPROVE,
            review_result=_review(handoff, False),
            final_decision=_agent_final(handoff),
            execution_blocked=False,
        )
    )


def _human_edit(handoff: ProposedDecisionHandoff) -> ExecuteRefundRequest:
    return ExecuteRefundRequest(
        resolution_handoff=HumanEditResolutionHandoff(
            case_ref=handoff.case_ref,
            handoff_id=handoff.handoff_id,
            emitted_at=TIME,
            outcome_source=OutcomeSource.HUMAN_EDIT,
            review_result=_review(handoff, False),
            final_decision=HumanEditedFullRefundFinalDecision(
                action=ResolutionAction.FULL_REFUND,
                refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
                amount="1200",
                currency="TWD",
                return_decision=HumanReviewReturnDecision(
                    source="HUMAN_REVIEW",
                    requirement=WaivedReturnRequirement(
                        required=False,
                        reason_code="ITEM_UNSALVAGEABLE",
                    ),
                ),
                reason_code=ReasonCode.ITEM_DAMAGED,
            ),
            execution_blocked=False,
        )
    )


def _dossier(handoff, review, bundle):
    proposals = [handoff.model_copy(update={"handoff_id": f"{handoff.handoff_id}-round-{i}", "revision_round": i})
                 for i in range(handoff.revision_round)] + [handoff]
    return HumanReviewDossier(
        claim_registry_version=handoff.claim_registry_version,
        claimed_line_item_ids=["LI-001", "LI-002"], order_snapshot=_context().order_snapshot,
        policy_bundle=bundle, proposal_history=proposals, review_history=[review] * len(proposals),
        revision_events=[dict(event_id=f"REV-{p.handoff_id}", case_ref=p.case_ref,
            handoff_before_ref=p.handoff_id, review_result=review, revision_round=i+1, created_at=TIME)
            for i, p in enumerate(proposals[:-1])],
    )


def _seed_authorization(
    session_factory: sessionmaker[Session],
    handoff: ProposedDecisionHandoff,
    route: str,
    human_decision: str = "EDIT",
) -> None:
    payload = handoff.model_dump(mode="json")
    payload_hash = _canonical_hash(payload)
    with session_factory.begin() as session:
        session.add(
            HandoffVerificationRecord(
                verification_id=f"verification:{handoff.handoff_id}",
                handoff_id=handoff.handoff_id,
                payload_hash=payload_hash,
                handoff_payload=payload,
                result_payload=PassedVerificationResult(
                    status=VerificationStatus.PASS,
                    issues=[],
                    verification_version="verification:1.0",
                ).model_dump(mode="json"),
                verification_status=VerificationStatus.PASS.value,
                verification_version="verification:1.0",
                created_at=TIME,
                updated_at=TIME,
            )
        )

        if session.scalar(select(PolicyRetrievalRecord).where(
            PolicyRetrievalRecord.bundle_version == handoff.policy_bundle_version
        )) is None:
            bundle = PolicyBundle.model_validate(dict(
                policy_bundle_version=handoff.policy_bundle_version,
                retrieval_status="OK", retrieved_at=TIME,
                clauses=[dict(clause_id="POLICY-001#damaged", policy_version="policy:1",
                    effective_from="2026-01-01T00:00:00Z", applicable_conditions={},
                    required_claim_ids=["ITEM_PHYSICALLY_DAMAGED"],
                    allowed_actions=["FULL_REFUND"], return_policy="MODEL_JUDGMENT",
                    text="Physical damage supports a scoped full refund.")],
            ))
            session.add(PolicyRetrievalRecord(
                retrieval_id="POLICY-001", request_hash="a" * 64,
                bundle_version=bundle.policy_bundle_version, retrieval_status="OK",
                bundle_payload=bundle.model_dump(mode="json"), retrieved_at=TIME,
            ))
        if route == "HUMAN":
            policy_record = session.scalar(select(PolicyRetrievalRecord).where(
                PolicyRetrievalRecord.bundle_version == handoff.policy_bundle_version
            ))
            bundle = PolicyBundle.model_validate(policy_record.bundle_payload)
            result = dict(decision=human_decision, review_note="Checked manually.",
                          final_resolution_ref="RES-" + handoff.handoff_id,
                          reviewed_at=TIME.isoformat())
            if human_decision == "EDIT":
                result.update(corrected_decision=dict(
                    action="FULL_REFUND", refund_scope={"line_item_ids": ["LI-002"]},
                    return_decision=_human_edit(handoff).resolution_handoff.final_decision.return_decision.model_dump(mode="json"),
                ), correction_reason_code="RETURN_REQUIREMENT_INCORRECT")
            dossier_payload = _dossier(handoff, _review(handoff, False), bundle).model_dump(mode="json")
            session.add(HumanReviewRecord(
                review_ref="REVIEW-" + handoff.handoff_id,
                handoff_id=handoff.handoff_id, case_ref=handoff.case_ref,
                payload_hash=_canonical_hash({"handoff":payload,"review":_review(handoff, False).model_dump(mode="json"), "dossier": dossier_payload}),
                handoff_payload=payload, review_payload=_review(handoff, False).model_dump(mode="json"),
                dossier_payload=dossier_payload,
                result_payload=result, submitted_at=TIME, reviewed_at=TIME,
            ))


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
class ApplicationProvider:
    timeout_once: bool = False
    malformed: bool = False
    rejected: bool = False
    calls: list[ApplyRefundRequest] = field(default_factory=list)
    applied_effects: list[str] = field(default_factory=list)
    _results: dict[str, object] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def apply(self, request: ApplyRefundRequest) -> object:
        with self._lock:
            self.calls.append(request)
            if self.timeout_once:
                self.timeout_once = False
                raise TimeoutError("Allen did not return a response")
            if self.malformed:
                return {"status": "APPLIED"}
            existing = self._results.get(request.execution_ref)
            if existing is not None:
                return existing
            if self.rejected:
                result: object = RejectedRefundApplicationResult(
                    status=RefundApplicationStatus.REJECTED,
                    reason_codes=["ORDER_STATE_CHANGED"],
                    rejected_at=TIME,
                )
            else:
                self.applied_effects.append(request.execution_ref)
                result = AppliedRefundApplicationResult(
                    status=RefundApplicationStatus.APPLIED,
                    application_ref=f"application:{request.execution_ref}",
                    applied_at=TIME,
                )
            self._results[request.execution_ref] = result
            return result


def _provider(
    session_factory: sessionmaker[Session],
    application: ApplicationProvider,
) -> SqlAlchemyRefundExecutionProvider:
    return SqlAlchemyRefundExecutionProvider(
        session_factory,
        CaseProvider(_context()),
        application,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("tamper", ["missing", "version", "hash", "amount", "config"])
def test_auto_refund_rejects_invalid_gate_before_mutation(tamper: str) -> None:
    factory = _session_factory()
    handoff = _handoff("HANDOFF-GATE")
    _seed_authorization(factory, handoff, "AUTO")
    application = ApplicationProvider()
    request = _reviewer_approve(handoff)
    gate = request.resolution_handoff.review_gate
    assert gate is not None
    changes = {"version": {"config_version": "stale:0"},
               "hash": {"config_hash": "0" * 64},
               "amount": {"amount": Decimal("0")}}
    if tamper != "config":
        gate = None if tamper == "missing" else gate.model_copy(update=changes[tamper])
        request = request.model_copy(update={"resolution_handoff": request.resolution_handoff.model_copy(update={"review_gate": gate})})
    provider = SqlAlchemyRefundExecutionProvider(factory, CaseProvider(_context()), application,
        reviewer_gate_config=ReviewerGateConfig(version="changed:2") if tamper == "config" else ReviewerGateConfig())
    result = provider.execute(request)
    assert result.status.value == "REJECTED"
    assert application.calls == []


def test_auto_refund_is_idempotent_and_persists_successful_items() -> None:
    session_factory = _session_factory()
    handoff = _handoff("HANDOFF-AUTO")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)
    request = _reviewer_approve(handoff)

    first = provider.execute(request)
    replay = provider.execute(request)

    assert first.status.value == "SUCCEEDED"
    assert replay == first
    assert len(application.calls) == 1
    assert application.applied_effects == [first.execution_ref]
    assert provider.get_status(first.execution_ref) == first
    assert provider.get_status("refund:missing") is None
    with session_factory() as session:
        items = session.scalars(select(RefundExecutionItemRecord)).all()
        assert [(item.order_ref, item.line_item_ref) for item in items] == [
            ("ORDER-001", "LI-002")
        ]

    changed_resolution = request.resolution_handoff.model_copy(
        update={"emitted_at": datetime(2026, 9, 8, 11, tzinfo=UTC)}
    )
    changed = request.model_copy(update={"resolution_handoff": changed_resolution})
    with pytest.raises(RefundExecutionConflictError):
        provider.execute(changed)


def test_human_approval_and_edit_rejects_substituted_scope() -> None:
    session_factory = _session_factory()
    approved_handoff = _handoff("HANDOFF-HUMAN-APPROVE")
    edited_handoff = _handoff("HANDOFF-HUMAN-EDIT")
    _seed_authorization(session_factory, approved_handoff, "HUMAN", "APPROVE")
    _seed_authorization(session_factory, edited_handoff, "HUMAN")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)

    approved = provider.execute(_human_approve(approved_handoff))
    edited_request = _human_edit(edited_handoff).model_dump(mode="json")
    edited_request["resolution_handoff"]["final_decision"].update(
        refund_scope={"line_item_ids": ["LI-001"]}, amount="700"
    )
    edited = provider.execute(ExecuteRefundRequest.model_validate(edited_request))

    assert approved.status.value == "SUCCEEDED"
    assert edited.status.value == "REJECTED"
    assert edited.application_result.reason_codes == ["HUMAN_REVIEW_NOT_AUTHORIZED"]
    assert len(application.calls) == 1
    assert len(application.applied_effects) == 1
    with session_factory() as session:
        items = session.scalars(
            select(RefundExecutionItemRecord).order_by(
                RefundExecutionItemRecord.line_item_ref
            )
        ).all()
        assert [item.line_item_ref for item in items] == ["LI-002"]


@pytest.mark.parametrize("original_scope,scope,amount,currency,reason", [
    (["LI-002"], ["LI-002"], "1200", "TWD", None),
    (["LI-001", "LI-002"], ["LI-002"], "1200", "TWD", None),
    (["LI-002"], ["LI-001", "LI-002"], "1900", "TWD", "HUMAN_REVIEW_NOT_AUTHORIZED"),
    (["LI-002"], ["UNKNOWN"], "1200", "TWD", "HUMAN_REVIEW_NOT_AUTHORIZED"),
    (["LI-002"], ["LI-002"], "1", "TWD", "REFUND_AMOUNT_MISMATCH"),
    (["LI-002"], ["LI-002"], "1200", "USD", "REFUND_CURRENCY_MISMATCH"),
])
def test_human_edit_authorized_scope(
    original_scope: list[str], scope: list[str], amount: str, currency: str,
    reason: str | None,
) -> None:
    session_factory = _session_factory()
    payload = _handoff("HANDOFF-EDIT-SCOPE").model_dump(mode="json")
    payload["proposed_decision"]["refund_scope"] = {"line_item_ids": original_scope}
    payload["proposed_decision"]["amount"] = "1900" if len(original_scope) == 2 else "1200"
    handoff = ProposedDecisionHandoff.model_validate(payload)
    _seed_authorization(session_factory, handoff, "HUMAN")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)
    request = _human_edit(handoff).model_dump(mode="json")
    request["resolution_handoff"]["final_decision"].update(
        refund_scope={"line_item_ids": scope}, amount=amount, currency=currency
    )
    result = provider.execute(ExecuteRefundRequest.model_validate(request))
    if reason is None:
        assert result.status.value == "SUCCEEDED"
        assert len(application.calls) == 1
    else:
        assert result.status.value == "REJECTED"
        assert result.application_result.reason_codes == [reason]
        assert application.calls == []
        with session_factory() as session:
            assert session.scalars(select(RefundItemReservation)).all() == []


def test_rejections_never_call_allens_mutation_adapter() -> None:
    session_factory = _session_factory()
    auto_handoff = _handoff("HANDOFF-REJECT-AUTO")
    human_handoff = _handoff("HANDOFF-REJECT-HUMAN")
    _seed_authorization(session_factory, auto_handoff, "AUTO")
    _seed_authorization(session_factory, human_handoff, "HUMAN")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)

    altered = _reviewer_approve(auto_handoff).model_copy(
        update={
            "resolution_handoff": _reviewer_approve(auto_handoff)
            .resolution_handoff.model_copy(
                update={
                    "final_decision": _agent_final(auto_handoff).model_copy(
                        update={"amount": Decimal("1")}
                    )
                }
            )
        }
    )
    mismatch = provider.execute(altered)
    assert mismatch.status.value == "REJECTED"
    assert mismatch.application_result.reason_codes == ["FINAL_DECISION_MISMATCH"]

    blocked = _reviewer_approve(auto_handoff)
    blocked = blocked.model_copy(update={"resolution_handoff":
        blocked.resolution_handoff.model_copy(update={
            "handoff_id": "HANDOFF-BLOCKED", "execution_blocked": True,
        })})
    blocked_result = provider.execute(blocked)
    assert blocked_result.status.value == "REJECTED"
    assert blocked_result.application_result.reason_codes == ["EXECUTION_BLOCKED"]

    declined = ExecuteRefundRequest(
        resolution_handoff=HumanRejectResolutionHandoff(
            case_ref=auto_handoff.case_ref,
            handoff_id="HANDOFF-DECLINED",
            emitted_at=TIME,
            outcome_source=OutcomeSource.HUMAN_REJECT,
            review_result=_review(auto_handoff, False),
            final_decision=DeclineFinalDecision(
                action=ResolutionAction.DECLINE,
                refund_scope=EmptyRefundScope(),
                amount="0",
                currency="TWD",
                reason_code=ReasonCode.ITEM_DAMAGED,
            ),
            execution_blocked=False,
        )
    )
    declined_result = provider.execute(declined)
    assert declined_result.status.value == "REJECTED"
    assert declined_result.application_result.reason_codes == [
        "FINAL_DECISION_DECLINED"
    ]

    missing_authorization = provider.execute(_reviewer_approve(_handoff("HANDOFF-MISSING")))
    assert missing_authorization.status.value == "REJECTED"
    assert missing_authorization.application_result.reason_codes == [
        "AUTHORIZATION_NOT_FOUND"
    ]

    invalid_edit = _human_edit(human_handoff).model_copy(
        update={
            "resolution_handoff": _human_edit(human_handoff)
            .resolution_handoff.model_copy(
                update={
                    "final_decision": _human_edit(human_handoff)
                    .resolution_handoff.final_decision.model_copy(
                        update={"amount": Decimal("1")}
                    )
                }
            )
        }
    )
    invalid_edit_result = provider.execute(invalid_edit)
    assert invalid_edit_result.status.value == "REJECTED"
    assert invalid_edit_result.application_result.reason_codes == [
        "REFUND_AMOUNT_MISMATCH"
    ]
    assert application.calls == []


def test_allen_rejection_is_persisted_as_a_terminal_public_result() -> None:
    session_factory = _session_factory()
    handoff = _handoff("HANDOFF-ALLEN-REJECTED")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider(rejected=True)
    provider = _provider(session_factory, application)

    result = provider.execute(_reviewer_approve(handoff))

    assert result.status.value == "REJECTED"
    assert result.application_result.reason_codes == ["ORDER_STATE_CHANGED"]
    assert provider.execute(_reviewer_approve(handoff)) == result
    assert len(application.calls) == 1


def test_unavailable_application_is_replayed_with_the_same_execution_ref() -> None:
    session_factory = _session_factory()
    handoff = _handoff("HANDOFF-RETRY")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider(timeout_once=True)
    provider = _provider(session_factory, application)
    request = _reviewer_approve(handoff)

    with pytest.raises(RefundExecutionUnavailableError):
        provider.execute(request)
    pending_ref = application.calls[0].execution_ref
    with pytest.raises(RefundExecutionUnavailableError):
        provider.get_status(pending_ref)

    completed = provider.execute(request)
    assert completed.status.value == "SUCCEEDED"
    assert completed.execution_ref == pending_ref
    assert [call.execution_ref for call in application.calls] == [
        pending_ref,
        pending_ref,
    ]
    assert application.applied_effects == [pending_ref]


def test_concurrent_replay_has_one_canonical_refund_effect(tmp_path: Path) -> None:
    session_factory = _file_session_factory(tmp_path)
    handoff = _handoff("HANDOFF-CONCURRENT")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)
    request = _reviewer_approve(handoff)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: provider.execute(request), range(2)))

    assert {result.execution_ref for result in results} == {results[0].execution_ref}
    assert {result.status.value for result in results} == {"SUCCEEDED"}
    assert application.applied_effects == [results[0].execution_ref]
    with session_factory() as session:
        assert len(session.scalars(select(RefundExecutionRecord)).all()) == 1
        assert len(session.scalars(select(RefundExecutionItemRecord)).all()) == 1


@pytest.mark.parametrize("concurrent", [False, True])
def test_different_handoffs_reserve_before_mutation(tmp_path: Path, concurrent: bool) -> None:
    sessions = _file_session_factory(tmp_path)
    handoffs = [_handoff(f"HANDOFF-RESERVE-{index}") for index in range(2)]
    for handoff in handoffs:
        _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    barrier = Barrier(2)

    def execute(handoff: ProposedDecisionHandoff):
        if concurrent:
            barrier.wait(timeout=5)
        return _provider(sessions, application).execute(_reviewer_approve(handoff))

    if concurrent:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(execute, handoffs))
    else:
        results = list(map(execute, handoffs))
    assert sorted(result.status.value for result in results) == ["REJECTED", "SUCCEEDED"]
    assert len(application.calls) == len(application.applied_effects) == 1
    with sessions() as session:
        reservations = session.scalars(select(RefundItemReservation)).all()
        assert len(reservations) == 1
        assert reservations[0].execution_ref == application.calls[0].execution_ref


def test_partial_overlap_rolls_back_new_reservations() -> None:
    sessions = _session_factory()
    first = _handoff("HANDOFF-FIRST")
    payload = _handoff("HANDOFF-OVERLAP").model_dump(mode="json")
    payload["proposed_decision"].update(
        refund_scope={"line_item_ids": ["LI-001", "LI-002"]}, amount="1900"
    )
    second = ProposedDecisionHandoff.model_validate(payload)
    for handoff in (first, second):
        _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(sessions, application)
    assert provider.execute(_reviewer_approve(first)).status.value == "SUCCEEDED"
    assert provider.execute(_reviewer_approve(second)).status.value == "REJECTED"
    with sessions() as session:
        reservations = session.scalars(select(RefundItemReservation)).all()
        assert [item.line_item_ref for item in reservations] == ["LI-002"]
    assert len(application.calls) == 1


def test_disjoint_scopes_proceed_concurrently(tmp_path: Path) -> None:
    sessions = _file_session_factory(tmp_path)
    first = _handoff("HANDOFF-DISJOINT-1")
    payload = _handoff("HANDOFF-DISJOINT-2").model_dump(mode="json")
    payload["proposed_decision"].update(
        refund_scope={"line_item_ids": ["LI-001"]}, amount="700"
    )
    second = ProposedDecisionHandoff.model_validate(payload)
    for handoff in (first, second):
        _seed_authorization(sessions, handoff, "AUTO")
    barrier = Barrier(2)
    application = ApplicationProvider()

    class ConcurrentApplication:
        def apply(self, request: ApplyRefundRequest):
            # Both calls must reach the external boundary without waiting for
            # the other execution to finish its mutation.
            barrier.wait(timeout=5)
            return application.apply(request)

    provider = SqlAlchemyRefundExecutionProvider(
        sessions, CaseProvider(_context()), ConcurrentApplication()
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(provider.execute, map(_reviewer_approve, (first, second))))
    assert all(result.status.value == "SUCCEEDED" for result in results)
    assert len(application.applied_effects) == 2


def test_crash_after_reservation_before_mutation_is_recoverable() -> None:
    sessions = _session_factory()
    handoff = _handoff("HANDOFF-RESERVED-CRASH")
    _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(sessions, application)
    request = _reviewer_approve(handoff)
    execution = provider._repository.start_pending(
        execution_ref="execution-before-crash", request=request,
        payload_hash=_canonical_hash(request.model_dump(mode="json")), order_ref="ORDER-001",
    )
    provider._repository.mark_application_started(execution.execution_ref, execution.payload_hash)
    assert application.calls == []
    recovered = _provider(sessions, application).execute(request)
    assert recovered.status.value == "SUCCEEDED"
    assert application.applied_effects == [execution.execution_ref]


def test_database_reservation_failure_never_calls_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = _session_factory()
    handoff = _handoff("HANDOFF-RESERVATION-UNAVAILABLE")
    _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(sessions, application)

    def unavailable(*args: object):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(provider._repository, "mark_application_started", unavailable)
    with pytest.raises(RefundExecutionUnavailableError):
        provider.execute(_reviewer_approve(handoff))
    assert application.calls == []


@pytest.mark.parametrize("outcome", ["rejected", "timeout", "malformed"])
def test_reservation_lifetime_tracks_known_outcome(outcome: str) -> None:
    sessions = _session_factory()
    first, second = _handoff("HANDOFF-LIFETIME-1"), _handoff("HANDOFF-LIFETIME-2")
    for handoff in (first, second):
        _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider(
        rejected=outcome == "rejected", timeout_once=outcome == "timeout",
        malformed=outcome == "malformed",
    )
    provider = _provider(sessions, application)
    if outcome == "rejected":
        assert provider.execute(_reviewer_approve(first)).status.value == "REJECTED"
    else:
        with pytest.raises(RefundExecutionUnavailableError):
            provider.execute(_reviewer_approve(first))
    with sessions() as session:
        assert len(session.scalars(select(RefundItemReservation)).all()) == (
            0 if outcome == "rejected" else 1
        )
    application.rejected = application.malformed = False
    result = provider.execute(_reviewer_approve(second))
    assert result.status.value == ("SUCCEEDED" if outcome == "rejected" else "REJECTED")
    assert len(application.calls) == (2 if outcome == "rejected" else 1)


def test_malformed_application_response_remains_unresolved() -> None:
    session_factory = _session_factory()
    handoff = _handoff("HANDOFF-MALFORMED")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider(malformed=True)
    provider = _provider(session_factory, application)

    with pytest.raises(RefundExecutionUnavailableError):
        provider.execute(_reviewer_approve(handoff))
    with session_factory() as session:
        execution = session.scalar(select(RefundExecutionRecord))
        assert execution is not None
        assert execution.state == "IN_PROGRESS"
        assert execution.application_result_payload is None


def test_replay_recovers_after_allen_commits_before_local_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = _session_factory()
    handoff = _handoff("HANDOFF-CRASH-RECOVERY")
    _seed_authorization(session_factory, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(session_factory, application)

    def crash_before_local_completion(*_args: object) -> object:
        raise RuntimeError("process crashed after Allen committed")

    monkeypatch.setattr(provider._repository, "complete", crash_before_local_completion)
    with pytest.raises(RefundExecutionUnavailableError):
        provider.execute(_reviewer_approve(handoff))

    recovered_provider = _provider(session_factory, application)
    recovered = recovered_provider.execute(_reviewer_approve(handoff))
    assert recovered.status.value == "SUCCEEDED"
    assert application.applied_effects == [recovered.execution_ref]
    assert [call.execution_ref for call in application.calls] == [
        recovered.execution_ref,
        recovered.execution_ref,
    ]


def test_refund_migration_upgrades_and_downgrades_fresh_sqlite(
    tmp_path: Path,
) -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'refund.db'}")

    command.upgrade(config, "head")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    assert {"refund_executions", "refund_execution_items"}.issubset(
        inspect(engine).get_table_names()
    )
    command.downgrade(config, "base")
    assert not {"refund_executions", "refund_execution_items"}.intersection(
        inspect(engine).get_table_names()
    )


@pytest.mark.parametrize("legacy", ["pending", "success", "overlap", "bad_hash", "missing_ledger"])
def test_reservation_migration_populated_0006(tmp_path: Path, legacy: str) -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'legacy.db'}")
    command.upgrade(config, "0006_refund_execution")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    application = ApplicationProvider()
    provider = _provider(sessions, application)
    for index in range(2 if legacy == "overlap" else 1):
        request = _reviewer_approve(_handoff(f"HANDOFF-LEGACY-{index}"))
        payload = request.model_dump(mode="json")
        provider._repository.start_pending(
            execution_ref=f"execution-legacy-{index}", request=request,
            payload_hash=_canonical_hash(payload), order_ref="ORDER-001",
        )
    with sessions.begin() as session:
        execution = session.get(RefundExecutionRecord, "execution-legacy-0")
        assert execution is not None
        if legacy == "bad_hash":
            execution.payload_hash = "0" * 64
        if legacy in {"success", "missing_ledger"}:
            execution.state = "SUCCEEDED"
            execution.completed_at = TIME
            execution.application_result_payload = AppliedRefundApplicationResult(
                status="APPLIED", application_ref="legacy-application", applied_at=TIME
            ).model_dump(mode="json")
            if legacy == "success":
                session.add(RefundExecutionItemRecord(
                    execution_ref=execution.execution_ref, order_ref="ORDER-001",
                    line_item_ref="LI-002", applied_at=TIME,
                ))
    if legacy in {"overlap", "bad_hash", "missing_ledger"}:
        with pytest.raises(RuntimeError, match="Reservation migration blocked"):
            command.upgrade(config, "head")
        assert "refund_item_reservations" not in inspect(engine).get_table_names()
    else:
        command.upgrade(config, "head")
        with sessions() as session:
            reservation = session.get(RefundItemReservation, ("ORDER-001", "LI-002"))
            assert reservation is not None
            assert reservation.execution_ref == "execution-legacy-0"
        command.downgrade(config, "0006_refund_execution")
        assert "refund_item_reservations" not in inspect(engine).get_table_names()
    assert application.calls == []


@pytest.mark.parametrize("overlap", [False, True])
def test_reservation_migration_on_database(tmp_path: Path, overlap: bool) -> None:
    sessions = _file_session_factory(tmp_path)
    engine = sessions.kw["bind"]
    # This factory creates only isolated test tables/schema.
    RefundItemReservation.__table__.drop(engine)
    provider = _provider(sessions, ApplicationProvider())
    for index in range(2 if overlap else 1):
        request = _reviewer_approve(_handoff(f"HANDOFF-MIGRATION-{index}"))
        provider._repository.start_pending(
            execution_ref=f"migration-{index}", request=request,
            payload_hash=_canonical_hash(request.model_dump(mode="json")),
            order_ref="ORDER-001",
        )
    migration = runpy.run_path(str(
        Path(__file__).resolve().parents[1] / "alembic/versions/0007_refund_item_reservations.py"
    ))
    if overlap:
        with pytest.raises(RuntimeError, match="overlapping executions"):
            with engine.begin() as connection:
                with Operations.context(MigrationContext.configure(connection)):
                    migration["upgrade"]()
    else:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
        with sessions() as session:
            reservation = session.get(RefundItemReservation, ("ORDER-001", "LI-002"))
            assert reservation is not None
            assert reservation.execution_ref == "migration-0"


def test_offline_postgres_sql_requires_online_preflight_for_populated_database() -> None:
    migration = runpy.run_path(str(
        Path(__file__).resolve().parents[1] / "alembic/versions/0007_refund_item_reservations.py"
    ))
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        migration["upgrade"]()
    sql = output.getvalue()
    assert "requires online Alembic preflight" in sql
    assert sql.index("RAISE EXCEPTION") < sql.index("CREATE TABLE")
    assert "json_array_elements_text" in sql
