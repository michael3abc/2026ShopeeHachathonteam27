"""Export versioned JSON Schema files for the Demo/UI adapter boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from .activity import ActivityEvent, ActivityPage
from .attachments import AttachmentView, ConversationPage, UploadOptions
from .ui import (
    AgentEvent,
    CaseDetail,
    ClarificationInterruptPayload,
    CreateCaseRequest,
    CreateCaseResponse,
    DonePayload,
    ErrorPayload,
    EvidenceRequestView,
    HumanReviewPayload,
    InterruptPayload,
    MemoryRecordView,
    MemoryRetrievalPayload,
    NodeLifecyclePayload,
    ReviewDecision,
    SendMessageRequest,
    StateChangePayload,
    TokenPayload,
    ToolCallPayload,
    ToolResultPayload,
)

UI_SCHEMA_MODELS = {
    "AttachmentView.schema.json": AttachmentView,
    "ConversationPage.schema.json": ConversationPage,
    "UploadOptions.schema.json": UploadOptions,
    "ActivityEvent.schema.json": ActivityEvent,
    "ActivityPage.schema.json": ActivityPage,
    "AgentEvent.schema.json": AgentEvent,
    "TokenPayload.schema.json": TokenPayload,
    "StateChangePayload.schema.json": StateChangePayload,
    "NodeLifecyclePayload.schema.json": NodeLifecyclePayload,
    "DonePayload.schema.json": DonePayload,
    "ErrorPayload.schema.json": ErrorPayload,
    "InterruptPayload.schema.json": InterruptPayload,
    "ClarificationInterruptPayload.schema.json": ClarificationInterruptPayload,
    "EvidenceRequestView.schema.json": EvidenceRequestView,
    "HumanReviewPayload.schema.json": HumanReviewPayload,
    "ReviewDecision.schema.json": ReviewDecision,
    "MemoryRecordView.schema.json": MemoryRecordView,
    "MemoryRetrievalPayload.schema.json": MemoryRetrievalPayload,
    "ToolCallPayload.schema.json": ToolCallPayload,
    "ToolResultPayload.schema.json": ToolResultPayload,
    "CreateCaseRequest.schema.json": CreateCaseRequest,
    "CreateCaseResponse.schema.json": CreateCaseResponse,
    "CaseDetail.schema.json": CaseDetail,
    "SendMessageRequest.schema.json": SendMessageRequest,
}


def export_ui_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in UI_SCHEMA_MODELS.items():
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
            {"ui_contract_version": "v1", "schemas": [path.name for path in written]},
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
        default=Path("apps/contracts/schemas/ui/v1"),
        help="directory for versioned UI schemas",
    )
    args = parser.parse_args()
    for path in export_ui_schemas(args.output):
        print(path)


if __name__ == "__main__":
    main()
