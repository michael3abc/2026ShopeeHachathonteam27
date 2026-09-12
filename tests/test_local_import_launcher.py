from pathlib import Path
import runpy

import pytest

LAUNCHER = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/local_import.py"))


def test_dotenv_is_literal_and_does_not_execute(tmp_path):
    path = tmp_path / "settings"
    marker = tmp_path / "must-not-exist"
    path.write_text(f"VALUE='$(touch {marker})'\nOTHER='hello world' # comment\n")
    assert LAUNCHER["read_env"](path) == {"VALUE": f"$(touch {marker})", "OTHER": "hello world"}
    assert not marker.exists()


@pytest.mark.parametrize("line", ["not an assignment", "1KEY=x", "KEY=unquoted space"])
def test_dotenv_rejects_invalid_assignment(tmp_path, line):
    path = tmp_path / "settings"
    path.write_text(line)
    with pytest.raises(ValueError):
        LAUNCHER["read_env"](path)


def launcher_config(tmp_path, monkeypatch):
    monkeypatch.setattr(LAUNCHER["os"], "environ", {"DATABASE_URL": "postgresql://other-live-db"})
    key = tmp_path / "key"
    key.write_text("synthetic-test-secret")
    config = tmp_path / "settings"
    config.write_text("\n".join([
        "RETURN_AGENT_MODEL_BASE_URL=http://127.0.0.1:1/v1",
        "RETURN_AGENT_MODEL_NAME=synthetic-test",
        "RETURN_AGENT_MODEL_API_KEY_FILE=key",
        "RETURN_AGENT_EMBEDDING_BASE_URL=http://127.0.0.1:1/v1",
        "RETURN_AGENT_EMBEDDING_MODEL=text-embedding-3-large",
        "RETURN_AGENT_EMBEDDING_API_KEY_FILE=key",
        "RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE=key",
        "RETURN_AGENT_SERVICE_PROFILE=integrated-compass",
    ]))
    return config


def test_launcher_derives_all_service_urls_from_isolated_overrides(tmp_path, monkeypatch):
    config = launcher_config(tmp_path, monkeypatch)
    env = LAUNCHER["environment"](config, {"COMPOSE_PROJECT_NAME": "isolated-test",
        "API_POSTGRES_PORT": "15432", "AGENT_POSTGRES_PORT": "15433",
        "REDIS_PORT": "16379", "API_PORT": "18200",
        "AGENT_SERVICE_PORT": "18290", "WEB_PORT": "13200"})
    assert "127.0.0.1:15432/" in env["DATABASE_URL"]
    assert "127.0.0.1:15433/" in env["RETURN_AGENT_DATABASE_URL"]
    assert env["RETURN_AGENT_REDIS_URL"] == "redis://127.0.0.1:16379/0"
    assert env["API_BASE_URL"] == env["RETURN_AGENT_API_BASE_URL"] == "http://127.0.0.1:18200"
    assert env["RETURN_AGENT_SERVICE_PORT"] == "18290"
    assert env["WEB_PORT"] == "13200"
    assert env["COMPOSE_PROJECT_NAME"] == "isolated-test"
    assert env["RETURN_AGENT_MODEL_API_KEY_FILE"] == str(tmp_path / "key")


@pytest.mark.parametrize("overrides", [{"API_PORT": "0"}, {"REDIS_PORT": "65536"},
    {"COMPOSE_PROJECT_NAME": "invalid/project"}])
def test_launcher_rejects_invalid_isolation_settings(tmp_path, monkeypatch, overrides):
    with pytest.raises(ValueError):
        LAUNCHER["environment"](launcher_config(tmp_path, monkeypatch), overrides)
