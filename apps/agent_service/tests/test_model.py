import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from return_agent_contracts.domain import EvidenceAssessment
from return_agent_contracts.memory import MemoryQuerySummary
from return_agent_contracts.providers import ProviderUnavailable
from return_agent_service.model import ModelSettings, StructuredModel, output_schema


class Client:
    def __init__(self, response):
        self.response = response
    def with_structured_output(self, schema, **kwargs):
        self.schema, self.options = schema, kwargs
        return self
    def invoke(self, messages):
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def settings(profile="integrated-compass"):
    return ModelSettings(profile=profile, base_url="https://model.invalid/v1", model_name="explicit-test-model", api_key=SecretStr("synthetic-key"))


def test_strict_union_schema_preserves_local_validation():
    schema, wrapped = output_schema(EvidenceAssessment)
    assert wrapped and schema["type"] == "object" and schema["required"] == ["output"]
    assert "$defs" in schema and "anyOf" in schema["properties"]["output"]
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition["required"] == list(definition["properties"])
            assert definition["additionalProperties"] is False


@pytest.mark.parametrize("profile", ["integrated-compass", "integrated-qwen"])
def test_explicit_profile_and_prompt_envelope(profile):
    client = Client({"parsed": {"query_summary": "音訊商品需確認外觀損壞與退回檢測必要性。"}})
    model = StructuredModel(settings(profile), client=client)
    result = model.generate("MEMORY_QUERY_SUMMARY", {"reason": "外觀損壞"}, MemoryQuerySummary)
    assert result.query_summary
    body = json.loads(client.messages[1].content)
    assert body["task_mode"] == "MEMORY_QUERY_SUMMARY"
    assert ("required_output_schema" in body) == (profile == "integrated-qwen")
    assert client.options == {"method": "json_schema", "include_raw": True, "strict": True}


def test_responses_function_arguments_are_explicitly_parsed():
    client = Client({"parsed": None, "raw": SimpleNamespace(tool_calls=[{"args": '{"query_summary":"外觀損壞待獨立確認。"}'}])})
    assert StructuredModel(settings(), client=client).generate("MEMORY_QUERY_SUMMARY", {}, MemoryQuerySummary).query_summary


@pytest.mark.parametrize("response", [{"parsed": None}, {"parsed": {"query_summary": "https://private.invalid"}}, RuntimeError("remote-sensitive-payload")])
def test_no_mock_fallback_and_no_remote_payload_leak(response):
    client = Client(response)
    with pytest.raises(ProviderUnavailable) as error:
        StructuredModel(settings(), client=client).generate("MEMORY_QUERY_SUMMARY", {}, MemoryQuerySummary)
    assert str(error.value) == "Structured model task MEMORY_QUERY_SUMMARY failed"
    assert error.value.__suppress_context__


def test_env_uses_explicit_host_secret_file_without_changing_model(tmp_path):
    key = tmp_path / "synthetic-secret"
    key.write_text("synthetic-test-key\n")
    values = {"RETURN_AGENT_SERVICE_PROFILE": "integrated-compass", "RETURN_AGENT_MODEL_BASE_URL": "https://model.invalid/v1", "RETURN_AGENT_MODEL_NAME": "keep-this-model", "RETURN_AGENT_MODEL_API_KEY_FILE": "/container-only/key", "RETURN_AGENT_MODEL_API_KEY_HOST_FILE": str(key)}
    loaded = ModelSettings.from_env(values, host=True)
    assert loaded.model_name == "keep-this-model" and loaded.api_key.get_secret_value() == "synthetic-test-key"
    assert "synthetic-test-key" not in repr(loaded)
    with pytest.raises(FileNotFoundError):
        ModelSettings.from_env(values)
