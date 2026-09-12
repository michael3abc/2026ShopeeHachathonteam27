from __future__ import annotations

import json
import subprocess
from pathlib import Path

from return_agent_contracts.review_gates import load_reviewer_gate_config
from return_agent_contracts.user_risk import load_user_risk_config


def test_compose_resolves_one_reviewer_gate_config_for_api_and_agent() -> None:
    root = Path(__file__).resolve().parents[1]
    rendered = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(rendered.stdout)["services"]
    container_path = "/run/config/reviewer-gates.json"
    host_paths: list[Path] = []

    for service_name in ("api", "agent-service"):
        service = services[service_name]
        assert service["environment"]["RETURN_AGENT_REVIEW_GATE_CONFIG"] == container_path
        mounts = [
            mount
            for mount in service["volumes"]
            if mount["target"] == container_path
        ]
        assert len(mounts) == 1
        assert mounts[0]["type"] == "bind"
        assert mounts[0]["read_only"] is True
        host_paths.append(Path(mounts[0]["source"]))

    assert host_paths[0].resolve() == host_paths[1].resolve()
    api_config = load_reviewer_gate_config(str(host_paths[0]))
    agent_config = load_reviewer_gate_config(str(host_paths[1]))
    assert api_config.version == agent_config.version == "reviewer-gates:1.0"
    assert api_config.fingerprint == agent_config.fingerprint
    assert api_config.thresholds == agent_config.thresholds
    risk_paths = []
    for name in ("api", "agent-service"):
        service = services[name]
        path = service["environment"]["RETURN_AGENT_USER_RISK_CONFIG"]
        mount = next(m for m in service["volumes"] if m["target"] == path)
        assert mount["read_only"] is True
        risk_paths.append(mount["source"])
    assert risk_paths[0] == risk_paths[1]
    assert load_user_risk_config(risk_paths[0]).fingerprint == load_user_risk_config(risk_paths[1]).fingerprint
    assert any(s["source"] == "demo_identities" for s in services["api"]["secrets"])
