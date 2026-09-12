"""Environment-backed Agent service settings without secret defaults."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentServiceSettings:
    redis_url: str
    consumer_name: str
    profile: str
    agent_database_url: str = (
        "postgresql://return_agent_graph:return_agent_graph@localhost:5433/"
        "return_agent_graph"
    )
    api_base_url: str = "http://localhost:8000"
    internal_service_token: str | None = None
    provider_timeout_seconds: float = 30.0
    command_lease_seconds: int = 900
    memory_retry_initial_seconds: float = 0.25
    memory_retry_max_seconds: float = 30.0
    host: str = "0.0.0.0"
    port: int = 8090
    block_ms: int = 1_000
    reclaim_idle_ms: int = 60_000

    @classmethod
    def from_env(cls) -> AgentServiceSettings:
        internal_token = os.environ.get("RETURN_AGENT_INTERNAL_SERVICE_TOKEN")
        internal_token_file = os.environ.get("RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE")
        if not internal_token and internal_token_file:
            internal_token = (
                Path(internal_token_file).read_text(encoding="utf-8").strip()
            )
        return cls(
            redis_url=os.environ.get(
                "RETURN_AGENT_REDIS_URL", "redis://localhost:6379/0"
            ),
            consumer_name=os.environ.get(
                "RETURN_AGENT_CONSUMER_NAME", f"agent-{socket.gethostname()}"
            ),
            profile=os.environ.get("RETURN_AGENT_SERVICE_PROFILE", "production"),
            agent_database_url=os.environ.get(
                "RETURN_AGENT_DATABASE_URL",
                "postgresql://return_agent_graph:return_agent_graph@localhost:5433/return_agent_graph",
            ),
            api_base_url=os.environ.get(
                "RETURN_AGENT_API_BASE_URL", "http://localhost:8000"
            ),
            internal_service_token=internal_token,
            provider_timeout_seconds=float(
                os.environ.get("RETURN_AGENT_PROVIDER_TIMEOUT_SECONDS", "30")
            ),
            command_lease_seconds=int(
                os.environ.get("RETURN_AGENT_COMMAND_LEASE_SECONDS", "900")
            ),
            memory_retry_initial_seconds=float(
                os.environ.get("RETURN_AGENT_MEMORY_RETRY_INITIAL_SECONDS", "0.25")
            ),
            memory_retry_max_seconds=float(
                os.environ.get("RETURN_AGENT_MEMORY_RETRY_MAX_SECONDS", "30")
            ),
            host=os.environ.get("RETURN_AGENT_SERVICE_HOST", "0.0.0.0"),
            port=int(os.environ.get("RETURN_AGENT_SERVICE_PORT", "8090")),
            block_ms=int(os.environ.get("RETURN_AGENT_REDIS_BLOCK_MS", "1000")),
            reclaim_idle_ms=int(
                os.environ.get("RETURN_AGENT_REDIS_RECLAIM_IDLE_MS", "60000")
            ),
        )
