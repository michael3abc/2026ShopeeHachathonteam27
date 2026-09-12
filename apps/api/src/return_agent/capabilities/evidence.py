"""Read-only evidence capability and idempotent metadata fixture import."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError, field_validator
from return_agent_contracts.base import (
    ContractModel,
    NonEmptyText,
    OpaqueRef,
    UTCDateTime,
)
from return_agent_contracts.enums import EvidenceSource, EvidenceType
from return_agent_contracts.interfaces import EvidenceProvider
from return_agent_contracts.models import EvidenceItem
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from return_agent.db.models import EvidenceRecord


class EvidenceArtifactNotFoundError(LookupError):
    """Raised when no neutral metadata exists for an artifact reference."""


class EvidenceDataIntegrityError(RuntimeError):
    """Raised when persisted metadata cannot satisfy the public DTO contract."""


class EvidenceSeedConflictError(ValueError):
    """Raised when an evidence ID or artifact reference is reused with new content."""


class EvidenceFixture(ContractModel):
    """Strict seed shape: metadata only, not artifacts or decision output."""

    evidence_id: OpaqueRef
    type: EvidenceType
    source: EvidenceSource
    subject: OpaqueRef
    artifact_ref: OpaqueRef
    extracted_summary: NonEmptyText
    collected_at: UTCDateTime

    @field_validator("extracted_summary")
    @classmethod
    def reject_embedded_artifact_data(cls, value: str) -> str:
        if "data:" in value.lower() or "base64," in value.lower():
            raise ValueError("extracted_summary must not contain artifact bytes")
        return value


def load_evidence_fixture(path: Path) -> list[EvidenceFixture]:
    """Parse a JSON list of strict, neutral evidence metadata records."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to read evidence fixture {path}") from error
    if not isinstance(payload, list):
        # The decoded JSON is syntactically valid but violates the fixture shape.
        raise ValueError("evidence fixture must be a JSON array")  # noqa: TRY004
    try:
        return [EvidenceFixture.model_validate(item) for item in payload]
    except ValidationError as error:
        raise ValueError("evidence fixture contains malformed metadata") from error


def _fixture_hash(evidence: EvidenceFixture) -> str:
    payload = evidence.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def upsert_evidence(session: Session, evidence: EvidenceFixture) -> bool:
    """Insert metadata once; reject identity reuse that would change evidence."""

    content_hash = _fixture_hash(evidence)
    existing_by_id = session.get(EvidenceRecord, evidence.evidence_id)
    existing_by_artifact = session.scalar(
        select(EvidenceRecord).where(
            EvidenceRecord.artifact_ref == evidence.artifact_ref
        )
    )

    for existing in (existing_by_id, existing_by_artifact):
        if existing is None:
            continue
        if (
            existing.evidence_id == evidence.evidence_id
            and existing.artifact_ref == evidence.artifact_ref
            and existing.content_hash == content_hash
        ):
            return False
        raise EvidenceSeedConflictError(
            "evidence_id or artifact_ref is already associated with different metadata"
        )

    session.add(
        EvidenceRecord(
            evidence_id=evidence.evidence_id,
            type=evidence.type.value,
            source=evidence.source.value,
            subject=evidence.subject,
            artifact_ref=evidence.artifact_ref,
            extracted_summary=evidence.extracted_summary,
            collected_at=evidence.collected_at,
            content_hash=content_hash,
        )
    )
    return True


def _as_utc(timestamp: datetime) -> datetime:
    """SQLite test storage loses TZ info; production PostgreSQL returns TIMESTAMPTZ."""

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


class SqlAlchemyEvidenceProvider(EvidenceProvider):
    """Resolve artifact references to neutral, contract-validated evidence metadata."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def resolve(self, artifact_ref: OpaqueRef) -> EvidenceItem:
        with self._session_factory() as session:
            record = session.scalar(
                select(EvidenceRecord).where(
                    EvidenceRecord.artifact_ref == artifact_ref
                )
            )
        if record is None:
            raise EvidenceArtifactNotFoundError(
                f"unknown evidence artifact: {artifact_ref}"
            )
        try:
            return EvidenceItem(
                evidence_id=record.evidence_id,
                type=record.type,
                source=record.source,
                subject=record.subject,
                artifact_ref=record.artifact_ref,
                extracted_summary=record.extracted_summary,
                collected_at=_as_utc(record.collected_at),
            )
        except (TypeError, ValidationError, ValueError) as error:
            raise EvidenceDataIntegrityError(
                "evidence record "
                f"{record.evidence_id} violates the EvidenceItem contract"
            ) from error
