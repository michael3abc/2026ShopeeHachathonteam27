"""In-process deterministic test fakes; these are not production Mock APIs."""

from __future__ import annotations

from return_agent_contracts.models import ReviewResult

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeVar

from pydantic import TypeAdapter
from return_agent_contracts.enums import ClaimId, ReasonCode
from return_agent_contracts.models import (
    ApprovedMemory,
    CaseContext,
    CaseContextLoadResult,
    EvidenceItem,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryCandidate,
    MemorySearchHit,
    OrderSnapshot,
    PolicyBundle,
    ProposedDecisionHandoff,
    VerificationResult,
)
from return_agent_runtime.model import ModelTask, OutputSchema

OutputT = TypeVar("OutputT")
VERIFICATION_ADAPTER = TypeAdapter(VerificationResult)
HUMAN_REVIEW_ADAPTER = TypeAdapter(HumanReviewResult)


@dataclass(frozen=True, slots=True)
class ModelCall:
    task: ModelTask
    system_prompt: str
    payload: Mapping[str, Any]
    schema_name: str


@dataclass(slots=True)
class QueuedModel:
    outputs: dict[ModelTask, deque[Any]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    calls: list[ModelCall] = field(default_factory=list)

    def queue(self, task: ModelTask, *outputs: Any) -> None:
        self.outputs[task].extend(outputs)

    def generate(
        self,
        *,
        task: ModelTask,
        system_prompt: str,
        payload: Mapping[str, Any],
        output_schema: OutputSchema[OutputT],
    ) -> OutputT:
        self.calls.append(ModelCall(task, system_prompt, payload, output_schema.name))
        if task is ModelTask.MEMORY_QUERY_SUMMARY and not self.outputs[task]:
            return output_schema.adapter.validate_python(
                {"query_summary": "Damaged speaker with current evidence."}
            )
        if not self.outputs[task]:
            raise AssertionError(f"no queued output for {task.value}")
        return output_schema.adapter.validate_python(self.outputs[task].popleft())


@dataclass(frozen=True, slots=True)
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


@dataclass(slots=True)
class CaseProviderFake:
    result: CaseContextLoadResult | Exception
    calls: list[str] = field(default_factory=list)

    def load_case_context(self, case_ref: str) -> CaseContextLoadResult:
        self.calls.append(case_ref)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class PolicyProviderFake:
    result: PolicyBundle | Exception
    calls: list[tuple[CaseContext, OrderSnapshot, ReasonCode, tuple[str, ...]]] = field(
        default_factory=list
    )

    def retrieve_policy(
        self,
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[str],
    ) -> PolicyBundle:
        self.calls.append(
            (
                case_context,
                order_snapshot,
                reason_code,
                tuple(claimed_line_item_ids),
            )
        )
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(slots=True)
class VerificationProviderFake:
    results: deque[VerificationResult | Exception]
    calls: list[ProposedDecisionHandoff] = field(default_factory=list)

    def verify(self, handoff: ProposedDecisionHandoff) -> VerificationResult:
        self.calls.append(handoff)
        result = self.results.popleft()
        if isinstance(result, Exception):
            raise result
        return VERIFICATION_ADAPTER.validate_python(result)


@dataclass(slots=True)
class HumanReviewProviderFake:
    results: deque[HumanReviewResult | None | Exception] = field(default_factory=deque)
    review_ref: str = "HUMAN-REVIEW-001"
    submit_error: Exception | None = None
    submit_calls: list[tuple[ProposedDecisionHandoff, ReviewResult]] = field(
        default_factory=list
    )
    fetch_calls: list[str] = field(default_factory=list)

    def submit_for_review(
        self, handoff: ProposedDecisionHandoff, review: ReviewResult,
        dossier: HumanReviewDossier | None = None,
    ) -> str:
        self.submit_calls.append((handoff, review))
        if self.submit_error is not None:
            raise self.submit_error
        return self.review_ref

    def fetch_result(self, review_ref: str) -> HumanReviewResult | None:
        self.fetch_calls.append(review_ref)
        result = self.results.popleft()
        if isinstance(result, Exception):
            raise result
        if result is None:
            return None
        return HUMAN_REVIEW_ADAPTER.validate_python(result)


@dataclass(slots=True)
class MemoryStoreFake:
    results: Sequence[ApprovedMemory | MemorySearchHit] | Exception = ()
    query_calls: list[dict[str, Any]] = field(default_factory=list)

    def query_approved(
        self,
        query_summary: str,
        market: str,
        reason_code: ReasonCode,
        required_claim_ids: Sequence[ClaimId],
        categories: Sequence[str],
        policy_versions: Sequence[str],
        claim_registry_major: int,
        top_k: int = 3,
    ) -> Sequence[MemorySearchHit]:
        self.query_calls.append(
            {
                "query_summary": query_summary,
                "market": market,
                "reason_code": reason_code,
                "required_claim_ids": tuple(required_claim_ids),
                "categories": tuple(categories),
                "policy_versions": tuple(policy_versions),
                "claim_registry_major": claim_registry_major,
                "top_k": top_k,
            }
        )
        if isinstance(self.results, Exception):
            raise self.results
        return [
            item
            if isinstance(item, MemorySearchHit)
            else MemorySearchHit(memory=item, similarity=0.8)
            for item in self.results
        ]

    def submit_candidate(self, candidate: MemoryCandidate) -> str:
        raise AssertionError("memory submission is outside this runtime branch")


@dataclass(slots=True)
class EvidenceProviderFake:
    items: dict[str, EvidenceItem | Exception]
    calls: list[str] = field(default_factory=list)

    def resolve(self, artifact_ref: str) -> EvidenceItem:
        self.calls.append(artifact_ref)
        result = self.items[artifact_ref]
        if isinstance(result, Exception):
            raise result
        return result
