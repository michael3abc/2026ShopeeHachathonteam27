import copy
import json
import os
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr, TypeAdapter, model_validator

from return_agent_contracts.primitives import ContractModel
from return_agent_contracts.providers import ProviderUnavailable

PROMPTS = {"INTAKE": "intake", "ASSESS": "resolver", "PROPOSE_OR_REVISE": "resolver", "REVIEW": "reviewer", "MEMORY_QUERY_SUMMARY": "memory-query", "MEMORY_DISTILL": "memory-distiller", "ACTIVITY_NARRATION": "narration"}


class ModelSettings(ContractModel):
    profile: Literal["integrated-qwen", "integrated-compass"]
    base_url: str
    model_name: str
    api_key: SecretStr
    timeout_seconds: float = Field(default=180, gt=0, le=600)

    @model_validator(mode="after")
    def usable(self):
        url = urlsplit(self.base_url)
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
            raise ValueError("Model endpoint must be an HTTP URL without embedded credentials")
        if not self.model_name.strip() or not self.api_key.get_secret_value().strip():
            raise ValueError("Model name and secret are required")
        return self

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None, *, host: bool = False):
        values = os.environ if values is None else values
        prefix = "RETURN_AGENT_MODEL_"
        key_path = values.get(prefix + "API_KEY_HOST_FILE") if host else None
        key_path = key_path or values.get(prefix + "API_KEY_FILE")
        if not key_path:
            raise ValueError("A model API key file must be configured")
        return cls(profile=values.get("RETURN_AGENT_SERVICE_PROFILE"), base_url=values.get(prefix + "BASE_URL", ""), model_name=values.get(prefix + "NAME", ""), api_key=SecretStr(Path(key_path).read_text().strip()), timeout_seconds=float(values.get(prefix + "TIMEOUT_SECONDS", "180")))


def output_schema(output_type: Any) -> tuple[dict[str, Any], bool]:
    schema = copy.deepcopy(TypeAdapter(output_type).json_schema(mode="serialization"))
    wrapped = schema.get("type") != "object"
    if wrapped:
        definitions = schema.pop("$defs", {})
        schema = {"title": "TypedTaskOutput", "type": "object", "properties": {"output": schema}, "required": ["output"], "additionalProperties": False, "$defs": definitions}

    def strict(value):
        if isinstance(value, dict):
            value.pop("default", None)
            value.pop("discriminator", None)
            if "oneOf" in value:
                value["anyOf"] = value.pop("oneOf")
            if "const" in value:
                value["enum"] = [value.pop("const")]
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                strict(child)
        elif isinstance(value, list):
            for child in value:
                strict(child)
    strict(schema)
    return schema, wrapped


class StructuredModel:
    def __init__(self, settings: ModelSettings, *, client=None):
        self.settings = settings
        self.client = client if client is not None else ChatOpenAI(model=settings.model_name, base_url=settings.base_url, api_key=settings.api_key, timeout=settings.timeout_seconds, max_retries=0, temperature=0 if settings.profile == "integrated-qwen" else None, streaming=True, use_responses_api=settings.profile == "integrated-compass", extra_body={"chat_template_kwargs": {"enable_thinking": False}} if settings.profile == "integrated-qwen" else None)

    def generate(self, task: str, payload: dict[str, Any], output_type: Any):
        if task not in PROMPTS:
            raise ValueError("Unknown model task")
        schema, wrapped = output_schema(output_type)
        body = {"task_mode": task, "input": payload}
        if self.settings.profile == "integrated-qwen":
            body["required_output_schema"] = schema
        prompt = files("return_agent_service").joinpath("prompts", PROMPTS[task] + ".txt").read_text()
        messages = [SystemMessage(content=prompt), HumanMessage(content=json.dumps(body, ensure_ascii=False, separators=(",", ":")))]
        try:
            response = self.client.with_structured_output(schema, method="json_schema", include_raw=True, strict=True).invoke(messages)
            parsed = response.get("parsed")
            if parsed is None:
                raw = response.get("raw")
                calls = getattr(raw, "tool_calls", None) or []
                if len(calls) == 1:
                    parsed = calls[0].get("args")
                    if isinstance(parsed, str):
                        parsed = json.loads(parsed)
                else:
                    # Some compatible Responses services expose only a function-call item.
                    content = getattr(raw, "content", None)
                    functions = [item for item in content if isinstance(item, dict) and item.get("type") == "function_call"] if isinstance(content, list) else []
                    if len(functions) == 1:
                        parsed = json.loads(functions[0]["arguments"])
            if isinstance(parsed, BaseModel):
                parsed = parsed.model_dump(mode="python")
            if not isinstance(parsed, dict):
                raise ValueError("Model returned no structured object")
            if wrapped:
                if set(parsed) != {"output"}:
                    raise ValueError("Invalid union output envelope")
                parsed = parsed["output"]
            return TypeAdapter(output_type).validate_python(parsed)
        except Exception:
            # SDK exceptions may contain remote response bodies; never forward those to events/logs.
            raise ProviderUnavailable(f"Structured model task {task} failed") from None
