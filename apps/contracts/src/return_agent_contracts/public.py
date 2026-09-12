"""Browser projections. The API remains the source of canonical case state."""
from typing import Annotated, Literal

from pydantic import Field

from .domain import AgentReturnDecision, EmptyRefundScope, EvidenceRequest, EvidenceType, HumanReviewDossier, NonEmptyRefundScope, ReviewGateResult, ReviewResult
from .human import HumanReviewResult, ResolutionHandoff
from .providers import RefundExecutionRecord
from .memory import MemoryRetrievalObservation
from .messages import ClarificationRequest
from .primitives import Amount, ContractModel, Currency, Ref, UTCDateTime
from .workflow import GraphNodeName, RoutingReason

CaseStatus = Literal["OBSERVING", "AWAITING_CLARIFICATION", "AWAITING_EVIDENCE", "AWAITING_HUMAN_REVIEW", "EXECUTING", "RESOLVED", "ESCALATED"]
CASE_TRANSITIONS: dict[str, frozenset[str]] = {
    "OBSERVING": frozenset({"AWAITING_CLARIFICATION", "AWAITING_EVIDENCE", "AWAITING_HUMAN_REVIEW", "EXECUTING", "ESCALATED"}),
    "AWAITING_CLARIFICATION": frozenset({"OBSERVING", "ESCALATED"}),
    "AWAITING_EVIDENCE": frozenset({"OBSERVING", "ESCALATED"}),
    "AWAITING_HUMAN_REVIEW": frozenset({"OBSERVING", "EXECUTING", "ESCALATED"}),
    "EXECUTING": frozenset({"RESOLVED", "ESCALATED"}),
    "RESOLVED": frozenset(), "ESCALATED": frozenset(),
}


class CreateCaseRequest(ContractModel):
    order_ref: Ref
    user_ref: Ref
    initial_message: Ref
    attached_artifact_refs: list[Ref] = Field(default_factory=list)


class CreateCaseResponse(ContractModel):
    case_ref: Ref


class SendMessageRequest(ContractModel):
    message: Ref
    attached_artifact_refs: list[Ref] = Field(default_factory=list)


class EvidenceRequestView(EvidenceRequest):
    case_ref: Ref


class EvidenceDisplayRef(ContractModel):
    evidence_id: Ref
    artifact_ref: Ref
    caption: Ref
    subject: Ref
    type: EvidenceType


class PolicyDisplayRef(ContractModel):
    clause_id: Ref
    excerpt: Ref
    policy_version: Ref
    relevance: Annotated[float, Field(ge=0, le=1)] | None = None
    title: Ref | None = None


class HumanReviewViewBase(ContractModel):
    case_ref: Ref
    handoff_id: Ref
    amount: Amount
    currency: Currency
    dossier: HumanReviewDossier | None = None
    evidence_refs: list[EvidenceDisplayRef] = Field(default_factory=list)
    policy_hits: list[PolicyDisplayRef] = Field(default_factory=list)
    memories_used: list[Ref] = Field(default_factory=list)
    rationale_summary: Ref
    review_result: ReviewResult
    routing_reason: RoutingReason = "REVISION_BUDGET_EXCEEDED"


class FullRefundHumanReviewPayload(HumanReviewViewBase):
    action: Literal["FULL_REFUND"]
    refund_scope: NonEmptyRefundScope
    return_decision: AgentReturnDecision


class DeclineHumanReviewPayload(HumanReviewViewBase):
    action: Literal["DECLINE"]
    refund_scope: EmptyRefundScope


HumanReviewPayload = Annotated[FullRefundHumanReviewPayload | DeclineHumanReviewPayload, Field(discriminator="action")]


class CaseDetail(ContractModel):
    case_ref: Ref
    order_ref: Ref
    user_ref: Ref
    status: CaseStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime
    clarification_request: ClarificationRequest | None = None
    evidence_request: EvidenceRequestView | None = None
    human_review: HumanReviewPayload | None = None
    human_review_result: HumanReviewResult | None = None
    final_resolution: ResolutionHandoff | None = None
    refund_execution: RefundExecutionRecord | None = None


class UiClarificationInterruptPayload(ContractModel):
    interrupt_kind: Literal["CLARIFICATION"]
    case_ref: Ref
    request: ClarificationRequest


class UiEvidenceInterruptPayload(ContractModel):
    interrupt_kind: Literal["EVIDENCE_REQUEST"]
    request: EvidenceRequestView


class UiHumanReviewInterruptPayload(ContractModel):
    interrupt_kind: Literal["HUMAN_REVIEW"]
    review: HumanReviewPayload


UiInterruptPayload = Annotated[UiClarificationInterruptPayload | UiEvidenceInterruptPayload | UiHumanReviewInterruptPayload, Field(discriminator="interrupt_kind")]


class StateChangePayload(ContractModel):
    from_status: CaseStatus | None = None
    to_status: CaseStatus
    reason: Ref


class NodeLifecyclePayload(ContractModel):
    detail: Ref | None = None
    review_gate: ReviewGateResult | None = None


class TokenPayload(ContractModel):
    text: Ref


class ToolCallPayload(ContractModel):
    call_id: Ref
    tool_name: Ref
    arguments: dict[Ref, Ref] = Field(default_factory=dict)


class ToolResultPayload(ContractModel):
    call_id: Ref
    tool_name: Ref
    duration_ms: Annotated[int, Field(ge=0)]
    ok: bool
    summary: Ref
    error: Ref | None = None


class DonePayload(ContractModel):
    status: Literal["RESOLVED", "ESCALATED"]
    terminal_ref: Ref


class ErrorPayload(ContractModel):
    code: Ref
    message: Ref
    retryable: bool


class PublicEventBase(ContractModel):
    case_ref: Ref
    node: GraphNodeName
    seq: Annotated[int, Field(ge=1)]
    ts: UTCDateTime


class StateChangeEvent(PublicEventBase):
    type: Literal["state_change"]
    payload: StateChangePayload


class NodeEnterEvent(PublicEventBase):
    type: Literal["node_enter"]
    payload: NodeLifecyclePayload


class NodeExitEvent(PublicEventBase):
    type: Literal["node_exit"]
    payload: NodeLifecyclePayload


class TokenEvent(PublicEventBase):
    type: Literal["token"]
    payload: TokenPayload


class ToolCallEvent(PublicEventBase):
    type: Literal["tool_call"]
    payload: ToolCallPayload


class ToolResultEvent(PublicEventBase):
    type: Literal["tool_result"]
    payload: ToolResultPayload


class InterruptEvent(PublicEventBase):
    type: Literal["interrupt"]
    payload: UiInterruptPayload


class MemoryRetrievalEvent(PublicEventBase):
    type: Literal["memory_retrieval"]
    payload: MemoryRetrievalObservation


class DoneEvent(PublicEventBase):
    type: Literal["done"]
    payload: DonePayload


class ErrorEvent(PublicEventBase):
    type: Literal["error"]
    payload: ErrorPayload


AgentEvent = Annotated[StateChangeEvent | NodeEnterEvent | NodeExitEvent | TokenEvent | ToolCallEvent | ToolResultEvent | InterruptEvent | MemoryRetrievalEvent | DoneEvent | ErrorEvent, Field(discriminator="type")]
