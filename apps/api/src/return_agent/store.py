"""Backend-owned case lifecycle: the CaseStatus machine and its persistence.

This is the canonical record of where a case stands. It is deliberately not
a copy of the Agent graph working state: the graph owns its counters and
snapshots and resumes from its own checkpointer.

The status machine lives here rather than in the database because a CHECK
constraint can only reject an invalid status, not an invalid *transition* —
that needs the previous value, which is application knowledge.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import TypeAdapter
from return_agent_contracts.adapters import to_human_review_payload
from return_agent_contracts.models import (
    ClarificationRequest,
    HumanReviewDossier,
    HumanReviewResult,
    ProposedDecisionHandoff,
    ReviewResult,
)
from return_agent_contracts.ui import (
    CaseDetail,
    CaseStatus,
    CreateCaseRequest,
    EvidenceRequestView,
    HumanReviewPayload,
    InterruptEvent,
    SendMessageRequest,
    UIEventType,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.case import AGENT_EVENT, USER_TURN, CaseEventRecord, CaseRecord, append_event
from .db.models import HumanReviewRecord

# Terminal statuses have no outgoing transitions; every other edge is one the
# graph runner drives. AWAITING_* -> OBSERVING is the resume edge.
ALLOWED_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.OBSERVING: frozenset(
        {
            CaseStatus.AWAITING_CLARIFICATION,
            CaseStatus.AWAITING_EVIDENCE,
            CaseStatus.AWAITING_HUMAN_REVIEW,
            CaseStatus.EXECUTING,
            CaseStatus.ESCALATED,
        }
    ),
    CaseStatus.AWAITING_CLARIFICATION: frozenset(
        {CaseStatus.OBSERVING, CaseStatus.ESCALATED}
    ),
    CaseStatus.AWAITING_EVIDENCE: frozenset(
        {CaseStatus.OBSERVING, CaseStatus.ESCALATED}
    ),
    CaseStatus.AWAITING_HUMAN_REVIEW: frozenset(
        {CaseStatus.OBSERVING, CaseStatus.EXECUTING, CaseStatus.ESCALATED}
    ),
    CaseStatus.EXECUTING: frozenset({CaseStatus.RESOLVED, CaseStatus.ESCALATED}),
    CaseStatus.RESOLVED: frozenset(),
    CaseStatus.ESCALATED: frozenset(),
}

_INTERRUPT_EVENT = TypeAdapter(InterruptEvent)


class CaseNotFoundError(KeyError):
    """Raised when a case_ref has no stored case."""


class IllegalTransitionError(ValueError):
    """Raised when a status transition is not in ALLOWED_TRANSITIONS."""


class CaseStore:
    """Reads and writes the case tables through one request-scoped session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, request: CreateCaseRequest, *, turn_ref: str | None = None) -> CaseRecord:
        case = CaseRecord(
            case_ref=f"CASE-{uuid4().hex[:8].upper()}",
            # Backend-private and never reused; the UI only ever sees case_ref.
            thread_id=uuid4().hex,
            order_ref=request.order_ref,
            user_ref=request.user_ref,
            status=CaseStatus.OBSERVING.value,
        )
        self._session.add(case)
        self._session.flush()
        append_event(
            self._session,
            case.case_ref,
            {
                "message": request.initial_message,
                **({"turn_ref": turn_ref} if turn_ref else {}),
                "attached_artifact_refs": list(request.attached_artifact_refs),
            },
            kind=USER_TURN,
        )
        return case

    def get(self, case_ref: str) -> CaseRecord:
        case = self._session.get(CaseRecord, case_ref)
        if case is None:
            raise CaseNotFoundError(case_ref)
        return case

    def lock(self, case_ref: str) -> CaseRecord:
        case = self._session.scalar(
            select(CaseRecord)
            .where(CaseRecord.case_ref == case_ref)
            .with_for_update()
        )
        if case is None:
            raise CaseNotFoundError(case_ref)
        return case

    def append_turn(self, case_ref: str, request: SendMessageRequest, *, turn_ref: str | None = None) -> CaseRecord:
        case = self.lock(case_ref)
        if not ALLOWED_TRANSITIONS[CaseStatus(case.status)]:
            raise IllegalTransitionError(f"case {case_ref} is terminal ({case.status})")
        append_event(
            self._session,
            case_ref,
            {
                "message": request.message,
                **({"turn_ref": turn_ref} if turn_ref else {}),
                "attached_artifact_refs": list(request.attached_artifact_refs),
            },
            kind=USER_TURN,
        )
        return self._touch(case)

    def transition(
        self,
        case_ref: str,
        status: CaseStatus,
    ) -> CaseRecord:
        case = self.lock(case_ref)
        current = CaseStatus(case.status)
        if status not in ALLOWED_TRANSITIONS[current]:
            raise IllegalTransitionError(
                f"{current.value} -> {status.value} is not allowed"
            )
        case.status = status.value
        return self._touch(case)

    def latest_interrupt(self, case_ref: str) -> InterruptEvent | None:
        """The most recent interrupt event, or None if none was emitted.

        Pending interrupt payloads are derived from the transcript rather
        than stored a second time on the case row.
        """

        payloads = self._session.scalars(
            select(CaseEventRecord.payload)
            .where(
                CaseEventRecord.case_ref == case_ref,
                CaseEventRecord.kind == AGENT_EVENT,
            )
            .order_by(CaseEventRecord.seq.desc())
        )
        for payload in payloads:
            if payload.get("type") == UIEventType.INTERRUPT.value:
                return _INTERRUPT_EVENT.validate_python(payload)
        return None

    def _touch(self, case: CaseRecord) -> CaseRecord:
        case.updated_at = datetime.now(UTC)
        self._session.flush()
        return case

    def latest_human_review(self, case_ref: str) -> HumanReviewRecord | None:
        return self._session.scalar(
            select(HumanReviewRecord).where(HumanReviewRecord.case_ref == case_ref)
            .order_by(HumanReviewRecord.submitted_at.desc()).limit(1)
        )


def _as_utc(moment: datetime) -> datetime:
    """Attach UTC to a naive timestamp.

    Postgres hands back tz-aware values, but SQLite has no timezone type
    and returns naive ones. Every write here is UTC, so labelling is safe
    and keeps the contract's UTCDateTime validator satisfied on both.
    """

    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def to_case_detail(store: CaseStore, case: CaseRecord) -> CaseDetail:
    """Project a case row into the DTO the Demo/UI reads."""

    clarification_request: ClarificationRequest | None = None
    evidence_request: EvidenceRequestView | None = None
    human_review: HumanReviewPayload | None = None
    status = CaseStatus(case.status)
    record = store.latest_human_review(case.case_ref)
    interrupt = (
        store.latest_interrupt(case.case_ref)
        if status
        in (
            CaseStatus.AWAITING_CLARIFICATION,
            CaseStatus.AWAITING_EVIDENCE,
            CaseStatus.AWAITING_HUMAN_REVIEW,
        )
        or record is not None
        else None
    )
    if status in (
        CaseStatus.AWAITING_CLARIFICATION,
        CaseStatus.AWAITING_EVIDENCE,
        CaseStatus.AWAITING_HUMAN_REVIEW,
    ) and interrupt is not None:
        payload = interrupt.payload
        # A case only advertises the interrupt its status is waiting on.
        if status is CaseStatus.AWAITING_CLARIFICATION:
            clarification_request = getattr(payload, "request", None)
        elif status is CaseStatus.AWAITING_EVIDENCE:
            evidence_request = getattr(payload, "request", None)
        else:
            human_review = getattr(payload, "review", None)

    human_result = None
    if record is not None and record.dossier_payload is not None:
        dossier = HumanReviewDossier.model_validate(record.dossier_payload)
        memory_ids: list[str] = []
        if interrupt is not None:
            interrupt_review = getattr(interrupt.payload, "review", None)
            if (
                interrupt_review is not None
                and interrupt_review.handoff_id == record.handoff_id
            ):
                memory_ids = interrupt_review.memories_used
        human_review = to_human_review_payload(
            ProposedDecisionHandoff.model_validate(record.handoff_payload),
            TypeAdapter(ReviewResult).validate_python(record.review_payload),
            dossier.policy_bundle,
            memory_ids,
            dossier,
        )
        if record.result_payload is not None:
            human_result = TypeAdapter(HumanReviewResult).validate_python(record.result_payload)

    return CaseDetail(
        case_ref=case.case_ref,
        order_ref=case.order_ref,
        user_ref=case.user_ref,
        status=status,
        clarification_request=clarification_request,
        human_review=human_review,
        human_review_result=human_result,
        evidence_request=evidence_request,
        created_at=_as_utc(case.created_at),
        updated_at=_as_utc(case.updated_at),
    )
