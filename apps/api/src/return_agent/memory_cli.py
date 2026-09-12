"""Resumable maintenance of derived memory vectors; never changes governance."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator

from return_agent_contracts.validation import validate_memory_summary
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.embeddings import (
    POLICY_EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    embedding_provider_from_env,
    validate_embedding,
)
from return_agent.capabilities.operational_memory import _canonical_hash
from return_agent.db.models import OperationalMemoryRecord
from return_agent.db.session import create_session_factory


def backfill_memory_vectors(
    sessions: sessionmaker[Session],
    embedding: EmbeddingProvider,
    *,
    dry_run: bool = False,
) -> Iterator[dict[str, str]]:
    """Commit each record separately; reruns skip matching valid vectors."""
    if embedding.dimensions != POLICY_EMBEDDING_DIMENSIONS:
        raise ValueError("memory embeddings require 1536 dimensions")
    last_id = ""
    while True:
        with sessions() as session:
            rows = session.scalars(
                select(OperationalMemoryRecord)
                .where(
                    OperationalMemoryRecord.memory_id > last_id,
                )
                .order_by(OperationalMemoryRecord.memory_id)
                .limit(100)
            ).all()
        if not rows:
            return
        for row in rows:
            last_id = row.memory_id
            try:
                action = _backfill_record(
                    sessions, embedding, row, dry_run=dry_run
                )
            except Exception as error:
                # Identify validation/DB failures too, without exposing content.
                yield {
                    "memory_id": row.memory_id,
                    "action": "failed",
                    "error_type": type(error).__name__,
                }
                raise
            yield {"memory_id": row.memory_id, "action": action}


def _backfill_record(
    sessions: sessionmaker[Session],
    embedding: EmbeddingProvider,
    row: OperationalMemoryRecord,
    *,
    dry_run: bool,
) -> str:
    summary = row.retrieval_summary
    if summary is None:
        summary = (
            "Situation: "
            + "; ".join(row.trigger_conditions)
            + "\nAction: "
            + row.recommended_behavior
        )
    validate_memory_summary(summary)
    digest = _canonical_hash(summary)
    valid = (
        row.retrieval_summary is not None
        and row.embedding is not None
        and row.summary_version
        and row.embedding_model == embedding.model_name
        and row.summary_hash == digest
    )
    if valid:
        validate_embedding(row.embedding, dimensions=embedding.dimensions)
        return "unchanged"
    if dry_run:
        return "would_embed"
    vector = validate_embedding(
        embedding.embed(summary), dimensions=embedding.dimensions
    )
    with sessions.begin() as session:
        locked = session.scalar(
            select(OperationalMemoryRecord)
            .where(OperationalMemoryRecord.memory_id == row.memory_id)
            .with_for_update()
        )
        if (
            locked is None
            or locked.candidate_payload_hash != row.candidate_payload_hash
            or locked.retrieval_summary != row.retrieval_summary
        ):
            raise RuntimeError(
                "memory changed during backfill; rerun from current data"
            )
        locked.retrieval_summary = summary
        locked.summary_version = row.summary_version or "legacy-composed:1.0"
        locked.summary_hash = digest
        locked.embedding_model = embedding.model_name
        locked.embedding = vector
    return "embedded"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for result in backfill_memory_vectors(
        create_session_factory(),
        embedding_provider_from_env(),
        dry_run=args.dry_run,
    ):
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
