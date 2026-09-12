"""FastAPI boundary for cases, Agent commands, and UI events."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from return_agent_contracts.enums import UserRole
from return_agent_contracts.models import UserTurn
from return_agent_contracts.runtime import (
    ClarificationResume,
    EvidenceResume,
    GraphNodeName,
    HumanReviewPollResume,
)
from return_agent_contracts.service import AgentResumeCommand, AgentStartCommand
from return_agent_contracts.transport import (
    FetchHumanReviewRequest,
    FetchHumanReviewResponse,
    LoadCaseContextRequest,
    LoadCaseContextResponse,
    QueryApprovedMemoryRequest,
    QueryApprovedMemoryResponse,
    ResolveEvidenceRequest,
    ResolveEvidenceResponse,
    RetrievePolicyRequest,
    RetrievePolicyResponse,
    SubmitHumanReviewRequest,
    SubmitHumanReviewResponse,
    SubmitMemoryCandidateRequest,
    SubmitMemoryCandidateResponse,
    VerifyHandoffRequest,
    VerifyHandoffResponse,
)
from return_agent_contracts.ui import (
    CaseDetail,
    CaseStatus,
    CreateCaseRequest,
    CreateCaseResponse,
    ReviewDecision,
    SendMessageRequest,
)
from sqlalchemy.orm import Session

from .agent_bridge import AgentBridge, AgentBridgeSettings
from .agent_commands import AgentCommandOutbox, SqlAlchemyAgentCommandOutbox
from .capabilities.embeddings import embedding_provider_from_env
from .capabilities.human_review import (
    HumanReviewConflictError,
    HumanReviewNotFoundError,
    SqlAlchemyHumanReviewProvider,
)
from .capabilities.integration import (
    IntegratedProviderBundle,
    compose_integrated_demo_providers,
)
from .capabilities.safety import (
    SafetyConflictError,
    SafetyDataIntegrityError,
    SafetyProviders,
)
from .db.case import append_agent_event
from .db.session import create_session_factory
from .sse import CaseEventStream, EventStreamSettings
from .store import (
    CaseNotFoundError,
    CaseStore,
    IllegalTransitionError,
    to_case_detail,
)
from .http_dependencies import get_session, require_internal_service
from .attachments import router as attachment_router, ImageRequestLimitMiddleware


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    _configure_integrated_demo(application)
    provider_bundle: IntegratedProviderBundle | None = application.state.provider_bundle
    bridge = AgentBridge.from_settings(
        application.state.session_factory,
        AgentBridgeSettings.from_env(),
        refund_execution_provider=(
            provider_bundle.refund_execution_provider if provider_bundle else None
        ),
    )
    application.state.agent_command_outbox = SqlAlchemyAgentCommandOutbox()
    application.state.agent_bridge = bridge
    bridge.start()
    from redis.asyncio import Redis

    from .activity_bridge import ActivityBridge
    activity_redis = Redis.from_url(AgentBridgeSettings.from_env().redis_url, decode_responses=True)
    activity_bridge = ActivityBridge(application.state.session_factory, activity_redis)
    activity_task = asyncio.create_task(activity_bridge.run_forever(), name="activity-api")
    try:
        yield
    finally:
        activity_task.cancel()
        await asyncio.gather(activity_task, return_exceptions=True)
        await activity_redis.aclose()
        await bridge.close()


app = FastAPI(title="Adaptive Return Resolution API", lifespan=lifespan)
from .activities import router as activity_router

app.include_router(activity_router)
app.include_router(attachment_router)
app.add_middleware(ImageRequestLimitMiddleware)

# The Next.js dev server is a separate origin, so the browser needs this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creating the factory does not open a connection, so importing this module
# stays safe without a database.
app.state.session_factory = create_session_factory()
app.state.agent_command_outbox = SqlAlchemyAgentCommandOutbox()
app.state.agent_bridge = None
app.state.event_stream_settings = EventStreamSettings()
app.state.safety_providers = None
app.state.provider_bundle = None
app.state.internal_service_token = None


def _secret_from_env(value_name: str, file_name: str) -> str | None:
    value = os.environ.get(value_name)
    path = os.environ.get(file_name)
    if not value and path:
        value = Path(path).read_text(encoding="utf-8").strip()
    return value


def _configure_integrated_demo(application: FastAPI) -> None:
    application.state.internal_service_token = _secret_from_env(
        "RETURN_AGENT_INTERNAL_SERVICE_TOKEN",
        "RETURN_AGENT_INTERNAL_SERVICE_TOKEN_FILE",
    )
    if os.environ.get("RETURN_AGENT_API_PROFILE", "unconfigured") != (
        "integrated-demo"
    ):
        return
    bundle = compose_integrated_demo_providers(
        session_factory=application.state.session_factory,
        embedding_provider=embedding_provider_from_env(),
        data_dir=Path(os.environ.get("RETURN_AGENT_DEMO_DATA_DIR", "data")),
    )
    application.state.provider_bundle = bundle
    application.state.safety_providers = bundle.safety_providers


def get_store(session: Annotated[Session, Depends(get_session)]) -> CaseStore:
    return CaseStore(session)


def get_command_outbox(request: Request) -> AgentCommandOutbox:
    outbox = request.app.state.agent_command_outbox
    if outbox is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent command outbox is not configured",
        )
    return outbox


def get_safety_providers(request: Request) -> SafetyProviders:
    providers = request.app.state.safety_providers
    if providers is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Safety providers are not configured",
        )
    return providers


def get_provider_bundle(request: Request) -> IntegratedProviderBundle:
    providers = request.app.state.provider_bundle
    if providers is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent Provider boundary is not configured",
        )
    return providers


def _not_found(case_ref: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"unknown case {case_ref}")


@app.get("/health")
def health() -> dict[str, str]:
    """Report process health without querying another owner's data."""

    return {"status": "ok"}


@app.post("/internal/v1/verification")
def verify_handoff(
    request: VerifyHandoffRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[SafetyProviders, Depends(get_safety_providers)],
) -> VerifyHandoffResponse:
    try:
        return VerifyHandoffResponse(
            result=providers.verification_provider.verify(request.params.handoff)
        )
    except SafetyConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except SafetyDataIntegrityError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Verification persistence is unavailable",
        ) from error


@app.post("/internal/v1/case-context")
def load_case_context(
    request: LoadCaseContextRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> LoadCaseContextResponse:
    try:
        return LoadCaseContextResponse(
            result=providers.case_context_provider.load_case_context(
                request.params.case_ref
            )
        )
    except LookupError as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Case context not found"
        ) from error


@app.post("/internal/v1/policy")
def retrieve_policy(
    request: RetrievePolicyRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> RetrievePolicyResponse:
    params = request.params
    return RetrievePolicyResponse(
        result=providers.policy_provider.retrieve_policy(
            params.case_context,
            params.order_snapshot,
            params.reason_code,
            params.claimed_line_item_ids,
        )
    )


@app.post("/internal/v1/memory/query")
def query_approved_memory(
    request: QueryApprovedMemoryRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> QueryApprovedMemoryResponse:
    params = request.params
    return QueryApprovedMemoryResponse(
        result=list(
            providers.operational_memory_store.query_approved(
                query_summary=params.query_summary,
                market=params.market,
                reason_code=params.reason_code,
                required_claim_ids=params.required_claim_ids,
                categories=params.categories,
                policy_versions=params.policy_versions,
                claim_registry_major=params.claim_registry_major,
                top_k=params.top_k,
            )
        )
    )


@app.post("/internal/v1/memory/candidates")
def submit_memory_candidate(
    request: SubmitMemoryCandidateRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> SubmitMemoryCandidateResponse:
    return SubmitMemoryCandidateResponse(
        result=providers.operational_memory_store.submit_candidate(
            request.params.candidate
        )
    )


@app.post("/internal/v1/evidence/resolve")
def resolve_evidence(
    request: ResolveEvidenceRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> ResolveEvidenceResponse:
    try:
        return ResolveEvidenceResponse(
            result=providers.evidence_provider.resolve(request.params.artifact_ref)
        )
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found") from error


@app.post("/internal/v1/human-reviews")
def submit_human_review(
    request: SubmitHumanReviewRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> SubmitHumanReviewResponse:
    return SubmitHumanReviewResponse(
        result=providers.human_review_provider.submit_for_review(
            request.params.handoff,
            request.params.review,
            request.params.dossier,
        )
    )


@app.post("/internal/v1/human-reviews/result")
def fetch_human_review_result(
    request: FetchHumanReviewRequest,
    _authorization: Annotated[None, Depends(require_internal_service)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> FetchHumanReviewResponse:
    try:
        result = providers.human_review_provider.fetch_result(request.params.review_ref)
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found") from error
    return FetchHumanReviewResponse(result=result)


@app.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(
    request: CreateCaseRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[CaseStore, Depends(get_store)],
) -> CreateCaseResponse:
    outbox = get_command_outbox(http_request)
    case = store.create(request)
    from .attachments import bind_attachments
    bind_attachments(session, case, request.attached_artifact_refs)
    initial_turn = _user_turn(request.initial_message, request.attached_artifact_refs)
    outbox.enqueue(
        session,
        AgentStartCommand(
            command_type="START",
            command_id=f"COMMAND-{uuid4().hex.upper()}",
            case_ref=case.case_ref,
            thread_id=case.thread_id,
            issued_at=datetime.now(UTC),
            payload={"order_ref": request.order_ref, "initial_turn": initial_turn},
        ),
    )
    session.commit()
    return CreateCaseResponse(case_ref=case.case_ref)


@app.get("/cases/{case_ref}")
def get_case(
    case_ref: str,
    store: Annotated[CaseStore, Depends(get_store)],
) -> CaseDetail:
    try:
        return to_case_detail(store, store.get(case_ref))
    except CaseNotFoundError:
        raise _not_found(case_ref) from None


@app.post("/cases/{case_ref}/messages")
def send_message(
    case_ref: str,
    request: SendMessageRequest,
    http_request: Request,
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[CaseStore, Depends(get_store)],
) -> CaseDetail:
    try:
        case = store.lock(case_ref)
        outbox = get_command_outbox(http_request)
        current = CaseStatus(case.status)
        if current is CaseStatus.AWAITING_CLARIFICATION:
            resume_node = GraphNodeName.REQUEST_CLARIFICATION
            payload = ClarificationResume(
                kind="CLARIFICATION",
                turn=_user_turn(request.message, request.attached_artifact_refs),
            )
        elif current is CaseStatus.AWAITING_EVIDENCE:
            resume_node = GraphNodeName.REQUEST_EVIDENCE
            if not request.attached_artifact_refs:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "evidence resume requires at least one attached artifact",
                )
            payload = EvidenceResume(
                kind="EVIDENCE_REQUEST",
                artifact_refs=request.attached_artifact_refs,
            )
        else:
            raise IllegalTransitionError(
                f"case {case_ref} cannot accept a message while {current.value}"
            )

        from .attachments import bind_attachments
        bind_attachments(session, case, request.attached_artifact_refs)
        store.append_turn(case_ref, request)
        case = store.transition(case_ref, CaseStatus.OBSERVING)
        append_agent_event(
            session,
            case_ref,
            {
                "type": "state_change",
                "ts": datetime.now(UTC),
                "node": resume_node,
                "payload": {
                    "from_status": current,
                    "to_status": CaseStatus.OBSERVING,
                    "reason": "User supplied the requested Agent input.",
                },
            },
        )
        outbox.enqueue(
            session,
            AgentResumeCommand(
                command_type="RESUME",
                command_id=f"COMMAND-{uuid4().hex.upper()}",
                case_ref=case.case_ref,
                thread_id=case.thread_id,
                issued_at=datetime.now(UTC),
                payload={"resume": payload},
            ),
        )
        session.commit()
        return to_case_detail(store, case)
    except CaseNotFoundError:
        raise _not_found(case_ref) from None
    except IllegalTransitionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None


@app.post("/cases/{case_ref}/review")
def complete_human_review(
    case_ref: str,
    request: ReviewDecision,
    http_request: Request,
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[CaseStore, Depends(get_store)],
    providers: Annotated[IntegratedProviderBundle, Depends(get_provider_bundle)],
) -> CaseDetail:
    try:
        case = store.lock(case_ref)
        if CaseStatus(case.status) is not CaseStatus.AWAITING_HUMAN_REVIEW:
            raise IllegalTransitionError(
                f"case {case_ref} is not awaiting Human Review"
            )
        human_provider = providers.human_review_provider
        if not isinstance(human_provider, SqlAlchemyHumanReviewProvider):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Human Review completion is not configured",
            )
        human_provider.complete_for_case(
            session,
            case_ref=case_ref,
            decision=request,
        )
        outbox = get_command_outbox(http_request)
        current = CaseStatus(case.status)
        case = store.transition(case_ref, CaseStatus.OBSERVING)
        append_agent_event(
            session,
            case_ref,
            {
                "type": "state_change",
                "ts": datetime.now(UTC),
                "node": GraphNodeName.AWAIT_HUMAN_REVIEW,
                "payload": {
                    "from_status": current,
                    "to_status": CaseStatus.OBSERVING,
                    "reason": "Human Review supplied a final result.",
                },
            },
        )
        outbox.enqueue(
            session,
            AgentResumeCommand(
                command_type="RESUME",
                command_id=f"COMMAND-{uuid4().hex.upper()}",
                case_ref=case.case_ref,
                thread_id=case.thread_id,
                issued_at=datetime.now(UTC),
                payload={"resume": HumanReviewPollResume(kind="HUMAN_REVIEW")},
            ),
        )
        session.commit()
        return to_case_detail(store, case)
    except CaseNotFoundError:
        raise _not_found(case_ref) from None
    except HumanReviewNotFoundError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except (HumanReviewConflictError, IllegalTransitionError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None


@app.get("/cases/{case_ref}/events")
def stream_case_events(
    case_ref: str,
    request: Request,
    store: Annotated[CaseStore, Depends(get_store)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        store.get(case_ref)
    except CaseNotFoundError:
        raise _not_found(case_ref) from None
    after_seq = _parse_last_event_id(last_event_id)
    event_stream = CaseEventStream(
        request.app.state.session_factory,
        request.app.state.event_stream_settings,
    )
    return StreamingResponse(
        event_stream.iterate(request, case_ref=case_ref, after_seq=after_seq),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _user_turn(message: str, artifact_refs: list[str] | None = None) -> UserTurn:
    return UserTurn(
        turn_id=f"TURN-{uuid4().hex.upper()}",
        role=UserRole.USER,
        text=message,
        attached_artifact_refs=artifact_refs or [],
        received_at=datetime.now(UTC),
    )


def _parse_last_event_id(value: str | None) -> int:
    if value is None:
        return 0
    try:
        parsed = int(value)
    except ValueError:
        parsed = -1
    if parsed < 0 or str(parsed) != value.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Last-Event-ID must be a non-negative integer",
        )
    return parsed
