"""Injected dependencies used by graph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.user_risk import UserRiskConfig
from return_agent_contracts.interfaces import UserRiskProvider
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from return_agent_contracts.interfaces import (
    CaseContextProvider,
    EvidenceProvider,
    HumanReviewProvider,
    OperationalMemoryStore,
    PolicyProvider,
    VerificationProvider,
)

from .model import StructuredOutputModel
from .learning import LearningTraceLimits


class Clock(Protocol):
    """UTC timestamp source, injectable for deterministic tests."""

    def now(self) -> datetime: ...


class IdFactory(Protocol):
    """Stable opaque-reference source."""

    def make(self, kind: str, *parts: object) -> str: ...


@dataclass(frozen=True, slots=True)
class UtcClock:
    """Production UTC clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class StableIdFactory:
    """Generate retry-stable opaque identifiers from logical graph inputs."""

    namespace: str = "return-agent"

    def make(self, kind: str, *parts: object) -> str:
        identity = ":".join(str(part) for part in parts)
        value = uuid5(NAMESPACE_URL, f"{self.namespace}:{kind}:{identity}")
        return f"{kind.upper()}-{value.hex}"


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """All side-effecting or environment-dependent graph collaborators."""

    model: StructuredOutputModel
    case_context_provider: CaseContextProvider
    policy_provider: PolicyProvider
    verification_provider: VerificationProvider
    human_review_provider: HumanReviewProvider
    operational_memory_store: OperationalMemoryStore
    evidence_provider: EvidenceProvider
    learning_trace_limits: LearningTraceLimits = field(default_factory=LearningTraceLimits)
    reviewer_gate_config: ReviewerGateConfig = field(default_factory=ReviewerGateConfig)
    user_risk_config: UserRiskConfig = field(default_factory=UserRiskConfig)
    user_risk_provider: UserRiskProvider | None = None
    clock: Clock = UtcClock()
    id_factory: IdFactory = StableIdFactory()
