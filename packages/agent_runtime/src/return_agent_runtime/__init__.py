"""LangGraph runtime for adaptive return resolution."""

from return_agent_contracts.runtime import (
    AgentInterruptKind,
    AgentRunResult,
    AgentRunStatus,
    ClarificationResume,
    EvidenceResume,
    HumanReviewPollResume,
    ResumePayload,
)

from .checkpoint import create_checkpoint_serializer
from .dependencies import AgentDependencies, StableIdFactory, UtcClock
from .errors import (
    AgentRuntimeError,
    InvalidGraphResultError,
    ResumeMismatchError,
    ThreadAlreadyExistsError,
    ThreadNotFoundError,
)
from .memory import MemoryDistiller
from .model import OpenAIStructuredOutputModel, StructuredOutputModel
from .runtime import ReturnAgentRuntime

__all__ = [
    "AgentDependencies",
    "AgentInterruptKind",
    "AgentRunResult",
    "AgentRunStatus",
    "AgentRuntimeError",
    "ClarificationResume",
    "EvidenceResume",
    "HumanReviewPollResume",
    "InvalidGraphResultError",
    "MemoryDistiller",
    "OpenAIStructuredOutputModel",
    "ResumeMismatchError",
    "ResumePayload",
    "ReturnAgentRuntime",
    "StableIdFactory",
    "StructuredOutputModel",
    "ThreadAlreadyExistsError",
    "ThreadNotFoundError",
    "UtcClock",
    "create_checkpoint_serializer",
]
