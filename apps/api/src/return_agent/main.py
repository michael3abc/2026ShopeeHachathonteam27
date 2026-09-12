import os
import asyncio
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from return_agent_contracts.public import CaseDetail, CreateCaseRequest, CreateCaseResponse, SendMessageRequest

from .cases import CaseNotFound, CaseStateConflict, CaseStore, MissingEvidence
from .db import make_engine, make_sessions
from .settings import Settings
from .capabilities import CapabilityNotFound, CapabilityStore
from .internal import internal_router
from return_agent_contracts.providers import ContractConflict, ProviderUnavailable


def create_app(settings: Settings | None = None, *, store: CaseStore | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = None
    if store is None and settings.profile == "integrated-demo":
        engine = make_engine(settings)
        store = CaseStore(make_sessions(engine))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(title="退貨案件 API", version="0.1.0", lifespan=lifespan)
    app.include_router(internal_router(settings, CapabilityStore(store) if store else None))

    def case_store() -> CaseStore:
        if store is None:
            raise HTTPException(503, "Case persistence is not configured")
        return store

    @app.exception_handler(CaseNotFound)
    async def not_found(request: Request, exc: CaseNotFound):
        return JSONResponse(status_code=404, content={"detail": "Case not found"})

    @app.exception_handler(CaseStateConflict)
    async def conflict(request: Request, exc: CaseStateConflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MissingEvidence)
    async def missing_evidence(request: Request, exc: MissingEvidence):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "Case persistence is unavailable"})

    @app.exception_handler(CapabilityNotFound)
    async def capability_not_found(request: Request, exc: CapabilityNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ContractConflict)
    async def contract_conflict(request: Request, exc: ContractConflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderUnavailable)
    async def provider_unavailable(request: Request, exc: ProviderUnavailable):
        return JSONResponse(status_code=503, content={"detail": "Provider is unavailable"})

    @app.exception_handler(ValueError)
    async def invalid_semantics(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": "Input failed semantic validation"})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        raise HTTPException(503, "API composition is not configured")

    @app.post("/cases", status_code=201, response_model=CreateCaseResponse)
    def create_case(body: CreateCaseRequest) -> CreateCaseResponse:
        return CreateCaseResponse(case_ref=case_store().create(body))

    @app.get("/cases/{case_ref}", response_model=CaseDetail)
    def get_case(case_ref: str) -> CaseDetail:
        return case_store().detail(case_ref)

    @app.post("/cases/{case_ref}/messages", response_model=CaseDetail)
    def message(case_ref: str, body: SendMessageRequest) -> CaseDetail:
        return case_store().message(case_ref, body)

    @app.get("/cases/{case_ref}/events")
    async def case_events(case_ref: str, request: Request) -> StreamingResponse:
        service = case_store()
        await asyncio.to_thread(service.detail, case_ref)
        header = request.headers.get("Last-Event-ID")
        if header is not None and (not header.isascii() or not header.isdigit()):
            raise HTTPException(400, "Invalid event cursor")
        cursor = int(header) if header is not None else 0

        async def stream():
            nonlocal cursor
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                batch = await asyncio.to_thread(service.events, case_ref, cursor)
                for event in batch:
                    cursor = event.seq
                    yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
                if batch:
                    continue
                detail = await asyncio.to_thread(service.detail, case_ref)
                if detail.status in ("RESOLVED", "ESCALATED"):
                    # Query once more after observing the committed terminal state.
                    tail = await asyncio.to_thread(service.events, case_ref, cursor)
                    for event in tail:
                        cursor = event.seq
                        yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
                    return
                if time.monotonic() - heartbeat >= settings.sse_heartbeat_seconds:
                    yield ": keep-alive\n\n"
                    heartbeat = time.monotonic()
                await asyncio.sleep(settings.sse_poll_seconds)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def main() -> None:
    uvicorn.run(create_app(), host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", "8000")))
