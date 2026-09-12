"""Prepare a fresh single-case fixture directory; never connects to a database."""

import argparse
import json
from pathlib import Path

from return_agent.capabilities.evidence import load_evidence_fixture
from return_agent.capabilities.policy import load_policy_fixture
from return_agent_contracts.models import CaseContextLoadResult, MemoryCandidate
from return_agent_contracts.ui import CreateCaseRequest, SendMessageRequest


def _load_case(source: Path, case: str) -> dict[str, object]:
    payload = json.loads((source / f"case-{case}.json.example").read_text())
    context = {key: payload[key] for key in ("case_context", "order_snapshot")}
    CaseContextLoadResult.model_validate(context)
    CreateCaseRequest.model_validate(payload["create_case_request"])
    for message in payload["followup_messages"]:
        SendMessageRequest.model_validate(message)
    return context


def prepare(case: str, output: Path) -> None:
    source = Path(__file__).resolve().parent
    selected = ["a", "b", "c"] if case == "all" else [case]
    contexts = [_load_case(source, name) for name in selected]
    context_fixture = (
        contexts[0] if len(contexts) == 1 else {"orders": contexts}
    )
    memory = json.loads((source / "memory-preload.json.example").read_text())
    MemoryCandidate.model_validate(memory["candidate"])
    load_policy_fixture(source / "policy.json.example")
    load_evidence_fixture(source / "evidence.json.example")
    # Same speaker-only preload for all cases: B/C receive no headphone seed.
    fixtures = {
        "case-context.json.example": context_fixture,
        "operational-memory.json.example": memory,
        "policy.json.example": json.loads((source / "policy.json.example").read_text()),
        "evidence.json.example": json.loads((source / "evidence.json.example").read_text()),
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, value in fixtures.items():
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(f"Prepared case set {case.upper()} in {output.resolve()}")
    print("No DB changes. Review image/summary agreement before starting API bootstrap.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["a", "b", "c", "all"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.case, args.output)
