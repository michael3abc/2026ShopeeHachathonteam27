import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from return_agent_contracts.domain import CaseContextLoadResult, EvidenceItem, PolicyBundle, VerificationResult
from return_agent_contracts.human import HumanReviewResult
from return_agent_contracts.providers import FetchHumanReviewRequest, LoadCaseContextRequest, ProviderResponse, ResolveEvidenceRequest, RetrievePolicyRequest, SubmitHumanReviewRequest, VerifyHandoffRequest

from .capabilities import CapabilityStore
from .settings import Settings


def internal_router(settings: Settings, capabilities: CapabilityStore | None) -> APIRouter:
    def authenticate(authorization: str | None = Header(default=None)) -> None:
        token = settings.internal_service_token
        if token is None or not token.get_secret_value():
            raise HTTPException(503, "Internal authorization is not configured")
        expected = "Bearer " + token.get_secret_value()
        if authorization is None or not secrets.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "Invalid internal authorization")
        if capabilities is None:
            raise HTTPException(503, "Providers are not configured")

    router = APIRouter(prefix="/internal/v1", dependencies=[Depends(authenticate)])

    @router.post("/case-context", response_model=ProviderResponse[CaseContextLoadResult])
    def context(body: LoadCaseContextRequest):
        return ProviderResponse(result=capabilities.load_case_context(body.params))

    @router.post("/evidence/resolve", response_model=ProviderResponse[EvidenceItem])
    def evidence(body: ResolveEvidenceRequest):
        return ProviderResponse(result=capabilities.resolve(body.params))

    @router.post("/policy", response_model=ProviderResponse[PolicyBundle])
    def policy(body: RetrievePolicyRequest):
        return ProviderResponse(result=capabilities.retrieve_policy(body.params))

    @router.post("/verification", response_model=ProviderResponse[VerificationResult])
    def verification(body: VerifyHandoffRequest):
        return ProviderResponse(result=capabilities.verify(body.params))

    @router.post("/human-reviews", response_model=ProviderResponse[str])
    def submit(body: SubmitHumanReviewRequest):
        return ProviderResponse(result=capabilities.submit_for_review(body.params))

    @router.post("/human-reviews/result", response_model=ProviderResponse[HumanReviewResult | None])
    def fetch(body: FetchHumanReviewRequest):
        return ProviderResponse(result=capabilities.fetch_result(body.params))

    return router
