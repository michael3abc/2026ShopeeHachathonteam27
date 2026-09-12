"""Regression coverage for Reviewer-based human handoff and execution safety."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from return_agent.capabilities.human_review import (
    HumanReviewConflictError,
    SqlAlchemyHumanReviewProvider,
)
from return_agent.db.models import HumanReviewRecord, PolicyRetrievalRecord
from return_agent_contracts.enums import ClaimStatus
from return_agent_contracts.models import (
    HumanReviewDossier,
    OrderSnapshot,
    PolicyBundle,
)
from return_agent_contracts.ui import ApproveReviewDecision
from sqlalchemy import create_engine, select, text

from .test_refund_execution import (
    TIME,
    ApplicationProvider,
    CaseProvider,
    _context,
    _handoff,
    _human_approve,
    _provider,
    _review,
    _reviewer_approve,
    _seed_authorization,
    _session_factory,
)


def test_first_approved_proposal_requires_durable_amount_authorization():
    from return_agent_contracts.review_gates import ReviewerGateConfig, evaluate_review_gate
    from return_agent.capabilities.refund import SqlAlchemyRefundExecutionProvider
    from .test_refund_execution import _dossier

    sessions = _session_factory()
    config = ReviewerGateConfig(thresholds={"TWD": "1"})
    handoff = _handoff("HANDOFF-AMOUNT").model_copy(update={"revision_round": 0})
    review = _review(handoff, True)
    _seed_authorization(sessions, handoff, "AUTO")
    with sessions() as session:
        bundle = PolicyBundle.model_validate(session.scalar(select(PolicyRetrievalRecord)).bundle_payload)
    decision = handoff.proposed_decision
    gate = evaluate_review_gate(decision.action, decision.amount, decision.currency, config)
    dossier = _dossier(handoff, review, bundle).model_copy(update={
        "proposal_history": [handoff], "review_history": [review], "revision_events": [],
        "claimed_line_item_ids": ["LI-002"],
        "routing_reason": gate.reason, "review_gate": gate})
    dossier = HumanReviewDossier.model_validate(dossier.model_dump(mode="json"))
    provider = SqlAlchemyHumanReviewProvider(sessions, CaseProvider(_context()), reviewer_gate_config=config)
    ref = provider.submit_for_review(handoff, review, dossier)
    assert provider.submit_for_review(handoff, review, dossier) == ref
    with pytest.raises(HumanReviewConflictError):
        SqlAlchemyHumanReviewProvider(sessions, CaseProvider(_context())).submit_for_review(handoff, review, dossier)
    with sessions.begin() as session:
        result = provider.complete_for_case(session, case_ref=handoff.case_ref, decision=ApproveReviewDecision(
            decision="APPROVE", handoff_id=handoff.handoff_id, review_note="Authorize this refund."))
    assert provider.fetch_result(ref) == result
    request = _human_approve(handoff)
    request = request.model_copy(update={"resolution_handoff": request.resolution_handoff.model_copy(update={
        "review_result": review, "review_gate": gate})})
    application = ApplicationProvider()
    execution = SqlAlchemyRefundExecutionProvider(sessions, CaseProvider(_context()), application, reviewer_gate_config=config)
    response = execution.execute(request)
    assert response.status.value == "SUCCEEDED", response.model_dump(mode="json")
    assert execution.execute(request) == response
    assert len(application.calls) == 1


def test_human_submission_requires_exhausted_revisions_and_preserves_objections():
    sessions = _session_factory()
    provider = SqlAlchemyHumanReviewProvider(sessions, CaseProvider(_context()))
    handoff = _handoff("HANDOFF-REVIEW")
    review = _review(handoff, False)
    _seed_authorization(sessions, handoff, "AUTO")
    with sessions() as session:
        bundle = PolicyBundle.model_validate(session.scalar(select(PolicyRetrievalRecord)).bundle_payload)
    from .test_refund_execution import _dossier
    dossier = _dossier(handoff, review, bundle)
    for round_number in (0, 1, 2):
        with pytest.raises(HumanReviewConflictError):
            provider.submit_for_review(
                handoff.model_copy(update={"revision_round": round_number}), review
            )
    with pytest.raises(HumanReviewConflictError):
        provider.submit_for_review(handoff, _review(handoff, True))
    ref = provider.submit_for_review(handoff, review, dossier)
    assert provider.submit_for_review(handoff, review, dossier) == ref
    assert provider.fetch_result(ref) is None
    with sessions() as session:
        record = session.get(HumanReviewRecord, ref)
        assert record.review_payload == review.model_dump(mode="json")
        assert session.query(HumanReviewRecord).count() == 1
    changed = review.model_copy(update={"reviewer_prompt_version": "changed"})
    with pytest.raises(HumanReviewConflictError):
        provider.submit_for_review(handoff, changed)
    with sessions.begin() as session:
        result = provider.complete_for_case(session, case_ref=handoff.case_ref,
            decision=ApproveReviewDecision(decision="APPROVE", handoff_id=handoff.handoff_id, review_note="Checked the dispute."))
    assert provider.fetch_result(ref) == result


def test_human_outcome_cannot_replace_a_missing_persisted_human_decision():
    sessions = _session_factory()
    handoff = _handoff("HANDOFF-NO-HUMAN")
    _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    result = _provider(sessions, application).execute(_human_approve(handoff))
    assert result.application_result.reason_codes == ["HUMAN_REVIEW_NOT_AUTHORIZED"]
    assert application.calls == []


@pytest.mark.parametrize("change", ["snapshot", "amount", "currency", "claim"])
def test_current_facts_and_reviewer_findings_are_checked_before_execution(change):
    sessions = _session_factory()
    handoff = _handoff("HANDOFF-CURRENT")
    _seed_authorization(sessions, handoff, "AUTO")
    application = ApplicationProvider()
    provider = _provider(sessions, application)
    request = _reviewer_approve(handoff)
    if change == "claim":
        review = request.resolution_handoff.review_result
        finding = review.reviewer_claim_findings[0].model_copy(update={"status": ClaimStatus.UNSUPPORTED})
        request = request.model_copy(update={"resolution_handoff": request.resolution_handoff.model_copy(
            update={"review_result": review.model_copy(update={"reviewer_claim_findings": [finding]})})})
    else:
        context = _context()
        updates = {
            "snapshot": {"order_snapshot_ref": "ORDER-001@2"},
            "amount": {"refundable_amount_max": "1"},
            "currency": {"currency": "USD"},
        }[change]
        provider._case_context_provider.result = context.model_copy(update={
            "order_snapshot": OrderSnapshot.model_validate({**context.order_snapshot.model_dump(mode="json"), **updates})})
    result = provider.execute(request)
    assert result.status.value == "REJECTED"
    assert result.application_result.reason_codes == ["CURRENT_HANDOFF_INVALID"]
    assert application.calls == []


def test_migration_preserves_old_risk_data_and_supports_new_human_submissions(tmp_path: Path):
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'review-migration.db'}")
    command.upgrade(config, "0009_human_reviews")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO human_reviews
            (review_ref,handoff_id,case_ref,payload_hash,handoff_payload,risk_payload,submitted_at)
            VALUES ('old','old','old',:hash,'{}',:risk,:time)
        """), {"hash": "a" * 64, "risk": '{"route":"HUMAN"}', "time": TIME.isoformat()})
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT legacy_risk_payload,review_payload FROM human_reviews WHERE review_ref='old'"
        )).one()
        assert row[0] == '{"route":"HUMAN"}'
        assert row[1] is None
    from sqlalchemy.orm import sessionmaker
    sessions = sessionmaker(engine, expire_on_commit=False)
    handoff = _handoff("new")
    ref = SqlAlchemyHumanReviewProvider(sessions).submit_for_review(handoff, _review(handoff, False))
    with sessions() as session:
        assert session.get(HumanReviewRecord, ref).review_payload["verdict"] == "REVISE"
    with pytest.raises(RuntimeError, match="Reviewer submissions exist"):
        command.downgrade(config, "0009_human_reviews")


@pytest.mark.parametrize("currency", ["TWD", "USD"])
def test_reviewer_approved_refund_requires_human_for_high_or_unconfigured_currency(currency):
    from return_agent_contracts.models import ProposedDecisionHandoff
    sessions = _session_factory()
    payload = _handoff("HANDOFF-HIGH-VALUE").model_dump(mode="json")
    payload["proposed_decision"].update(amount="6000", currency=currency)
    handoff = ProposedDecisionHandoff.model_validate(payload)
    _seed_authorization(sessions, handoff, "AUTO")
    context = _context().model_dump(mode="json")
    context["order_snapshot"].update(currency=currency, refundable_amount_max="6700")
    context["order_snapshot"]["line_items"][1]["refundable_amount"] = "6000"
    application = ApplicationProvider()
    provider = _provider(sessions, application)
    provider._case_context_provider.result = type(_context()).model_validate(context)
    result = provider.execute(_reviewer_approve(handoff))
    assert result.status.value == "REJECTED"
    assert result.application_result.reason_codes == ["HUMAN_AUTHORIZATION_REQUIRED"]
    assert application.calls == []
