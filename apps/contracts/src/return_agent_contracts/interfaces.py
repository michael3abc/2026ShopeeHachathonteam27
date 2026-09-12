"""Provider interfaces at Agent and trusted operations boundaries.

These interfaces intentionally describe semantics, not HTTP paths or SDKs. A
provider owner may implement them directly or provide an adapter around its API.
"""

from __future__ import annotations
from .policy_v2 import PolicyPathId

from .models import ReviewResult

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .base import NonEmptyText, OpaqueRef, PositiveInt
from .enums import ClaimId, ReasonCode
from .base import UTCDateTime
from .user_risk import UserRiskSnapshot
from .models import (
    ApplyRefundRequest,
    CaseContext,
    CaseContextLoadResult,
    EvidenceItem,
    ExecuteRefundRequest,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryCandidate,
    MemorySearchHit,
    OrderSnapshot,
    PolicyBundle,
    ProposedDecisionHandoff,
    RefundApplicationResult,
    RefundExecutionRecord,
    VerificationResult,
)


@runtime_checkable
class UserRiskProvider(Protocol):
    def prepare_snapshot(self, case_ref: OpaqueRef, reason_code: ReasonCode, as_of: UTCDateTime) -> UserRiskSnapshot: ...


@runtime_checkable
class CaseContextProvider(Protocol):
    """Graph node: load_case_context. Read-only and safe to retry."""

    def load_case_context(self, case_ref: OpaqueRef) -> CaseContextLoadResult: ...


@runtime_checkable
class PolicyProvider(Protocol):
    """Graph node: retrieve_policy. Read-only and safe to retry."""

    def retrieve_policy(
        self,
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[OpaqueRef],
        *, selected_path_id: PolicyPathId | None = None,
    ) -> PolicyBundle: ...


@runtime_checkable
class VerificationProvider(Protocol):
    """Graph node: external_verification. Safe to retry for the same handoff."""

    def verify(self, handoff: ProposedDecisionHandoff) -> VerificationResult: ...


@runtime_checkable
class HumanReviewProvider(Protocol):
    """Graph interrupt boundary for submitting and polling human review."""

    def submit_for_review(
        self, handoff: ProposedDecisionHandoff, review: ReviewResult,
        dossier: HumanReviewDossier | None = None,
    ) -> OpaqueRef: ...

    def fetch_result(self, review_ref: OpaqueRef) -> HumanReviewResult | None: ...


@runtime_checkable
class OperationalMemoryStore(Protocol):
    """External approved-memory store and candidate submission boundary."""

    def query_approved(
        self,
        query_summary: NonEmptyText,
        market: NonEmptyText,
        reason_code: ReasonCode,
        required_claim_ids: Sequence[ClaimId],
        categories: Sequence[OpaqueRef],
        policy_versions: Sequence[OpaqueRef],
        claim_registry_major: PositiveInt,
        top_k: PositiveInt = 3,
        *, policy_path_id: PolicyPathId | None = None,
    ) -> Sequence[MemorySearchHit]: ...

    def submit_candidate(self, candidate: MemoryCandidate) -> OpaqueRef: ...


@runtime_checkable
class EvidenceProvider(Protocol):
    """Resolve an uploaded artifact reference into neutral evidence metadata."""

    def resolve(self, artifact_ref: OpaqueRef) -> EvidenceItem: ...


@runtime_checkable
class RefundExecutionProvider(Protocol):
    """Trusted Backend boundary; not a graph tool or public frontend API."""

    def execute(self, request: ExecuteRefundRequest) -> RefundExecutionRecord: ...

    def get_status(self, execution_ref: OpaqueRef) -> RefundExecutionRecord | None: ...


@runtime_checkable
class RefundApplicationProvider(Protocol):
    """Allen-owned idempotent mutation of canonical order/case state."""

    def apply(self, request: ApplyRefundRequest) -> RefundApplicationResult: ...
