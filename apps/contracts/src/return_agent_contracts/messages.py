"""Runtime input and transport contracts, separate from canonical API state."""
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .domain import EvidenceRequest, ProposedDecisionDraft, ReasonCode, RevisionReasonCode
from .primitives import ContractModel, Ref, UTCDateTime


class UserTurn(ContractModel):
    turn_id: Ref
    role: Literal["USER", "AGENT"]
    text: Ref
    received_at: UTCDateTime
    attached_artifact_refs: list[Ref] = Field(default_factory=list)


class AgentUserTurn(UserTurn):
    role: Literal["USER"]


class IntakeResult(ContractModel):
    completeness: Literal["COMPLETE", "INCOMPLETE"]
    requested_action: Literal["REFUND", "RETURN_AND_REFUND", "EXCHANGE", "UNSPECIFIED"]
    order_ref: Ref | None = None
    reason_code: ReasonCode | None = None
    reason_summary: Ref | None = None
    claimed_line_item_ids: list[Ref] = Field(default_factory=list)
    missing_fields: list[Ref] = Field(default_factory=list)
    clarification_question: Ref | None = None

    @model_validator(mode="after")
    def completeness_matches_question(self) -> Self:
        if self.completeness == "INCOMPLETE" and (not self.missing_fields or not self.clarification_question):
            raise ValueError("Incomplete intake must name missing information and a question")
        if self.completeness == "COMPLETE" and (self.missing_fields or self.clarification_question is not None):
            raise ValueError("Complete intake cannot request clarification")
        return self


class ClarificationRequest(ContractModel):
    request_id: Ref
    clarification_round: Annotated[int, Field(ge=1)]
    missing_fields: Annotated[list[Ref], Field(min_length=1)]
    clarification_question: Ref


class RevisionConflictReport(ContractModel):
    conflicting_reason_codes: Annotated[list[RevisionReasonCode], Field(min_length=2)]
    conflicting_review_refs: Annotated[list[Ref], Field(min_length=2)]
    explanation: Ref


class ResolverDraftOutput(ContractModel):
    result_type: Literal["DRAFT"]
    draft: ProposedDecisionDraft


class ResolverEvidenceRequestOutput(ContractModel):
    result_type: Literal["REQUEST_EVIDENCE"]
    evidence_request: EvidenceRequest


class ResolverConflictOutput(ContractModel):
    result_type: Literal["CONFLICTING_REVISIONS"]
    conflict: RevisionConflictReport


ResolverOutput = Annotated[ResolverDraftOutput | ResolverEvidenceRequestOutput | ResolverConflictOutput, Field(discriminator="result_type")]


class ClarificationResume(ContractModel):
    kind: Literal["CLARIFICATION"]
    turn: AgentUserTurn


class EvidenceResume(ContractModel):
    kind: Literal["EVIDENCE_REQUEST"]
    artifact_refs: Annotated[list[Ref], Field(min_length=1)]


class HumanReviewPollResume(ContractModel):
    kind: Literal["HUMAN_REVIEW"]


ResumePayload = Annotated[ClarificationResume | EvidenceResume | HumanReviewPollResume, Field(discriminator="kind")]


class AgentStartRequest(ContractModel):
    case_ref: Ref
    thread_id: Ref
    initial_turn: AgentUserTurn
    order_ref: Ref | None = None


class AgentResumeRequest(ContractModel):
    thread_id: Ref
    payload: ResumePayload


class AgentStartPayload(ContractModel):
    order_ref: Ref
    initial_turn: AgentUserTurn


class AgentResumePayload(ContractModel):
    resume: ResumePayload


class CommandBase(ContractModel):
    schema_version: Literal["v1"] = "v1"
    command_id: Ref
    case_ref: Ref
    thread_id: Ref
    issued_at: UTCDateTime


class AgentStartCommand(CommandBase):
    command_type: Literal["START"]
    payload: AgentStartPayload


class AgentResumeCommand(CommandBase):
    command_type: Literal["RESUME"]
    payload: AgentResumePayload


AgentCommand = Annotated[AgentStartCommand | AgentResumeCommand, Field(discriminator="command_type")]

COMMAND_STREAM = "return-agent.commands.v1"
EVENT_STREAM = "return-agent.events.v1"
COMMAND_GROUP = "return-agent-workers-v1"
COMMAND_DLQ = "return-agent.commands.dlq.v1"
ACTIVITY_STREAM = "return-agent.activities.v1"
NARRATION_STREAM = "return-agent.narrations.v1"
MEMORY_JOB_STREAM = "return-agent.memory-jobs.v1"
MEMORY_EVENT_STREAM = "return-agent.memory-events.v1"
