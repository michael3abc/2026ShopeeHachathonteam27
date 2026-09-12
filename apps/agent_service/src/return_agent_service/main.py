import os

import uvicorn
from fastapi import FastAPI, HTTPException


def create_app() -> FastAPI:
    app = FastAPI(title="退貨案件 Agent Service", version="0.1.0")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        raise HTTPException(503, "Durable workers are not configured")

    return app


def main() -> None:
    uvicorn.run(create_app(), host=os.getenv("AGENT_HOST", "127.0.0.1"), port=int(os.getenv("AGENT_PORT", "8090")))
