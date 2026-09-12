from typing import Any

import httpx

from return_agent_contracts.domain import CaseContextLoadResult, EvidenceItem, PolicyBundle, VerificationResult
from return_agent_contracts.human import HumanReviewResult
from return_agent_contracts.memory import MemorySearchHit
from return_agent_contracts.providers import ContractConflict, FetchHumanReviewParams, FetchHumanReviewRequest, LoadCaseContextParams, LoadCaseContextRequest, ProviderResponse, ProviderUnavailable, QueryApprovedMemoryParams, QueryApprovedMemoryRequest, ResolveEvidenceParams, ResolveEvidenceRequest, RetrievePolicyParams, RetrievePolicyRequest, SubmitHumanReviewParams, SubmitHumanReviewRequest, SubmitMemoryCandidateParams, SubmitMemoryCandidateRequest, VerifyHandoffParams, VerifyHandoffRequest


class HttpProviders:
    def __init__(self, base_url: str, token: str, *, timeout: float = 30, transport=None):
        if not token:
            raise ValueError("Internal service token is required")
        self.client = httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": "Bearer " + token}, timeout=httpx.Timeout(timeout, connect=5), limits=httpx.Limits(max_connections=8, max_keepalive_connections=4), transport=transport)

    def close(self) -> None:
        self.client.close()

    def call(self, path: str, request, result_type: Any):
        try:
            response = self.client.post(path, json=request.model_dump(mode="json"))
        except httpx.HTTPError:
            raise ProviderUnavailable("Internal provider transport is unavailable") from None
        if response.status_code == 409:
            raise ContractConflict("Internal provider rejected conflicting content")
        if response.status_code == 422:
            raise ValueError("Internal provider rejected the typed request")
        if response.status_code != 200:
            raise ProviderUnavailable(f"Internal provider returned HTTP {response.status_code}")
        try:
            return ProviderResponse[result_type].model_validate_json(response.content).result
        except ValueError:
            raise ProviderUnavailable("Internal provider response failed validation") from None

    def load_case_context(self, params: LoadCaseContextParams) -> CaseContextLoadResult:
        return self.call("/internal/v1/case-context", LoadCaseContextRequest(method="CaseContextProvider.load_case_context", params=params), CaseContextLoadResult)

    def retrieve_policy(self, params: RetrievePolicyParams) -> PolicyBundle:
        return self.call("/internal/v1/policy", RetrievePolicyRequest(method="PolicyProvider.retrieve_policy", params=params), PolicyBundle)

    def resolve(self, params: ResolveEvidenceParams) -> EvidenceItem:
        return self.call("/internal/v1/evidence/resolve", ResolveEvidenceRequest(method="EvidenceProvider.resolve", params=params), EvidenceItem)

    def verify(self, params: VerifyHandoffParams) -> VerificationResult:
        return self.call("/internal/v1/verification", VerifyHandoffRequest(method="VerificationProvider.verify", params=params), VerificationResult)

    def submit_for_review(self, params: SubmitHumanReviewParams) -> str:
        return self.call("/internal/v1/human-reviews", SubmitHumanReviewRequest(method="HumanReviewProvider.submit_for_review", params=params), str)

    def fetch_result(self, params: FetchHumanReviewParams) -> HumanReviewResult | None:
        return self.call("/internal/v1/human-reviews/result", FetchHumanReviewRequest(method="HumanReviewProvider.fetch_result", params=params), HumanReviewResult | None)

    def query_approved(self, params: QueryApprovedMemoryParams) -> list[MemorySearchHit]:
        return self.call("/internal/v1/memory/query", QueryApprovedMemoryRequest(method="OperationalMemoryStore.query_approved", params=params), list[MemorySearchHit])

    def submit_candidate(self, params: SubmitMemoryCandidateParams) -> str:
        return self.call("/internal/v1/memory/candidates", SubmitMemoryCandidateRequest(method="OperationalMemoryStore.submit_candidate", params=params), str)
