import pytest
from pydantic import ValidationError
from return_agent_contracts.activity import ActivityFacts, IntentDisplay, NodeSummary


def test_intent_snapshot_roundtrip_and_old_summary():
    value = IntentDisplay(
        requested_action="REFUND",
        completeness="INCOMPLETE",
        claimed_line_item_ids=["LI-1"],
        missing_fields=["ITEMS", "OTHER"],
    )
    summary = NodeSummary(facts=ActivityFacts(), intent_display=value)
    assert (
        NodeSummary.model_validate_json(summary.model_dump_json()).intent_display
        == value
    )
    assert NodeSummary.model_validate({"facts": {}}).intent_display is None


@pytest.mark.parametrize(
    "extra",
    [
        {"reason_summary": "private prose"},
        {"missing_fields": ["user@example.com"]},
        {"claimed_line_item_ids": ["artifact://private"]},
        {"prompt": "secret"},
    ],
)
def test_intent_snapshot_rejects_non_allowlisted_content(extra):
    with pytest.raises(ValidationError):
        IntentDisplay(requested_action="REFUND", completeness="INCOMPLETE", **extra)
