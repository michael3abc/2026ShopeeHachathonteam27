"""Backend-owned transactional outbox port for Agent commands."""

from __future__ import annotations

from typing import Protocol

from return_agent_contracts.service import AgentCommand
from sqlalchemy.orm import Session

from .db.agent_bridge import AgentCommandOutboxRecord


class AgentCommandOutbox(Protocol):
    """Stage a command in the caller's case-state transaction.

    A production implementation must persist the command through the supplied
    SQLAlchemy session and dispatch it to Redis after commit. Direct Redis
    publication does not satisfy this contract.
    """

    def enqueue(self, session: Session, command: AgentCommand) -> None: ...


class SqlAlchemyAgentCommandOutbox:
    """Persist the exact wire command in the caller's transaction."""

    def enqueue(self, session: Session, command: AgentCommand) -> None:
        session.add(
            AgentCommandOutboxRecord(
                command_id=command.command_id,
                payload=command.model_dump(mode="json"),
            )
        )
