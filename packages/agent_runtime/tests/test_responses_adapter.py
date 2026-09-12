import json

import httpx
import pytest
import respx
from return_agent_runtime.graph import (
    ASSESSMENT_SCHEMA,
    INTAKE_SCHEMA,
    MEMORY_QUERY_SCHEMA,
    RESOLVER_SCHEMA,
    REVIEW_SCHEMA,
)
from return_agent_runtime.memory import MEMORY_OUTPUT_SCHEMA
from return_agent_runtime.model import ModelTask, OpenAIStructuredOutputModel

from .conftest import approved_review, proposal_output, supported_assessment
from .test_interrupt_resume import complete_intake


def stream_body(output, *, status="completed", terminal=True):
    response = {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": "gpt-5.6-luna",
        "status": status,
        "output": [],
    }
    item = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [
            {"type": "output_text", "text": json.dumps(output), "annotations": []}
        ],
    }
    events = [
        {"type": "response.created", "response": {**response, "status": "in_progress"}},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "content": [], "status": "in_progress"},
        },
        {
            "type": "response.output_text.delta",
            "item_id": "msg_test",
            "output_index": 0,
            "content_index": 0,
            "delta": json.dumps(output),
        },
    ]
    if terminal:
        events.append(
            {"type": f"response.{status}", "response": {**response, "output": [item]}}
        )
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


def model():
    return OpenAIStructuredOutputModel(
        model_name="compass-5.6-luna",
        api_key="local-router",
        base_url="http://compass.test/v1",
        temperature=None,
        use_responses_api=True,
        streaming=True,
    )


@pytest.mark.parametrize("memory", [False, True])
@respx.mock
def test_responses_wire_and_streamed_schema(memory):
    output = (
        {
            "output": {
                "result_type": "SKIP",
                "reason_code": "NO_CONFIRMED_GENERALIZABLE_CORRECTION",
            }
        }
        if memory
        else complete_intake()
    )
    route = respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200, text=stream_body(output), headers={"content-type": "text/event-stream"}
        )
    )
    result = model().generate(
        task=ModelTask.INTAKE,
        system_prompt="test",
        payload={},
        output_schema=MEMORY_OUTPUT_SCHEMA if memory else INTAKE_SCHEMA,
    )
    assert result is not None
    request = json.loads(route.calls[0].request.content)
    assert request["model"] == "compass-5.6-luna"
    assert request["stream"] is True
    assert request["text"]["format"]["type"] == "json_schema"
    assert not {"temperature", "reasoning", "chat_template_kwargs"} & request.keys()


def memory_reflection():
    return dict(
        case_review=dict(key_issue="Evidence context matters.", actions_taken=["Assessed evidence."],
            observations=["Observed damage."], judgment_changes=[], final_action="FULL_REFUND",
            limitations=["Execution and causal benefit not verified."], source_event_refs=["EVENT-1"], downstream_execution_verified=False),
        learning=dict(category="OPERATIONAL_METHOD", explanation="A context-aware observation.",
            source_event_refs=["EVENT-1"]),
    )


@pytest.mark.parametrize(
    "status,terminal,output",
    [
        ("incomplete", True, complete_intake()),
        ("completed", False, complete_intake()),
        ("completed", True, {"completeness": "INVALID"}),
    ],
)
@respx.mock
def test_responses_reject_incomplete_or_invalid_output(status, terminal, output):
    respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200,
            text=stream_body(output, status=status, terminal=terminal),
            headers={"content-type": "text/event-stream"},
        )
    )
    with pytest.raises(ValueError):
        model().generate(
            task=ModelTask.INTAKE,
            system_prompt="test",
            payload={},
            output_schema=INTAKE_SCHEMA,
        )


@respx.mock
def test_responses_timeout_is_not_retried():
    route = respx.post("http://compass.test/v1/responses").mock(
        side_effect=httpx.ReadTimeout("timeout")
    )
    from openai import APITimeoutError

    with pytest.raises(APITimeoutError):
        model().generate(
            task=ModelTask.INTAKE,
            system_prompt="test",
            payload={},
            output_schema=INTAKE_SCHEMA,
        )
    assert route.call_count == 1


@pytest.mark.parametrize(
    "schema,output",
    [
        (ASSESSMENT_SCHEMA, {"output": supported_assessment().model_dump(mode="json")}),
        (RESOLVER_SCHEMA, {"output": proposal_output().model_dump(mode="json")}),
        (REVIEW_SCHEMA, {"output": approved_review().model_dump(mode="json")}),
        (
            MEMORY_OUTPUT_SCHEMA,
            {
                "output": {
                    "result_type": "CREATE_CANDIDATE",
                    **memory_reflection(),
                    "candidate": {
                        "memory_id": "MEMORY-TEST",
                        "retrieval_summary": "Confirmed correction; request evidence.",
                        "trigger_conditions": ["Confirmed correction"],
                        "recommended_behavior": "Request evidence",
                        "rationale": "Confirmed revision",
                        "source_case_refs": ["CASE-TEST"],
                        "source_event_refs": ["REVISION-TEST"],
                        "applicability_limits": [],
                        "prohibited_inferences": [],
                        "policy_version": "RETURNS-TW:v1",
                        "claim_registry_version": "claim-registry:1.0",
                        "scope": {
                            "market": "TW",
                            "reason_codes": ["ITEM_DAMAGED"],
                            "claim_ids": ["DAMAGE_PRESENT_ON_ARRIVAL"],
                            "categories": ["CAT-AUDIO-SPEAKERS"],
                        },
                        "confidence": 0.8,
                        "status": "CANDIDATE",
                    },
                }
            },
        ),
    ],
)
@respx.mock
def test_actual_node_and_candidate_schemas(schema, output):
    respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200, text=stream_body(output), headers={"content-type": "text/event-stream"}
        )
    )
    result = model().generate(
        task=ModelTask.INTAKE, system_prompt="test", payload={}, output_schema=schema
    )
    assert result.model_dump(mode="json") == output["output"]


@respx.mock
def test_memory_query_summary_uses_completed_responses_output():
    output = {"query_summary": "買家主張音箱到貨破損，現有照片顯示外殼裂痕。"}
    respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200, text=stream_body(output), headers={"content-type": "text/event-stream"}
        )
    )
    result = model().generate(
        task=ModelTask.MEMORY_QUERY_SUMMARY,
        system_prompt="test",
        payload={},
        output_schema=MEMORY_QUERY_SCHEMA,
    )
    assert result.model_dump(mode="json") == output


@pytest.mark.parametrize("output", [{}, {"query_summary": "x" * 2001}])
@respx.mock
def test_memory_query_summary_rejects_invalid_completed_output(output):
    respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200, text=stream_body(output), headers={"content-type": "text/event-stream"}
        )
    )
    with pytest.raises(ValueError):
        model().generate(
            task=ModelTask.MEMORY_QUERY_SUMMARY,
            system_prompt="test",
            payload={},
            output_schema=MEMORY_QUERY_SCHEMA,
        )


@respx.mock
def test_completed_refusal_is_not_a_valid_output():
    response = {
        "id": "resp_refused",
        "object": "response",
        "created_at": 1,
        "model": "gpt-5.6-luna",
        "status": "completed",
        "output": [
            {
                "id": "msg_refused",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "refusal", "refusal": "Cannot comply"}],
            }
        ],
    }
    event = {"type": "response.completed", "response": response}
    respx.post("http://compass.test/v1/responses").mock(
        return_value=httpx.Response(
            200,
            text=f"event: response.completed\ndata: {json.dumps(event)}\n\n",
            headers={"content-type": "text/event-stream"},
        )
    )
    with pytest.raises(ValueError):
        model().generate(
            task=ModelTask.INTAKE,
            system_prompt="test",
            payload={},
            output_schema=INTAKE_SCHEMA,
        )
