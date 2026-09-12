"""Verify pixel transport without live model calls or encoded graph state."""

import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, TypeAdapter
from return_agent_contracts.attachments import ImageContent
from return_agent_contracts.image_adapter import HttpEvidenceImageProvider
from return_agent_runtime.model import (
    ModelTask,
    OpenAIStructuredOutputModel,
    OutputSchema,
)


class Answer(BaseModel):
    observed: str


SCHEMA = OutputSchema("Answer", TypeAdapter(Answer))
REF = "artifact://upload/" + "a" * 32


class Pictures:
    def __init__(self):
        self.calls = []

    def load_image(self, case_ref, artifact_ref):
        self.calls.append((case_ref, artifact_ref))
        return ImageContent("image/png", b"test-pixels")


@pytest.mark.parametrize(
    "task", [ModelTask.ASSESS, ModelTask.PROPOSE_OR_REVISE, ModelTask.REVIEW]
)
@pytest.mark.parametrize("responses", [False, True])
def test_images_reach_model_and_do_not_mutate_payload(task, responses):
    pictures = Pictures()
    model = OpenAIStructuredOutputModel(
        model_name="gpt-5.6",
        api_key="test",
        use_responses_api=responses,
        image_provider=pictures,
        temperature=None,
    )
    sdk = model._model
    captured = []

    def invoke(messages):
        captured.extend(messages)
        result = {"observed": "neutral pixel observation"}
        return (
            {
                "raw": SimpleNamespace(response_metadata={"status": "completed"}),
                "parsing_error": None,
                "parsed": result,
            }
            if responses
            else result
        )

    model._model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(invoke=invoke)
    )
    evidence = [{"evidence_id": "EV-A", "subject": "LI-1", "artifact_ref": REF}]
    payload = {"case_context": {"case_ref": "CASE-1"}, "evidence_bundle": evidence}
    if task == ModelTask.REVIEW:
        payload = {
            "case_context": payload["case_context"],
            "proposed_decision_handoff": {"evidence_bundle": evidence},
        }
    before = json.dumps(payload)
    assert model.generate(
        task=task,
        system_prompt="Inspect evidence",
        payload=payload,
        output_schema=SCHEMA,
    ).observed
    assert pictures.calls == [("CASE-1", REF)]
    blocks = captured[1].content
    assert "EV-A" in blocks[1]["text"] and "LI-1" in blocks[1]["text"]
    assert (
        blocks[2]["image_url"]["url"]
        == "data:image/png;base64," + base64.b64encode(b"test-pixels").decode()
    )
    assert json.dumps(payload) == before
    assert "base64" not in before and "test-pixels" not in repr(model)
    # Exercise the installed SDK's actual Chat/Responses wire conversion too.
    wire = sdk._get_request_payload(captured)
    if responses:
        assert wire["input"][1]["content"][2]["type"] == "input_image"
    else:
        assert wire["messages"][1]["content"][2]["type"] == "image_url"


def test_no_provider_or_fetch_failure_never_invokes_text_model():
    model = OpenAIStructuredOutputModel(
        model_name="gpt-5.6", api_key="test", temperature=None
    )
    payload = {
        "case_context": {"case_ref": "CASE-1"},
        "evidence_bundle": [
            {"evidence_id": "EV", "subject": "ORDER", "artifact_ref": REF}
        ],
    }

    def invoke(messages):
        pytest.fail("Should never invoke model")

    model._model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(invoke=invoke)
    )
    with pytest.raises(RuntimeError, match="Image provider is not configured"):
        model.generate(
            task=ModelTask.ASSESS,
            system_prompt="test",
            payload=payload,
            output_schema=SCHEMA,
        )

    def unavailable(*args):
        raise RuntimeError("Image unavailable")

    model.image_provider = SimpleNamespace(load_image=unavailable)
    with pytest.raises(RuntimeError, match="Image unavailable"):
        model.generate(
            task=ModelTask.ASSESS,
            system_prompt="test",
            payload=payload,
            output_schema=SCHEMA,
        )


def test_model_failure_does_not_echo_image_content():
    model = OpenAIStructuredOutputModel(
        model_name="gpt-5.6",
        api_key="test",
        image_provider=Pictures(),
        temperature=None,
    )

    def invoke(messages):
        raise ValueError(str(messages))

    model._model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(invoke=invoke)
    )
    with pytest.raises(RuntimeError) as caught:
        model.generate(
            task=ModelTask.ASSESS,
            system_prompt="test",
            payload={
                "case_context": {"case_ref": "CASE-1"},
                "evidence_bundle": [
                    {"artifact_ref": REF, "evidence_id": "EV", "subject": "ORDER"}
                ],
            },
            output_schema=SCHEMA,
        )
    assert "base64" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_metadata_only_fixtures_and_nonvisual_tasks_remain_text():
    model = OpenAIStructuredOutputModel(
        model_name="gpt-5.6", api_key="test", temperature=None
    )

    def invoke(messages):
        assert isinstance(messages[1].content, str)
        return {"observed": "text-only"}

    model._model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(invoke=invoke)
    )
    for task, ref in [
        (ModelTask.ASSESS, "artifact://demo/fixture"),
        (ModelTask.MEMORY_DISTILL, REF),
    ]:
        model.generate(
            task=task,
            system_prompt="test",
            payload={"evidence_bundle": [{"artifact_ref": ref}]},
            output_schema=SCHEMA,
        )


@pytest.mark.parametrize(
    "status,mime,body,expected",
    [
        (403, "image/png", b"", RuntimeError),
        (200, "text/html", b"html", ValueError),
        (200, "image/png", b"", ValueError),
        (200, "image/png", b"large-content", ValueError),
        (302, "image/png", b"", RuntimeError),
    ],
)
def test_image_transport_rejects_invalid_responses(status, mime, body, expected):
    def handle(request):
        assert request.headers["authorization"] == "Bearer secret-test"
        assert request.url.path == "/internal/cases/CASE-1/images/" + "a" * 32
        return httpx.Response(status, headers={"content-type": mime}, content=body)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = HttpEvidenceImageProvider(
            "http://api", "secret-test", client, max_bytes=5
        )
        with pytest.raises(expected):
            provider.load_image("CASE-1", REF)


def test_image_transport_has_no_arbitrary_url_fetch():
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected fetch"))
    ) as client:
        provider = HttpEvidenceImageProvider("http://api", "test", client)
        with pytest.raises(ValueError):
            provider.load_image("CASE-1", "https://attacker/image.png")
