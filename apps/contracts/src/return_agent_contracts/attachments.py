"""Image upload and conversation contracts; bytes never enter graph state."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pydantic import Field

from .base import ContractModel, OpaqueRef, UTCDateTime
from .models import OrderSnapshot


class AttachmentView(ContractModel):
    attachment_id: str
    artifact_ref: str
    evidence_id: str
    subject: str
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    size_bytes: int = Field(gt=0)
    content_sha256: str


class UploadOptions(ContractModel):
    max_bytes: int
    max_images: int
    max_pixels: int
    media_types: list[str]
    subjects: dict[str, str]


class ConversationTurn(ContractModel):
    seq: int
    message: str
    created_at: UTCDateTime
    attached_artifact_refs: list[str]
    attachments: list[AttachmentView]


class ConversationPage(ContractModel):
    turns: list[ConversationTurn]


@runtime_checkable
class OrderUploadProvider(Protocol):
    def load_order_snapshot(self, order_ref: OpaqueRef) -> OrderSnapshot: ...


@dataclass(frozen=True)
class ImageContent:
    media_type: str
    content: bytes = field(repr=False)


class EvidenceImageProvider(Protocol):
    def load_image(self, case_ref: str, artifact_ref: str) -> ImageContent: ...
