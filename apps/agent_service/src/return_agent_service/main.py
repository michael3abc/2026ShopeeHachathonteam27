import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from .settings import Settings
from .composition import AgentComposition


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    composition = None
    @asynccontextmanager
    async def lifespan(app):
        nonlocal composition
        if settings.profile != "unconfigured":
            composition = AgentComposition(settings)
            composition.start()
        yield
        if composition:
            await asyncio.to_thread(composition.close)
    app = FastAPI(title="退貨案件 Agent Service", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        if composition is None or not composition.ready():
            raise HTTPException(503, "Durable workers are not ready")
        return {"status": "ready", "profile": settings.profile}

    return app


def main() -> None:
    uvicorn.run(create_app(), host=os.getenv("AGENT_HOST", "127.0.0.1"), port=int(os.getenv("AGENT_PORT", "8090")))
