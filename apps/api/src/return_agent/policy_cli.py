"""CLI for repeatable ingestion of versioned structured policy fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from return_agent.capabilities.embeddings import (
    embedding_provider_from_env,
)
from return_agent.capabilities.policy import (
    ingest_policy_documents,
    load_policy_fixture,
)
from return_agent.db.session import create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest structured policy fixtures.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/policy.json.example"),
        help="path to a JSON array of versioned policy documents",
    )
    parser.add_argument(
        "--reembed",
        action="store_true",
        help="explicitly rebuild stored vectors using the configured model; "
        "policy identity/content and historical retrievals remain immutable",
    )
    args = parser.parse_args()

    documents = load_policy_fixture(args.input)
    session_factory = create_session_factory()
    with session_factory.begin() as session:
        result = ingest_policy_documents(
            session,
            documents,
            embedding_provider_from_env(),
            reembed=args.reembed,
        )
    print(
        "policy ingestion complete: "
        f"inserted={result.inserted_documents}, "
        f"updated={result.updated_documents}, "
        f"unchanged={result.unchanged_documents}"
    )
