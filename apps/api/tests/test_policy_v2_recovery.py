"""Real PostgreSQL workers contend on durable fulfillment state."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from return_agent.capabilities.fulfillment import FulfillmentWorker
from return_agent.capabilities.refund import RefundExecutionUnavailableError, SqlAlchemyRefundExecutionProvider
from return_agent.db.models import (
    RefundCompletionOutboxRecord, RefundExecutionItemRecord, RefundExecutionRecord,
    RefundItemReservation, ReturnAuthorizationRecord, ReturnReceiptRecord, UserRiskEventRecord,
)

from .test_policy_v2_fulfillment import setup_case, authorize, consent, event, accept, release
from .test_policy_v2_migrations import migrated_database  # noqa: F401
from .test_refund_execution import CaseProvider


@pytest.fixture
def postgres_case(migrated_database):
    engine, _cfg = migrated_database
    if engine.dialect.name != "postgresql":
        pytest.skip("PV2_TEST_POSTGRES_URL enables real row-lock/worker tests")
    return setup_case(sessions=sessionmaker(engine, expire_on_commit=False))


def test_parallel_return_event_replay_and_workers_pay_once(postgres_case):
    env = postgres_case
    authorize(env)
    consent(env)
    for kind in ("RETURN_ARRIVED", "INSPECTION_PASSED"):
        delivery = event(env, kind)
        barrier = Barrier(4)

        def deliver(_):
            barrier.wait(timeout=5)
            return accept(env, delivery)

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(deliver, range(4)))
        assert all(receipt == receipts[0] for receipt in receipts)
        assert env.application.calls == []
    workers = [FulfillmentWorker(env.sessions, env.executor, owner=f"worker-{i}") for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda worker: worker.run_once(), workers))
    assert results.count(True) == 1
    assert len(env.application.calls) == len(env.application.applied_effects) == 1
    assert env.executor.execute(env.request).status == "SUCCEEDED"
    with env.sessions() as session:
        for model, count in ((ReturnReceiptRecord, 2), (RefundExecutionRecord, 1),
                             (RefundExecutionItemRecord, 1), (RefundItemReservation, 1),
                             (RefundCompletionOutboxRecord, 1)):
            assert session.scalar(select(func.count()).select_from(model)) == count
        assert session.scalar(select(func.count()).select_from(UserRiskEventRecord).where(
            UserRiskEventRecord.case_ref == env.case.case_ref,
            UserRiskEventRecord.event_type == "REFUND_SUCCEEDED",
        )) == 1


def test_worker_restart_recovers_unknown_payment_after_lease_expiry(postgres_case):
    env = postgres_case
    authorize(env)
    release(env)
    env.application.timeout_once = True
    with pytest.raises(RefundExecutionUnavailableError):
        FulfillmentWorker(env.sessions, env.executor, owner="old-worker").run_once()
    replacement = SqlAlchemyRefundExecutionProvider(
        env.sessions, CaseProvider(env.context), env.application
    )
    reopened = FulfillmentWorker(env.sessions, replacement, owner="new-worker")
    assert not reopened.run_once()
    with env.sessions.begin() as session:
        authorization = session.scalar(select(ReturnAuthorizationRecord))
        assert authorization.lease_owner == "old-worker"
        assert session.scalar(select(RefundItemReservation)) is not None
        assert session.scalar(select(RefundExecutionRecord)).state == "IN_PROGRESS"
        assert session.scalar(select(RefundCompletionOutboxRecord)) is None
        assert session.scalar(select(UserRiskEventRecord).where(
            UserRiskEventRecord.case_ref == env.case.case_ref,
            UserRiskEventRecord.event_type == "REFUND_SUCCEEDED",
        )) is None
        authorization.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    assert reopened.run_once()
    assert not reopened.run_once()
    assert len({request.execution_ref for request in env.application.calls}) == 1
    assert len(env.application.applied_effects) == 1


def test_parallel_cases_reserve_same_item_before_any_payment(postgres_case):
    first = postgres_case
    second = setup_case(sessions=first.sessions, case_ref="CASE-PV2-OTHER")
    barrier = Barrier(2)

    def attempt(env):
        barrier.wait(timeout=5)
        try:
            authorize(env)
            return "AUTHORIZED"
        except ValueError as error:
            assert "reserved by another authorization" in str(error)
            return "CONFLICT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (first, second)))
    assert sorted(results) == ["AUTHORIZED", "CONFLICT"]
    assert first.application.calls == second.application.calls == []
    with first.sessions() as session:
        assert session.scalar(select(func.count()).select_from(RefundItemReservation)) == 1
        assert session.scalar(select(func.count()).select_from(ReturnAuthorizationRecord)) == 1
        assert session.scalar(select(func.count()).select_from(RefundExecutionRecord)) == 1
