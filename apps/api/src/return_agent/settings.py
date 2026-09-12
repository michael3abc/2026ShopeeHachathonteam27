import os
from typing import Literal

from pydantic import Field

from return_agent_contracts.primitives import ContractModel


class Settings(ContractModel):
    profile: Literal["unconfigured", "integrated-demo"] = "unconfigured"
    database_url: str | None = None
    redis_url: str = "redis://127.0.0.1:6379/0"
    database_timeout_seconds: int = Field(default=5, ge=1, le=60)
    sse_poll_seconds: float = Field(default=0.25, gt=0, le=15)
    sse_heartbeat_seconds: float = Field(default=15, ge=1, le=60)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            profile=os.getenv("API_PROFILE", "unconfigured"),
            database_url=os.getenv("API_DATABASE_URL"), redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        )
