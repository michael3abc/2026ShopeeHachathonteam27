"""Allowlisted observation data. Never an authorization surface."""
import re
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, field_validator, model_validator

from .domain import Action, ClaimId, ReasonCode, ReviewGateResult
from .memory import MemoryRetrievalObservation, RESTRICTED_TEXT
from .primitives import ContractModel, UTCDateTime


def safe_identifier(value: str) -> str:
    if re.fullmatch(r"\+?\d[\d.-]{7,}\d", value):
        raise ValueError("Phone-shaped values cannot enter activity identifiers")
    return value


SafeId = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_:.-]+$"), AfterValidator(safe_identifier)]
Nonnegative = Annotated[int, Field(ge=0, strict=True)]


class ActivityFinding(ContractModel):
    claim_id: ClaimId
    status: Literal["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]
    evidence_refs: Annotated[list[SafeId], Field(max_length=30)] = Field(default_factory=list)


class ActivityInputs(ContractModel):
    argument_count: Nonnegative
    reason_code: ReasonCode | None = None
    required_claim_ids: Annotated[list[ClaimId], Field(max_length=30)] = Field(default_factory=list)
    top_k: Annotated[int, Field(ge=1, le=3)] | None = None


class ActivityFacts(ContractModel):
    action: Action | None = None
    count: Nonnegative | None = None
    finding_statuses: Annotated[list[SafeId], Field(max_length=30)] = Field(default_factory=list)
    findings: Annotated[list[ActivityFinding], Field(max_length=30)] = Field(default_factory=list)
    next_node: SafeId | None = None
    outcome: SafeId | None = None
    reason_codes: Annotated[list[SafeId], Field(max_length=30)] = Field(default_factory=list)
    references: Annotated[list[SafeId], Field(max_length=30)] = Field(default_factory=list)
    revision_round: Nonnegative | None = None
    verdict: Literal["APPROVE", "REVISE"] | None = None


class Lifecycle(ContractModel):
    type: Literal["node", "model", "tool"]
    name: SafeId
    phase: Literal["STARTED", "COMPLETED", "PAUSED", "FAILED"]
    duration_ms: Nonnegative | None = None
    error_code: SafeId | None = None
    facts: ActivityFacts = Field(default_factory=ActivityFacts)
    inputs: ActivityInputs | None = None
    model: SafeId | None = None


class NodeSummary(ContractModel):
    type: Literal["node_summary"] = "node_summary"
    facts: ActivityFacts
    memory_retrieval: MemoryRetrievalObservation | None = None
    review_gate: ReviewGateResult | None = None

    @field_validator("memory_retrieval", mode="before")
    @classmethod
    def omit_memory_prose(cls, value: object) -> None:
        # Full text is available through the dedicated memory projection only.
        return None

    @field_validator("review_gate")
    @classmethod
    def allowlisted_gate_version(cls, value: ReviewGateResult | None) -> ReviewGateResult | None:
        if value is not None:
            if not re.fullmatch(r"[A-Za-z0-9_:.-]{1,200}", value.config_version):
                raise ValueError("Gate version cannot contain free text")
            safe_identifier(value.config_version)
        return value


class BackgroundStatus(ContractModel):
    type: Literal["background"] = "background"
    status: Literal["SCHEDULED", "STARTED", "RETRYING", "COMPLETED", "SKIPPED", "FAILED"]
    error_code: SafeId | None = None


def validate_narration_text(text: str) -> str:
    if RESTRICTED_TEXT.search(text):
        raise ValueError("Narration contains restricted text")
    sentences = [part.strip() for part in re.split(r"[。！？!?]+", text) if part.strip()]
    if not 1 <= len(sentences) <= 2 or not re.search(r"[\u3400-\u9fff]", text):
        raise ValueError("Narration must contain one or two Chinese sentences")
    if re.search(r"已(?:進入|轉交|送交|啟動)(?:下|下一)", text):
        raise ValueError("Narration cannot assert execution of the next node")
    return text


NarrationTextValue = Annotated[str, Field(min_length=1, max_length=600), AfterValidator(validate_narration_text)]


class NarrationText(ContractModel):
    text: NarrationTextValue


class Narration(ContractModel):
    type: Literal["narration"] = "narration"
    source_event_id: SafeId
    status: Literal["COMPLETED", "UNAVAILABLE"]
    text: NarrationTextValue | None = None
    error_code: SafeId | None = None

    @model_validator(mode="after")
    def coherent_result(self) -> Self:
        if self.status == "COMPLETED" and (self.text is None or self.error_code is not None):
            raise ValueError("Completed narration requires text without an error")
        if self.status == "UNAVAILABLE" and (self.text is not None or self.error_code is None):
            raise ValueError("Unavailable narration requires an error and no text")
        return self


ActivityPayload = Annotated[Lifecycle | NodeSummary | Narration | BackgroundStatus, Field(discriminator="type")]


class ActivityEmission(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: SafeId
    case_ref: SafeId
    scope: Literal["CASE", "REFUND", "MEMORY"]
    run_id: SafeId
    job_id: SafeId | None = None
    node: SafeId
    operation_id: SafeId
    parent_operation_id: SafeId | None = None
    attempt_id: SafeId
    occurred_at: UTCDateTime
    payload: ActivityPayload


class ActivityEvent(ActivityEmission):
    seq: Annotated[int, Field(ge=1)]


class ActivityPage(ContractModel):
    events: list[ActivityEvent]
    next_cursor: Nonnegative
    has_more: bool


class NarrationJob(ContractModel):
    job_id: SafeId
    source: ActivityEmission

    @model_validator(mode="after")
    def facts_only(self) -> Self:
        if not isinstance(self.source.payload, NodeSummary):
            raise ValueError("Narration source must be a node summary")
        if self.source.payload.review_gate is not None or self.source.payload.memory_retrieval is not None:
            raise ValueError("Narration source permits facts only")
        return self
