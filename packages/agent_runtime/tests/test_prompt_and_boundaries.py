from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import TypeAdapter
from return_agent_contracts.enums import ClaimId
from return_agent_contracts.models import (
    ApprovedMemory,
    IntakeResult,
    MemoryScope,
)
from return_agent_contracts.runtime import AgentRunStatus
from return_agent_runtime.graph import ASSESSMENT_SCHEMA
from return_agent_runtime.model import (
    ModelTask,
    OpenAIStructuredOutputModel,
    OutputSchema,
)
from return_agent_runtime.prompts import (
    INTAKE_SYSTEM_PROMPT,
    MEMORY_DISTILLER_SYSTEM_PROMPT,
    MEMORY_QUERY_SYSTEM_PROMPT,
    RESOLVER_SYSTEM_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
)
from return_agent_runtime.serialization import json_value
from return_agent_runtime.state import MemoryRetrievalStatus

from .conftest import (
    approved_review,
    case_load,
    evidence_item,
    make_runtime,
    proposal_output,
    supported_assessment,
    user_turn,
)
from .fakes import QueuedModel
from .test_interrupt_resume import complete_intake


def _contains_key(value, prohibited: set[str]) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in prohibited or _contains_key(item, prohibited)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_key(item, prohibited) for item in value)
    return False


def _doc_system_prompt(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    section = content.split("## System prompt", 1)[1]
    return section.split("```text", 1)[1].split("```", 1)[0].strip()


def test_packaged_prompts_match_canonical_docs():
    repo = Path(__file__).resolve().parents[3]
    overview = (repo / "docs/spec/05-prompts/README.md").read_text()
    assert MEMORY_QUERY_SYSTEM_PROMPT in overview
    prompt_dir = repo / "docs/spec/05-prompts"
    assert INTAKE_SYSTEM_PROMPT == _doc_system_prompt(prompt_dir / "intake.md")
    assert RESOLVER_SYSTEM_PROMPT == _doc_system_prompt(prompt_dir / "resolver.md")
    assert REVIEWER_SYSTEM_PROMPT == _doc_system_prompt(prompt_dir / "reviewer.md")
    assert MEMORY_DISTILLER_SYSTEM_PROMPT == _doc_system_prompt(
        prompt_dir / "memory-distiller.md"
    )


def test_diagnostic_prompt_regression_boundaries():
    assert "still alleges QUALITY_ISSUE" in INTAKE_SYSTEM_PROMPT
    assert "claimed_line_item_ids MUST be []" in INTAKE_SYSTEM_PROMPT
    assert "not an evidence ID" in REVIEWER_SYSTEM_PROMPT
    assert "schema/prompt/integration defect" in MEMORY_DISTILLER_SYSTEM_PROMPT
    assert "These require system repairs, not operational memory" in MEMORY_DISTILLER_SYSTEM_PROMPT


def test_resolver_has_no_money_and_reviewer_is_independent(happy_runtime):
    runtime, model, _ = happy_runtime
    runtime.start(
        thread_id="THREAD-VISIBILITY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=["artifact://evidence/EV-002"]),
    )

    resolver_calls = [
        call
        for call in model.calls
        if call.task in (ModelTask.ASSESS, ModelTask.PROPOSE_OR_REVISE)
    ]
    assessment_call = next(
        call for call in resolver_calls if call.task is ModelTask.ASSESS
    )
    proposal_call = next(
        call for call in resolver_calls if call.task is ModelTask.PROPOSE_OR_REVISE
    )
    assert assessment_call.payload["evidence_assessment"] is None
    assert proposal_call.payload["evidence_assessment"]["evidence_status"] == (
        "SUFFICIENT_FOR_APPROVAL"
    )
    for call in resolver_calls:
        assert call.payload["claim_registry_version"] == "claim-registry:1.0"
        assert {
            (pair["claim_id"], pair["subject"])
            for pair in call.payload["expected_claim_subject_pairs"]
        } == {
            ("DELIVERY_CONFIRMED", "ORDER"),
            ("ORDER_WITHIN_RETURN_WINDOW", "ORDER"),
            ("ITEM_PHYSICALLY_DAMAGED", "LI-002"),
            ("DAMAGE_PRESENT_ON_ARRIVAL", "LI-002"),
        }
        assert not _contains_key(
            call.payload,
            {
                "amount",
                "currency",
                "refundable_amount",
                "refundable_amount_max",
                "already_refunded_amount",
                "handoff_id",
            },
        )

    reviewer_call = next(call for call in model.calls if call.task is ModelTask.REVIEW)
    assert "proposed_decision_handoff" in reviewer_call.payload
    assert "policy_bundle" in reviewer_call.payload
    assert "claim_registry" in reviewer_call.payload
    assert reviewer_call.payload["claim_registry_version"] == "claim-registry:1.0"
    assert {
        (pair["claim_id"], pair["subject"])
        for pair in reviewer_call.payload["expected_claim_subject_pairs"]
    } == {
        ("DELIVERY_CONFIRMED", "ORDER"),
        ("ORDER_WITHIN_RETURN_WINDOW", "ORDER"),
        ("ITEM_PHYSICALLY_DAMAGED", "LI-002"),
        ("DAMAGE_PRESENT_ON_ARRIVAL", "LI-002"),
    }
    assert "evidence_assessment" not in reviewer_call.payload
    assert "operational_memory" not in reviewer_call.payload
    assert "review_feedback" not in reviewer_call.payload
    assert "verification_feedback" not in reviewer_call.payload


def test_graph_overwrites_reviewer_owned_metadata():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    assessment = supported_assessment().model_copy(
        update={"claim_registry_version": "model-selected-version"}
    )
    model.queue(ModelTask.ASSESS, assessment)
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    review = approved_review().model_dump(mode="json")
    review["reviewer_prompt_version"] = "model-selected-version"
    review["reviewed_at"] = "2026-08-01T00:00:00Z"
    model.queue(ModelTask.REVIEW, review)
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )

    runtime.start(
        thread_id="THREAD-REVIEW-METADATA",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-REVIEW-METADATA"}}
    ).values
    review_result = state["review_history"][0]
    assert state["evidence_assessment"].claim_registry_version == "claim-registry:1.0"
    assert review_result.reviewer_prompt_version == "reviewer:2.2"
    assert review_result.reviewed_at.isoformat() == "2026-09-01T10:00:00+00:00"


def test_graph_binds_trusted_order_and_owns_decision_references():
    model = QueuedModel()
    model.queue(
        ModelTask.INTAKE,
        {
            "completeness": "INCOMPLETE",
            "order_ref": None,
            "reason_code": "ITEM_DAMAGED",
            "reason_summary": "Speaker arrived damaged.",
            "requested_action": "REFUND",
            "claimed_line_item_ids": [],
            "missing_fields": ["order_ref"],
            "clarification_question": "What is the order number?",
        },
    )
    model.queue(ModelTask.ASSESS, supported_assessment())
    proposal = proposal_output().model_dump(mode="json")
    proposal["draft"]["policy_refs"] = ["ORDER-001@12"]
    proposal["draft"]["evidence_refs"] = ["EV-002", "ORDER-001@12"]
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal)
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )

    completed = runtime.start(
        thread_id="THREAD-TRUSTED-ORDER",
        case_ref="CASE-001",
        order_ref="ORDER-001",
        initial_turn=user_turn(
            text="Speaker arrived damaged; please refund it.",
            artifacts=[evidence.artifact_ref],
        ),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-TRUSTED-ORDER"}}
    ).values
    assert state["normalized_intent"].order_ref == "ORDER-001"
    assert state["clarification_round"] == 0
    decision = state["current_handoff"].proposed_decision
    assert decision.policy_refs == ["POLICY-12:v3#4.2"]
    assert decision.evidence_refs == ["EV-002"]


def test_memory_query_uses_only_claimed_item_category():
    model = QueuedModel()
    model.queue(
        ModelTask.INTAKE,
        complete_intake(),
        complete_intake(claimed=["LI-002"]),
    )
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        case_result=case_load(multi=True),
        evidence_items={evidence.artifact_ref: evidence},
    )

    completed = runtime.start(
        thread_id="THREAD-MEMORY-CATEGORY",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    query = providers["memory"].query_calls[0]
    assert query["categories"] == ("CAT-AUDIO-SPEAKERS",)
    assert "CAT-AUDIO-HEADPHONES" not in query["categories"]
    assert query["claim_registry_major"] == 1
    assert query["top_k"] == 3


def test_mismatched_memory_is_not_injected():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    stale = ApprovedMemory(
        memory_id="MEM-STALE",
        retrieval_summary="Damaged-item evidence is incomplete; request the required evidence together.",
        status="APPROVED",
        recommended_behavior="Request all evidence together.",
        trigger_conditions=["Damage evidence is incomplete."],
        policy_version="POLICY-OLD:v1",
        claim_registry_version="claim-registry:1.0",
        scope=MemoryScope(
            market="TW",
            reason_codes=["ITEM_DAMAGED"],
            claim_ids=[ClaimId.DAMAGE_PRESENT_ON_ARRIVAL],
            categories=["CAT-AUDIO-SPEAKERS"],
        ),
        confidence=0.9,
        approved_at="2026-09-01T09:00:00Z",
    )
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        memory_results=[stale],
        evidence_items={evidence.artifact_ref: evidence},
    )
    runtime.start(
        thread_id="THREAD-MEMORY-FILTER",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assessment_call = next(
        call for call in model.calls if call.task is ModelTask.ASSESS
    )
    assert assessment_call.payload["operational_memory"] == []
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-MEMORY-FILTER"}}
    ).values
    assert state["memory_retrieval_status"] is MemoryRetrievalStatus.OK


def test_openai_adapter_requests_json_schema_and_revalidates(monkeypatch):
    calls = {}

    class Runnable:
        def invoke(self, messages):
            calls["messages"] = messages
            return complete_intake()

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def with_structured_output(self, schema, **kwargs):
            calls["schema"] = schema
            calls["structured_kwargs"] = kwargs
            return Runnable()

    monkeypatch.setattr("return_agent_runtime.model.ChatOpenAI", FakeChatOpenAI)
    adapter = OpenAIStructuredOutputModel(model_name="test-model", api_key="secret")
    result = adapter.generate(
        task=ModelTask.INTAKE,
        system_prompt="system",
        payload={"conversation_turns": []},
        output_schema=OutputSchema("IntakeResult", TypeAdapter(IntakeResult)),
    )

    assert result.order_ref == "ORDER-001"
    assert calls["init"] == {
        "model": "test-model",
        "api_key": "secret",
        "timeout": 180.0,
        "max_retries": 0,
        "temperature": 0.0,
        "use_responses_api": False,
        "streaming": False,
    }
    assert calls["structured_kwargs"] == {"method": "json_schema"}
    assert calls["schema"]["title"] == "IntakeResult"
    request_body = json.loads(calls["messages"][1].content)
    assert "required_output_schema" not in request_body


def test_openai_compatible_adapter_forwards_options_and_prompts_schema(monkeypatch):
    calls = {}

    class Runnable:
        def invoke(self, messages):
            calls["messages"] = messages
            return complete_intake()

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def with_structured_output(self, schema, **kwargs):
            calls["schema"] = schema
            return Runnable()

    monkeypatch.setattr("return_agent_runtime.model.ChatOpenAI", FakeChatOpenAI)
    adapter = OpenAIStructuredOutputModel(
        model_name="compatible-model",
        api_key="not-required",
        base_url="http://127.0.0.1:18080/v1",
        timeout_seconds=90,
        max_retries=0,
        temperature=0,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        include_schema_in_prompt=True,
        use_responses_api=False,
        streaming=True,
    )
    adapter.generate(
        task=ModelTask.INTAKE,
        system_prompt="system",
        payload={"observed_at": datetime(2026, 9, 6, tzinfo=UTC)},
        output_schema=OutputSchema("IntakeResult", TypeAdapter(IntakeResult)),
    )

    assert calls["init"] == {
        "model": "compatible-model",
        "api_key": "not-required",
        "base_url": "http://127.0.0.1:18080/v1",
        "timeout": 90,
        "max_retries": 0,
        "temperature": 0,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "use_responses_api": False,
        "streaming": True,
    }
    request_body = json.loads(calls["messages"][1].content)
    assert request_body["required_output_schema"] == calls["schema"]
    assert request_body["input"]["observed_at"] == "2026-09-06T00:00:00Z"


def test_json_value_serializes_wire_scalars():
    value = json_value(
        {
            "observed_at": datetime(2026, 9, 6, tzinfo=UTC),
            "amount": Decimal("12.50"),
            "claim_id": ClaimId.ITEM_PHYSICALLY_DAMAGED,
        }
    )

    assert value == {
        "observed_at": "2026-09-06T00:00:00Z",
        "amount": "12.50",
        "claim_id": "ITEM_PHYSICALLY_DAMAGED",
    }
    json.dumps(value)


def test_openai_adapter_wraps_root_union_schema(monkeypatch):
    calls = {}

    class Runnable:
        def invoke(self, messages):
            return {"output": supported_assessment().model_dump(mode="json")}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema, **kwargs):
            calls["schema"] = schema
            return Runnable()

    monkeypatch.setattr("return_agent_runtime.model.ChatOpenAI", FakeChatOpenAI)
    adapter = OpenAIStructuredOutputModel(model_name="test-model", api_key="secret")
    result = adapter.generate(
        task=ModelTask.ASSESS,
        system_prompt="system",
        payload={},
        output_schema=ASSESSMENT_SCHEMA,
    )

    assert result.evidence_status == "SUFFICIENT_FOR_APPROVAL"
    assert calls["schema"]["type"] == "object"
    assert list(calls["schema"]["properties"]) == ["output"]


def test_runtime_graph_only_prepares_deferred_memory_pipeline(happy_runtime):
    runtime, _, _ = happy_runtime
    graph = runtime.graph.get_graph()
    assert "retrieve_memory" in graph.nodes
    assert "enqueue_memory_distillation" in graph.nodes
    assert "distill_memory" not in graph.nodes
    assert "submit_candidate" not in graph.nodes
    sources = {edge.source for edge in graph.edges}
    assert set(graph.nodes) - {"__end__"} <= sources


def test_adapter_can_omit_temperature_without_changing_qwen_defaults(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("return_agent_runtime.model.ChatOpenAI", FakeChatOpenAI)
    OpenAIStructuredOutputModel(model_name="compass-model", temperature=None, use_responses_api=True)
    assert "temperature" not in captured
    OpenAIStructuredOutputModel(model_name="qwen-model")
    assert captured["temperature"] == 0.0
