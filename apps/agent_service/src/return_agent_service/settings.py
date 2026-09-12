import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from return_agent_contracts.primitives import ContractModel


class Settings(ContractModel):
    profile: Literal["unconfigured", "integrated-demo", "integrated-qwen", "integrated-compass"] = "unconfigured"
    database_url: str | None = None
    redis_url: str = "redis://127.0.0.1:6379/0"
    api_base_url: str = "http://127.0.0.1:8000"
    internal_service_token: SecretStr | None = None
    concurrency: int = Field(default=2, ge=1, le=8)
    host_secrets: bool = False

    @model_validator(mode="after")
    def composition(self):
        if self.profile != "unconfigured" and (not self.database_url or self.internal_service_token is None or not self.internal_service_token.get_secret_value()):
            raise ValueError("Integrated Agent requires its database and internal service token")
        return self

    @classmethod
    def from_env(cls):
        token_file = os.getenv("INTERNAL_SERVICE_TOKEN_FILE")
        token = Path(token_file).read_text().strip() if token_file else os.getenv("INTERNAL_SERVICE_TOKEN")
        return cls(profile=os.getenv("RETURN_AGENT_SERVICE_PROFILE", "unconfigured"), database_url=os.getenv("AGENT_DATABASE_URL"), redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"), api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"), internal_service_token=token, concurrency=int(os.getenv("AGENT_CONCURRENCY", "2")), host_secrets=os.getenv("RETURN_AGENT_HOST_SECRETS", "false").lower() == "true")
