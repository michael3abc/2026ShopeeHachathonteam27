"""CLI entry points for safe local capability setup."""

from __future__ import annotations

import argparse
from pathlib import Path

from return_agent.capabilities.evidence import load_evidence_fixture, upsert_evidence
from return_agent.db.session import create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Import neutral evidence metadata.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("apps/api/fixtures/evidence.json"),
        help="path to a JSON array of evidence metadata",
    )
    args = parser.parse_args()

    evidence_records = load_evidence_fixture(args.input)
    inserted = 0
    session_factory = create_session_factory()
    with session_factory.begin() as session:
        for evidence in evidence_records:
            inserted += upsert_evidence(session, evidence)
    print(
        f"evidence seed complete: inserted={inserted}, unchanged={len(evidence_records) - inserted}"
    )
