from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import TypeAdapter
from sqlalchemy import delete, func, select

from return_agent_contracts.domain import NonEmptyRefundScope, ReviewerGateConfig
from return_agent_contracts.gates import evaluate_gate
from return_agent_contracts.human import EditReviewDecision, ReviewDecision, ReviewerApprovedResolutionHandoff, HumanEditResolutionHandoff
from return_agent_contracts.providers import ContractConflict, ExecuteRefundRequest, LoadCaseContextParams, ProviderUnavailable, RejectedRefundApplicationResult, RetrievePolicyParams, SubmitHumanReviewParams, VerifyHandoffParams
from return_agent_contracts.public import CreateCaseRequest, HumanReviewPayload

from return_agent.cases import CaseStateConflict
from return_agent.db import CaseRow, CommandOutboxRow, HumanReviewRow, MockRefundReceiptRow, RefundExecutionRow, RefundItemRow, RefundReservationRow
from return_agent.human_review import HumanReviewService, authorized_human_final, proposal_final
from return_agent.refunds import AuthorizationRejected, RefundService, SimulatedRefundApplication



def automatic(trusted, *, items=None, amount="1200", identifier="auto-proposal"):
    caps, _, original, review, _ = trusted
    items = items or ["item-two"]
    proposed = original.proposed_decision.model_copy(update={"amount": Decimal(amount), "refund_scope": NonEmptyRefundScope(line_item_ids=items)})
    handoff = original.model_copy(update={"handoff_id": identifier, "proposed_decision": proposed})
    assert caps.verify(VerifyHandoffParams(handoff=handoff)).status == "PASS"
    final = proposal_final(handoff)
    return ExecuteRefundRequest(resolution_handoff=ReviewerApprovedResolutionHandoff(handoff_id=handoff.handoff_id, case_ref=handoff.case_ref, emitted_at=caps.cases.clock(), execution_blocked=False, outcome_source="REVIEWER_APPROVE", final_decision=final, review_result=review, review_gate=evaluate_gate(final.action, final.amount, final.currency, caps.gates)))


def new_case(trusted):
    caps, params, handoff, review, dossier = trusted
    case_ref = caps.cases.create(CreateCaseRequest(order_ref=params.order_snapshot.order_ref, user_ref="another-synthetic-user", initial_message="相同品項再次申請"))
    context = caps.load_case_context(LoadCaseContextParams(case_ref=case_ref))
    retrieval = RetrievePolicyParams(case_context=context.case_context, order_snapshot=context.order_snapshot, reason_code="ITEM_DAMAGED", claimed_line_item_ids=params.claimed_line_item_ids)
    policy = caps.retrieve_policy(retrieval)
    return caps, retrieval, handoff.model_copy(update={"case_ref": case_ref, "policy_bundle_version": policy.policy_bundle_version}), review, dossier


def pending_human(trusted):
    caps, _, handoff, review, dossier = trusted
    assert caps.verify(VerifyHandoffParams(handoff=handoff)).status == "PASS"
    submission = SubmitHumanReviewParams(handoff=handoff, review=review, dossier=dossier)
    ref = caps.submit_for_review(submission)
    decision = handoff.proposed_decision
    view = TypeAdapter(HumanReviewPayload).validate_python({"case_ref": handoff.case_ref, "handoff_id": handoff.handoff_id, "action": decision.action, "amount": decision.amount, "currency": decision.currency, "refund_scope": decision.refund_scope, "return_decision": decision.return_decision, "dossier": dossier, "rationale_summary": handoff.rationale_summary, "review_result": review, "routing_reason": dossier.routing_reason})
    with caps.sessions.begin() as session:
        case = caps.cases.locked_case(session, handoff.case_ref)
        caps.cases.transition(session, case, "AWAITING_HUMAN_REVIEW", "Test projection of persisted dossier", "await_human_review")
        case.human_review = view.model_dump(mode="json")
    return ref, submission


def edit_decision(handoff_id):
    return EditReviewDecision.model_validate({"decision": "EDIT", "handoff_id": handoff_id, "review_note": "退回檢測仍有價值，保留退回要求並限縮為線材品項。", "generalizable": True, "correction_reason_code": "SCOPE_INCORRECT", "corrected_decision": {"action": "FULL_REFUND", "refund_scope": {"line_item_ids": ["item-two"]}, "return_decision": {"source": "HUMAN_REVIEW", "requirement": {"required": True, "reason_code": "RETURN_REQUIRED_FOR_INSPECTION"}}}})


def test_automatic_refund_applied_and_replay(trusted):
    caps = trusted[0]
    request = automatic(trusted)
    service = RefundService(caps, SimulatedRefundApplication(caps))
    result = service.execute(request)
    assert result.status == "SUCCEEDED" and result.application_result.status == "APPLIED"
    assert service.execute(request) == result == service.get_status(result.execution_ref)
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MockRefundReceiptRow)) == 1
        assert session.scalar(select(func.count()).select_from(RefundItemRow)) == 1
    changed = request.model_copy(update={"resolution_handoff": request.resolution_handoff.model_copy(update={"emitted_at": caps.cases.clock()})})
    with pytest.raises(ContractConflict):
        service.execute(changed)


@pytest.mark.parametrize("forgery", ["missing_gate", "config", "high_amount", "final_amount", "human_source"])
def test_forged_authority_never_applies(trusted, forgery):
    caps = trusted[0]
    request = automatic(trusted, items=["item-one"], amount="6200") if forgery == "high_amount" else automatic(trusted)
    resolution = request.resolution_handoff
    if forgery == "missing_gate":
        resolution = resolution.model_copy(update={"review_gate": None})
    elif forgery == "config":
        resolution = resolution.model_copy(update={"review_gate": resolution.review_gate.model_copy(update={"config_version": "untrusted:2"})})
    elif forgery == "final_amount":
        resolution = resolution.model_copy(update={"final_decision": resolution.final_decision.model_copy(update={"amount": Decimal("2")})})
    elif forgery == "human_source":
        values = resolution.model_dump(mode="python")
        values["outcome_source"] = "HUMAN_APPROVE"
        request = ExecuteRefundRequest.model_validate({"resolution_handoff": values})
        resolution = request.resolution_handoff
    result = RefundService(caps, SimulatedRefundApplication(caps)).execute(ExecuteRefundRequest(resolution_handoff=resolution))
    assert result.status == "REJECTED"
    assert result.application_result.reason_codes == ["REFUND_AUTHORIZATION_REJECTED"]
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MockRefundReceiptRow)) == 0
        assert session.scalar(select(func.count()).select_from(RefundReservationRow)) == 0


def test_application_commit_then_connection_loss_recovers_same_key(trusted):
    caps = trusted[0]
    request = automatic(trusted)

    class DisconnectAfterCommit(SimulatedRefundApplication):
        def apply(self, request):
            super().apply(request)
            raise TimeoutError("synthetic connection loss")

    with pytest.raises(ProviderUnavailable):
        RefundService(caps, DisconnectAfterCommit(caps)).execute(request)
    with caps.sessions() as session:
        execution = session.scalar(select(RefundExecutionRow))
        assert execution.status == "IN_PROGRESS" and execution.application_started_at
        assert session.scalar(select(func.count()).select_from(RefundReservationRow)) == 1
        assert session.scalar(select(func.count()).select_from(RefundItemRow)) == 0
        assert session.scalar(select(func.count()).select_from(MockRefundReceiptRow)) == 1
    competing = automatic(new_case(trusted), identifier="competing-proposal")
    assert RefundService(caps, SimulatedRefundApplication(caps)).execute(competing).status == "REJECTED"
    recovered = RefundService(caps, SimulatedRefundApplication(caps)).execute(request)
    assert recovered.status == "SUCCEEDED"
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MockRefundReceiptRow)) == 1


def test_same_key_concurrency_and_cross_case_item_reservation(trusted):
    caps = trusted[0]
    first = automatic(trusted)
    second = automatic(new_case(trusted), identifier="another-proposal")
    service = RefundService(caps, SimulatedRefundApplication(caps))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(service.execute, [first, first, second]))
    assert results[0] == results[1]
    assert {results[0].status, results[2].status} == {"SUCCEEDED", "REJECTED"}
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(MockRefundReceiptRow)) == 1
        assert session.scalar(select(func.count()).select_from(RefundItemRow)) == 1


def test_multi_item_conflict_rolls_back_all_new_reservations(trusted):
    caps = trusted[0]
    service = RefundService(caps, SimulatedRefundApplication(caps))
    assert service.execute(automatic(trusted)).status == "SUCCEEDED"
    caps.gates = ReviewerGateConfig(thresholds={"TWD": "10000"})
    conflict = automatic(new_case(trusted), items=["item-one", "item-two"], amount="7400", identifier="combined-proposal")
    assert service.execute(conflict).status == "REJECTED"
    with caps.sessions() as session:
        assert [r.line_item_ref for r in session.scalars(select(RefundReservationRow))] == ["item-two"]


def test_lost_reservation_after_attempt_is_integrity_error(trusted):
    caps = trusted[0]
    request = automatic(trusted)

    class NeverReturns:
        def apply(self, request):
            raise TimeoutError("synthetic transport failure")

    service = RefundService(caps, NeverReturns())
    with pytest.raises(ProviderUnavailable):
        service.execute(request)
    with caps.sessions.begin() as session:
        session.execute(delete(RefundReservationRow))
    with pytest.raises(ProviderUnavailable, match="integrity"):
        service.execute(request)


def test_human_edit_atomic_resume_and_execution(trusted):
    caps, _, handoff, review, dossier = trusted
    _, submission = pending_human(trusted)
    result = HumanReviewService(caps).complete(handoff.case_ref, edit_decision(handoff.handoff_id))
    assert result.status == "OBSERVING" and result.human_review is None and result.human_review_result.decision == "EDIT"
    with caps.sessions() as session:
        final = authorized_human_final(caps, session, submission, result.human_review_result)
        assert final.amount == Decimal("1200")
        assert session.scalar(select(func.count()).select_from(CommandOutboxRow)) == 2
    resolution = HumanEditResolutionHandoff(handoff_id=handoff.handoff_id, case_ref=handoff.case_ref, emitted_at=caps.cases.clock(), execution_blocked=False, outcome_source="HUMAN_EDIT", final_decision=final, review_result=review, review_gate=dossier.review_gate)
    assert RefundService(caps, SimulatedRefundApplication(caps)).execute(ExecuteRefundRequest(resolution_handoff=resolution)).status == "SUCCEEDED"
    with pytest.raises(CaseStateConflict):
        HumanReviewService(caps).complete(handoff.case_ref, edit_decision(handoff.handoff_id))


def test_human_scope_stale_handoff_and_rollback(trusted, monkeypatch):
    caps, _, handoff, _, _ = trusted
    pending_human(trusted)
    service = HumanReviewService(caps)
    decision = edit_decision(handoff.handoff_id)
    with pytest.raises(CaseStateConflict):
        service.complete(handoff.case_ref, decision.model_copy(update={"handoff_id": "stale"}))
    changed = decision.corrected_decision.model_copy(update={"refund_scope": NonEmptyRefundScope(line_item_ids=["outside-order"])})
    with pytest.raises(CaseStateConflict):
        service.complete(handoff.case_ref, decision.model_copy(update={"corrected_decision": changed}))
    def fail(*args):
        raise RuntimeError("synthetic outbox failure")
    monkeypatch.setattr(caps.cases, "enqueue", fail)
    with pytest.raises(RuntimeError):
        service.complete(handoff.case_ref, decision)
    with caps.sessions() as session:
        assert session.scalar(select(HumanReviewRow)).result is None
        assert session.get(CaseRow, handoff.case_ref).status == "AWAITING_HUMAN_REVIEW"


def test_application_explicit_rejection_is_terminal_without_payment(trusted):
    caps = trusted[0]
    class RejectApplication:
        calls = 0
        def apply(self, request):
            self.calls += 1
            return RejectedRefundApplicationResult(status="REJECTED", reason_codes=["SIMULATED_DECLINE"], rejected_at=caps.cases.clock())
    application = RejectApplication()
    service = RefundService(caps, application)
    request = automatic(trusted)
    result = service.execute(request)
    assert result.status == "REJECTED" and result.application_result.status == "REJECTED"
    assert service.execute(request) == result and application.calls == 1
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(RefundItemRow)) == 0
        assert session.scalar(select(func.count()).select_from(RefundReservationRow)) == 0


@pytest.mark.parametrize("decision", ["APPROVE", "REJECT"])
def test_human_approve_reject_are_persisted_and_server_authorized(trusted, decision):
    caps, _, handoff, _, _ = trusted
    _, submission = pending_human(trusted)
    request = TypeAdapter(ReviewDecision).validate_python({"decision": decision, "handoff_id": handoff.handoff_id, "review_note": "測試人工獨立裁決"})
    detail = HumanReviewService(caps).complete(handoff.case_ref, request)
    with caps.sessions() as session:
        final = authorized_human_final(caps, session, submission, detail.human_review_result)
    assert final.amount == (Decimal("6200") if decision == "APPROVE" else Decimal("0"))
    assert final.action == ("FULL_REFUND" if decision == "APPROVE" else "DECLINE")
