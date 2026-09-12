from datetime import datetime, timedelta, timezone

from pydantic import TypeAdapter
from sqlalchemy import func, select

from return_agent_contracts.messages import AgentCommand
from return_agent_contracts.primitives import payload_hash
from return_agent_contracts.providers import ContractConflict
from return_agent_contracts.workflow import AgentRunResult, AgentServiceEvent, NodeExecutionObservation
from return_agent_runtime.ports import stable_id

from .db import CommandRow, EventOutboxRow, ThreadRow


class JournalBusy(RuntimeError):
    pass


class CommandJournal:
    def __init__(self, sessions, *, clock=lambda: datetime.now(timezone.utc), lease_seconds: int = 900):
        self.sessions, self.clock, self.lease_seconds = sessions, clock, lease_seconds

    def claim(self, command: AgentCommand, owner: str, checkpoint_id: str | None) -> tuple[str, str | None]:
        with self.sessions.begin() as session:
            session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(command.thread_id, 0))))
            row = session.get(CommandRow, command.command_id, with_for_update=True)
            if row:
                if row.payload_hash != payload_hash(command):
                    raise ContractConflict("Command ID reused with different content")
                if row.status == "TERMINAL":
                    return "TERMINAL", row.initial_checkpoint_id
                if row.leased_until > self.clock() and row.lease_owner != owner:
                    return "BUSY", row.initial_checkpoint_id
                row.lease_owner, row.leased_until = owner, self.clock() + timedelta(seconds=self.lease_seconds)
                return "CLAIMED", row.initial_checkpoint_id
            thread = session.get(ThreadRow, command.thread_id)
            if command.command_type == "START":
                if thread is not None:
                    raise ContractConflict("Thread already has a start command")
                thread = ThreadRow(thread_id=command.thread_id, case_ref=command.case_ref, start_command_id=command.command_id)
                session.add(thread)
                session.flush()
            elif thread is None or thread.case_ref != command.case_ref:
                raise ContractConflict("Resume is not bound to a known case thread")
            session.add(CommandRow(command_id=command.command_id, thread_id=command.thread_id, case_ref=command.case_ref, payload_hash=payload_hash(command), request=command.model_dump(mode="json"), status="CLAIMED", lease_owner=owner, leased_until=self.clock() + timedelta(seconds=self.lease_seconds), initial_checkpoint_id=checkpoint_id, created_at=self.clock()))
            return "CLAIMED", checkpoint_id

    def append(self, session, command, event_id, event_type, payload):
        session.get(CommandRow, command.command_id, with_for_update=True)
        existing = session.get(EventOutboxRow, event_id)
        if existing:
            if existing.payload["payload"] != payload:
                raise ContractConflict("Journal event identity reused with different content")
            return
        index = (session.scalar(select(func.max(EventOutboxRow.event_index)).where(EventOutboxRow.command_id == command.command_id)) or 0) + 1
        event = TypeAdapter(AgentServiceEvent).validate_python({"event_id": event_id, "command_id": command.command_id, "case_ref": command.case_ref, "thread_id": command.thread_id, "event_index": index, "occurred_at": self.clock(), "event_type": event_type, "payload": payload})
        session.add(EventOutboxRow(event_id=event_id, command_id=command.command_id, event_index=index, payload=event.model_dump(mode="json")))

    def observe(self, command: AgentCommand, observation: NodeExecutionObservation):
        with self.sessions.begin() as session:
            self.append(session, command, stable_id("agent-event", command.command_id, observation.task_ref, observation.phase), "NODE_OBSERVED", {"observation": observation.model_dump(mode="json")})

    def complete(self, command: AgentCommand, owner: str, result: AgentRunResult, distillation_input):
        result = TypeAdapter(AgentRunResult).validate_python(result)
        event_type = {"RESOLUTION": "RESOLVED", "INTERRUPTED": "INTERRUPTED", "MANUAL_ESCALATION": "ESCALATED"}[result.result_type]
        with self.sessions.begin() as session:
            row = session.get(CommandRow, command.command_id, with_for_update=True)
            if row.lease_owner != owner or row.payload_hash != payload_hash(command):
                raise JournalBusy("Command lease was replaced")
            self.append(session, command, stable_id("agent-event", command.command_id, "terminal"), event_type, {"result": result.model_dump(mode="json")})
            row.result, row.status = result.model_dump(mode="json"), "TERMINAL"
            row.distillation_input = distillation_input.model_dump(mode="json") if distillation_input else None

    def fail(self, command: AgentCommand, owner: str):
        with self.sessions.begin() as session:
            row = session.get(CommandRow, command.command_id, with_for_update=True)
            if row.lease_owner != owner:
                raise JournalBusy("Command lease was replaced")
            self.append(session, command, stable_id("agent-event", command.command_id, "terminal"), "RUN_FAILED", {"code": "INVALID_RUNTIME_COMMAND", "message": "Command does not match the durable runtime state", "retryable": False, "failed_node": None})
            row.status = "TERMINAL"
