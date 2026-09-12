from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from return_agent_contracts.domain import ReviewerGateConfig
from return_agent_contracts.providers import CaseContextProvider, EvidenceProvider, HumanReviewProvider, OperationalMemoryStore, PolicyProvider, VerificationProvider
from return_agent_contracts.workflow import GraphNodeName, NodeExecutionObservation

ModelTask = Literal["INTAKE", "MEMORY_QUERY_SUMMARY", "ASSESS", "PROPOSE_OR_REVISE", "REVIEW", "MEMORY_DISTILL", "ACTIVITY_NARRATION"]


class StructuredOutputModel(Protocol):
    def generate(self, task: ModelTask, payload: dict[str, Any], output_type: Any) -> object: ...


class RuntimeObserver(Protocol):
    def observe(self, observation: NodeExecutionObservation) -> None: ...
    def paused(self, node: GraphNodeName, task_ref: str) -> None: ...


def stable_id(kind: str, *parts: object) -> str:
    name = f"return-agent:{kind}:" + ":".join(str(part) for part in parts)
    return f"{kind.upper()}-{uuid5(NAMESPACE_URL, name).hex}"


@dataclass(frozen=True)
class RuntimeDependencies:
    model: StructuredOutputModel
    context: CaseContextProvider
    policy: PolicyProvider
    evidence: EvidenceProvider
    verification: VerificationProvider
    human: HumanReviewProvider
    memory: OperationalMemoryStore
    clock: Callable[[], datetime]
    gates: ReviewerGateConfig
    observer: RuntimeObserver | None = None
    ids: Callable[..., str] = stable_id
