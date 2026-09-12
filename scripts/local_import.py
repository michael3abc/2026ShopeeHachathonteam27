"""Run the imported implementation using this host's keys and isolated databases."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    """Parse literal assignments without executing shell expressions."""
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise ValueError(f"Invalid dotenv key on line {number}")
        parts = shlex.split(value, comments=True, posix=True)
        if len(parts) > 1:
            raise ValueError(f"Quote dotenv values on line {number}")
        values[key.strip()] = parts[0] if parts else ""
    return values


def environment() -> dict[str, str]:
    values = {**read_env(ROOT / ".env"), **os.environ}
    for name in (
        "RETURN_AGENT_MODEL_BASE_URL", "RETURN_AGENT_MODEL_NAME",
        "RETURN_AGENT_MODEL_API_KEY_FILE", "RETURN_AGENT_EMBEDDING_BASE_URL",
        "RETURN_AGENT_EMBEDDING_MODEL", "RETURN_AGENT_EMBEDDING_API_KEY_FILE",
    ):
        if not values.get(name):
            raise ValueError(f"{name} must be configured on this host")
        if name.endswith("_FILE"):
            path = Path(values[name])
            if not path.is_absolute():
                path = ROOT / path
            if not path.is_file():
                raise ValueError(f"{name} does not reference a local file")
            values[name] = str(path)
    if values.get("RETURN_AGENT_SERVICE_PROFILE") not in {"integrated-compass", "integrated-qwen"}:
        raise ValueError("An explicit live model profile is required; no demo fallback")
    token = ROOT / "secrets/internal-service-token"
    if not token.is_file():
        raise ValueError("Existing internal service token is required")
    # Never inherit the rebuild's database URLs, port overrides, or Redis DB.
    values.update(
        DATABASE_URL="postgresql+psycopg://return_agent_api:return_agent_api@127.0.0.1:55432/return_agent_api",
        RETURN_AGENT_DATABASE_URL="postgresql://return_agent_graph:return_agent_graph@127.0.0.1:55433/return_agent_graph",
        RETURN_AGENT_REDIS_URL="redis://127.0.0.1:56379/0",
        API_POSTGRES_PORT="55432", AGENT_POSTGRES_PORT="55433", REDIS_PORT="56379",
        RETURN_AGENT_API_PROFILE="integrated-demo",
        RETURN_AGENT_API_BASE_URL="http://127.0.0.1:8000",
        RETURN_AGENT_DEMO_DATA_DIR=str(ROOT / "data"),
        RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE=str(token),
        RETURN_AGENT_REVIEW_GATE_CONFIG=str(ROOT / "config/reviewer-gates.json"),
        RETURN_AGENT_SERVICE_HOST="127.0.0.1", RETURN_AGENT_SERVICE_PORT="8090",
        API_BASE_URL="http://127.0.0.1:8000", LANGGRAPH_STRICT_MSGPACK="true",
    )
    values.pop("RETURN_AGENT_INTERNAL_SERVICE_TOKEN", None)
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=("check-config", "infra", "migrate", "api", "agent", "web", "smoke"))
    args = parser.parse_args()
    values = environment()
    os.chdir(ROOT)
    if args.component == "check-config":
        print("Configuration valid; local key files present (no network probe).")
        print("Model:", values["RETURN_AGENT_MODEL_NAME"])
        print("Profile:", values["RETURN_AGENT_SERVICE_PROFILE"])
        return
    if args.component == "migrate":
        os.environ.update(values)
        from alembic import command
        from alembic.config import Config
        config = Config(str(ROOT / "apps/api/alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
        command.upgrade(config, "head")
        return
    commands = {
        "infra": ["docker", "compose", "-p", "team27-imported", "-f", "docker-compose.yml", "up", "-d", "--wait", "--wait-timeout", "90", "api-db", "agent-db", "redis"],
        "api": [sys.executable, "-m", "uvicorn", "return_agent.app:app", "--host", "127.0.0.1", "--port", "8000"],
        "agent": [sys.executable, "-m", "return_agent_service.main"],
        "web": ["npm", "--prefix", "apps/web", "run", "start", "--", "--hostname", "127.0.0.1"],
        "smoke": [sys.executable, "scripts/run_no_ui_e2e.py", "--timeout", "300"],
    }
    command_args = commands[args.component]
    if args.component == "infra":
        subprocess.run(command_args, env=values, check=True, timeout=120)
        return
    os.execvpe(command_args[0], command_args, values)


if __name__ == "__main__":
    main()
