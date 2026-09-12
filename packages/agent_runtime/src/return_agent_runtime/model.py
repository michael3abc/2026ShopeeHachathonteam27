"""Structured-output model abstraction and OpenAI implementation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import TypeAdapter

from .serialization import json_value


class ModelTask(StrEnum):
    ACTIVITY_NARRATION = "ACTIVITY_NARRATION"
    INTAKE = "INTAKE"
    ASSESS = "ASSESS"
    PROPOSE_OR_REVISE = "PROPOSE_OR_REVISE"
    REVIEW = "REVIEW"
    MEMORY_DISTILL = "MEMORY_DISTILL"
    MEMORY_QUERY_SUMMARY = "MEMORY_QUERY_SUMMARY"


OutputT = TypeVar("OutputT")


@dataclass(frozen=True, slots=True)
class OutputSchema(Generic[OutputT]):
    """Named Pydantic adapter accepted by both production and fake models."""

    name: str
    adapter: TypeAdapter[OutputT]


class StructuredOutputModel(Protocol):
    """Minimal model boundary consumed by graph nodes."""

    def generate(
        self,
        *,
        task: ModelTask,
        system_prompt: str,
        payload: Mapping[str, Any],
        output_schema: OutputSchema[OutputT],
    ) -> OutputT: ...


@dataclass(slots=True)
class OpenAIStructuredOutputModel:
    """ChatOpenAI adapter with a final local Pydantic validation pass.

    ``include_schema_in_prompt`` exists for OpenAI-compatible servers that use
    JSON Schema only as a decoding grammar and do not expose its meaning to the
    model. Official OpenAI endpoints can leave it disabled.
    """

    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 180.0
    max_retries: int = 0
    temperature: float | None = 0.0
    extra_body: Mapping[str, Any] | None = None
    include_schema_in_prompt: bool = False
    use_responses_api: bool = False
    streaming: bool = False
    _model: ChatOpenAI = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be blank")
        if self.base_url is not None and not self.base_url.strip():
            raise ValueError("base_url must not be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "timeout": self.timeout_seconds,
            "max_retries": self.max_retries,
            "use_responses_api": self.use_responses_api,
            "streaming": self.streaming,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if self.base_url is not None:
            kwargs["base_url"] = self.base_url
        if self.extra_body is not None:
            kwargs["extra_body"] = dict(self.extra_body)
        self._model = ChatOpenAI(**kwargs)

    def generate(
        self,
        *,
        task: ModelTask,
        system_prompt: str,
        payload: Mapping[str, Any],
        output_schema: OutputSchema[OutputT],
    ) -> OutputT:
        schema = output_schema.adapter.json_schema()
        schema.setdefault("title", output_schema.name)
        wrapped = schema.get("type") != "object"
        if wrapped:
            definitions = schema.pop("$defs", None)
            schema = {
                "title": f"{output_schema.name}Envelope",
                "type": "object",
                "properties": {"output": schema},
                "required": ["output"],
                "additionalProperties": False,
            }
            if definitions is not None:
                schema["$defs"] = definitions
        runnable = self._model.with_structured_output(
            schema,
            method="json_schema",
            **({"include_raw": True} if self.use_responses_api else {}),
        )
        request_body: dict[str, Any] = {
            "task_mode": task.value,
            "input": json_value(payload),
        }
        if self.include_schema_in_prompt:
            request_body["required_output_schema"] = schema

        raw = runnable.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=json.dumps(
                        request_body,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                ),
            ]
        )
        if self.use_responses_api:
            message = raw["raw"]
            if message.response_metadata.get("status") != "completed":
                raise ValueError("Responses request did not complete successfully")
            if raw["parsing_error"] is not None:
                raise raw["parsing_error"]
            raw = raw["parsed"]
        if wrapped:
            if not isinstance(raw, Mapping) or set(raw) != {"output"}:
                raise ValueError("structured union output must use the output envelope")
            raw = raw["output"]
        return output_schema.adapter.validate_python(raw)
