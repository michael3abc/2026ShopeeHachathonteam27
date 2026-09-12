from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from return_agent_contracts.activity import (
    ActivityEmission,
    ActivityFacts,
    Narration,
    NarrationJob,
    NodeSummary,
)
from return_agent_contracts.activity_observer import safe_reference


def event(**updates):
    raw = {
        "event_id": "event-1",
        "case_ref": "CASE-1",
        "run_id": "RUN-1",
        "scope": "CASE",
        "node": "reviewer",
        "operation_id": "OP-1",
        "attempt_id": "ATTEMPT-1",
        "occurred_at": datetime.now(UTC),
        "payload": NodeSummary(facts=ActivityFacts(verdict="APPROVE")),
    }
    return ActivityEmission(**(raw | updates))


def test_producer_cannot_supply_seq_or_raw_state():
    with pytest.raises(ValidationError):
        event(seq=1)
    with pytest.raises(ValidationError):
        event(state={"secret": "test"})
    with pytest.raises(ValidationError):
        event(payload={"type": "node_summary", "facts": {"raw_prompt": "test"}})


@pytest.mark.parametrize(
    "value",
    [
        "https://secret",
        "artifact://secret",
        "user@example.com",
        "sk-secretkey",
        "+886912345678",
    ],
)
def test_identifiers_and_references_never_leak_restricted_values(value):
    with pytest.raises(ValidationError):
        event(operation_id=value)
    assert value not in safe_reference(value)


def test_narration_requires_summary_source_and_coherent_payload():
    with pytest.raises(ValidationError):
        Narration(source_event_id="x", status="COMPLETED", text="user@example.com")
    with pytest.raises(ValidationError):
        Narration(source_event_id="x", status="UNAVAILABLE", text="完成。")
    with pytest.raises(ValidationError):
        NarrationJob(job_id="unrelated", source=event())
    assert (
        NarrationJob(job_id="narration:event-1", source=event()).source.payload.type
        == "node_summary"
    )


def test_memory_prose_is_removed_before_serialization():
    summary = NodeSummary(
        facts=ActivityFacts(outcome="OK"),
        memory_retrieval={
            "status": "OK",
            "query_summary": "user@example.com at https://secret",
            "hits": [],
        },
    )
    assert "user@example.com" not in summary.model_dump_json()
    assert "https://" not in summary.model_dump_json()
    with pytest.raises(ValidationError):
        NarrationJob(job_id="narration:event-1", source=event(payload=summary))
