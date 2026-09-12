import pytest
from return_agent_service.main import _configured_model, create_application


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
    assert model.extra_body == (
        None if compass else {"chat_template_kwargs": {"enable_thinking": False}}
    )


def test_compass_profile_uses_integrated_composition(monkeypatch):
    monkeypatch.setenv("RETURN_AGENT_SERVICE_PROFILE", "integrated-compass")
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://127.0.0.1:8790/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "compass-5.6-luna")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY", "local-router")
    monkeypatch.setattr(
        "return_agent_service.composition.compose_integrated_service",
        lambda **kwargs: kwargs,
    )
    composition = create_application()
    assert composition["settings"].profile == "integrated-compass"
    assert composition["model"].use_responses_api


def test_model_key_file_and_missing_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("RETURN_AGENT_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("RETURN_AGENT_MODEL_BASE_URL", "http://127.0.0.1:8790/v1")
    monkeypatch.setenv("RETURN_AGENT_MODEL_NAME", "compass-5.6-luna")
    key = tmp_path / "client-key"
    key.write_text("local-router\n")
    monkeypatch.setenv("RETURN_AGENT_MODEL_API_KEY_FILE", str(key))
    assert _configured_model(compass=True).api_key == "local-router"
    monkeypatch.delenv("RETURN_AGENT_MODEL_NAME")
    with pytest.raises(RuntimeError, match="requires"):
        _configured_model(compass=True)
