from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from return_agent.capabilities.embeddings import (
    POLICY_EMBEDDING_DIMENSIONS,
    OpenAIEmbeddingProvider,
    embedding_provider_from_env,
)
from return_agent.capabilities.policy import (
    PolicyDataIntegrityError,
    PolicyDocumentFixture,
    PolicyEmbeddingModelMismatchError,
    PolicyFixtureError,
    PolicyIngestionConflictError,
    SqlAlchemyPolicyProvider,
    ingest_policy_documents,
    load_policy_fixture,
)
from return_agent.db.models import Base, PolicyClauseRecord, PolicyRetrievalRecord
from return_agent_contracts.models import CaseContext, OrderLineItem, OrderSnapshot
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker


class DeterministicEmbeddingProvider:
    """Test-only 1536-dimension embedding provider with no external I/O."""

    model_name = "deterministic-test-embedding"
    dimensions = POLICY_EMBEDDING_DIMENSIONS

    def embed(self, text: str) -> list[float]:
        seed = sum(text.encode("utf-8")) % 17 + 1
        return [float(seed)] + [0.0] * (self.dimensions - 1)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _case_context() -> CaseContext:
    return CaseContext(
        case_ref="CASE-001",
        order_ref="ORDER-001",
        market="TW",
        case_opened_at="2026-09-01T10:00:00Z",
        snapshot_version=1,
    )


def _order_snapshot() -> OrderSnapshot:
    return OrderSnapshot(
        order_snapshot_ref="ORDER-001@1",
        order_ref="ORDER-001",
        snapshot_version=1,
        captured_at="2026-09-01T10:00:00Z",
        currency="TWD",
        delivered_at="2026-08-30T10:00:00Z",
        line_items=[
            OrderLineItem(
                line_item_id="LI-HEADPHONES",
                sku_ref="SKU-HEADPHONES",
                category_ref="CAT-AUDIO-HEADPHONES",
                title="Headphones",
                quantity=1,
                refundable_amount="700",
            ),
            OrderLineItem(
                line_item_id="LI-SPEAKER",
                sku_ref="SKU-SPEAKER",
                category_ref="CAT-AUDIO-SPEAKERS",
                title="Speaker",
                quantity=1,
                refundable_amount="1200",
            ),
        ],
        refundable_amount_max="1900",
        already_refunded_amount="0",
    )


def _document(
    *,
    family: str = "RETURNS-TW",
    version: str = "v1",
    source_ref: str = "repo://policy/returns-tw/v1",
    categories: list[str] | None = None,
    effective_to: str | None = None,
    return_policy: str = "MODEL_JUDGMENT",
    allowed_actions: list[str] | None = None,
    active: bool = True,
) -> PolicyDocumentFixture:
    return PolicyDocumentFixture.model_validate(
        {
            "policy_family": family,
            "version": version,
            "source_ref": source_ref,
            "active": active,
            "clauses": [
                {
                    "clause_id": f"{family}:{version}#damaged",
                    "effective_from": "2026-01-01T00:00:00Z",
                    "effective_to": effective_to,
                    "applicable_conditions": {
                        "markets": ["TW"],
                        "reason_codes": ["ITEM_DAMAGED"],
                        "categories": categories or [],
                    },
                    "required_claim_ids": [
                        "DELIVERY_CONFIRMED",
                        "ORDER_WITHIN_RETURN_WINDOW",
                        "ITEM_PHYSICALLY_DAMAGED",
                    ],
                    "allowed_actions": allowed_actions
                    or ["FULL_REFUND", "DECLINE"],
                    "return_policy": return_policy,
                    "text": f"{family} {version} damaged-item return policy.",
                }
            ],
        }
    )


def _ingest(
    session_factory: sessionmaker[Session],
    *documents: PolicyDocumentFixture,
) -> None:
    with session_factory.begin() as session:
        ingest_policy_documents(
            session,
            documents,
            DeterministicEmbeddingProvider(),
        )


def _provider(session_factory: sessionmaker[Session]) -> SqlAlchemyPolicyProvider:
    return SqlAlchemyPolicyProvider(session_factory, DeterministicEmbeddingProvider())


def test_openai_embedding_adapter_is_injectable_and_pins_1536_dimensions() -> None:
    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        embedding=[0.5] * POLICY_EMBEDDING_DIMENSIONS,
                    )
                ]
            )

    adapter = OpenAIEmbeddingProvider(
        client=SimpleNamespace(embeddings=FakeEmbeddings())
    )

    assert adapter.embed("Structured policy clause.") == [
        0.5
    ] * POLICY_EMBEDDING_DIMENSIONS
    assert calls == [
        {
            "model": "text-embedding-3-large",
            "input": "Structured policy clause.",
            "dimensions": POLICY_EMBEDDING_DIMENSIONS,
        }
    ]


def test_openai_embedding_adapter_uses_configured_model_name() -> None:
    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        embedding=[0.5] * POLICY_EMBEDDING_DIMENSIONS,
                    )
                ]
            )

    adapter = OpenAIEmbeddingProvider(
        model_name="gte-Qwen2-1.5B-instruct-q8_0",
        client=SimpleNamespace(embeddings=FakeEmbeddings()),
    )

    adapter.embed("Structured policy clause.")

    assert calls[0]["model"] == "gte-Qwen2-1.5B-instruct-q8_0"


def test_openai_embedding_adapter_configures_openai_compatible_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_openai(**kwargs: str) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr("openai.OpenAI", fake_openai)

    OpenAIEmbeddingProvider(
        api_key="test-key",
        base_url="https://embeddings.example.com/v1",
        model_name="gte-Qwen2-1.5B-instruct-q8_0",
    )

    assert captured == {
        "timeout": 25.0,
        "max_retries": 0,
        "api_key": "test-key",
        "base_url": "https://embeddings.example.com/v1",
    }


@pytest.mark.parametrize("configured_endpoint", [False, True])
def test_embedding_factory_requires_endpoint_and_explicit_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, configured_endpoint: bool
) -> None:
    for name in [
        "RETURN_AGENT_EMBEDDING_BASE_URL", "RETURN_AGENT_EMBEDDING_MODEL",
        "RETURN_AGENT_EMBEDDING_API_KEY", "RETURN_AGENT_EMBEDDING_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(name, raising=False)
    key_file = tmp_path / "embedding_key"
    key_file.write_text("test-compass-key\n")
    monkeypatch.setenv("RETURN_AGENT_EMBEDDING_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    captured: dict[str, object] = {}

    def fake_openai(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr("openai.OpenAI", fake_openai)
    if configured_endpoint:
        monkeypatch.setenv("RETURN_AGENT_EMBEDDING_BASE_URL", "http://127.0.0.1:8790/v1")
        monkeypatch.setenv("RETURN_AGENT_EMBEDDING_TIMEOUT_SECONDS", "12")
        monkeypatch.setenv("RETURN_AGENT_EMBEDDING_API_KEY", "explicit-key")
    if not configured_endpoint:
        with pytest.raises(ValueError, match="RETURN_AGENT_EMBEDDING_BASE_URL"):
            embedding_provider_from_env()
        assert captured == {}
        return
    adapter = embedding_provider_from_env()
    assert adapter.model_name == "text-embedding-3-large"
    assert adapter.dimensions == 1536
    assert captured == {
        "base_url": "http://127.0.0.1:8790/v1",
        "api_key": "explicit-key" if configured_endpoint else "test-compass-key",
        "timeout": 12.0 if configured_endpoint else 25.0,
        "max_retries": 0,
    }


def test_embedding_factory_does_not_borrow_an_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETURN_AGENT_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("RETURN_AGENT_EMBEDDING_API_KEY_FILE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-sent-to-compass")
    with pytest.raises(ValueError, match="RETURN_AGENT_EMBEDDING_API_KEY"):
        embedding_provider_from_env()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_embedding_timeout_requires_finite_positive_seconds(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenAIEmbeddingProvider(timeout_seconds=timeout, client=SimpleNamespace())


def test_ingestion_is_idempotent_and_rejects_changed_version_content() -> None:
    session_factory = _session_factory()
    document = _document()
    with session_factory.begin() as session:
        first = ingest_policy_documents(
            session,
            [document],
            DeterministicEmbeddingProvider(),
        )
    assert first.inserted_documents == 1
    assert first.updated_documents == 0
    assert first.unchanged_documents == 0

    with session_factory.begin() as session:
        replay = ingest_policy_documents(
            session,
            [document],
            DeterministicEmbeddingProvider(),
        )
    assert replay.inserted_documents == 0
    assert replay.updated_documents == 0
    assert replay.unchanged_documents == 1

    changed = _document(categories=["CAT-AUDIO-SPEAKERS"])
    with session_factory.begin() as session, pytest.raises(PolicyIngestionConflictError):
        ingest_policy_documents(session, [changed], DeterministicEmbeddingProvider())


def test_model_switch_requires_explicit_reembedding_and_preserves_history() -> None:
    sessions = _session_factory()
    document = _document()
    _ingest(sessions, document)
    original = _provider(sessions).retrieve_policy(
        _case_context(), _order_snapshot(), "ITEM_DAMAGED", ["LI-SPEAKER"]
    )

    class ReplacementEmbedding(DeterministicEmbeddingProvider):
        model_name = "replacement-model"
        calls = 0

        def embed(self, text: str) -> list[float]:
            self.calls += 1
            return [0.0, 1.0] + [0.0] * (self.dimensions - 2)

    replacement = ReplacementEmbedding()
    with (
        pytest.raises(PolicyEmbeddingModelMismatchError, match="--reembed"),
        sessions.begin() as session,
    ):
        ingest_policy_documents(session, [document], replacement)
    provider = SqlAlchemyPolicyProvider(sessions, replacement)
    with pytest.raises(PolicyEmbeddingModelMismatchError):
        provider.retrieve_policy(
            _case_context(), _order_snapshot(), "ITEM_DAMAGED", ["LI-SPEAKER"]
        )
    assert replacement.calls == 0
    with sessions.begin() as session:
        result = ingest_policy_documents(session, [document], replacement, reembed=True)
    assert result.updated_documents == 1
    assert replacement.calls == 1
    with sessions() as session:
        clause = session.scalar(select(PolicyClauseRecord))
        assert clause.embedding_model == replacement.model_name
        assert list(clause.embedding[:2]) == [0.0, 1.0]
    assert provider.get_persisted_bundle(original.policy_bundle_version) == original
    assert provider.retrieve_policy(
        _case_context(), _order_snapshot(), "ITEM_DAMAGED", ["LI-SPEAKER"]
    ).retrieval_status == "OK"
    with pytest.raises(PolicyEmbeddingModelMismatchError):
        _provider(sessions).retrieve_policy(
            _case_context(), _order_snapshot(), "ITEM_DAMAGED", ["LI-SPEAKER"]
        )
    with pytest.raises(PolicyIngestionConflictError), sessions.begin() as session:
        ingest_policy_documents(
            session, [_document(categories=["CAT-AUDIO-SPEAKERS"])],
            replacement, reembed=True,
        )


def test_failed_reembedding_rolls_back_all_vectors() -> None:
    sessions = _session_factory()
    documents = [_document(), _document(family="OTHER", source_ref="repo://other")]
    _ingest(sessions, *documents)

    class FailingEmbedding(DeterministicEmbeddingProvider):
        model_name = "replacement-model"
        calls = 0

        def embed(self, text: str) -> list[float]:
            self.calls += 1
            if self.calls == 2:
                raise TimeoutError("embedding unavailable")
            return [0.0, 1.0] + [0.0] * (self.dimensions - 2)

    with pytest.raises(TimeoutError), sessions.begin() as session:
        ingest_policy_documents(session, documents, FailingEmbedding(), reembed=True)
    with sessions() as session:
        clauses = session.scalars(select(PolicyClauseRecord)).all()
        assert len(clauses) == 2
        assert {row.embedding_model for row in clauses} == {
            DeterministicEmbeddingProvider.model_name
        }
        assert all(row.embedding[1] == 0 for row in clauses)


def test_ingestion_updates_activation_without_changing_immutable_content() -> None:
    session_factory = _session_factory()
    active_document = _document()
    _ingest(session_factory, active_document)

    with session_factory.begin() as session:
        result = ingest_policy_documents(
            session,
            [active_document.model_copy(update={"active": False})],
            DeterministicEmbeddingProvider(),
        )
    assert result.inserted_documents == 0
    assert result.updated_documents == 1
    assert result.unchanged_documents == 0

    inactive_bundle = _provider(session_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert inactive_bundle.retrieval_status == "NOT_FOUND"

    _ingest(
        session_factory,
        active_document.model_copy(update={"active": False}),
        _document(version="v2", source_ref="repo://policy/returns-tw/v2"),
    )
    replacement_bundle = _provider(session_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert replacement_bundle.retrieval_status == "OK"
    assert {clause.policy_version for clause in replacement_bundle.clauses} == {
        "RETURNS-TW:v2"
    }


def test_retrieval_returns_persisted_complete_structured_clauses() -> None:
    session_factory = _session_factory()
    _ingest(session_factory, _document())

    provider = _provider(session_factory)
    bundle = provider.retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )

    assert bundle.retrieval_status == "OK"
    assert [clause.clause_id for clause in bundle.clauses] == [
        "RETURNS-TW:v1#damaged"
    ]
    assert bundle.clauses[0].required_claim_ids
    assert bundle.clauses[0].allowed_actions
    assert provider.get_persisted_bundle(bundle.policy_bundle_version) == bundle
    assert (
        provider.retrieve_policy(
            _case_context(),
            _order_snapshot(),
            "ITEM_DAMAGED",
            ["LI-SPEAKER"],
        )
        == bundle
    )
    with session_factory() as session:
        retrievals = session.scalars(select(PolicyRetrievalRecord)).all()
    assert len(retrievals) == 1


def test_retrieval_rejects_conflicting_canonical_bundle_content() -> None:
    session_factory = _session_factory()
    _ingest(session_factory, _document())
    provider = _provider(session_factory)
    bundle = provider.retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )

    with session_factory.begin() as session:
        retrieval = session.scalar(
            select(PolicyRetrievalRecord).where(
                PolicyRetrievalRecord.bundle_version
                == bundle.policy_bundle_version
            )
        )
        assert retrieval is not None
        retrieval.request_hash = "different-request"

    with pytest.raises(PolicyDataIntegrityError):
        provider.retrieve_policy(
            _case_context(),
            _order_snapshot(),
            "ITEM_DAMAGED",
            ["LI-SPEAKER"],
        )


def test_vector_ranking_never_removes_structurally_eligible_clauses() -> None:
    session_factory = _session_factory()
    document = _document()
    second_clause = {
        **document.model_dump(mode="json")["clauses"][0],
        "clause_id": "RETURNS-TW:v1#damaged-secondary",
        "text": "A second compatible return clause used only for ranking order.",
    }
    two_clause_document = PolicyDocumentFixture.model_validate(
        {
            **document.model_dump(mode="json"),
            "clauses": [
                *document.model_dump(mode="json")["clauses"],
                second_clause,
            ],
        }
    )
    _ingest(session_factory, two_clause_document)

    bundle = _provider(session_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )

    assert bundle.retrieval_status == "OK"
    assert {clause.clause_id for clause in bundle.clauses} == {
        "RETURNS-TW:v1#damaged",
        "RETURNS-TW:v1#damaged-secondary",
    }


def test_retrieval_returns_not_found_for_expired_or_category_mismatch() -> None:
    expired_factory = _session_factory()
    _ingest(expired_factory, _document(effective_to="2026-08-31T23:59:59Z"))
    expired_bundle = _provider(expired_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert expired_bundle.retrieval_status == "NOT_FOUND"
    assert expired_bundle.clauses == []

    scoped_factory = _session_factory()
    _ingest(scoped_factory, _document(categories=["CAT-AUDIO-SPEAKERS"]))
    scoped_provider = _provider(scoped_factory)
    mismatch = scoped_provider.retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-HEADPHONES"],
    )
    match = scoped_provider.retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert mismatch.retrieval_status == "NOT_FOUND"
    assert match.retrieval_status == "OK"


def test_retrieval_fails_closed_for_versions_policy_conflicts_or_no_action_overlap(
) -> None:
    version_factory = _session_factory()
    _ingest(
        version_factory,
        _document(version="v1", source_ref="repo://policy/returns-tw/v1"),
        _document(version="v2", source_ref="repo://policy/returns-tw/v2"),
    )
    version_conflict = _provider(version_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert version_conflict.retrieval_status == "AMBIGUOUS"
    assert version_conflict.clauses == []

    policy_factory = _session_factory()
    _ingest(
        policy_factory,
        _document(
            family="RETURNS-TW-REQUIRED",
            source_ref="repo://policy/returns-tw-required/v1",
            return_policy="REQUIRED",
        ),
        _document(
            family="RETURNS-TW-WAIVED",
            source_ref="repo://policy/returns-tw-waived/v1",
            return_policy="NOT_REQUIRED",
        ),
    )
    policy_conflict = _provider(policy_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert policy_conflict.retrieval_status == "AMBIGUOUS"

    action_factory = _session_factory()
    _ingest(
        action_factory,
        _document(
            family="RETURNS-TW-REFUND",
            source_ref="repo://policy/returns-tw-refund/v1",
            allowed_actions=["FULL_REFUND"],
        ),
        _document(
            family="RETURNS-TW-DECLINE",
            source_ref="repo://policy/returns-tw-decline/v1",
            allowed_actions=["DECLINE"],
        ),
    )
    action_conflict = _provider(action_factory).retrieve_policy(
        _case_context(),
        _order_snapshot(),
        "ITEM_DAMAGED",
        ["LI-SPEAKER"],
    )
    assert action_conflict.retrieval_status == "AMBIGUOUS"


def test_fixture_rejects_incomplete_structured_clauses(tmp_path: Path) -> None:
    path = tmp_path / "invalid-policy.json"
    path.write_text(
        """[
          {
            \"policy_family\": \"RETURNS-TW\",
            \"version\": \"v1\",
            \"source_ref\": \"repo://policy/returns-tw/v1\",
            \"clauses\": []
          }
        ]""",
        encoding="utf-8",
    )

    with pytest.raises(PolicyFixtureError):
        load_policy_fixture(path)


@pytest.mark.parametrize("duplicate_kind", ["family", "source"])
def test_fixture_rejects_duplicate_document_identities(
    tmp_path: Path,
    duplicate_kind: str,
) -> None:
    document = _document().model_dump(mode="json")
    duplicate = (
        document
        if duplicate_kind == "family"
        else _document(family="RETURNS-TW-OTHER").model_dump(mode="json")
    )
    path = tmp_path / "duplicate-policy.json"
    path.write_text(
        json.dumps([document, duplicate]),
        encoding="utf-8",
    )

    with pytest.raises(PolicyFixtureError):
        load_policy_fixture(path)
