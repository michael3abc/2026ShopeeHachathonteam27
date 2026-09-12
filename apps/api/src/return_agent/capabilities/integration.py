"""Explicit demo-data composition for the cross-service integration profile."""

from __future__ import annotations
import os
from return_agent_contracts.review_gates import load_reviewer_gate_config

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from return_agent_contracts.enums import RefundApplicationStatus
from return_agent_contracts.interfaces import (
    CaseContextProvider,
    EvidenceProvider,
    HumanReviewProvider,
    OperationalMemoryStore,
    PolicyProvider,
    RefundApplicationProvider,
    RefundExecutionProvider,
)
from return_agent_contracts.models import (
    AppliedRefundApplicationResult,
    ApplyRefundRequest,
    CaseContextLoadResult,
    MemoryCandidate,
    OrderSnapshot,
    RefundApplicationResult,
)
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.embeddings import EmbeddingProvider
from return_agent.capabilities.evidence import (
    SqlAlchemyEvidenceProvider,
    load_evidence_fixture,
    upsert_evidence,
)
from return_agent.capabilities.human_review import SqlAlchemyHumanReviewProvider
from return_agent.capabilities.operational_memory import (
    OperationalMemoryGovernanceService,
    OperationalMemoryLifecycleError,
    SqlAlchemyOperationalMemoryStore,
)
from return_agent.capabilities.policy import (
    SqlAlchemyPolicyProvider,
    ingest_policy_documents,
    load_policy_fixture,
)
from return_agent.capabilities.refund import SqlAlchemyRefundExecutionProvider
from return_agent.capabilities.safety import (
    SafetyProviders,
    compose_safety_providers,
)
from return_agent.db.case import CaseRecord
from return_agent.db.models import OperationalMemoryRecord


class IntegrationFixtureError(ValueError):
    """A versioned integration fixture is missing or contract-invalid."""


class FixtureCaseContextProvider(CaseContextProvider):
    """Bind a demo order snapshot to the real Backend-created case reference."""

    DEMO_ORDER_PREFIX = "ORDER-DEMO-"

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        fixture_path: Path,
    ) -> None:
        self._session_factory = session_factory
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
            if "orders" in raw:
                orders = raw["orders"]
                if not isinstance(orders, list) or not orders:
                    raise ValueError("orders must be a non-empty list")
                templates = [CaseContextLoadResult.model_validate(item) for item in orders]
                self._templates = {
                    item.case_context.order_ref: item for item in templates
                }
                if len(self._templates) != len(templates):
                    raise ValueError("orders must have unique order_ref values")
                if any(
                    order_ref != item.order_snapshot.order_ref
                    for order_ref, item in self._templates.items()
                ):
                    raise ValueError("case context and snapshot order_ref must match")
                self._template = None
            else:
                self._template = CaseContextLoadResult.model_validate(
                    {
                        "case_context": raw["case_context"],
                        "order_snapshot": raw["order_snapshot"],
                    }
                )
                self._templates = None
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise IntegrationFixtureError(
                f"invalid case context fixture: {fixture_path}"
            ) from error

    def load_case_context(self, case_ref: str) -> CaseContextLoadResult:
        with self._session_factory() as session:
            case = session.get(CaseRecord, case_ref)
        if case is None:
            raise LookupError(f"unknown case {case_ref}")
        if self._templates is not None:
            template = self._templates.get(case.order_ref)
            if template is None:
                raise LookupError(
                    f"demo context has no order snapshot for {case.order_ref}"
                )
        elif not case.order_ref.startswith(self.DEMO_ORDER_PREFIX):
            raise LookupError(
                f"demo context has no order snapshot for {case.order_ref}"
            )
        else:
            assert self._template is not None
            template = self._template
        snapshot_version = template.order_snapshot.snapshot_version
        return CaseContextLoadResult(
            case_context=template.case_context.model_copy(
                update={"case_ref": case_ref, "order_ref": case.order_ref}
            ),
            order_snapshot=template.order_snapshot.model_copy(
                update={
                    "order_ref": case.order_ref,
                    "order_snapshot_ref": f"{case.order_ref}@{snapshot_version}",
                }
            ),
        )

    def load_order_snapshot(self, order_ref: str) -> OrderSnapshot:
        """Read the trusted fixture before a case exists, for upload subjects."""
        if self._templates is not None:
            template = self._templates.get(order_ref)
        else:
            template = self._template if order_ref.startswith(self.DEMO_ORDER_PREFIX) else None
        if template is None:
            raise LookupError("Unknown order")
        return template.order_snapshot.model_copy(update={"order_ref": order_ref})


class DeterministicDemoRefundApplicationProvider(RefundApplicationProvider):
    """Non-production terminal adapter with stable execution-ref semantics."""

    def apply(self, request: ApplyRefundRequest) -> RefundApplicationResult:
        return AppliedRefundApplicationResult(
            status=RefundApplicationStatus.APPLIED,
            application_ref=f"demo-application:{request.execution_ref}",
            applied_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class IntegratedProviderBundle:
    case_context_provider: CaseContextProvider
    policy_provider: PolicyProvider
    evidence_provider: EvidenceProvider
    operational_memory_store: OperationalMemoryStore
    human_review_provider: HumanReviewProvider
    safety_providers: SafetyProviders
    refund_execution_provider: RefundExecutionProvider


def compose_integrated_demo_providers(
    *,
    session_factory: sessionmaker[Session],
    embedding_provider: EmbeddingProvider,
    data_dir: Path,
) -> IntegratedProviderBundle:
    """Seed approved demo inputs and compose every currently defined Provider."""

    case_provider = FixtureCaseContextProvider(
        session_factory,
        data_dir / "case-context.json.example",
    )
    evidence_provider = SqlAlchemyEvidenceProvider(session_factory)
    memory_store = SqlAlchemyOperationalMemoryStore(session_factory, embedding_provider)
    reviewer_gate_config = load_reviewer_gate_config(os.environ.get("RETURN_AGENT_REVIEW_GATE_CONFIG"))
    human_provider = SqlAlchemyHumanReviewProvider(session_factory, case_provider, reviewer_gate_config)

    _seed_evidence(session_factory, data_dir / "evidence.json.example")
    _seed_policy(
        session_factory,
        data_dir / "policy.json.example",
        embedding_provider,
    )
    _seed_approved_memory(
        memory_store,
        session_factory,
        data_dir / "operational-memory.json.example",
    )

    policy_provider = SqlAlchemyPolicyProvider(session_factory, embedding_provider)
    safety = compose_safety_providers(
        session_factory=session_factory,
        case_context_provider=case_provider,
        evidence_provider=evidence_provider,
    )
    refund_provider = SqlAlchemyRefundExecutionProvider(
        session_factory,
        case_provider,
        DeterministicDemoRefundApplicationProvider(),
        reviewer_gate_config,
    )
    return IntegratedProviderBundle(
        case_context_provider=case_provider,
        policy_provider=policy_provider,
        evidence_provider=evidence_provider,
        operational_memory_store=memory_store,
        human_review_provider=human_provider,
        safety_providers=safety,
        refund_execution_provider=refund_provider,
    )


def _seed_evidence(session_factory: sessionmaker[Session], fixture_path: Path) -> None:
    fixtures = load_evidence_fixture(fixture_path)
    with session_factory.begin() as session:
        for fixture in fixtures:
            upsert_evidence(session, fixture)


def _seed_policy(
    session_factory: sessionmaker[Session],
    fixture_path: Path,
    embedding_provider: EmbeddingProvider,
) -> None:
    with session_factory.begin() as session:
        ingest_policy_documents(
            session,
            load_policy_fixture(fixture_path),
            embedding_provider,
        )


def _seed_approved_memory(
    store: SqlAlchemyOperationalMemoryStore,
    session_factory: sessionmaker[Session],
    fixture_path: Path,
) -> None:
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        candidate = MemoryCandidate.model_validate(payload["candidate"])
    except (
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        ValidationError,
    ) as error:
        raise IntegrationFixtureError(
            f"invalid operational memory fixture: {fixture_path}"
        ) from error
    # Bootstrap owns creation of the named demo fixture, not lifecycle replay.
    # A migrated row has a mechanically composed summary and its ORIGINAL hash;
    # never resubmit it as a newly distilled candidate or overwrite its governance.
    original = candidate.model_dump(mode="json", exclude={"retrieval_summary", "status", "scope"})
    original.update({f"scope_{key}": value for key, value in candidate.scope.model_dump(mode="json").items()})
    with session_factory() as session:
        existing = session.get(OperationalMemoryRecord, candidate.memory_id)
        if existing is not None:
            if any(getattr(existing, key) != value for key, value in original.items()):
                raise IntegrationFixtureError("stored demo memory differs from original fixture content")
            return
    store.submit_candidate(candidate)
    governance = OperationalMemoryGovernanceService(session_factory)
    try:
        governance.approve(candidate.memory_id)
    except OperationalMemoryLifecycleError:
        # Replaying bootstrap after approval is expected and leaves it unchanged.
        pass
