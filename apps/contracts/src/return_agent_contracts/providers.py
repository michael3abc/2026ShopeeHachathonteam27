"""Infrastructure-neutral capability ports and their typed parameters."""
from typing import Annotated, Generic, Literal, Protocol, TypeVar

from pydantic import Field

from .domain import (
    CaseContext, CaseContextLoadResult, ClaimId, EvidenceItem, HumanReviewDossier,
    OrderSnapshot, PolicyBundle, ProposedDecisionHandoff, ReasonCode, ReviewResult,
    VerificationResult,
)
from .human import HumanReviewResult, ResolutionHandoff
from .memory import MemoryCandidate, MemorySearchHit, Summary
from .primitives import ContractModel, Ref, UTCDateTime


class ProviderUnavailable(RuntimeError):
    """A dependency has no trustworthy result; callers must not invent success."""


class ContractConflict(ValueError):
    """A stable identifier was reused with different content."""


class LoadCaseContextParams(ContractModel):
    case_ref: Ref


class RetrievePolicyParams(ContractModel):
    case_context: CaseContext
    order_snapshot: OrderSnapshot
    reason_code: ReasonCode
    claimed_line_item_ids: Annotated[list[Ref], Field(min_length=1)]


class VerifyHandoffParams(ContractModel):
    handoff: ProposedDecisionHandoff


class ResolveEvidenceParams(ContractModel):
    artifact_ref: Ref


class QueryApprovedMemoryParams(ContractModel):
    query_summary: Summary
    market: Ref
    reason_code: ReasonCode
    required_claim_ids: Annotated[list[ClaimId], Field(min_length=1)]
    categories: list[Ref] = Field(default_factory=list)
    policy_versions: Annotated[list[Ref], Field(min_length=1)]
    claim_registry_major: Annotated[int, Field(ge=1)]
    top_k: Annotated[int, Field(ge=1, le=3)] = 3


class SubmitMemoryCandidateParams(ContractModel):
    candidate: MemoryCandidate


class SubmitHumanReviewParams(ContractModel):
    handoff: ProposedDecisionHandoff
    review: ReviewResult
    dossier: HumanReviewDossier | None = None


class FetchHumanReviewParams(ContractModel):
    review_ref: Ref


class ExecuteRefundRequest(ContractModel):
    resolution_handoff: ResolutionHandoff


class ApplyRefundRequest(ExecuteRefundRequest):
    execution_ref: Ref


class AppliedRefundApplicationResult(ContractModel):
    status: Literal["APPLIED"]
    application_ref: Ref
    applied_at: UTCDateTime


class RejectedRefundApplicationResult(ContractModel):
    status: Literal["REJECTED"]
    reason_codes: Annotated[list[Ref], Field(min_length=1)]
    rejected_at: UTCDateTime


RefundApplicationResult = Annotated[AppliedRefundApplicationResult | RejectedRefundApplicationResult, Field(discriminator="status")]


class ExecutionRecordBase(ContractModel):
    execution_ref: Ref
    case_ref: Ref
    handoff_id: Ref
    created_at: UTCDateTime
    updated_at: UTCDateTime


class SucceededRefundExecutionRecord(ExecutionRecordBase):
    status: Literal["SUCCEEDED"]
    application_result: AppliedRefundApplicationResult


class RejectedRefundExecutionRecord(ExecutionRecordBase):
    status: Literal["REJECTED"]
    application_result: RejectedRefundApplicationResult


RefundExecutionRecord = Annotated[SucceededRefundExecutionRecord | RejectedRefundExecutionRecord, Field(discriminator="status")]


class LoadCaseContextRequest(ContractModel):
    method: Literal["CaseContextProvider.load_case_context"]
    params: LoadCaseContextParams


class RetrievePolicyRequest(ContractModel):
    method: Literal["PolicyProvider.retrieve_policy"]
    params: RetrievePolicyParams


class VerifyHandoffRequest(ContractModel):
    method: Literal["VerificationProvider.verify"]
    params: VerifyHandoffParams


class ResolveEvidenceRequest(ContractModel):
    method: Literal["EvidenceProvider.resolve"]
    params: ResolveEvidenceParams


class QueryApprovedMemoryRequest(ContractModel):
    method: Literal["OperationalMemoryStore.query_approved"]
    params: QueryApprovedMemoryParams


class SubmitMemoryCandidateRequest(ContractModel):
    method: Literal["OperationalMemoryStore.submit_candidate"]
    params: SubmitMemoryCandidateParams


class SubmitHumanReviewRequest(ContractModel):
    method: Literal["HumanReviewProvider.submit_for_review"]
    params: SubmitHumanReviewParams


class FetchHumanReviewRequest(ContractModel):
    method: Literal["HumanReviewProvider.fetch_result"]
    params: FetchHumanReviewParams


ResultT = TypeVar("ResultT")


class ProviderResponse(ContractModel, Generic[ResultT]):
    result: ResultT


class CaseContextProvider(Protocol):
    def load_case_context(self, params: LoadCaseContextParams) -> CaseContextLoadResult: ...


class PolicyProvider(Protocol):
    def retrieve_policy(self, params: RetrievePolicyParams) -> PolicyBundle: ...


class EvidenceProvider(Protocol):
    def resolve(self, params: ResolveEvidenceParams) -> EvidenceItem: ...


class VerificationProvider(Protocol):
    def verify(self, params: VerifyHandoffParams) -> VerificationResult: ...


class HumanReviewProvider(Protocol):
    def submit_for_review(self, params: SubmitHumanReviewParams) -> str: ...
    def fetch_result(self, params: FetchHumanReviewParams) -> HumanReviewResult | None: ...


class OperationalMemoryStore(Protocol):
    def query_approved(self, params: QueryApprovedMemoryParams) -> list[MemorySearchHit]: ...
    def submit_candidate(self, params: SubmitMemoryCandidateParams) -> str: ...


class RefundExecutionProvider(Protocol):
    def execute(self, request: ExecuteRefundRequest) -> RefundExecutionRecord: ...
    def get_status(self, execution_ref: str) -> RefundExecutionRecord | None: ...


class RefundApplicationProvider(Protocol):
    def apply(self, request: ApplyRefundRequest) -> RefundApplicationResult: ...
