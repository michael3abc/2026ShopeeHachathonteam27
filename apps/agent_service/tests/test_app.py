from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from return_agent_service.app import create_health_app


class IdleWorker:
    async def run_forever(self, stop: asyncio.Event) -> None:
        await stop.wait()


class HealthyBroker:
    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_health_endpoints_report_worker_and_broker_readiness() -> None:
    app = create_health_app(worker=IdleWorker(), broker=HealthyBroker())
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
