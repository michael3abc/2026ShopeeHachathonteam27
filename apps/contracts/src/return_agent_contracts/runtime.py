"""Cross-component Python invocation contracts for the Agent runtime."""

from __future__ import annotations
from .review_gates import HumanReviewRoutingReason
from .review_gates import ReviewGateResult

from .models import ReviewResult
from .policy_v2 import PolicyConfirmation, PolicyConfirmationRequest

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BeforeValidator, ConfigDict, Field, model_validator

from .base import ContractModel, NonEmptyText, OpaqueRef
from .enums import UserRole
from .models import (
    ClarificationRequest,
    EvidenceRequest,
    HumanReviewDossier,
    ManualEscalationHandoff,
    MemoryRetrievalObservation,
    PolicyBundle,
    ProposedDecisionHandoff,
    ResolutionHandoff,
    RevisedReviewResult,
    UserTurn,
)


class AgentInterruptKind(StrEnum):
    POLICY_CONFIRMATION = "POLICY_CONFIRMATION"
    CLARIFICATION = "CLARIFICATION"
    EVIDENCE_REQUEST = "EVIDENCE_REQUEST"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AgentRunStatus(StrEnum):
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"


class AgentRunResultType(StrEnum):
    INTERRUPTED = "INTERRUPTED"
    RESOLUTION = "RESOLUTION"
    MANUAL_ESCALATION = "MANUAL_ESCALATION"


class GraphNodeName(StrEnum):
    EVALUATE_POLICY = "evaluate_policy"
    CONFIRM_POLICY_PATH = "confirm_policy_path"
    PARSE_REQUEST = "parse_request"
    REQUEST_CLARIFICATION = "request_clarification"
    LOAD_CASE_CONTEXT = "load_case_context"
    RETRIEVE_POLICY = "retrieve_policy"
    PREPARE_MEMORY_QUERY = "prepare_memory_query"
    RETRIEVE_MEMORY = "retrieve_memory"
    ASSESS_CASE = "assess_case"
    REQUEST_EVIDENCE = "request_evidence"
    PROPOSE_DECISION = "propose_decision"
    EXTERNAL_VERIFICATION = "external_verification"
    REVIEWER = "reviewer"
    RECORD_REVISION_EVENT = "record_revision_event"
    AWAIT_HUMAN_REVIEW = "await_human_review"
    EMIT_RESOLUTION_HANDOFF = "emit_resolution_handoff"
    ENQUEUE_MEMORY_DISTILLATION = "enqueue_memory_distillation"
    DISTILL_MEMORY = "distill_memory"
    SUBMIT_CANDIDATE = "submit_candidate"
    EXTERNAL_MEMORY_APPROVAL = "external_memory_approval"
    TERMINATE_AUTOMATION = "terminate_automation"


class NodeExecutionPhase(StrEnum):
    ENTER = "ENTER"
    EXIT = "EXIT"
    ERROR = "ERROR"


class NodeExecutionObservation(ContractModel):
    """Framework-neutral lifecycle observation emitted around one graph task."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "required": ["memory_retrieval"],
                        "properties": {"memory_retrieval": {"type": "object"}},
                    },
                    "then": {
                        "properties": {
                            "phase": {"const": "EXIT"},
                            "node": {
                                "enum": ["prepare_memory_query", "retrieve_memory"]
                            },
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"phase": {"const": "ERROR"}},
                        "required": ["phase"],
                    },
                    "then": {
                        "properties": {
                            "error_message": {"minLength": 1, "type": "string"}
                        },
                        "required": ["error_message"],
                    },
                    "else": {"properties": {"error_message": {"type": "null"}}},
                },
            ]
        }
    )

    phase: NodeExecutionPhase
    node: GraphNodeName
    task_ref: OpaqueRef
    error_message: NonEmptyText | None = None
    memory_retrieval: MemoryRetrievalObservation | None = None
    review_gate: ReviewGateResult | None = None

    @model_validator(mode="after")
    def _error_message_matches_phase(self) -> NodeExecutionObservation:
        if self.review_gate is not None and (self.phase is not NodeExecutionPhase.EXIT or self.node is not GraphNodeName.REVIEWER):
            raise ValueError("review gate is only valid on reviewer EXIT")
        if self.phase is NodeExecutionPhase.ERROR and self.error_message is None:
            raise ValueError("ERROR observation requires error_message")
        if (
            self.phase is not NodeExecutionPhase.ERROR
            and self.error_message is not None
        ):
            raise ValueError("only ERROR observation may include error_message")
        if self.memory_retrieval is not None and (
            self.phase is not NodeExecutionPhase.EXIT
            or self.node
            not in {GraphNodeName.PREPARE_MEMORY_QUERY, GraphNodeName.RETRIEVE_MEMORY}
        ):
            raise ValueError("memory retrieval data is only valid on memory-node EXIT")
        return self


class AgentUserTurn(UserTurn):
    role: Literal[UserRole.USER]


def _coerce_user_turn(value: object) -> object:
    if isinstance(value, UserTurn):
        return value.model_dump()
    return value


AgentInputTurn: TypeAlias = Annotated[
    AgentUserTurn,
    BeforeValidator(_coerce_user_turn),
]


class AgentStartRequest(ContractModel):
    thread_id: OpaqueRef
    case_ref: OpaqueRef
    order_ref: OpaqueRef | None = None
    initial_turn: AgentInputTurn


class ClarificationResume(ContractModel):
    kind: Literal[AgentInterruptKind.CLARIFICATION]
    turn: AgentInputTurn


class EvidenceResume(ContractModel):
    kind: Literal[AgentInterruptKind.EVIDENCE_REQUEST]
    artifact_refs: list[OpaqueRef] = Field(min_length=1)


class HumanReviewPollResume(ContractModel):
    kind: Literal[AgentInterruptKind.HUMAN_REVIEW]


class PolicyConfirmationResume(ContractModel):
    kind: Literal[AgentInterruptKind.POLICY_CONFIRMATION]
    confirmation: PolicyConfirmation


ResumePayload: TypeAlias = Annotated[
    ClarificationResume | EvidenceResume | HumanReviewPollResume | PolicyConfirmationResume,
    Field(discriminator="kind"),
]


class AgentResumeRequest(ContractModel):
    thread_id: OpaqueRef
    payload: ResumePayload


class ClarificationInterruptPayload(ContractModel):
    kind: Literal[AgentInterruptKind.CLARIFICATION]
    case_ref: OpaqueRef
    request: ClarificationRequest


class EvidenceInterruptPayload(ContractModel):
    kind: Literal[AgentInterruptKind.EVIDENCE_REQUEST]
    case_ref: OpaqueRef
    request: EvidenceRequest


class HumanReviewInterruptPayload(ContractModel):
    kind: Literal[AgentInterruptKind.HUMAN_REVIEW]
    case_ref: OpaqueRef
    handoff_id: OpaqueRef
    review_ref: OpaqueRef
    handoff: ProposedDecisionHandoff
    dossier: HumanReviewDossier | None = None
    routing_reason: HumanReviewRoutingReason = "REVISION_BUDGET_EXCEEDED"
    review_result: ReviewResult
    policy_bundle: PolicyBundle
    memory_ids: list[OpaqueRef] = Field(default_factory=list)


class PolicyConfirmationInterruptPayload(ContractModel):
    kind: Literal[AgentInterruptKind.POLICY_CONFIRMATION]
    case_ref: OpaqueRef
    request: PolicyConfirmationRequest


AgentInterruptPayload: TypeAlias = Annotated[
    ClarificationInterruptPayload
    | EvidenceInterruptPayload
    | HumanReviewInterruptPayload
    | PolicyConfirmationInterruptPayload,
    # Policy consent comes from the authenticated API command outbox.
    Field(discriminator="kind"),
]


class InterruptedAgentRunResult(ContractModel):
    result_type: Literal[AgentRunResultType.INTERRUPTED]
    status: Literal[AgentRunStatus.INTERRUPTED]
    interrupt_payload: AgentInterruptPayload

    @property
    def interrupt_kind(self) -> AgentInterruptKind:
        return self.interrupt_payload.kind

    @property
    def resolution_handoff(self) -> None:
        return None

    @property
    def manual_escalation(self) -> None:
        return None


class ResolutionAgentRunResult(ContractModel):
    result_type: Literal[AgentRunResultType.RESOLUTION]
    status: Literal[AgentRunStatus.COMPLETED]
    resolution_handoff: ResolutionHandoff

    @property
    def manual_escalation(self) -> None:
        return None


class ManualEscalationAgentRunResult(ContractModel):
    result_type: Literal[AgentRunResultType.MANUAL_ESCALATION]
    status: Literal[AgentRunStatus.COMPLETED]
    manual_escalation: ManualEscalationHandoff

    @property
    def resolution_handoff(self) -> None:
        return None


AgentRunResult: TypeAlias = Annotated[
    InterruptedAgentRunResult
    | ResolutionAgentRunResult
    | ManualEscalationAgentRunResult,
    Field(discriminator="result_type"),
]
