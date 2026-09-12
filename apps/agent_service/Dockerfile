FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY apps/agent_service/pyproject.toml apps/agent_service/
COPY apps/contracts/pyproject.toml apps/contracts/
COPY packages/agent_runtime/pyproject.toml packages/agent_runtime/
RUN uv sync --locked --package return-agent-service --no-dev --no-install-workspace

COPY apps ./apps
COPY packages ./packages
RUN uv sync --locked --package return-agent-service --no-dev

EXPOSE 8090
CMD ["uv", "run", "--no-sync", "--package", "return-agent-service", "return-agent-service"]
