"""Durable, scope-bound Operational Memory storage for Louis's capability layer."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError
from return_agent_contracts.base import NonEmptyText, OpaqueRef, PositiveInt
from return_agent_contracts.enums import ClaimId, MemoryStatus, ReasonCode
from return_agent_contracts.interfaces import OperationalMemoryStore
from return_agent_contracts.models import (
    MEMORY_SUMMARY_VERSION,
    ApprovedMemory,
    MemoryCandidate,
    MemoryScope,
    MemorySearchHit,
)
from return_agent_contracts.transport import QueryApprovedMemoryParams
from return_agent_contracts.validation import (
    ContractInvariantError,
    validate_memory_candidate,
    validate_memory_summary,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.embeddings import (
    POLICY_EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    validate_embedding,
)
from return_agent.capabilities.policy import _cosine_distance
from return_agent.db.models import (
    OperationalMemoryEventRecord,
    OperationalMemoryRecord,
)

_CLAIM_REGISTRY_VERSION = re.compile(
    r"^claim-registry:(?P<major>[1-9][0-9]*)(?:\.[0-9]+)*$"
)


class OperationalMemoryCandidateError(ValueError):
    """Raised when a submission cannot satisfy the existing MemoryCandidate DTO."""


class OperationalMemoryQueryError(ValueError):
    """Raised when an approved-memory query cannot satisfy its existing DTO."""


class OperationalMemoryConflictError(ValueError):
    """Raised when a memory ID is retried with a changed candidate payload."""


class OperationalMemoryDataIntegrityError(RuntimeError):
    """Raised when stored memory cannot be projected to the public DTO."""


class OperationalMemoryNotFoundError(LookupError):
    """Raised when a governance transition names an unknown memory."""


class OperationalMemoryLifecycleError(ValueError):
    """Raised for a transition outside CANDIDATE -> APPROVED -> RETIRED."""


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_hash(candidate: MemoryCandidate) -> str:
    return _canonical_hash(candidate.model_dump(mode="json"))


def _submission_ref(memory_id: str) -> str:
    return f"memory-submission:{memory_id}"


def _as_utc(timestamp: datetime) -> datetime:
    """Normalise SQLite timestamps while preserving PostgreSQL TIMESTAMPTZ values."""

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _string_values(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


def _registry_major(version: str) -> int | None:
    match = _CLAIM_REGISTRY_VERSION.fullmatch(version)
    return int(match.group("major")) if match is not None else None


def _to_approved_memory(record: OperationalMemoryRecord) -> ApprovedMemory:
    if record.status != MemoryStatus.APPROVED.value or record.approved_at is None:
        raise OperationalMemoryDataIntegrityError(
            f"memory {record.memory_id} is not an approved record"
        )
    try:
        return ApprovedMemory(
            memory_id=record.memory_id,
            retrieval_summary=record.retrieval_summary,
            status=MemoryStatus.APPROVED,
            recommended_behavior=record.recommended_behavior,
            trigger_conditions=list(record.trigger_conditions),
            policy_version=record.policy_version,
            claim_registry_version=record.claim_registry_version,
            scope=MemoryScope(
                market=record.scope_market,
                reason_codes=list(_string_values(record.scope_reason_codes)),
                claim_ids=list(_string_values(record.scope_claim_ids)),
                categories=list(_string_values(record.scope_categories)),
            ),
            confidence=record.confidence,
            approved_at=_as_utc(record.approved_at),
        )
    except (TypeError, ValidationError, ValueError) as error:
        raise OperationalMemoryDataIntegrityError(
            f"memory {record.memory_id} violates the ApprovedMemory contract"
        ) from error


class SqlAlchemyOperationalMemoryStore(OperationalMemoryStore):
    """Submit candidates and retrieve only approved, currently compatible memory."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        if embedding_provider.dimensions != POLICY_EMBEDDING_DIMENSIONS:
            raise ValueError("memory embeddings require 1536 dimensions")
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    def submit_candidate(self, candidate: MemoryCandidate) -> OpaqueRef:
        """Persist a Yoyo-validated candidate, idempotently by memory ID."""

        try:
            validated_candidate = MemoryCandidate.model_validate(candidate)
            validate_memory_candidate(validated_candidate)
        except (ValidationError, ContractInvariantError) as error:
            raise OperationalMemoryCandidateError(
                "candidate violates the MemoryCandidate contract"
            ) from error

        payload_hash = _candidate_hash(validated_candidate)
        submission_ref = _submission_ref(validated_candidate.memory_id)
        with self._session_factory() as session:
            existing = session.get(
                OperationalMemoryRecord, validated_candidate.memory_id
            )
            if existing is not None:
                self._ensure_idempotent(existing, payload_hash)
                return existing.submission_ref
        # External I/O is outside the insert transaction. A failed embedding
        # cannot leave a partial candidate; the second lookup handles races.
        vector = validate_embedding(
            self._embedding_provider.embed(validated_candidate.retrieval_summary),
            dimensions=self._embedding_provider.dimensions,
        )
        submitted_at = _now_utc()
        try:
            with self._session_factory.begin() as session:
                existing = session.get(
                    OperationalMemoryRecord, validated_candidate.memory_id
                )
                if existing is not None:
                    self._ensure_idempotent(existing, payload_hash)
                    return existing.submission_ref

                session.add(
                    OperationalMemoryRecord(
                        memory_id=validated_candidate.memory_id,
                        submission_ref=submission_ref,
                        candidate_payload_hash=payload_hash,
                        retrieval_summary=validated_candidate.retrieval_summary,
                        summary_version=MEMORY_SUMMARY_VERSION,
                        summary_hash=_canonical_hash(
                            validated_candidate.retrieval_summary
                        ),
                        embedding_model=self._embedding_provider.model_name,
                        embedding=vector,
                        trigger_conditions=list(validated_candidate.trigger_conditions),
                        recommended_behavior=validated_candidate.recommended_behavior,
                        rationale=validated_candidate.rationale,
                        source_case_refs=list(validated_candidate.source_case_refs),
                        source_revision_event_refs=list(
                            validated_candidate.source_revision_event_refs
                        ),
                        policy_version=validated_candidate.policy_version,
                        claim_registry_version=validated_candidate.claim_registry_version,
                        scope_market=validated_candidate.scope.market,
                        scope_reason_codes=[
                            reason_code.value
                            for reason_code in validated_candidate.scope.reason_codes
                        ],
                        scope_claim_ids=[
                            claim_id.value
                            for claim_id in validated_candidate.scope.claim_ids
                        ],
                        scope_categories=list(validated_candidate.scope.categories),
                        confidence=validated_candidate.confidence,
                        status=MemoryStatus.CANDIDATE.value,
                        submitted_at=submitted_at,
                    )
                )
                session.flush()
                return submission_ref
        except IntegrityError:
            # A concurrent submit is still idempotent once the unique key commits.
            with self._session_factory() as session:
                existing = session.get(
                    OperationalMemoryRecord, validated_candidate.memory_id
                )
            if existing is not None:
                self._ensure_idempotent(existing, payload_hash)
                return existing.submission_ref
            raise

    def query_approved(
        self,
        query_summary: NonEmptyText,
        market: NonEmptyText,
        reason_code: ReasonCode,
        required_claim_ids: Sequence[ClaimId],
        categories: Sequence[OpaqueRef],
        policy_versions: Sequence[OpaqueRef],
        claim_registry_major: PositiveInt,
        top_k: PositiveInt = 3,
    ) -> Sequence[MemorySearchHit]:
        """Filter approved scope first, then rank by exact cosine similarity."""

        try:
            query = QueryApprovedMemoryParams.model_validate(
                {
                    "query_summary": query_summary,
                    "market": market,
                    "reason_code": reason_code,
                    "required_claim_ids": list(required_claim_ids),
                    "categories": list(categories),
                    "policy_versions": list(policy_versions),
                    "claim_registry_major": claim_registry_major,
                    "top_k": top_k,
                }
            )
        except (TypeError, ValidationError) as error:
            raise OperationalMemoryQueryError(
                "approved-memory query violates the existing DTO contract"
            ) from error

        validate_memory_summary(query.query_summary)
        with self._session_factory() as session:
            records = session.scalars(
                select(OperationalMemoryRecord).where(
                    OperationalMemoryRecord.status == MemoryStatus.APPROVED.value,
                    OperationalMemoryRecord.scope_market == query.market,
                    OperationalMemoryRecord.policy_version.in_(query.policy_versions),
                )
            ).all()

        matching = [record for record in records if self._matches_query(record, query)]
        if not matching:
            return []
        for record in matching:
            if (
                record.embedding is None
                or not record.retrieval_summary
                or not record.summary_version
                or record.summary_hash != _canonical_hash(record.retrieval_summary)
                or record.embedding_model != self._embedding_provider.model_name
            ):
                raise OperationalMemoryDataIntegrityError(
                    "memory vector is missing, stale or uses another model; run memory backfill"
                )
            validate_embedding(
                record.embedding, dimensions=self._embedding_provider.dimensions
            )
        vector = validate_embedding(
            self._embedding_provider.embed(query.query_summary),
            dimensions=self._embedding_provider.dimensions,
        )
        # Recheck visibility after external I/O to exclude concurrent retirement.
        with self._session_factory() as session:
            eligible = select(OperationalMemoryRecord).where(
                OperationalMemoryRecord.memory_id.in_([r.memory_id for r in matching]),
                OperationalMemoryRecord.status == MemoryStatus.APPROVED.value,
                OperationalMemoryRecord.embedding_model
                == self._embedding_provider.model_name,
            )
            if session.get_bind().dialect.name == "postgresql":
                distance = OperationalMemoryRecord.embedding.cosine_distance(vector)
                ranked = session.execute(
                    eligible.add_columns(distance)
                    .order_by(
                        distance,
                        OperationalMemoryRecord.confidence.desc(),
                        OperationalMemoryRecord.approved_at.desc(),
                        OperationalMemoryRecord.memory_id,
                    )
                    .limit(query.top_k)
                ).all()
            else:
                # SQLite is the explicit test backend; production ranking is SQL.
                ranked = [
                    (r, _cosine_distance(vector, r.embedding))
                    for r in session.scalars(eligible).all()
                ]
                ranked.sort(
                    key=lambda pair: (
                        pair[1],
                        -pair[0].confidence,
                        -_as_utc(pair[0].approved_at).timestamp(),
                        pair[0].memory_id,
                    )
                )
                ranked = ranked[: query.top_k]
            return [
                MemorySearchHit(
                    memory=_to_approved_memory(record),
                    similarity=max(-1.0, min(1.0, 1.0 - float(distance))),
                )
                for record, distance in ranked
            ]

    @staticmethod
    def _ensure_idempotent(
        record: OperationalMemoryRecord,
        candidate_payload_hash: str,
    ) -> None:
        if record.candidate_payload_hash != candidate_payload_hash:
            raise OperationalMemoryConflictError(
                "memory_id is already associated with a different candidate payload"
            )

    @staticmethod
    def _matches_query(
        record: OperationalMemoryRecord,
        query: QueryApprovedMemoryParams,
    ) -> bool:
        reason_codes = _string_values(record.scope_reason_codes)
        if reason_codes and query.reason_code.value not in reason_codes:
            return False

        scope_claim_ids = set(_string_values(record.scope_claim_ids))
        required_claim_ids = {claim_id.value for claim_id in query.required_claim_ids}
        if scope_claim_ids and not scope_claim_ids.intersection(required_claim_ids):
            return False

        scope_categories = set(_string_values(record.scope_categories))
        if scope_categories and not scope_categories.intersection(query.categories):
            return False

        return (
            _registry_major(record.claim_registry_version) == query.claim_registry_major
        )


class OperationalMemoryGovernanceService:
    """Trusted approval/retirement transitions, intentionally outside Agent contracts."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def approve(
        self,
        memory_id: OpaqueRef,
    ) -> ApprovedMemory:
        """Promote a candidate after an external governance decision."""

        with self._session_factory.begin() as session:
            record = self._locked_memory(session, memory_id)
            self._require_status(record, MemoryStatus.CANDIDATE, MemoryStatus.APPROVED)
            timestamp = _now_utc()
            self._require_not_before(
                timestamp,
                record.submitted_at,
                transition=MemoryStatus.APPROVED,
            )
            record.status = MemoryStatus.APPROVED.value
            record.approved_at = timestamp
            session.add(
                OperationalMemoryEventRecord(
                    event_id=f"memory-event:{uuid4()}",
                    memory_id=record.memory_id,
                    event_type=MemoryStatus.APPROVED.value,
                    from_status=MemoryStatus.CANDIDATE.value,
                    to_status=MemoryStatus.APPROVED.value,
                    occurred_at=timestamp,
                )
            )
            return _to_approved_memory(record)

    def retire(
        self,
        memory_id: OpaqueRef,
    ) -> None:
        """Retire an approved memory after an external governance decision."""

        with self._session_factory.begin() as session:
            record = self._locked_memory(session, memory_id)
            self._require_status(record, MemoryStatus.APPROVED, MemoryStatus.RETIRED)
            if record.approved_at is None:
                raise OperationalMemoryDataIntegrityError(
                    f"approved memory {record.memory_id} has no approval timestamp"
                )
            timestamp = _now_utc()
            self._require_not_before(
                timestamp,
                record.approved_at,
                transition=MemoryStatus.RETIRED,
            )
            record.status = MemoryStatus.RETIRED.value
            record.retired_at = timestamp
            session.add(
                OperationalMemoryEventRecord(
                    event_id=f"memory-event:{uuid4()}",
                    memory_id=record.memory_id,
                    event_type=MemoryStatus.RETIRED.value,
                    from_status=MemoryStatus.APPROVED.value,
                    to_status=MemoryStatus.RETIRED.value,
                    occurred_at=timestamp,
                )
            )

    @staticmethod
    def _locked_memory(session: Session, memory_id: str) -> OperationalMemoryRecord:
        record = session.scalar(
            select(OperationalMemoryRecord)
            .where(OperationalMemoryRecord.memory_id == memory_id)
            .with_for_update()
        )
        if record is None:
            raise OperationalMemoryNotFoundError(f"unknown memory: {memory_id}")
        return record

    @staticmethod
    def _require_status(
        record: OperationalMemoryRecord,
        expected: MemoryStatus,
        target: MemoryStatus,
    ) -> None:
        if record.status != expected.value:
            raise OperationalMemoryLifecycleError(
                f"cannot transition {record.status} memory to {target.value}"
            )

    @staticmethod
    def _require_not_before(
        timestamp: datetime,
        previous_timestamp: datetime,
        *,
        transition: MemoryStatus,
    ) -> None:
        if _as_utc(timestamp) < _as_utc(previous_timestamp):
            raise OperationalMemoryLifecycleError(
                f"{transition.value} timestamp precedes the prior lifecycle event"
            )
