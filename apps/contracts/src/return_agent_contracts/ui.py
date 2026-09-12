"""Backend/UI projection contracts for the return-resolution Agent demo.

These DTOs render or resume core Agent DTOs. They do not own Policy, Risk,
canonical case state, or graph routing.
"""

from __future__ import annotations
from .review_gates import HumanReviewRoutingReason
from .review_gates import ReviewGateResult

from .models import ReviewResult

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from .base import (
    ContractModel,
    CurrencyCode,
    Money,
    NonEmptyText,
    NonNegativeInt,
    OpaqueRef,
    PositiveInt,
    UnitInterval,
    UTCDateTime,
    ZeroMoney,
)
from .enums import (
    EvidenceType,
    HumanCorrectionReasonCode,
    HumanDecision,
    MemoryStatus,
    ResolutionAction,
)
from .models import (
    AgentReturnDecision,
    ClarificationRequest,
    CorrectedDecision,
    EmptyRefundScope,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryRetrievalObservation,
    MemoryScope,
    MissingClaim,
    NonEmptyRefundScope,
    RevisedReviewResult,
)
from .runtime import AgentInterruptKind as InterruptKind
from .runtime import GraphNodeName


class UIEventType(StrEnum):
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN = "token"
    MEMORY_RETRIEVAL = "memory_retrieval"
    INTERRUPT = "interrupt"
    STATE_CHANGE = "state_change"
    DONE = "done"
    ERROR = "error"


class CaseStatus(StrEnum):
    """Backend-owned status displayed by the UI, not Agent graph state."""

    OBSERVING = "OBSERVING"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    EXECUTING = "EXECUTING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class TokenPayload(ContractModel):
    text: NonEmptyText


class StateChangePayload(ContractModel):
    from_status: CaseStatus | None = None
    to_status: CaseStatus
    reason: NonEmptyText


class NodeLifecyclePayload(ContractModel):
    review_gate: ReviewGateResult | None = None
    detail: NonEmptyText | None = None


class DonePayload(ContractModel):
    terminal_ref: OpaqueRef
    status: Literal[CaseStatus.RESOLVED, CaseStatus.ESCALATED]


class ErrorPayload(ContractModel):
    code: NonEmptyText
    message: NonEmptyText
    retryable: bool


class EvidenceDisplayRef(ContractModel):
    """Reference-only evidence view; signed URLs stay in the Backend/UI layer."""

    evidence_id: OpaqueRef
    type: EvidenceType
    subject: OpaqueRef
    artifact_ref: OpaqueRef
    caption: NonEmptyText


class PolicyDisplayRef(ContractModel):
    clause_id: OpaqueRef
    policy_version: OpaqueRef
    excerpt: NonEmptyText
    title: NonEmptyText | None = None
    relevance: UnitInterval | None = None


class EvidenceRequestView(ContractModel):
    """The user-evidence interrupt rendered by the conversation UI."""

    case_ref: OpaqueRef
    request_id: OpaqueRef
    user_message: NonEmptyText
    missing_claims: list[MissingClaim] = Field(min_length=1)
    accepted_evidence_types: list[EvidenceType] = Field(min_length=1)
    policy_refs: list[OpaqueRef] = Field(min_length=1)


class ClarificationInterruptPayload(ContractModel):
    interrupt_kind: Literal[InterruptKind.CLARIFICATION]
    case_ref: OpaqueRef
    request: ClarificationRequest


class _HumanReviewPayloadBase(ContractModel):
    dossier: HumanReviewDossier | None = None
    case_ref: OpaqueRef
    handoff_id: OpaqueRef
    routing_reason: HumanReviewRoutingReason = "REVISION_BUDGET_EXCEEDED"
    review_result: ReviewResult
    rationale_summary: NonEmptyText
    evidence_refs: list[EvidenceDisplayRef] = Field(default_factory=list)
    policy_hits: list[PolicyDisplayRef] = Field(default_factory=list)
    memories_used: list[OpaqueRef] = Field(default_factory=list)


class FullRefundHumanReviewPayload(_HumanReviewPayloadBase):
    action: Literal[ResolutionAction.FULL_REFUND]
    refund_scope: NonEmptyRefundScope
    amount: Money
    currency: CurrencyCode
    return_decision: AgentReturnDecision


class DeclineHumanReviewPayload(_HumanReviewPayloadBase):
    action: Literal[ResolutionAction.DECLINE]
    refund_scope: EmptyRefundScope
    amount: ZeroMoney
    currency: CurrencyCode


HumanReviewPayload: TypeAlias = Annotated[
    FullRefundHumanReviewPayload | DeclineHumanReviewPayload,
    Field(discriminator="action"),
]


class EvidenceInterruptPayload(ContractModel):
    interrupt_kind: Literal[InterruptKind.EVIDENCE_REQUEST]
    request: EvidenceRequestView


class HumanReviewInterruptPayload(ContractModel):
    interrupt_kind: Literal[InterruptKind.HUMAN_REVIEW]
    review: HumanReviewPayload


InterruptPayload: TypeAlias = Annotated[
    ClarificationInterruptPayload
    | EvidenceInterruptPayload
    | HumanReviewInterruptPayload,
    Field(discriminator="interrupt_kind"),
]


class ToolCallPayload(ContractModel):
    call_id: OpaqueRef
    tool_name: NonEmptyText
    arguments: dict[NonEmptyText, NonEmptyText] = Field(default_factory=dict)


class ToolResultPayload(ContractModel):
    call_id: OpaqueRef
    tool_name: NonEmptyText
    ok: bool
    duration_ms: NonNegativeInt
    summary: NonEmptyText
    error: NonEmptyText | None = None


class MemoryRecordView(ContractModel):
    """Display-only memory card; only APPROVED records are retrievable."""

    memory_id: OpaqueRef
    status: MemoryStatus
    trigger: NonEmptyText
    boundary: NonEmptyText
    action: NonEmptyText
    scope: MemoryScope
    source_case_refs: list[OpaqueRef] = Field(default_factory=list)
    created_at: UTCDateTime
    hit_count: NonNegativeInt | None = None


class ApprovedMemoryRecordView(MemoryRecordView):
    """Retrievable memory view allowed inside a memory-hit event."""

    status: Literal[MemoryStatus.APPROVED]


class MemoryRetrievalPayload(MemoryRetrievalObservation):
    """The latest query result, including empty or unavailable retrieval."""


class _AgentEventBase(ContractModel):
    case_ref: OpaqueRef
    seq: PositiveInt
    ts: UTCDateTime
    node: GraphNodeName


class NodeEnterEvent(_AgentEventBase):
    type: Literal[UIEventType.NODE_ENTER]
    payload: NodeLifecyclePayload = Field(default_factory=NodeLifecyclePayload)


class NodeExitEvent(_AgentEventBase):
    type: Literal[UIEventType.NODE_EXIT]
    payload: NodeLifecyclePayload = Field(default_factory=NodeLifecyclePayload)


class ToolCallEvent(_AgentEventBase):
    type: Literal[UIEventType.TOOL_CALL]
    payload: ToolCallPayload


class ToolResultEvent(_AgentEventBase):
    type: Literal[UIEventType.TOOL_RESULT]
    payload: ToolResultPayload


class TokenEvent(_AgentEventBase):
    type: Literal[UIEventType.TOKEN]
    payload: TokenPayload


class MemoryRetrievalEvent(_AgentEventBase):
    type: Literal[UIEventType.MEMORY_RETRIEVAL]
    payload: MemoryRetrievalPayload


class InterruptEvent(_AgentEventBase):
    type: Literal[UIEventType.INTERRUPT]
    payload: InterruptPayload


class StateChangeEvent(_AgentEventBase):
    type: Literal[UIEventType.STATE_CHANGE]
    payload: StateChangePayload


class DoneEvent(_AgentEventBase):
    type: Literal[UIEventType.DONE]
    payload: DonePayload


class ErrorEvent(_AgentEventBase):
    type: Literal[UIEventType.ERROR]
    payload: ErrorPayload


AgentEvent: TypeAlias = Annotated[
    NodeEnterEvent
    | NodeExitEvent
    | ToolCallEvent
    | ToolResultEvent
    | TokenEvent
    | MemoryRetrievalEvent
    | InterruptEvent
    | StateChangeEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]


class _ReviewDecisionBase(ContractModel):
    handoff_id: OpaqueRef | None = None
    review_note: NonEmptyText
    generalizable: bool | None = None
    reviewer_id: OpaqueRef = "demo_reviewer"


class ApproveReviewDecision(_ReviewDecisionBase):
    decision: Literal[HumanDecision.APPROVE]


class EditReviewDecision(_ReviewDecisionBase):
    decision: Literal[HumanDecision.EDIT]
    corrected_decision: CorrectedDecision
    correction_reason_code: HumanCorrectionReasonCode


class RejectReviewDecision(_ReviewDecisionBase):
    decision: Literal[HumanDecision.REJECT]


ReviewDecision: TypeAlias = Annotated[
    ApproveReviewDecision | EditReviewDecision | RejectReviewDecision,
    Field(discriminator="decision"),
]


class CreateCaseRequest(ContractModel):
    """Backend API payload; Backend creates the case and starts/resumes the graph."""

    order_ref: OpaqueRef
    user_ref: OpaqueRef
    initial_message: NonEmptyText
    attached_artifact_refs: list[OpaqueRef] = Field(default_factory=list)


class CreateCaseResponse(ContractModel):
    case_ref: OpaqueRef


class CaseDetail(ContractModel):
    """Backend-owned case view for the Demo UI."""

    case_ref: OpaqueRef
    order_ref: OpaqueRef
    user_ref: OpaqueRef
    status: CaseStatus
    clarification_request: ClarificationRequest | None = None
    human_review: HumanReviewPayload | None = None
    human_review_result: HumanReviewResult | None = None
    evidence_request: EvidenceRequestView | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class SendMessageRequest(ContractModel):
    message: NonEmptyText
    attached_artifact_refs: list[OpaqueRef] = Field(default_factory=list)
