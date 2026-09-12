"""Run local components with literal dotenv values; never source the file as shell code."""
import argparse
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
            raise ValueError(f"Invalid dotenv key on line {number}")
        parts = shlex.split(value, comments=True, posix=True)
        if len(parts) > 1:
            raise ValueError(f"Quote dotenv values containing spaces on line {number}")
        values[key.strip()] = parts[0] if parts else ""
    return values


def environment(profile: str) -> dict[str, str]:
    values = {"API_DATABASE_URL": "postgresql+psycopg://return_agent:local-demo@127.0.0.1:5432/return_agent", "AGENT_DATABASE_URL": "postgresql://return_agent:local-demo@127.0.0.1:5433/return_agent", "REDIS_URL": "redis://127.0.0.1:6379/0", "API_BASE_URL": "http://127.0.0.1:8000", **read_env(ROOT / ".env"), **os.environ}
    token_path = ROOT / "secrets" / "internal-service-token"
    token_path.parent.mkdir(mode=0o700, exist_ok=True)
    if not token_path.exists():
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(secrets.token_urlsafe(48))
    values.update(API_PROFILE="integrated-demo", API_WORKERS_ENABLED="true", INTERNAL_SERVICE_TOKEN_FILE=str(token_path), RETURN_AGENT_HOST_SECRETS="true")
    if profile == "offline":
        values.update(RETURN_AGENT_SERVICE_PROFILE="integrated-demo", NARRATION_ENABLED="false")
    elif values.get("RETURN_AGENT_SERVICE_PROFILE") not in ("integrated-qwen", "integrated-compass"):
        raise ValueError("Live mode requires an explicit configured model profile")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=["migrate", "seed", "api", "agent", "web"])
    parser.add_argument("--profile", choices=["offline", "live"], default="offline")
    args = parser.parse_args()
    env = environment(args.profile)
    os.chdir(ROOT)
    if args.component == "migrate":
        for command in (["uv", "run", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"], ["uv", "run", "alembic", "-c", "apps/agent_service/alembic.ini", "upgrade", "head"], ["uv", "run", "python", "-m", "return_agent_service.checkpoint"]):
            subprocess.run(command, env=env, check=True, timeout=180)
        return
    commands = {"seed": ["uv", "run", "python", "-m", "return_agent.demo"], "api": ["uv", "run", "return-agent-api"], "agent": ["uv", "run", "return-agent-service"], "web": ["npm", "--prefix", "apps/web", "run", "dev"]}
    command = commands[args.component]
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    main()
