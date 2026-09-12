"""Versioned Redis command and event contracts for the Agent service."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .base import ContractModel, NonEmptyText, OpaqueRef, PositiveInt, UTCDateTime
from .models import (
    MemoryCandidateOutput,
    MemoryDistillationInput,
    MemorySkipOutput,
)
from .runtime import (
    AgentInputTurn,
    GraphNodeName,
    InterruptedAgentRunResult,
    ManualEscalationAgentRunResult,
    NodeExecutionObservation,
    ResolutionAgentRunResult,
    ResumePayload,
)

AGENT_SERVICE_SCHEMA_VERSION = "v1"
AGENT_COMMAND_STREAM = "return-agent.commands.v1"
AGENT_EVENT_STREAM = "return-agent.events.v1"
AGENT_COMMAND_DLQ_STREAM = "return-agent.commands.dlq.v1"
AGENT_WORKER_CONSUMER_GROUP = "return-agent-workers-v1"
MEMORY_JOB_STREAM = "return-agent.memory-jobs.v1"
MEMORY_EVENT_STREAM = "return-agent.memory-events.v1"
MEMORY_JOB_DLQ_STREAM = "return-agent.memory-jobs.dlq.v1"
MEMORY_ENQUEUE_CONSUMER_GROUP = "return-agent-memory-enqueuers-v1"
MEMORY_WORKER_CONSUMER_GROUP = "return-agent-memory-workers-v1"
REDIS_BODY_FIELD = "body"


class AgentCommandType(StrEnum):
    START = "START"
    RESUME = "RESUME"


class AgentEventType(StrEnum):
    NODE_OBSERVED = "NODE_OBSERVED"
    INTERRUPTED = "INTERRUPTED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    RUN_FAILED = "RUN_FAILED"


class MemoryEventType(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentStartPayload(ContractModel):
    order_ref: OpaqueRef
    initial_turn: AgentInputTurn


class AgentResumePayload(ContractModel):
    resume: ResumePayload


class AgentStartCommand(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    command_type: Literal[AgentCommandType.START]
    command_id: OpaqueRef
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    issued_at: UTCDateTime
    payload: AgentStartPayload


class AgentResumeCommand(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    command_type: Literal[AgentCommandType.RESUME]
    command_id: OpaqueRef
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    issued_at: UTCDateTime
    payload: AgentResumePayload


AgentCommand: TypeAlias = Annotated[
    AgentStartCommand | AgentResumeCommand,
    Field(discriminator="command_type"),
]


class AgentNodeObservedPayload(ContractModel):
    observation: NodeExecutionObservation


class AgentInterruptedPayload(ContractModel):
    result: InterruptedAgentRunResult


class AgentResolvedPayload(ContractModel):
    result: ResolutionAgentRunResult


class AgentEscalatedPayload(ContractModel):
    result: ManualEscalationAgentRunResult


class AgentRunFailedPayload(ContractModel):
    code: NonEmptyText
    message: NonEmptyText
    retryable: bool
    failed_node: GraphNodeName | None = None


class _AgentServiceEventBase(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    event_id: OpaqueRef
    command_id: OpaqueRef
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    event_index: PositiveInt
    occurred_at: UTCDateTime


class AgentNodeObservedEvent(_AgentServiceEventBase):
    event_type: Literal[AgentEventType.NODE_OBSERVED]
    payload: AgentNodeObservedPayload


class AgentInterruptedEvent(_AgentServiceEventBase):
    event_type: Literal[AgentEventType.INTERRUPTED]
    payload: AgentInterruptedPayload

    @model_validator(mode="after")
    def _case_ref_matches_result(self) -> AgentInterruptedEvent:
        if self.payload.result.interrupt_payload.case_ref != self.case_ref:
            raise ValueError("interrupt case_ref must match event case_ref")
        return self


class AgentResolvedEvent(_AgentServiceEventBase):
    event_type: Literal[AgentEventType.RESOLVED]
    payload: AgentResolvedPayload

    @model_validator(mode="after")
    def _case_ref_matches_result(self) -> AgentResolvedEvent:
        if self.payload.result.resolution_handoff.case_ref != self.case_ref:
            raise ValueError("resolution case_ref must match event case_ref")
        return self


class AgentEscalatedEvent(_AgentServiceEventBase):
    event_type: Literal[AgentEventType.ESCALATED]
    payload: AgentEscalatedPayload

    @model_validator(mode="after")
    def _references_match_result(self) -> AgentEscalatedEvent:
        handoff = self.payload.result.manual_escalation
        if handoff.case_ref != self.case_ref or handoff.thread_id != self.thread_id:
            raise ValueError("escalation references must match event references")
        return self


class AgentRunFailedEvent(_AgentServiceEventBase):
    event_type: Literal[AgentEventType.RUN_FAILED]
    payload: AgentRunFailedPayload


AgentServiceEvent: TypeAlias = Annotated[
    AgentNodeObservedEvent
    | AgentInterruptedEvent
    | AgentResolvedEvent
    | AgentEscalatedEvent
    | AgentRunFailedEvent,
    Field(discriminator="event_type"),
]


class AgentCommandDeadLetter(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    source_stream: Literal["return-agent.commands.v1"] = AGENT_COMMAND_STREAM
    source_message_id: OpaqueRef
    raw_body: str
    error_code: NonEmptyText
    error_message: NonEmptyText
    failed_at: UTCDateTime


class MemoryDistillationJobPayload(ContractModel):
    input: MemoryDistillationInput


class MemoryDistillationJob(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    job_id: OpaqueRef
    source_command_id: OpaqueRef
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    issued_at: UTCDateTime
    payload: MemoryDistillationJobPayload

    @model_validator(mode="after")
    def _references_match_input(self) -> MemoryDistillationJob:
        if self.payload.input.case_context.case_ref != self.case_ref:
            raise ValueError("memory job case_ref must match its input")
        return self


class MemoryCandidateCompletedPayload(ContractModel):
    result: MemoryCandidateOutput
    submission_ref: OpaqueRef
    distiller_prompt_version: OpaqueRef


class MemorySkipCompletedPayload(ContractModel):
    result: MemorySkipOutput
    submission_ref: None = None
    distiller_prompt_version: OpaqueRef


MemoryDistillationCompletedPayload: TypeAlias = (
    MemoryCandidateCompletedPayload | MemorySkipCompletedPayload
)


class MemoryDistillationFailedPayload(ContractModel):
    code: NonEmptyText
    message: NonEmptyText
    retryable: bool
    distiller_prompt_version: OpaqueRef


class _MemoryServiceEventBase(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    event_id: OpaqueRef
    job_id: OpaqueRef
    source_command_id: OpaqueRef
    case_ref: OpaqueRef
    thread_id: OpaqueRef
    occurred_at: UTCDateTime


class MemoryDistillationCompletedEvent(_MemoryServiceEventBase):
    event_type: Literal[MemoryEventType.COMPLETED]
    payload: MemoryDistillationCompletedPayload


class MemoryDistillationFailedEvent(_MemoryServiceEventBase):
    event_type: Literal[MemoryEventType.FAILED]
    payload: MemoryDistillationFailedPayload


MemoryServiceEvent: TypeAlias = Annotated[
    MemoryDistillationCompletedEvent | MemoryDistillationFailedEvent,
    Field(discriminator="event_type"),
]


class MemoryJobDeadLetter(ContractModel):
    schema_version: Literal["v1"] = AGENT_SERVICE_SCHEMA_VERSION
    source_stream: Literal["return-agent.memory-jobs.v1"] = MEMORY_JOB_STREAM
    source_message_id: OpaqueRef
    raw_body: str
    error_code: NonEmptyText
    error_message: NonEmptyText
    failed_at: UTCDateTime
