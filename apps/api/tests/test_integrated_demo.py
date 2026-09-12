from __future__ import annotations

import json
from pathlib import Path

import pytest
from return_agent.capabilities.integration import (
    FixtureCaseContextProvider,
    compose_integrated_demo_providers,
)
from return_agent.capabilities.policy import (
    ingest_policy_documents,
    load_policy_fixture,
)
from return_agent.db.models import Base
from return_agent.store import CaseStore
from return_agent_contracts.ui import CreateCaseRequest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class EmbeddingFake:
    model_name = "text-embedding-3-large"
    dimensions = 1536

    def embed(self, _text: str) -> list[float]:
        return [1.0] + [0.0] * (self.dimensions - 1)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "case-context.json.example"


def test_demo_context_projects_fixture_onto_unique_demo_order() -> None:
    sessions = _session_factory()
    with sessions.begin() as session:
        case = CaseStore(session).create(
            CreateCaseRequest(
                order_ref="ORDER-DEMO-E2E-ABC12345",
                user_ref="USER-DEMO",
                initial_message="speaker arrived damaged",
            )
        )

    result = FixtureCaseContextProvider(sessions, _fixture_path()).load_case_context(
        case.case_ref
    )

    assert result.case_context.case_ref == case.case_ref
    assert result.case_context.order_ref == "ORDER-DEMO-E2E-ABC12345"
    assert result.order_snapshot.order_ref == "ORDER-DEMO-E2E-ABC12345"
    assert result.order_snapshot.order_snapshot_ref == "ORDER-DEMO-E2E-ABC12345@1"
    assert result.order_snapshot.line_items[0].line_item_id == "LI-DEMO-SPEAKER"


def test_demo_context_rejects_non_demo_order() -> None:
    sessions = _session_factory()
    with sessions.begin() as session:
        case = CaseStore(session).create(
            CreateCaseRequest(
                order_ref="ORDER-PRODUCTION-001",
                user_ref="USER-DEMO",
                initial_message="speaker arrived damaged",
            )
        )

    provider = FixtureCaseContextProvider(sessions, _fixture_path())
    with pytest.raises(LookupError, match="has no order snapshot"):
        provider.load_case_context(case.case_ref)


def test_keyed_demo_context_selects_exact_order_snapshot(tmp_path) -> None:
    source = _fixture_path().parent / "demo-case-study"
    orders = []
    for name in ("a", "b"):
        payload = json.loads((source / f"case-{name}.json.example").read_text())
        orders.append(
            {
                "case_context": payload["case_context"],
                "order_snapshot": payload["order_snapshot"],
            }
        )
    fixture = tmp_path / "case-context.json.example"
    fixture.write_text(json.dumps({"orders": orders}), encoding="utf-8")
    sessions = _session_factory()
    with sessions.begin() as session:
        store = CaseStore(session)
        case_a = store.create(
            CreateCaseRequest(
                order_ref="ORDER-DEMO-STUDY-A",
                user_ref="USER-A",
                initial_message="speaker arrived damaged",
            )
        )
        case_b = store.create(
            CreateCaseRequest(
                order_ref="ORDER-DEMO-STUDY-B",
                user_ref="USER-B",
                initial_message="headphones arrived damaged",
            )
        )

    provider = FixtureCaseContextProvider(sessions, fixture)
    result_a = provider.load_case_context(case_a.case_ref)
    result_b = provider.load_case_context(case_b.case_ref)

    assert result_a.order_snapshot.line_items[0].line_item_id == "LI-STUDY-A"
    assert result_a.order_snapshot.refundable_amount_max == 1200
    assert result_b.order_snapshot.line_items[0].line_item_id == "LI-STUDY-B"
    assert result_b.order_snapshot.refundable_amount_max == 6200


def test_documented_policy_ingestion_then_integrated_startup_is_idempotent() -> None:
    class Embeddings:
        model_name = "fixture-test"
        dimensions = 1536
        calls = 0

        def embed(self, text: str) -> list[float]:
            self.calls += 1
            return [1.0] + [0.0] * (self.dimensions - 1)

    sessions = _session_factory()
    embeddings = Embeddings()
    data_dir = _fixture_path().parent
    with sessions.begin() as session:
        result = ingest_policy_documents(
            session, load_policy_fixture(data_dir / "policy.json.example"), embeddings
        )
    assert result.inserted_documents == 1
    initial_calls = embeddings.calls
    for iteration in range(2):
        compose_integrated_demo_providers(
            session_factory=sessions,
            embedding_provider=embeddings,
            data_dir=data_dir,
        )
        if iteration == 0:
            first_startup_calls = embeddings.calls
        else:
            assert embeddings.calls == first_startup_calls
    assert (
        embeddings.calls == initial_calls + 5
    )  # Four v2 paths plus candidate embedded once, never on replay.


@pytest.mark.parametrize("status", ["CANDIDATE", "APPROVED", "RETIRED"])
def test_bootstrap_preserves_migrated_demo_memory_identity_and_governance(status):
    from datetime import UTC, datetime

    from return_agent.db.models import OperationalMemoryRecord
    from sqlalchemy import select

    sessions = _session_factory()
    data_dir = _fixture_path().parent
    compose_integrated_demo_providers(session_factory=sessions, embedding_provider=EmbeddingFake(), data_dir=data_dir)
    with sessions.begin() as session:
        row = session.scalar(select(OperationalMemoryRecord))
        row.candidate_payload_hash = "legacy-original-hash"
        row.retrieval_summary = "Situation: mechanical legacy summary. Action: compare evidence."
        row.status = status
        row.approved_at = None if status == "CANDIDATE" else datetime.now(UTC)
        row.retired_at = datetime.now(UTC) if status == "RETIRED" else None
    compose_integrated_demo_providers(session_factory=sessions, embedding_provider=EmbeddingFake(), data_dir=data_dir)
    with sessions() as session:
        row = session.scalar(select(OperationalMemoryRecord))
        assert row.candidate_payload_hash == "legacy-original-hash"
        assert row.retrieval_summary.startswith("Situation: mechanical")
        assert row.status == status
