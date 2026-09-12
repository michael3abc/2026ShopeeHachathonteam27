from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from return_agent_contracts.activity import BackgroundStatus
from return_agent_contracts.activity_observer import (
    CURRENT_ACTIVITY,
    ActivityContext,
    facts_from,
    span,
)

MEMORY_ATTEMPT: ContextVar[str | None] = ContextVar("memory_attempt", default=None)


@dataclass(frozen=True)
class MemoryActivityIdentity:
    case_ref: str
    source_command_id: str
    job_id: str


def background(sink, job, status, error_code=None):
    if sink:
        context = ActivityContext(
            case_ref=job.case_ref,
            run_id=job.source_command_id,
            job_id=job.job_id,
            scope="MEMORY",
            node="memory_worker",
            attempt_id=MEMORY_ATTEMPT.get() or uuid4().hex,
            sink=sink,
        )
        context.emit(BackgroundStatus(status=status, error_code=error_code), job.job_id)


def execute_memory_step(sink, job, node, function, *args):
    context = ActivityContext(
        case_ref=job.case_ref,
        run_id=job.source_command_id,
        job_id=job.job_id,
        scope="MEMORY",
        node=node,
        attempt_id=MEMORY_ATTEMPT.get() or uuid4().hex,
        sink=sink or (lambda e: None),
    )
    token = CURRENT_ACTIVITY.set(context)
    try:
        with span("node", node) as operation:
            result = function(*args)
            operation["facts"] = facts_from(result)
            return result
    finally:
        CURRENT_ACTIVITY.reset(token)
