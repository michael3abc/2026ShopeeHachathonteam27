FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
COPY apps/agent_service/pyproject.toml apps/agent_service/
COPY apps/contracts/pyproject.toml apps/contracts/
COPY packages/agent_runtime/pyproject.toml packages/agent_runtime/
RUN uv sync --locked --package return-agent-api --no-dev --no-install-workspace

COPY apps ./apps
COPY packages ./packages
COPY data ./data
RUN uv sync --locked --package return-agent-api --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "--package", "return-agent-api", "return-agent-api"]
