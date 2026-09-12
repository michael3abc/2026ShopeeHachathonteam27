import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from .domain import ClaimId, ReasonCode
from .primitives import ContractModel, Ref, UTCDateTime, unique

# A bounded safety rule for the documented public text surface, not a universal PII detector.
RESTRICTED_TEXT = re.compile(
    r"https?://|data:|file://|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\bbearer\s+\S+|"
    r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+|\b(?:\+?\d[\d ()-]{7,}\d)\b|"
    r"\b(?:ARTIFACT|CASE|ORDER|EVIDENCE|HANDOFF)-[A-Za-z0-9_-]+",
    re.IGNORECASE,
)


def safe_summary(value: str) -> str:
    if not value.strip() or RESTRICTED_TEXT.search(value):
        raise ValueError("Summary contains empty or restricted text")
    return value


Summary = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(safe_summary)]


class MemoryQuerySummary(ContractModel):
    query_summary: Summary


class MemoryScope(ContractModel):
    market: Ref
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    claim_ids: list[ClaimId] = Field(default_factory=list)
    categories: list[Ref] = Field(default_factory=list)


class MemoryBase(ContractModel):
    memory_id: Ref
    claim_registry_version: Ref
    policy_version: Ref
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    retrieval_summary: Summary
    recommended_behavior: Ref
    trigger_conditions: Annotated[list[Ref], Field(min_length=1)]
    scope: MemoryScope


class MemoryCandidate(MemoryBase):
    status: Literal["CANDIDATE"]
    rationale: Ref
    source_case_refs: Annotated[list[Ref], Field(min_length=1)]
    source_revision_event_refs: Annotated[list[Ref], Field(min_length=1)]


class ApprovedMemory(MemoryBase):
    status: Literal["APPROVED"]
    approved_at: UTCDateTime


class MemorySearchHit(ContractModel):
    memory: ApprovedMemory
    similarity: Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]


def validate_candidate(candidate: MemoryCandidate, allowed_scope: MemoryScope, case_refs: list[str], correction_refs: list[str], policy_version: str, registry_version: str) -> None:
    candidate = MemoryCandidate.model_validate(candidate)
    for label, values in (
        ("source case", candidate.source_case_refs), ("correction", candidate.source_revision_event_refs),
        ("reason", candidate.scope.reason_codes), ("claim", candidate.scope.claim_ids), ("category", candidate.scope.categories),
    ):
        unique(values, label)
    if candidate.scope.market != allowed_scope.market or candidate.policy_version != policy_version or candidate.claim_registry_version != registry_version:
        raise ValueError("Candidate changes the source market or versions")
    if not set(candidate.source_case_refs) <= set(case_refs) or not set(candidate.source_revision_event_refs) <= set(correction_refs):
        raise ValueError("Candidate cites an unconfirmed correction source")
    for supplied, allowed in (
        (candidate.scope.reason_codes, allowed_scope.reason_codes),
        (candidate.scope.claim_ids, allowed_scope.claim_ids),
        (candidate.scope.categories, allowed_scope.categories),
    ):
        if not set(supplied) <= set(allowed):
            raise ValueError("Candidate scope exceeds its correction sources")
    for prose in [candidate.retrieval_summary, candidate.recommended_behavior, candidate.rationale, *candidate.trigger_conditions]:
        safe_summary(prose)
