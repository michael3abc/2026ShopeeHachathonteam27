"""Versioned internal activity wire contracts; never raw model/tool payloads."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from .base import ContractModel, UTCDateTime
from .enums import ClaimId, ClaimStatus, IntakeCompleteness, ReasonCode, RequestedAction
from .models import MemoryRetrievalObservation
from .review_gates import ReviewGateResult

ACTIVITY_STREAM = "return-agent.activities.v1"
NARRATION_STREAM = "return-agent.narrations.v1"
ACTIVITY_GROUP = "activity-api-v1"
NARRATION_GROUP = "activity-narrator-v1"


def _safe_identifier(value: str) -> str:
    if redact(value) != value:
        raise ValueError("restricted identifier")
    return value


Identifier = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_:.-]+$"),
    AfterValidator(_safe_identifier),
]
Text = Annotated[str, Field(min_length=1, max_length=600)]
Phase = Literal["STARTED", "COMPLETED", "PAUSED", "FAILED"]


def redact(text: str) -> str:
    text = re.sub(
        r"(?i)(?:https?://|artifact://|s3://)\S+", "[reference removed]", text
    )
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?i)(?:bearer\s+|sk-)[A-Za-z0-9_.-]+", "[credential removed]", text)
    text = re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)", "[number removed]", text)
    return text[:600]


def safe_reference(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_:.-]{1,200}", value) and redact(value) == value:
        return value
    return "ref:" + sha256(value.encode()).hexdigest()[:24]


class ActivityFinding(ContractModel):
    claim_id: ClaimId
    status: ClaimStatus
    evidence_refs: list[Identifier] = Field(default_factory=list, max_length=30)


class ActivityFacts(ContractModel):
    """Finite allowlist; raw prose, URLs, messages and documents are excluded."""

    outcome: Identifier | None = None
    action: Literal["FULL_REFUND", "DECLINE"] | None = None
    verdict: Literal["APPROVE", "REVISE"] | None = None
    next_node: Identifier | None = None
    count: int | None = Field(default=None, ge=0)
    revision_round: int | None = Field(default=None, ge=0)
    reason_codes: list[Identifier] = Field(default_factory=list, max_length=30)
    # Opaque references, not artifact URLs or user-provided prose.
    references: list[Identifier] = Field(default_factory=list, max_length=30)
    finding_statuses: list[Identifier] = Field(default_factory=list, max_length=30)
    findings: list[ActivityFinding] = Field(default_factory=list, max_length=30)


class ActivityInputs(ContractModel):
    argument_count: int = Field(ge=0)
    reason_code: ReasonCode | None = None
    required_claim_ids: list[ClaimId] = Field(default_factory=list, max_length=30)
    top_k: int | None = Field(default=None, ge=1, le=3)
    # No query text, evidence URLs, user identity or complete request bodies.


class Lifecycle(ContractModel):
    type: Literal["node", "model", "tool"]
    phase: Phase
    name: Identifier
    duration_ms: int | None = Field(default=None, ge=0)
    model: Identifier | None = None
    facts: ActivityFacts = Field(default_factory=ActivityFacts)
    inputs: ActivityInputs | None = None
    error_code: Identifier | None = None


class IntentDisplay(ContractModel):
    """Safe snapshot of a validated intake, never model prose."""

    reason_code: ReasonCode | None = None
    requested_action: RequestedAction
    claimed_line_item_ids: list[Identifier] = Field(default_factory=list)
    completeness: IntakeCompleteness
    missing_fields: list[Literal["ORDER", "REASON", "ACTION", "ITEMS", "OTHER"]] = (
        Field(default_factory=list)
    )


class NodeSummary(ContractModel):
    type: Literal["node_summary"] = "node_summary"
    facts: ActivityFacts
    intent_display: IntentDisplay | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    memory_retrieval: MemoryRetrievalObservation | None = None
    review_gate: ReviewGateResult | None = None

    @field_validator("memory_retrieval")
    @classmethod
    def omit_memory_prose(cls, value):
        # Reuse the retrieval DTO/order/scores, never copy case or memory prose
        # into the activity stream. The dedicated retrieval surface owns it.
        if value is None:
            return None
        raw = value.model_dump(mode="json")
        if raw["query_summary"] is not None:
            raw["query_summary"] = "[omitted from activity]"
        for hit in raw["hits"]:
            memory = hit["memory"]
            for key in ("memory_id", "policy_version", "claim_registry_version"):
                memory[key] = safe_reference(memory[key])
            memory["scope"]["market"] = safe_reference(memory["scope"]["market"])
            memory["scope"]["categories"] = [
                safe_reference(value) for value in memory["scope"]["categories"]
            ]
            for key in ("retrieval_summary", "recommended_behavior"):
                memory[key] = "[omitted from activity]"
            memory["trigger_conditions"] = ["[omitted from activity]"]
        return MemoryRetrievalObservation.model_validate(raw)

    @field_validator("review_gate")
    @classmethod
    def safe_gate_version(
        cls, value: ReviewGateResult | None
    ) -> ReviewGateResult | None:
        if value is None:
            return None
        return value.model_copy(
            update={"config_version": safe_reference(value.config_version)}
        )


class Narration(ContractModel):
    type: Literal["narration"] = "narration"
    source_event_id: Identifier
    status: Literal["COMPLETED", "UNAVAILABLE"]
    text: Text | None = None
    error_code: Identifier | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.status == "COMPLETED":
            if not self.text or self.error_code:
                raise ValueError("successful narration requires text without error")
            if redact(self.text) != self.text:
                raise ValueError("narration contains restricted text")
            sentences = [
                part.strip()
                for part in re.split(r"[。！？!?]+", self.text)
                if part.strip()
            ]
            if not re.search(r"[一-鿿]", self.text) or not 1 <= len(sentences) <= 2:
                raise ValueError("narration requires one or two Chinese sentences")
        elif self.text is not None or not self.error_code:
            raise ValueError("unavailable narration requires error without text")
        return self


class BackgroundStatus(ContractModel):
    type: Literal["background"] = "background"
    status: Literal[
        "SCHEDULED", "STARTED", "RETRYING", "COMPLETED", "SKIPPED", "FAILED"
    ]
    error_code: Identifier | None = None


ActivityPayload = Annotated[
    Lifecycle | NodeSummary | Narration | BackgroundStatus, Field(discriminator="type")
]


class ActivityEmission(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: Identifier
    case_ref: Identifier
    run_id: Identifier
    job_id: Identifier | None = None
    scope: Literal["CASE", "REFUND", "MEMORY"]
    node: Identifier
    operation_id: Identifier
    parent_operation_id: Identifier | None = None
    attempt_id: Identifier
    occurred_at: UTCDateTime
    payload: ActivityPayload


class ActivityEvent(ActivityEmission):
    seq: int = Field(ge=1)


class ActivityPage(ContractModel):
    events: list[ActivityEvent]
    next_cursor: int = Field(ge=0)
    has_more: bool


class NarrationJob(ContractModel):
    job_id: Identifier
    source: ActivityEmission

    @model_validator(mode="after")
    def source_is_summary(self):
        if not isinstance(self.source.payload, NodeSummary):
            raise ValueError("narration input must be an allowlisted node summary")  # noqa: TRY004 - Pydantic validators require ValueError
        if self.source.payload.memory_retrieval or self.source.payload.review_gate:
            raise ValueError("narration input must contain facts only")
        if self.job_id != f"narration:{self.source.event_id}":
            raise ValueError("narration job must bind to its source")
        return self


ACTIVITY_ADAPTER = TypeAdapter(ActivityEmission)
