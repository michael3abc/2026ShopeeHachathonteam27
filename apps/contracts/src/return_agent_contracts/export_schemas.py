"""Export versioned JSON Schema files for non-Python provider implementations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import TypeAdapter

from .activity import ActivityEmission, NarrationJob
from .completion import RefundAppliedEvent
from .fulfillment import ReturnFulfillmentEvent, ReturnEventReceipt, ReturnSimulationInput, PolicyConfirmationInput, ReturnConfirmationInput
from .policy_v2 import PolicyEvaluation, PolicySelection, PolicyConfirmation
from .base import ContractModel
from .models import (
    ManualEscalationHandoff,
    MemoryCandidate,
    MemoryDistillationInput,
    MemoryDistillationOutput,
    ResolutionHandoff,
)
from .runtime import (
    AgentResumeRequest,
    AgentRunResult,
    AgentStartRequest,
    NodeExecutionObservation,
)
from .service import (
    AgentCommand,
    AgentCommandDeadLetter,
    AgentEscalatedEvent,
    AgentInterruptedEvent,
    AgentNodeObservedEvent,
    AgentResolvedEvent,
    AgentResumeCommand,
    AgentRunFailedEvent,
    AgentServiceEvent,
    AgentStartCommand,
    MemoryDistillationCompletedEvent,
    MemoryDistillationFailedEvent,
    MemoryDistillationJob,
    MemoryJobDeadLetter,
    MemoryServiceEvent,
)
from .transport import PROVIDER_REQUEST_MODELS, PROVIDER_RESPONSE_MODELS

SchemaSource: TypeAlias = type[ContractModel] | Any

SCHEMA_MODELS: dict[str, SchemaSource] = {
    "RefundAppliedEvent.schema.json":RefundAppliedEvent,
    "ReturnFulfillmentEvent.schema.json":ReturnFulfillmentEvent,
    "ReturnEventReceipt.schema.json":ReturnEventReceipt,
    "ReturnSimulationInput.schema.json":ReturnSimulationInput,
    "PolicyConfirmationInput.schema.json":PolicyConfirmationInput,
    "ReturnConfirmationInput.schema.json":ReturnConfirmationInput,
    "PolicyEvaluation.schema.json":PolicyEvaluation,
    "PolicySelection.schema.json":PolicySelection,
    "PolicyConfirmation.schema.json":PolicyConfirmation,
    "ActivityEmission.schema.json": ActivityEmission,
    "NarrationJob.schema.json": NarrationJob,
    **{f"{model.__name__}.schema.json": model for model in PROVIDER_REQUEST_MODELS},
    **{f"{model.__name__}.schema.json": model for model in PROVIDER_RESPONSE_MODELS},
    "ResolutionHandoff.schema.json": ResolutionHandoff,
    "ManualEscalationHandoff.schema.json": ManualEscalationHandoff,
    "MemoryCandidate.schema.json": MemoryCandidate,
    "MemoryDistillationInput.schema.json": MemoryDistillationInput,
    "MemoryDistillationOutput.schema.json": MemoryDistillationOutput,
    "AgentStartRequest.schema.json": AgentStartRequest,
    "AgentResumeRequest.schema.json": AgentResumeRequest,
    "AgentRunResult.schema.json": AgentRunResult,
    "NodeExecutionObservation.schema.json": NodeExecutionObservation,
    "AgentStartCommand.schema.json": AgentStartCommand,
    "AgentResumeCommand.schema.json": AgentResumeCommand,
    "AgentCommand.schema.json": AgentCommand,
    "AgentNodeObservedEvent.schema.json": AgentNodeObservedEvent,
    "AgentInterruptedEvent.schema.json": AgentInterruptedEvent,
    "AgentResolvedEvent.schema.json": AgentResolvedEvent,
    "AgentEscalatedEvent.schema.json": AgentEscalatedEvent,
    "AgentRunFailedEvent.schema.json": AgentRunFailedEvent,
    "AgentServiceEvent.schema.json": AgentServiceEvent,
    "AgentCommandDeadLetter.schema.json": AgentCommandDeadLetter,
    "MemoryDistillationJob.schema.json": MemoryDistillationJob,
    "MemoryDistillationCompletedEvent.schema.json": MemoryDistillationCompletedEvent,
    "MemoryDistillationFailedEvent.schema.json": MemoryDistillationFailedEvent,
    "MemoryServiceEvent.schema.json": MemoryServiceEvent,
    "MemoryJobDeadLetter.schema.json": MemoryJobDeadLetter,
}


def export_schemas(output_dir: Path) -> list[Path]:
    """Write deterministic JSON Schema files and return their paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in SCHEMA_MODELS.items():
        path = output_dir / filename
        path.write_text(
            json.dumps(
                TypeAdapter(model).json_schema(mode="validation"),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(path)

    manifest = output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "contract_version": "v1",
                "schemas": [path.name for path in written],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return [*written, manifest]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apps/contracts/schemas/agent/v1"),
        help="directory for versioned JSON Schema files",
    )
    args = parser.parse_args()
    for path in export_schemas(args.output):
        print(path)


if __name__ == "__main__":
    main()
