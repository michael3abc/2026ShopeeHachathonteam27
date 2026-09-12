from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .domain import EvidenceRequest, HumanReviewDossier, PolicyBundle, ProposedDecisionHandoff, ReviewGateResult, ReviewResult, VerificationIssue
from .human import ResolutionHandoff
from .memory import MemoryRetrievalObservation
from .messages import ClarificationRequest
from .primitives import ContractModel, Ref, UTCDateTime

GraphNodeName = Literal[
    "parse_request", "request_clarification", "load_case_context", "retrieve_policy",
    "prepare_memory_query", "retrieve_memory", "assess_case", "request_evidence",
    "propose_decision", "external_verification", "reviewer", "record_revision_event",
    "await_human_review", "emit_resolution_handoff", "enqueue_memory_distillation",
    "distill_memory", "submit_candidate", "external_memory_approval", "terminate_automation",
]
EscalationReason = Literal[
    "CLARIFICATION_BUDGET_EXCEEDED", "EVIDENCE_BUDGET_EXCEEDED", "VERIFICATION_BUDGET_EXCEEDED",
    "REVISION_BUDGET_EXCEEDED", "PROPOSE_BUDGET_EXCEEDED", "VERIFICATION_UNAVAILABLE",
    "POLICY_AMBIGUOUS", "POLICY_NOT_FOUND", "CONFLICTING_REVISIONS", "CONTRACT_VIOLATION",
]
RoutingReason = Literal["REVISION_BUDGET_EXCEEDED", "HIGH_VALUE_ITEM", "CURRENCY_THRESHOLD_UNCONFIGURED"]


class ClarificationInterruptPayload(ContractModel):
    kind: Literal["CLARIFICATION"]
    case_ref: Ref
    request: ClarificationRequest


class EvidenceInterruptPayload(ContractModel):
    kind: Literal["EVIDENCE_REQUEST"]
    case_ref: Ref
    request: EvidenceRequest


class HumanReviewInterruptPayload(ContractModel):
    kind: Literal["HUMAN_REVIEW"]
    case_ref: Ref
    handoff_id: Ref
    review_ref: Ref
    handoff: ProposedDecisionHandoff
    review_result: ReviewResult
    policy_bundle: PolicyBundle
    dossier: HumanReviewDossier | None = None
    memory_ids: list[Ref] = Field(default_factory=list)
    routing_reason: RoutingReason = "REVISION_BUDGET_EXCEEDED"


InterruptPayload = Annotated[ClarificationInterruptPayload | EvidenceInterruptPayload | HumanReviewInterruptPayload, Field(discriminator="kind")]


class AccumulatedEscalationContext(ContractModel):
    clarification_round: Annotated[int, Field(ge=0)]
    evidence_round: Annotated[int, Field(ge=0)]
    verification_round: Annotated[int, Field(ge=0)]
    revision_round: Annotated[int, Field(ge=0)]
    review_history_refs: list[Ref] = Field(default_factory=list)
    verification_issues: list[VerificationIssue] = Field(default_factory=list)


class ManualEscalationHandoff(ContractModel):
    case_ref: Ref
    thread_id: Ref
    created_at: UTCDateTime
    escalation_reason: EscalationReason
    last_known_handoff_ref: Ref | None = None
    accumulated_context: AccumulatedEscalationContext


class ResolutionAgentRunResult(ContractModel):
    result_type: Literal["RESOLUTION"]
    status: Literal["COMPLETED"]
    resolution_handoff: ResolutionHandoff


class InterruptedAgentRunResult(ContractModel):
    result_type: Literal["INTERRUPTED"]
    status: Literal["INTERRUPTED"]
    interrupt_payload: InterruptPayload


class ManualEscalationAgentRunResult(ContractModel):
    result_type: Literal["MANUAL_ESCALATION"]
    status: Literal["COMPLETED"]
    manual_escalation: ManualEscalationHandoff


AgentRunResult = Annotated[ResolutionAgentRunResult | InterruptedAgentRunResult | ManualEscalationAgentRunResult, Field(discriminator="result_type")]


class NodeExecutionObservation(ContractModel):
    node: GraphNodeName
    phase: Literal["ENTER", "EXIT", "ERROR"]
    task_ref: Ref
    error_message: Ref | None = None
    memory_retrieval: MemoryRetrievalObservation | None = None
    review_gate: ReviewGateResult | None = None

    @model_validator(mode="after")
    def phase_specific_fields(self) -> Self:
        if (self.phase == "ERROR") != (self.error_message is not None):
            raise ValueError("Only ERROR observations carry an error message")
        if self.review_gate is not None and (self.node != "reviewer" or self.phase != "EXIT"):
            raise ValueError("A gate belongs only to reviewer EXIT")
        if self.memory_retrieval is not None and (self.node not in ("prepare_memory_query", "retrieve_memory") or self.phase != "EXIT"):
            raise ValueError("Memory retrieval belongs only to memory-node EXIT")
        return self


class AgentResolvedPayload(ContractModel):
    result: ResolutionAgentRunResult


class AgentInterruptedPayload(ContractModel):
    result: InterruptedAgentRunResult


class AgentEscalatedPayload(ContractModel):
    result: ManualEscalationAgentRunResult


class AgentNodeObservedPayload(ContractModel):
    observation: NodeExecutionObservation


class AgentRunFailedPayload(ContractModel):
    code: Ref
    message: Ref
    retryable: bool
    failed_node: GraphNodeName | None = None


class ServiceEventBase(ContractModel):
    schema_version: Literal["v1"] = "v1"
    event_id: Ref
    command_id: Ref
    case_ref: Ref
    thread_id: Ref
    event_index: Annotated[int, Field(ge=1)]
    occurred_at: UTCDateTime


class AgentNodeObservedEvent(ServiceEventBase):
    event_type: Literal["NODE_OBSERVED"]
    payload: AgentNodeObservedPayload


class AgentResolvedEvent(ServiceEventBase):
    event_type: Literal["RESOLVED"]
    payload: AgentResolvedPayload

    @model_validator(mode="after")
    def same_case(self) -> Self:
        if self.case_ref != self.payload.result.resolution_handoff.case_ref:
            raise ValueError("Resolution event refers to another case")
        return self


class AgentInterruptedEvent(ServiceEventBase):
    event_type: Literal["INTERRUPTED"]
    payload: AgentInterruptedPayload

    @model_validator(mode="after")
    def same_case(self) -> Self:
        if self.case_ref != self.payload.result.interrupt_payload.case_ref:
            raise ValueError("Interrupt event refers to another case")
        return self


class AgentEscalatedEvent(ServiceEventBase):
    event_type: Literal["ESCALATED"]
    payload: AgentEscalatedPayload

    @model_validator(mode="after")
    def same_case_and_thread(self) -> Self:
        result = self.payload.result.manual_escalation
        if self.case_ref != result.case_ref or self.thread_id != result.thread_id:
            raise ValueError("Escalation event identity differs from its result")
        return self


class AgentRunFailedEvent(ServiceEventBase):
    event_type: Literal["RUN_FAILED"]
    payload: AgentRunFailedPayload


AgentServiceEvent = Annotated[AgentNodeObservedEvent | AgentResolvedEvent | AgentInterruptedEvent | AgentEscalatedEvent | AgentRunFailedEvent, Field(discriminator="event_type")]
