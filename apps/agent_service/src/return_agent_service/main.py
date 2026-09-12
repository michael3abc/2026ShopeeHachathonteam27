"""Console entrypoint for the health server and Redis worker process."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from return_agent_contracts.review_gates import load_reviewer_gate_config

from .settings import AgentServiceSettings


def create_application():
    settings = AgentServiceSettings.from_env()
    if settings.profile in {"demo", "demo-qwen"}:
        from .composition import compose_service
        from .demo import create_demo_runtime

        model = _qwen_model() if settings.profile == "demo-qwen" else None
        return compose_service(
            settings=settings,
            runtime=create_demo_runtime(model_override=model, reviewer_gate_config=load_reviewer_gate_config(os.environ.get("RETURN_AGENT_REVIEW_GATE_CONFIG"))),
        )
    if settings.profile in {"integrated-qwen", "integrated-compass"}:
        from .composition import compose_integrated_service

        return compose_integrated_service(
            settings=settings,
            model=_configured_model(compass=settings.profile == "integrated-compass"),
            memory_model=_configured_model(compass=settings.profile == "integrated-compass", memory=True),
        )
    raise RuntimeError(
        "production composition is intentionally unavailable until durable "
        "checkpointer, journal, and Provider adapters are injected"
    )


def _qwen_model():
    return _configured_model(compass=False)


def _configured_model(*, compass: bool, memory: bool = False):
    from return_agent_runtime import OpenAIStructuredOutputModel

    base_url = os.environ.get("RETURN_AGENT_MODEL_BASE_URL")
    model_name = os.environ.get("RETURN_AGENT_MODEL_NAME")
    api_key = os.environ.get("RETURN_AGENT_MODEL_API_KEY")
    key_file = os.environ.get("RETURN_AGENT_MODEL_API_KEY_FILE")
    effort = None
    if memory:
        model_name = os.environ.get("RETURN_AGENT_MEMORY_MODEL_NAME") or ("compass-5.6-sol" if compass else model_name)
        effort = os.environ.get("RETURN_AGENT_MEMORY_REASONING_EFFORT") or ("high" if compass else None)
        if not compass and (effort is not None or (model_name or "").startswith("compass-")):
            raise ValueError("Compass memory model/effort requires integrated-compass profile")
        # Transport credentials are deliberately shared unless explicitly overridden.
        base_url = os.environ.get("RETURN_AGENT_MEMORY_MODEL_BASE_URL") or base_url
        if os.environ.get("RETURN_AGENT_MEMORY_MODEL_API_KEY") or os.environ.get("RETURN_AGENT_MEMORY_MODEL_API_KEY_FILE"):
            api_key = os.environ.get("RETURN_AGENT_MEMORY_MODEL_API_KEY")
            key_file = os.environ.get("RETURN_AGENT_MEMORY_MODEL_API_KEY_FILE")
    if not api_key and key_file:
        api_key = Path(key_file).read_text(encoding="utf-8").strip()
    if not base_url or not model_name or not api_key:
        raise RuntimeError("model requires base URL, name, and API key or key file")
    return OpenAIStructuredOutputModel(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=float(os.environ.get("RETURN_AGENT_MEMORY_MODEL_TIMEOUT_SECONDS", "180")) if memory else 180,
        reasoning_effort=effort,
        max_output_tokens=int(os.environ.get("RETURN_AGENT_MEMORY_MAX_OUTPUT_TOKENS", "16384")) if memory else None,
        max_retries=0,
        temperature=None if compass else 0,
        use_responses_api=compass,
        include_schema_in_prompt=not compass,
        streaming=True,
        extra_body=None
        if compass
        else {"chat_template_kwargs": {"enable_thinking": False}},
    )


def main() -> None:
    settings = AgentServiceSettings.from_env()
    uvicorn.run(
        "return_agent_service.main:create_application",
        factory=True,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
