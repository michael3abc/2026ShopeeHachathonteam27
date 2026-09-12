import pytest
from return_agent_service.main import _configured_model, create_application


@pytest.fixture(autouse=True)
def clean_memory_env(monkeypatch):
    import os
    for name in os.environ:
        if name.startswith("RETURN_AGENT_MEMORY_MODEL_") or name in {
            "RETURN_AGENT_MODEL_REASONING_EFFORT",
            "RETURN_AGENT_MEMORY_REASONING_EFFORT",
            "RETURN_AGENT_MEMORY_MAX_OUTPUT_TOKENS",
        }:
            monkeypatch.delenv(name)


@pytest.mark.parametrize("compass", [False, True])
def test_model_profiles_keep_provider_options_separate(monkeypatch, compass):
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://127.0.0.1:8790/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "compass-5.6-luna")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY", "local-router")
    model = _configured_model(compass=compass)
    assert model.use_responses_api is compass
    assert model.streaming
    assert model.timeout_seconds == 180
    assert model.max_retries == 0
    assert model.temperature == (None if compass else 0)
    assert model.include_schema_in_prompt is not compass
    assert model.reasoning_effort == ("medium" if compass else None)
    assert model.extra_body == (
        None if compass else {"chat_template_kwargs": {"enable_thinking": False}}
    )


def test_compass_profile_uses_integrated_composition(monkeypatch):
    monkeypatch.setenv("RETURN_AGENT_SERVICE_PROFILE", "integrated-compass")
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://127.0.0.1:8790/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY", "local-router")
    monkeypatch.setattr(
        "return_agent_service.composition.compose_integrated_service",
        lambda **kwargs: kwargs,
    )
    composition = create_application()
    assert composition["settings"].profile == "integrated-compass"
    assert composition["model"].use_responses_api
    assert composition["model"].model_name == "compass-5.6-terra"
    assert composition["model"].reasoning_effort == "medium"
    assert composition["memory_model"].model_name == "compass-5.6-terra"
    assert composition["memory_model"].reasoning_effort == "medium"
    assert composition["memory_model"].max_output_tokens == 16384
    assert composition["memory_model"].max_retries == 0
    assert composition["model"] is not composition["memory_model"]


def test_model_key_file_and_missing_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("RETURN_AGENT_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://127.0.0.1:8790/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "compass-5.6-luna")
    key = tmp_path / "client-key"
    key.write_text("local-router\n")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY_FILE", str(key))
    assert _configured_model(compass=True).api_key == "local-router"
    monkeypatch.delenv("RETURN_AGENT_MODEL_BASE_URL")
    with pytest.raises(RuntimeError, match="requires"):
        _configured_model(compass=True)


def configure(monkeypatch):
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://compass.test/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "compass-5.6-luna")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY", "shared-key")


def test_compass_reasoning_effort_overrides_are_independent(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("RETURN_AGENT_MODEL_REASONING_EFFORT", "low")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_REASONING_EFFORT", "high")
    ordinary = _configured_model(compass=True)
    memory = _configured_model(compass=True, memory=True)
    assert ordinary.reasoning_effort == "low"
    assert memory.reasoning_effort == "high"


def test_empty_compose_effort_uses_profile_default(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("RETURN_AGENT_MODEL_REASONING_EFFORT", "")
    assert _configured_model(compass=True).reasoning_effort == "medium"
    assert _configured_model(compass=False).reasoning_effort is None


def test_memory_transport_override_and_credential_free_profile(monkeypatch, tmp_path):
    from return_agent_service.composition import _memory_model_profile

    configure(monkeypatch)
    key = tmp_path / "memory-key"
    key.write_text("separate-key\n")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_MODEL_API_KEY_FILE", str(key))
    monkeypatch.setenv("RETURN_AGENT_MEMORY_MODEL_BASE_URL", "http://memory.test/v1")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_MODEL_TIMEOUT_SECONDS", "95")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_MAX_OUTPUT_TOKENS", "8192")
    model = _configured_model(compass=True, memory=True)
    assert model.api_key == "separate-key" and model.base_url == "http://memory.test/v1"
    assert model.timeout_seconds == 95 and model.max_output_tokens == 8192
    ordinary = _configured_model(compass=True)
    assert ordinary.api_key == "shared-key" and ordinary.base_url == "http://compass.test/v1"
    profile = _memory_model_profile(model)
    assert profile["reasoning_effort"] == "medium"
    assert len(profile["endpoint_hash"]) == 64
    assert not any(secret in str(profile) for secret in ("separate-key", "memory.test", str(key)))


def test_qwen_memory_profile_stays_chat_and_rejects_compass_options(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "qwen-test")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_MODEL_NAME", "")
    monkeypatch.setenv("RETURN_AGENT_MEMORY_REASONING_EFFORT", "")
    model = _configured_model(compass=False, memory=True)
    assert model.model_name == "qwen-test" and not model.use_responses_api
    assert model.reasoning_effort is None and model.temperature == 0
    assert model.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    monkeypatch.setenv("RETURN_AGENT_MEMORY_REASONING_EFFORT", "high")
    with pytest.raises(ValueError, match="integrated-compass"):
        _configured_model(compass=False, memory=True)


def test_qwen_primary_profile_rejects_compass_reasoning_effort(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "qwen-test")
    monkeypatch.setenv("RETURN_AGENT_MODEL_REASONING_EFFORT", "medium")
    with pytest.raises(ValueError, match="integrated-compass"):
        _configured_model(compass=False)


@pytest.mark.parametrize("name,value", [
    ("REASONING_EFFORT", "sol-high"), ("MODEL_TIMEOUT_SECONDS", "nan"),
    ("MODEL_TIMEOUT_SECONDS", "inf"), ("MODEL_TIMEOUT_SECONDS", "0"),
    ("MAX_OUTPUT_TOKENS", "0"), ("MAX_OUTPUT_TOKENS", "not-a-number"),
])
def test_invalid_memory_config_fails_explicitly(monkeypatch, name, value):
    configure(monkeypatch)
    monkeypatch.setenv(f"RETURN_AGENT_MEMORY_{name}", value)
    with pytest.raises(ValueError):
        _configured_model(compass=True, memory=True)
    assert _configured_model(compass=True).model_name == "compass-5.6-luna"
