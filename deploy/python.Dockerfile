FROM ghcr.io/astral-sh/uv:0.12.13 AS uv
FROM python:3.12.0-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/contracts apps/contracts
COPY apps/api apps/api
COPY apps/agent_service apps/agent_service
COPY packages packages
RUN uv sync --frozen --all-packages --no-dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home agent
USER agent
CMD ["return-agent-api"]
