"""Migration and real row-lock ownership checks on an isolated PostgreSQL schema."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from return_agent.attachments import bind_attachments
from return_agent.capabilities.evidence import EvidenceFixture, upsert_evidence
from return_agent.db.attachments import AttachmentRecord
from return_agent.db.case import CaseRecord
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def test_image_migration_and_atomic_claim(tmp_path, monkeypatch):
    postgres = os.getenv("ACTIVITY_TEST_POSTGRES_URL")
    admin = create_engine(postgres) if postgres else None
    schema = "images_" + uuid4().hex
    url = f"sqlite:///{tmp_path / 'images.db'}"
    if admin:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            # Do not inherit a pre-existing public.alembic_version via search_path.
            connection.exec_driver_sql(
                f'CREATE TABLE "{schema}".alembic_version (version_num VARCHAR(32) PRIMARY KEY)'
            )
        url = (
            make_url(postgres)
            .update_query_dict({"options": f"-csearch_path={schema},public"})
            .render_as_string(hide_password=False)
        )
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    ref = "artifact://upload/" + "a" * 32
    try:
        command.upgrade(cfg, "0013_activity_tracing")
        with sessions.begin() as session:
            for index in range(2):
                session.add(
                    CaseRecord(
                        case_ref=f"CASE-{index}",
                        thread_id=f"THREAD-{index}",
                        order_ref="ORDER-1",
                        user_ref="demo_customer",
                        status="OBSERVING",
                        created_at=now,
                        updated_at=now,
                    )
                )
        command.upgrade(cfg, "head")
        # Alembic used a different engine; discard cached SQLite schema handles.
        engine.dispose()
        assert len(inspect(engine).get_foreign_keys("image_attachments")) == 2
        command.downgrade(cfg, "0013_activity_tracing")
        command.upgrade(cfg, "head")
        with sessions.begin() as session:
            assert session.get(CaseRecord, "CASE-0").order_ref == "ORDER-1"
            upsert_evidence(
                session,
                EvidenceFixture(
                    evidence_id="EV-1",
                    artifact_ref=ref,
                    type="IMAGE",
                    source="USER",
                    subject="ORDER",
                    collected_at=now,
                    extracted_summary="Uploaded image file",
                ),
            )
            session.flush()
            session.add(
                AttachmentRecord(
                    attachment_id="a" * 32,
                    artifact_ref=ref,
                    evidence_id="EV-1",
                    user_ref="demo_customer",
                    order_ref="ORDER-1",
                    subject="ORDER",
                    media_type="image/png",
                    width=1,
                    height=1,
                    size_bytes=10,
                    content_sha256="b" * 64,
                )
            )
        # A downstream outbox failure must roll back the claim too.
        with (
            pytest.raises(RuntimeError, match="outbox failed"),
            sessions.begin() as session,
        ):
            bind_attachments(session, session.get(CaseRecord, "CASE-0"), [ref])
            raise RuntimeError("outbox failed")
        with sessions() as session:
            assert session.get(AttachmentRecord, "a" * 32).case_ref is None
        barrier = Barrier(2) if admin else None

        def claim(index):
            try:
                with sessions.begin() as session:
                    case = session.get(CaseRecord, f"CASE-{index}")
                    if barrier:
                        barrier.wait(timeout=10)
                    bind_attachments(session, case, [ref])
                return index, 200
            except HTTPException as error:
                return index, error.status_code

        if admin:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(claim, range(2)))
        else:
            results = [claim(index) for index in range(2)]
        assert sorted(status for _, status in results) == [200, 403]
        winner = next(index for index, status in results if status == 200)
        with sessions.begin() as session:
            # Same-case re-submission remains idempotent.
            bind_attachments(session, session.get(CaseRecord, f"CASE-{winner}"), [ref])
            assert session.get(AttachmentRecord, "a" * 32).case_ref == f"CASE-{winner}"
        with pytest.raises(RuntimeError, match="attachment history"):
            command.downgrade(cfg, "0013_activity_tracing")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0014_image_attachments"
            )
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            admin.dispose()
