"""Synchronous HTTP adapters for Agent-to-API Provider boundaries."""

from __future__ import annotations
from .policy_v2 import PolicyPathId

from .models import ReviewResult

from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from .base import NonEmptyText, OpaqueRef, PositiveInt
from .enums import ClaimId, ReasonCode, VerificationStatus
from .base import UTCDateTime
from .user_risk import UserRiskSnapshot
from .interfaces import UserRiskProvider
from .transport import PrepareUserRiskSnapshotRequest, PrepareUserRiskSnapshotResponse
from .interfaces import (
    CaseContextProvider,
    EvidenceProvider,
    HumanReviewProvider,
    OperationalMemoryStore,
    PolicyProvider,
    VerificationProvider,
)
from .models import (
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
    UnavailableVerificationResult,
    VerificationResult,
)
from .transport import (
    FetchHumanReviewRequest,
    FetchHumanReviewResponse,
    LoadCaseContextRequest,
    LoadCaseContextResponse,
    QueryApprovedMemoryRequest,
    QueryApprovedMemoryResponse,
    ResolveEvidenceRequest,
    ResolveEvidenceResponse,
    RetrievePolicyRequest,
    RetrievePolicyResponse,
    SubmitHumanReviewRequest,
    SubmitHumanReviewResponse,
    SubmitMemoryCandidateRequest,
    SubmitMemoryCandidateResponse,
    VerifyHandoffRequest,
    VerifyHandoffResponse,
)


class ProviderTransportError(RuntimeError):
    """The remote Provider did not return a valid successful contract response."""


class _HttpProvider:
    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip() or not service_token.strip():
            raise ValueError("base_url and service_token must be non-empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def _post(self, path: str, request: object, response_type: type):
        try:
            response = self._client.post(
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._service_token}"},
                json=request.model_dump(mode="json"),
            )
        except httpx.RequestError as error:
            raise ProviderTransportError(
                f"Provider transport is unavailable for {path}"
            ) from error
        if not response.is_success:
            raise ProviderTransportError(
                f"Provider returned HTTP {response.status_code} for {path}"
            )
        try:
            return response_type.model_validate(response.json()).result
        except (TypeError, ValueError, ValidationError) as error:
            raise ProviderTransportError(
                f"Provider returned an invalid contract response for {path}"
            ) from error


class HttpCaseContextProvider(_HttpProvider, CaseContextProvider):
    def load_case_context(self, case_ref: OpaqueRef) -> CaseContextLoadResult:
        return self._post(
            "/internal/v1/case-context",
            LoadCaseContextRequest(
                method="CaseContextProvider.load_case_context",
                params={"case_ref": case_ref},
            ),
            LoadCaseContextResponse,
        )


class HttpUserRiskProvider(_HttpProvider, UserRiskProvider):
    def prepare_snapshot(self, case_ref: OpaqueRef, reason_code: ReasonCode, as_of: UTCDateTime) -> UserRiskSnapshot:
        return self._post("/internal/v1/user-risk/snapshot", PrepareUserRiskSnapshotRequest(
            method="UserRiskProvider.prepare_snapshot",params={"case_ref":case_ref,"reason_code":reason_code,"as_of":as_of}),
            PrepareUserRiskSnapshotResponse)


class HttpPolicyProvider(_HttpProvider, PolicyProvider):
    def retrieve_policy(
        self,
        case_context: CaseContext,
        order_snapshot: OrderSnapshot,
        reason_code: ReasonCode,
        claimed_line_item_ids: Sequence[OpaqueRef],
        *, selected_path_id: PolicyPathId | None = None,
    ) -> PolicyBundle:
        return self._post(
            "/internal/v1/policy",
            RetrievePolicyRequest(
                method="PolicyProvider.retrieve_policy",
                params={
                    "case_context": case_context,
                    "order_snapshot": order_snapshot,
                    "reason_code": reason_code,
                    "claimed_line_item_ids": list(claimed_line_item_ids),
                    **({"selected_path_id": selected_path_id} if selected_path_id is not None else {}),
                },
            ),
            RetrievePolicyResponse,
        )


class HttpOperationalMemoryStore(_HttpProvider, OperationalMemoryStore):
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
    ) -> Sequence[MemorySearchHit]:
        return self._post(
            "/internal/v1/memory/query",
            QueryApprovedMemoryRequest(
                method="OperationalMemoryStore.query_approved",
                params={
                    "query_summary": query_summary,
                    "market": market,
                    "reason_code": reason_code,
                    "required_claim_ids": list(required_claim_ids),
                    "categories": list(categories),
                    "policy_versions": list(policy_versions),
                    "claim_registry_major": claim_registry_major,
                    "top_k": top_k,
                    **({"policy_path_id":policy_path_id} if policy_path_id is not None else {}),
                },
            ),
            QueryApprovedMemoryResponse,
        )

    def submit_candidate(self, candidate: MemoryCandidate) -> OpaqueRef:
        return self._post(
            "/internal/v1/memory/candidates",
            SubmitMemoryCandidateRequest(
                method="OperationalMemoryStore.submit_candidate",
                params={"candidate": candidate},
            ),
            SubmitMemoryCandidateResponse,
        )


class HttpEvidenceProvider(_HttpProvider, EvidenceProvider):
    def resolve(self, artifact_ref: OpaqueRef) -> EvidenceItem:
        return self._post(
            "/internal/v1/evidence/resolve",
            ResolveEvidenceRequest(
                method="EvidenceProvider.resolve",
                params={"artifact_ref": artifact_ref},
            ),
            ResolveEvidenceResponse,
        )


class HttpHumanReviewProvider(_HttpProvider, HumanReviewProvider):
    def submit_for_review(
        self, handoff: ProposedDecisionHandoff, review: ReviewResult,
        dossier: HumanReviewDossier | None = None,
    ) -> OpaqueRef:
        return self._post(
            "/internal/v1/human-reviews",
            SubmitHumanReviewRequest(
                method="HumanReviewProvider.submit_for_review",
                params={"handoff": handoff, "review": review, "dossier": dossier},
            ),
            SubmitHumanReviewResponse,
        )

    def fetch_result(self, review_ref: OpaqueRef) -> HumanReviewResult | None:
        return self._post(
            "/internal/v1/human-reviews/result",
            FetchHumanReviewRequest(
                method="HumanReviewProvider.fetch_result",
                params={"review_ref": review_ref},
            ),
            FetchHumanReviewResponse,
        )


class HttpVerificationProvider(_HttpProvider, VerificationProvider):
    """Call API's trusted Verification boundary with a service credential."""

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            service_token=service_token,
            timeout_seconds=timeout_seconds,
            client=client,
        )

    def verify(self, handoff: ProposedDecisionHandoff) -> VerificationResult:
        request = VerifyHandoffRequest(
            method="VerificationProvider.verify",
            params={"handoff": handoff},
        )
        try:
            response = self._client.post(
                f"{self._base_url}/internal/v1/verification",
                headers={"Authorization": f"Bearer {self._service_token}"},
                json=request.model_dump(mode="json"),
            )
        except httpx.RequestError:
            return self._unavailable()
        if response.status_code >= 500:
            return self._unavailable()
        if not response.is_success:
            raise ProviderTransportError(
                f"Verification service returned HTTP {response.status_code}"
            )
        try:
            return VerifyHandoffResponse.model_validate(response.json()).result
        except (TypeError, ValueError, ValidationError) as error:
            raise ProviderTransportError(
                "Verification service returned an invalid contract response"
            ) from error

    @staticmethod
    def _unavailable() -> VerificationResult:
        return UnavailableVerificationResult(
            status=VerificationStatus.UNAVAILABLE,
            issues=[],
            verification_version="verification:transport-unavailable",
        )
