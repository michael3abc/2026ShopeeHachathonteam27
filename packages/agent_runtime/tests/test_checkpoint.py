"""Checkpoint serializer safety tests."""

from return_agent_contracts.runtime import AgentUserTurn
from return_agent_runtime import create_checkpoint_serializer
from return_agent_runtime.state import MemoryRetrievalStatus


def test_checkpoint_serializer_round_trips_agent_owned_types() -> None:
    serializer = create_checkpoint_serializer()
    value = {
        "turn": AgentUserTurn(
            turn_id="TURN-001",
            role="USER",
            text="商品到貨時損壞",
            attached_artifact_refs=[],
            received_at="2026-09-08T12:00:00Z",
        ),
        "memory_retrieval_status": MemoryRetrievalStatus.OK,
    }

    restored = serializer.loads_typed(serializer.dumps_typed(value))

    assert restored == value
    assert isinstance(restored["turn"], AgentUserTurn)
    assert restored["memory_retrieval_status"] is MemoryRetrievalStatus.OK
