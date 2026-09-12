"""JSON adapter envelopes defined by docs/spec/08-external-interfaces.md."""

from __future__ import annotations

from .models import ReviewResult

from typing import Literal

from pydantic import Field

from .base import ContractModel, OpaqueRef, PositiveInt
from .enums import ClaimId, ReasonCode
from .base import UTCDateTime
from .user_risk import UserRiskSnapshot
from .policy_v2 import PolicyPathId


class PrepareUserRiskSnapshotParams(ContractModel):
    case_ref: OpaqueRef
    reason_code: ReasonCode
    as_of: UTCDateTime


class PrepareUserRiskSnapshotRequest(ContractModel):
    method: Literal["UserRiskProvider.prepare_snapshot"]
    params: PrepareUserRiskSnapshotParams


class PrepareUserRiskSnapshotResponse(ContractModel):
    result: UserRiskSnapshot
from .models import (
    CaseContext,
    CaseContextLoadResult,
    EvidenceItem,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryCandidate,
    MemoryQuerySummary,
    MemorySearchHit,
    OrderSnapshot,
    PolicyBundle,
    ProposedDecisionHandoff,
    VerificationResult,
)


class LoadCaseContextParams(ContractModel):
    case_ref: OpaqueRef


class LoadCaseContextRequest(ContractModel):
    method: Literal["CaseContextProvider.load_case_context"]
    params: LoadCaseContextParams


class LoadCaseContextResponse(ContractModel):
    result: CaseContextLoadResult


class RetrievePolicyParams(ContractModel):
    selected_path_id: PolicyPathId | None = Field(default=None, exclude_if=lambda v: v is None)
    case_context: CaseContext
    order_snapshot: OrderSnapshot
    reason_code: ReasonCode
    claimed_line_item_ids: list[OpaqueRef] = Field(min_length=1)


class RetrievePolicyRequest(ContractModel):
    method: Literal["PolicyProvider.retrieve_policy"]
    params: RetrievePolicyParams


class RetrievePolicyResponse(ContractModel):
    result: PolicyBundle


class QueryApprovedMemoryParams(MemoryQuerySummary):
    market: OpaqueRef
    reason_code: ReasonCode
    required_claim_ids: list[ClaimId]
    policy_path_id: PolicyPathId | None = Field(default=None,exclude_if=lambda v: v is None)
    categories: list[OpaqueRef] = Field(default_factory=list)
    policy_versions: list[OpaqueRef] = Field(min_length=1)
    claim_registry_major: PositiveInt
    top_k: PositiveInt = Field(default=3, le=3)


class QueryApprovedMemoryRequest(ContractModel):
    method: Literal["OperationalMemoryStore.query_approved"]
    params: QueryApprovedMemoryParams


class QueryApprovedMemoryResponse(ContractModel):
    result: list[MemorySearchHit] = Field(max_length=3)


class ResolveEvidenceParams(ContractModel):
    artifact_ref: OpaqueRef


class ResolveEvidenceRequest(ContractModel):
    method: Literal["EvidenceProvider.resolve"]
    params: ResolveEvidenceParams


class ResolveEvidenceResponse(ContractModel):
    result: EvidenceItem


class VerifyHandoffParams(ContractModel):
    handoff: ProposedDecisionHandoff


class VerifyHandoffRequest(ContractModel):
    method: Literal["VerificationProvider.verify"]
    params: VerifyHandoffParams


class VerifyHandoffResponse(ContractModel):
    result: VerificationResult


class SubmitHumanReviewParams(ContractModel):
    handoff: ProposedDecisionHandoff
    review: ReviewResult
    dossier: HumanReviewDossier | None = None


class SubmitHumanReviewRequest(ContractModel):
    method: Literal["HumanReviewProvider.submit_for_review"]
    params: SubmitHumanReviewParams


class SubmitHumanReviewResponse(ContractModel):
    result: OpaqueRef


class FetchHumanReviewParams(ContractModel):
    review_ref: OpaqueRef


class FetchHumanReviewRequest(ContractModel):
    method: Literal["HumanReviewProvider.fetch_result"]
    params: FetchHumanReviewParams


class FetchHumanReviewResponse(ContractModel):
    result: HumanReviewResult | None


class SubmitMemoryCandidateParams(ContractModel):
    candidate: MemoryCandidate


class SubmitMemoryCandidateRequest(ContractModel):
    method: Literal["OperationalMemoryStore.submit_candidate"]
    params: SubmitMemoryCandidateParams


class SubmitMemoryCandidateResponse(ContractModel):
    result: OpaqueRef


PROVIDER_REQUEST_MODELS = (
    LoadCaseContextRequest,
    RetrievePolicyRequest,
    QueryApprovedMemoryRequest,
    ResolveEvidenceRequest,
    VerifyHandoffRequest,
    SubmitHumanReviewRequest,
    FetchHumanReviewRequest,
    SubmitMemoryCandidateRequest,
    PrepareUserRiskSnapshotRequest,
)

PROVIDER_RESPONSE_MODELS = (
    LoadCaseContextResponse,
    RetrievePolicyResponse,
    QueryApprovedMemoryResponse,
    ResolveEvidenceResponse,
    VerifyHandoffResponse,
    SubmitHumanReviewResponse,
    FetchHumanReviewResponse,
    SubmitMemoryCandidateResponse,
    PrepareUserRiskSnapshotResponse,
)
