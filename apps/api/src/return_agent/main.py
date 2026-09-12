import os

import uvicorn
from fastapi import FastAPI, HTTPException


def create_app() -> FastAPI:
    app = FastAPI(title="退貨案件 API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        raise HTTPException(503, "API composition is not configured")

    return app


def main() -> None:
    uvicorn.run(create_app(), host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", "8000")))
