import json
from copy import deepcopy

import jsonschema
import pytest
from pydantic import TypeAdapter

from return_agent_contracts.domain import ProposedDecisionHandoff
from return_agent_contracts.export import schemas
from return_agent_contracts.memory import MemoryCandidate, MemoryQuerySummary, MemoryScope, validate_candidate
from return_agent_contracts.messages import AgentCommand, IntakeResult
from return_agent_contracts.registry import REGISTRY_VERSION


def test_all_exported_schemas_are_valid_draft_2020():
    for schema in schemas().values():
        jsonschema.Draft202012Validator.check_schema(schema)


def test_handoff_shape_has_matching_python_and_json_validation(scenario):
    payload = scenario["handoff"].model_dump(mode="json")
    schema = ProposedDecisionHandoff.model_json_schema(mode="serialization")
    jsonschema.validate(payload, schema)
    assert ProposedDecisionHandoff.model_validate(payload) == scenario["handoff"]
    for mutation in [{"extra": True}, {"case_ref": ""}, {"revision_round": -1}, {"handoff_version": "2.0"}]:
        data = {**payload, **mutation}
        with pytest.raises(ValueError): ProposedDecisionHandoff.model_validate(data)
        with pytest.raises(jsonschema.ValidationError): jsonschema.validate(data, schema)
    bad = deepcopy(payload)
    bad["proposed_decision"]["amount"] = 1200.0
    with pytest.raises(ValueError): ProposedDecisionHandoff.model_validate(bad)
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(bad, schema)


@pytest.mark.parametrize("text", ["https://example.invalid/x", "person@example.invalid", "Bearer fake-secret", "CASE-original", "電話 0912-345-678", "   "])
def test_m01_r11_memory_summary_rejects_restricted_content(text):
    with pytest.raises(ValueError): MemoryQuerySummary(query_summary=text)


def test_memory_candidate_scope_and_correction_provenance():
    scope = MemoryScope(market="TW", categories=["audio"], reason_codes=["ITEM_DAMAGED"], claim_ids=["ITEM_PHYSICALLY_DAMAGED"])
    candidate = MemoryCandidate(memory_id="memory-test", status="CANDIDATE", claim_registry_version=REGISTRY_VERSION, policy_version="policy:1", confidence=0.3, retrieval_summary="破損音訊用品的退回要求評估", recommended_behavior="依政策評估退回必要性", trigger_conditions=["損壞證據充分"], scope=scope, rationale="人工修正了退回條件", source_case_refs=["case-test"], source_revision_event_refs=["correction-test"])
    args = (scope, ["case-test"], ["correction-test"], "policy:1", REGISTRY_VERSION)
    validate_candidate(candidate, *args)
    candidate.scope = candidate.scope.model_copy(update={"categories": ["other"]})
    with pytest.raises(ValueError): validate_candidate(candidate, *args)
    candidate.scope = scope
    candidate.source_case_refs = ["case-unknown"]
    with pytest.raises(ValueError): validate_candidate(candidate, *args)
    candidate.source_case_refs = ["case-test", "case-test"]
    with pytest.raises(ValueError): validate_candidate(candidate, *args)


def test_transport_rejects_unknown_version_and_human_payload_injection(scenario):
    base = {"schema_version": "v1", "command_type": "RESUME", "case_ref": "case-test", "thread_id": "thread-test", "command_id": "command-test", "issued_at": scenario["now"].isoformat(), "payload": {"resume": {"kind": "HUMAN_REVIEW"}}}
    adapter = TypeAdapter(AgentCommand)
    adapter.validate_python(base)
    bad = deepcopy(base); bad["payload"]["resume"]["result"] = {"decision": "APPROVE"}
    with pytest.raises(ValueError): adapter.validate_python(bad)
    with pytest.raises(ValueError): adapter.validate_python({**base, "schema_version": "v2"})


def test_intake_completeness_requires_coherent_question():
    with pytest.raises(ValueError): IntakeResult(completeness="INCOMPLETE", requested_action="REFUND")
    with pytest.raises(ValueError): IntakeResult(completeness="COMPLETE", requested_action="REFUND", missing_fields=["item"])
    IntakeResult(completeness="INCOMPLETE", requested_action="REFUND", missing_fields=["item"], clarification_question="請指定品項")
