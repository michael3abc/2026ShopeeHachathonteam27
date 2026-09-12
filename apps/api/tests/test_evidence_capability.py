from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from return_agent.capabilities.evidence import (
    EvidenceArtifactNotFoundError,
    EvidenceFixture,
    EvidenceSeedConflictError,
    SqlAlchemyEvidenceProvider,
    upsert_evidence,
)
from return_agent.db.models import Base
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _fixture() -> EvidenceFixture:
    return EvidenceFixture(
        evidence_id="EV-002",
        type="IMAGE",
        source="USER",
        subject="LI-002",
        artifact_ref="artifact://evidence/EV-002",
        extracted_summary="Packaging damage and an item crack are visible.",
        collected_at="2026-09-01T10:40:00Z",
    )


def test_evidence_provider_resolves_neutral_metadata_and_seed_is_idempotent() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        assert upsert_evidence(session, _fixture()) is True
    with session_factory.begin() as session:
        assert upsert_evidence(session, _fixture()) is False

    evidence = SqlAlchemyEvidenceProvider(session_factory).resolve(
        "artifact://evidence/EV-002"
    )
    assert evidence.evidence_id == "EV-002"
    assert (
        evidence.extracted_summary == "Packaging damage and an item crack are visible."
    )

    with pytest.raises(EvidenceArtifactNotFoundError):
        SqlAlchemyEvidenceProvider(session_factory).resolve(
            "artifact://evidence/unknown"
        )


def test_seed_rejects_identity_conflicts_and_non_metadata_payloads() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        upsert_evidence(session, _fixture())
    changed = _fixture().model_copy(update={"extracted_summary": "Different finding."})
    with (
        session_factory.begin() as session,
        pytest.raises(EvidenceSeedConflictError),
    ):
        upsert_evidence(session, changed)

    with pytest.raises(ValidationError):
        EvidenceFixture.model_validate(
            {
                **_fixture().model_dump(mode="json"),
                "claim_status": "SUPPORTED",
            }
        )
    with pytest.raises(ValidationError):
        EvidenceFixture.model_validate(
            {
                **_fixture().model_dump(mode="json"),
                "extracted_summary": "data:image/png;base64,not-artifact-metadata",
            }
        )


def test_evidence_migration_upgrades_a_fresh_database(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'evidence.db'}")

    command.upgrade(config, "head")

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    table_names = set(inspect(engine).get_table_names())
    assert {
        "evidence_items",
        "policy_documents",
        "policy_clauses",
        "policy_retrievals",
        "operational_memories",
        "operational_memory_events",
    }.issubset(table_names)
