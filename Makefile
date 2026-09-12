.PHONY: contracts test-agent-runtime test-agent-service test-api test-contracts test-e2e test-web dev-api dev-agent-service dev-web migrate check check-web

contracts:
	uv run --package return-agent-contracts return-agent-export-schemas --output apps/contracts/schemas/agent/v1
	uv run --package return-agent-contracts return-agent-export-ui-schemas --output apps/contracts/schemas/ui/v1
	uv run --package return-agent-contracts return-agent-export-operations-schemas --output apps/contracts/schemas/operations/v1

test-contracts:
	uv run --package return-agent-contracts pytest apps/contracts/tests

test-api:
	uv run --package return-agent-api pytest apps/api/tests

test-agent-service:
	uv run --package return-agent-service pytest apps/agent_service/tests

test-e2e:
	LANGGRAPH_STRICT_MSGPACK=true uv run --all-packages pytest tests

dev-api:
	uv run --package return-agent-api uvicorn return_agent.app:app --reload

dev-agent-service:
	RETURN_AGENT_SERVICE_PROFILE=demo uv run --package return-agent-service return-agent-service

dev-web:
	npm --prefix apps/web run dev

test-web:
	npm --prefix apps/web test

check-web: test-web
	npm --prefix apps/web run lint
	npm --prefix apps/web run build

migrate:
	cd apps/api && uv run --package return-agent-api alembic upgrade head

test-agent-runtime:
	uv run --package return-agent-runtime pytest packages/agent_runtime/tests

check: test-contracts test-api test-agent-runtime test-agent-service test-e2e
