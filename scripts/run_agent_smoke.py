"""Publish one demo Agent command and print its Redis event stream."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import TypeAdapter
from redis.asyncio import Redis
from return_agent_contracts.models import UserTurn
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    REDIS_BODY_FIELD,
    AgentServiceEvent,
    AgentStartCommand,
)

EVENT_ADAPTER = TypeAdapter(AgentServiceEvent)
TERMINAL_EVENTS = {"INTERRUPTED", "RESOLVED", "ESCALATED", "RUN_FAILED"}


async def run(redis_url: str, timeout_seconds: float) -> None:
    client = Redis.from_url(redis_url, decode_responses=True)
    try:
        latest = await client.xrevrange(AGENT_EVENT_STREAM, count=1)
        cursor = latest[0][0] if latest else "0-0"
        suffix = uuid4().hex.upper()
        command = AgentStartCommand(
            command_type="START",
            command_id=f"COMMAND-DEMO-{suffix}",
            case_ref="CASE-DEMO",
            thread_id=f"THREAD-DEMO-{suffix}",
            issued_at=datetime.now(UTC),
            payload={
                "order_ref": "ORDER-DEMO",
                "initial_turn": UserTurn(
                    turn_id=f"TURN-DEMO-{suffix}",
                    role="USER",
                    text="ORDER-DEMO 的喇叭到貨時損壞，我要退款",
                    attached_artifact_refs=["artifact://demo/damage"],
                    received_at=datetime.now(UTC),
                )
            },
        )
        await client.xadd(
            AGENT_COMMAND_STREAM,
            {REDIS_BODY_FIELD: command.model_dump_json()},
        )
        print(f"published {command.command_id}")

        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            remaining_ms = max(
                1,
                int((deadline - asyncio.get_running_loop().time()) * 1_000),
            )
            batches = await client.xread(
                {AGENT_EVENT_STREAM: cursor},
                count=20,
                block=min(remaining_ms, 1_000),
            )
            if not batches:
                continue
            for _stream, entries in batches:
                for message_id, fields in entries:
                    cursor = message_id
                    event = EVENT_ADAPTER.validate_json(fields[REDIS_BODY_FIELD])
                    if event.command_id != command.command_id:
                        continue
                    if event.event_type == "NODE_OBSERVED":
                        observation = event.payload.observation
                        print(
                            f"{event.event_index:03d} "
                            f"{observation.node.value} {observation.phase.value}"
                        )
                    else:
                        print(f"{event.event_index:03d} {event.event_type.value}")
                    if event.event_type.value in TERMINAL_EVENTS:
                        return
        raise TimeoutError(f"no terminal event within {timeout_seconds} seconds")
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis URL used by the Agent service",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    asyncio.run(run(args.redis_url, args.timeout))


if __name__ == "__main__":
    main()
