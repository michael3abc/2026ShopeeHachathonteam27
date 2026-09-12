"""Human judgment is durable authority, bounded by claimed scope and Policy."""

from copy import deepcopy

import pytest
from return_agent.capabilities.human_review import (
    HumanReviewConflictError,
    SqlAlchemyHumanReviewProvider,
)
from return_agent.db.models import HumanReviewRecord, PolicyRetrievalRecord
from return_agent_contracts.models import (
    HumanReviewDossier,
    PolicyBundle,
    ProposedDecisionHandoff,
)
from return_agent_contracts.operations import ExecuteRefundRequest
from return_agent_contracts.ui import EditReviewDecision, RejectReviewDecision
from sqlalchemy import select

from .test_refund_execution import (
    ApplicationProvider,
    CaseProvider,
    _context,
    _handoff,
    _human_edit,
    _provider,
    _review,
    _seed_authorization,
    _session_factory,
)


def _pending(*, decline=False, return_policy="MODEL_JUDGMENT"):
    sessions = _session_factory()
    handoff = _handoff("ADJUDICATION")
    review = _review(handoff, False)
    if decline:
        payload = handoff.model_dump(mode="json")
        payload["proposed_decision"] = dict(
            action="DECLINE",
            refund_scope={"line_item_ids": []},
            amount="0",
            currency="TWD",
            reason_code="ITEM_DAMAGED",
            policy_refs=handoff.policy_refs,
        )
        handoff = ProposedDecisionHandoff.model_validate(payload)
    _seed_authorization(sessions, handoff, "AUTO")
    with sessions.begin() as session:
        record = session.scalar(select(PolicyRetrievalRecord))
        payload = deepcopy(record.bundle_payload)
        payload["clauses"][0]["allowed_actions"] = ["FULL_REFUND", "DECLINE"]
        payload["clauses"][0]["return_policy"] = return_policy
        record.bundle_payload = payload
        bundle = PolicyBundle.model_validate(payload)
    from .test_refund_execution import _dossier
    dossier = _dossier(handoff, review, bundle)
    provider = SqlAlchemyHumanReviewProvider(sessions, CaseProvider(_context()))
    ref = provider.submit_for_review(handoff, review, dossier)
    return sessions, provider, ref, dossier


def _decision(dossier, scope=("LI-002",)):
    return EditReviewDecision(
        decision="EDIT",
        handoff_id=dossier.proposal_history[-1].handoff_id,
        review_note="Reviewed the original evidence; refund these claimed items.",
        reviewer_id="human-demo-2",
        correction_reason_code="OTHER",
        corrected_decision={
            "action": "FULL_REFUND",
            "refund_scope": {"line_item_ids": list(scope)},
            "return_decision": {
                "source": "HUMAN_REVIEW",
                "requirement": {
                    "required": False,
                    "reason_code": "ITEM_UNSALVAGEABLE",
                },
            },
        },
    )


@pytest.mark.parametrize(
    "decline,scope,amount",
    [
        (True, ("LI-002",), "1200"),
        (False, ("LI-001", "LI-002"), "1900"),
    ],
)
def test_human_can_reverse_decline_and_expand_to_original_claimed_scope(
    decline, scope, amount
):
    sessions, provider, ref, dossier = _pending(decline=decline)
    handoff = dossier.proposal_history[-1]
    with sessions.begin() as session:
        result = provider.complete_for_case(
            session, case_ref=handoff.case_ref, decision=_decision(dossier, scope)
        )
    assert provider.fetch_result(ref).reviewer_id == "human-demo-2"
    request = _human_edit(_handoff(handoff.handoff_id)).model_dump(mode="json")
    request["resolution_handoff"]["review_result"] = dossier.review_history[
        -1
    ].model_dump(mode="json")
    request["resolution_handoff"]["final_decision"].update(
        refund_scope={"line_item_ids": list(scope)},
        amount=amount,
    )
    application = ApplicationProvider()
    response = _provider(sessions, application).execute(
        ExecuteRefundRequest.model_validate(request)
    )
    assert response.status.value == "SUCCEEDED"
    assert len(application.calls) == 1
    with sessions.begin() as session:
        with pytest.raises(HumanReviewConflictError, match="already final"):
            provider.complete_for_case(
                session, case_ref=handoff.case_ref, decision=_decision(dossier)
            )
    assert provider.fetch_result(ref) == result


@pytest.mark.parametrize(
    "failure",
    ["scope", "stale", "return", "policy", "legacy", "verification", "tampered"],
)
def test_invalid_adjudication_never_commits_a_final_result(failure):
    sessions, provider, ref, dossier = _pending(
        return_policy="REQUIRED" if failure == "return" else "MODEL_JUDGMENT"
    )
    decision = _decision(dossier, ("UNKNOWN",) if failure == "scope" else ("LI-002",))
    if failure == "stale":
        decision = decision.model_copy(update={"handoff_id": "old-handoff"})
    with sessions.begin() as session:
        if failure == "legacy":
            session.get(HumanReviewRecord, ref).dossier_payload = None
        if failure == "policy":
            record = session.scalar(select(PolicyRetrievalRecord))
            session.delete(record)
        if failure == "verification":
            from return_agent.db.models import HandoffVerificationRecord

            session.scalar(
                select(HandoffVerificationRecord)
            ).verification_status = "FAIL"
        if failure == "tampered":
            record = session.get(HumanReviewRecord, ref)
            payload = deepcopy(record.dossier_payload)
            payload["claimed_line_item_ids"] = ["LI-002"]
            record.dossier_payload = payload
    with sessions.begin() as session:
        with pytest.raises(HumanReviewConflictError):
            provider.complete_for_case(
                session,
                case_ref=dossier.proposal_history[-1].case_ref,
                decision=decision,
            )
    assert provider.fetch_result(ref) is None


def test_decline_is_explicit_final_decision_not_rejection_of_the_proposal():
    sessions, provider, ref, dossier = _pending(decline=True)
    handoff = dossier.proposal_history[-1]
    with sessions.begin() as session:
        result = provider.complete_for_case(
            session,
            case_ref=handoff.case_ref,
            decision=RejectReviewDecision(
                decision="REJECT",
                handoff_id=handoff.handoff_id,
                review_note="Confirmed ineligible from existing evidence.",
            ),
        )
    assert result.decision.value == "REJECT"
    assert provider.fetch_result(ref) == result


def test_resubmission_cannot_replace_the_original_claimed_scope():
    sessions, provider, ref, dossier = _pending()
    altered = dossier.model_copy(update={"claimed_line_item_ids": ["LI-002"]})
    with pytest.raises(HumanReviewConflictError, match="another review payload"):
        provider.submit_for_review(
            dossier.proposal_history[-1], dossier.review_history[-1], altered
        )
    with sessions() as session:
        assert session.get(HumanReviewRecord, ref).dossier_payload[
            "claimed_line_item_ids"
        ] == ["LI-001", "LI-002"]


def test_case_api_validates_before_commit_and_preserves_closed_review():
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from return_agent.agent_commands import SqlAlchemyAgentCommandOutbox
    from return_agent.app import app, get_provider_bundle, get_session
    from return_agent.db.agent_bridge import AgentCommandOutboxRecord
    from return_agent.db.case import CaseRecord

    from .test_agent_bridge import _case

    sessions, provider, ref, dossier = _pending()
    handoff = dossier.proposal_history[-1]
    with sessions.begin() as session:
        case = _case(handoff.case_ref)
        case.status = "AWAITING_HUMAN_REVIEW"
        session.add(case)

    def get_test_session():
        with sessions() as session:
            yield session

    previous_overrides = dict(app.dependency_overrides)
    previous_outbox = app.state.agent_command_outbox
    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_provider_bundle] = lambda: SimpleNamespace(
        human_review_provider=provider
    )
    app.state.agent_command_outbox = SqlAlchemyAgentCommandOutbox()
    try:
        client = TestClient(app)
        url = f"/cases/{handoff.case_ref}"
        decision = _decision(dossier).model_dump(mode="json")
        assert (
            client.post(
                url + "/review", json={**decision, "handoff_id": "stale"}
            ).status_code
            == 409
        )
        assert client.get(url).json()["status"] == "AWAITING_HUMAN_REVIEW"
        assert provider.fetch_result(ref) is None
        with sessions() as session:
            assert session.query(AgentCommandOutboxRecord).count() == 0
        response = client.post(url + "/review", json=decision)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "OBSERVING"
        assert (
            response.json()["human_review_result"]["review_note"]
            == decision["review_note"]
        )
        assert client.post(url + "/review", json=decision).status_code == 409
        with sessions.begin() as session:
            assert session.query(AgentCommandOutboxRecord).count() == 1
            session.get(CaseRecord, handoff.case_ref).status = "RESOLVED"
        closed = client.get(url).json()
        assert closed["human_review"]["dossier"] == dossier.model_dump(mode="json")
        assert closed["human_review_result"]["reviewer_id"] == "human-demo-2"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        app.state.agent_command_outbox = previous_outbox


@pytest.mark.asyncio
async def test_human_dossier_survives_redis_projection_and_replay():
    import fakeredis.aioredis
    from return_agent.agent_bridge import API_EVENT_CONSUMER_GROUP
    from return_agent.db.case import CaseRecord
    from return_agent.store import CaseStore, to_case_detail
    from return_agent_contracts.service import (
        AGENT_EVENT_STREAM,
        REDIS_BODY_FIELD,
        AgentInterruptedEvent,
    )

    from .test_agent_bridge import _bridge, _case
    from .test_refund_execution import TIME

    sessions, provider, ref, dossier = _pending()
    handoff = dossier.proposal_history[-1]
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(sessions, redis)
    with sessions.begin() as session:
        session.add(_case(handoff.case_ref))
    event = AgentInterruptedEvent(
        event_type="INTERRUPTED",
        event_id="EVENT-HUMAN",
        command_id="COMMAND-001",
        case_ref=handoff.case_ref,
        thread_id="THREAD-001",
        event_index=1,
        occurred_at=TIME,
        payload={
            "result": {
                "result_type": "INTERRUPTED",
                "status": "INTERRUPTED",
                "interrupt_payload": {
                    "kind": "HUMAN_REVIEW",
                    "case_ref": handoff.case_ref,
                    "handoff_id": handoff.handoff_id,
                    "review_ref": ref,
                    "handoff": handoff,
                    "review_result": dossier.review_history[-1],
                    "policy_bundle": dossier.policy_bundle,
                    "dossier": dossier,
                    "memory_ids": ["MEMORY-USED-001"],
                },
            }
        },
    )
    try:
        await redis.xgroup_create(
            AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
        )
        for _ in range(2):
            await redis.xadd(
                AGENT_EVENT_STREAM, {REDIS_BODY_FIELD: event.model_dump_json()}
            )
            assert await bridge.consume_event_once()
        with sessions() as session:
            case = session.get(CaseRecord, handoff.case_ref)
            interrupts = [
                event
                for event in case.events
                if event.payload.get("type") == "interrupt"
            ]
            assert len(interrupts) == 1
            assert interrupts[0].payload["payload"]["review"][
                "dossier"
            ] == dossier.model_dump(mode="json")
            detail = to_case_detail(CaseStore(session), case)
            assert detail.human_review.dossier == dossier
            assert detail.human_review.memories_used == ["MEMORY-USED-001"]
            assert case.status == "AWAITING_HUMAN_REVIEW"
            case.status = "RESOLVED"
            session.flush()
            closed = to_case_detail(CaseStore(session), case)
            assert closed.human_review.memories_used == ["MEMORY-USED-001"]
    finally:
        await redis.aclose()
