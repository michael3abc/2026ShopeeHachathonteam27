"""Export schemas from this project's Python definitions only."""
import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from . import domain, human, memory, messages, providers
from .primitives import ContractModel


def schemas() -> dict[str, dict[str, Any]]:
    models: dict[str, Any] = {}
    for module in (domain, human, memory, messages, providers):
        for name, value in vars(module).items():
            if isinstance(value, type) and issubclass(value, ContractModel) and value.__module__ == module.__name__ and not name.endswith("Base") and name != "ProviderResponse":
                models[name] = value
    for name, value in {
        "EvidenceAssessment": domain.EvidenceAssessment, "ProposedDecision": domain.ProposedDecision,
        "ProposedDecisionDraft": domain.ProposedDecisionDraft, "ReviewResult": domain.ReviewResult,
        "VerificationResult": domain.VerificationResult, "CorrectedDecision": domain.CorrectedDecision,
        "ReviewDecision": human.ReviewDecision, "HumanReviewResult": human.HumanReviewResult,
        "ResolutionHandoff": human.ResolutionHandoff, "AgentCommand": messages.AgentCommand,
        "ResolverOutput": messages.ResolverOutput, "ResumePayload": messages.ResumePayload,
        "RefundApplicationResult": providers.RefundApplicationResult,
        "RefundExecutionRecord": providers.RefundExecutionRecord,
    }.items():
        models[name] = value
    return {name: {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": name, **TypeAdapter(model).json_schema(mode="serialization")} for name, model in sorted(models.items())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("apps/contracts/schemas"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    exported = schemas()
    if not args.check:
        args.output.mkdir(parents=True, exist_ok=True)
    mismatches = []
    expected_files = {f"{name}.schema.json" for name in exported}
    for name, schema in exported.items():
        content = json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = args.output / f"{name}.schema.json"
        if args.check:
            if not path.exists() or path.read_text() != content:
                mismatches.append(path.name)
        else:
            path.write_text(content)
    extra = {p.name for p in args.output.glob("*.schema.json")} - expected_files
    if mismatches or extra:
        raise SystemExit(f"Schema drift: {sorted(set(mismatches) | extra)}")
    print(f"{'Checked' if args.check else 'Exported'} {len(exported)} schemas")


if __name__ == "__main__":
    main()
