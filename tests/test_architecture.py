"""Dependency boundaries are requirements, not implementation snapshots."""
import ast
from pathlib import Path

from fastapi.testclient import TestClient

from return_agent.main import create_app
from return_agent_service.main import create_app as create_agent_app


def imported_roots(directory: str) -> set[str]:
    result: set[str] = set()
    for path in Path(directory).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                result.update(item.name.split(".")[0] for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                result.add(node.module.split(".")[0])
    return result


def test_api_cannot_import_graph_or_service():
    assert not imported_roots("apps/api/src") & {"return_agent_runtime", "return_agent_service", "langgraph"}


def test_runtime_cannot_own_infrastructure():
    assert not imported_roots("packages/agent_runtime/src") & {"fastapi", "httpx", "redis", "sqlalchemy", "psycopg", "return_agent"}


def test_unconfigured_services_do_not_claim_readiness():
    for app, live in [(create_app(), "/health"), (create_agent_app(), "/health/live")]:
        with TestClient(app) as client:
            assert client.get(live).status_code == 200
            assert client.get("/health/ready").status_code == 503
