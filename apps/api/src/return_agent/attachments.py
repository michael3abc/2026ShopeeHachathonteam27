"""Bounded image uploads, ownership checks and durable conversation reads."""

from __future__ import annotations

import hashlib
import io
import os
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from return_agent_contracts.attachments import (
    AttachmentView,
    ConversationPage,
    ConversationTurn,
    OrderUploadProvider,
    UploadOptions,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .capabilities.evidence import EvidenceFixture, upsert_evidence
from .db.attachments import AttachmentRecord
from .db.case import USER_TURN, CaseEventRecord, CaseRecord
from .http_dependencies import get_session, require_internal_service

router = APIRouter()
DEMO_USER = "demo_customer"
MEDIA = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
SessionDep = Annotated[Session, Depends(get_session)]


def limits() -> tuple[int, int, int]:
    values = tuple(
        int(os.environ.get(key, default))
        for key, default in (
            ("RETURN_AGENT_IMAGE_MAX_BYTES", "10485760"),
            ("RETURN_AGENT_IMAGE_MAX_PER_MESSAGE", "6"),
            ("RETURN_AGENT_IMAGE_MAX_PIXELS", "25000000"),
        )
    )
    if min(values) <= 0:
        raise RuntimeError("Image limits must be positive")
    return values


class ImageRequestLimitMiddleware:
    """Bound multipart parsing even for chunked requests without Content-Length."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["path"] != "/attachments"
            or scope["method"] != "POST"
        ):
            await self.app(scope, receive, send)
            return
        cap = limits()[0] + 64 * 1024
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"detail": "Invalid content length"}, 400)(
                scope, receive, send
            )
            return
        if declared > cap:
            await JSONResponse({"detail": "Upload request exceeds size limit"}, 413)(
                scope, receive, send
            )
            return
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > cap:
                raise HTTPException(413, "Upload request exceeds size limit")
            return message

        await self.app(scope, bounded_receive, send)


def file_path(attachment_id: str) -> Path:
    # Never derive a path from a browser filename or artifact URL.
    if len(attachment_id) != 32 or any(
        c not in "0123456789abcdef" for c in attachment_id
    ):
        raise HTTPException(404, "Unknown attachment")
    return (
        Path(os.environ.get("RETURN_AGENT_IMAGE_DIR", ".local/image-attachments"))
        / attachment_id
    )


def view(record: AttachmentRecord) -> AttachmentView:
    return AttachmentView(
        **{key: getattr(record, key) for key in AttachmentView.model_fields}
    )


def owned_case(session: Session, case_ref: str, *, lock: bool = False) -> CaseRecord:
    query = select(CaseRecord).where(
        CaseRecord.case_ref == case_ref, CaseRecord.user_ref == DEMO_USER
    )
    if lock:
        query = query.with_for_update()
    case = session.scalar(query)
    if case is None:
        raise HTTPException(404, "Unknown case")
    return case


def subjects(request: Request, order_ref: str) -> dict[str, str]:
    bundle = request.app.state.provider_bundle
    provider = bundle.case_context_provider if bundle else None
    if not isinstance(provider, OrderUploadProvider):
        raise HTTPException(503, "Order upload provider is not configured")
    try:
        snapshot = provider.load_order_snapshot(order_ref)
    except LookupError as error:
        raise HTTPException(404, "Unknown order") from error
    return {
        "ORDER": "訂單／外包裝",
        **{item.line_item_id: item.title for item in snapshot.line_items},
    }


@router.get("/attachments/options")
def upload_options(request: Request, order_ref: str) -> UploadOptions:
    max_bytes, max_images, max_pixels = limits()
    return UploadOptions(
        max_bytes=max_bytes,
        max_images=max_images,
        max_pixels=max_pixels,
        media_types=list(MEDIA.values()),
        subjects=subjects(request, order_ref),
    )


def sanitize(content: bytes, declared_type: str | None) -> tuple[bytes, str, int, int]:
    max_bytes, _, max_pixels = limits()
    if len(content) > max_bytes:
        raise HTTPException(413, "Image exceeds size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                fmt = source.format
                if fmt not in MEDIA or declared_type != MEDIA[fmt]:
                    raise HTTPException(
                        415, "Expected a JPEG, PNG or WebP with matching MIME type"
                    )
                width, height = source.size
                if width * height > max_pixels or getattr(source, "n_frames", 1) != 1:
                    raise HTTPException(413, "Image exceeds pixel limit or is animated")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                width, height = oriented.size
                # Fresh pixels discard EXIF, ICC and textual metadata.
                mode = (
                    "RGBA"
                    if ("A" in oriented.getbands() or "transparency" in oriented.info)
                    and fmt != "JPEG"
                    else "RGB"
                )
                clean = Image.frombytes(
                    mode, oriented.size, oriented.convert(mode).tobytes()
                )
                output = io.BytesIO()
                clean.save(output, format=fmt)
                encoded = output.getvalue()
                if len(encoded) > max_bytes:
                    raise HTTPException(413, "Sanitized image exceeds size limit")
                return encoded, MEDIA[fmt], width, height
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(422, "Invalid or unsafe image") from error


@router.post("/attachments", status_code=201)
def upload_image(
    request: Request,
    session: SessionDep,
    file: UploadFile,
    order_ref: Annotated[str, Form()],
    subject: Annotated[str, Form()],
    case_ref: Annotated[str | None, Form()] = None,
) -> AttachmentView:
    if subject not in subjects(request, order_ref):
        raise HTTPException(422, "Unknown evidence subject")
    if case_ref:
        case = owned_case(session, case_ref)
        if case.order_ref != order_ref or case.status not in {
            "AWAITING_EVIDENCE",
            "AWAITING_CLARIFICATION",
        }:
            raise HTTPException(409, "Case cannot accept images")
    encoded, media_type, width, height = sanitize(
        file.file.read(limits()[0] + 1), file.content_type
    )
    attachment_id = uuid4().hex
    artifact_ref = f"artifact://upload/{attachment_id}"
    evidence_id = f"EV-{attachment_id}"
    path = file_path(attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = AttachmentRecord(
        attachment_id=attachment_id,
        artifact_ref=artifact_ref,
        evidence_id=evidence_id,
        user_ref=DEMO_USER,
        order_ref=order_ref,
        case_ref=case_ref,
        subject=subject,
        media_type=media_type,
        width=width,
        height=height,
        size_bytes=len(encoded),
        content_sha256=hashlib.sha256(encoded).hexdigest(),
    )
    try:
        upsert_evidence(
            session,
            EvidenceFixture(
                evidence_id=evidence_id,
                artifact_ref=artifact_ref,
                type="IMAGE",
                source="USER",
                subject=subject,
                collected_at=datetime.now(UTC),
                extracted_summary=f"User-uploaded image {evidence_id}, {width}x{height}. Subject assigned by user; visual contents must be inspected, not assumed.",
            ),
        )
        session.flush()
        session.add(record)
        with path.open("xb") as output:
            path.chmod(0o600)
            output.write(encoded)
        session.commit()
    except Exception:
        session.rollback()
        path.unlink(missing_ok=True)
        raise
    return view(record)


def bind_attachments(session: Session, case: CaseRecord, refs: list[str]) -> None:
    if len(refs) > limits()[1] or len(set(refs)) != len(refs):
        raise HTTPException(422, "Too many or duplicate attachments")
    for ref in sorted(refs):
        record = session.scalar(
            select(AttachmentRecord)
            .where(AttachmentRecord.artifact_ref == ref)
            .with_for_update()
        )
        if record is None:
            if ref.startswith("artifact://upload/"):
                raise HTTPException(404, "Unknown attachment")
            continue  # Existing metadata-only demo fixtures retain their provider validation.
        if (
            record.user_ref != case.user_ref
            or record.order_ref != case.order_ref
            or record.case_ref not in (None, case.case_ref)
        ):
            raise HTTPException(403, "Attachment does not belong to this case")
        record.case_ref = case.case_ref
    session.flush()


def image_response(record: AttachmentRecord) -> Response:
    path = file_path(record.attachment_id)
    try:
        content = path.read_bytes()
    except FileNotFoundError as error:
        raise HTTPException(503, "Stored image unavailable") from error
    if hashlib.sha256(content).hexdigest() != record.content_sha256:
        raise HTTPException(503, "Stored image integrity failure")
    return Response(
        content,
        media_type=record.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/attachments/{attachment_id}/content")
def read_image(attachment_id: str, session: SessionDep) -> Response:
    record = session.get(AttachmentRecord, attachment_id)
    if record is None or record.user_ref != DEMO_USER:
        raise HTTPException(404, "Unknown attachment")
    if record.case_ref is not None:
        owned_case(session, record.case_ref)
    return image_response(record)


@router.get(
    "/internal/cases/{case_ref}/images/{attachment_id}",
    dependencies=[Depends(require_internal_service)],
)
def internal_image(case_ref: str, attachment_id: str, session: SessionDep) -> Response:
    record = session.get(AttachmentRecord, attachment_id)
    if record is None or record.case_ref != case_ref:
        raise HTTPException(404, "Unknown case image")
    turns = session.scalars(
        select(CaseEventRecord).where(
            CaseEventRecord.case_ref == case_ref, CaseEventRecord.kind == USER_TURN
        )
    )
    if not any(
        record.artifact_ref in turn.payload.get("attached_artifact_refs", [])
        for turn in turns
    ):
        raise HTTPException(403, "Image has not been submitted")
    return image_response(record)


@router.get("/cases/{case_ref}/conversation")
def conversation(case_ref: str, session: SessionDep) -> ConversationPage:
    owned_case(session, case_ref)
    turns = session.scalars(
        select(CaseEventRecord)
        .where(CaseEventRecord.case_ref == case_ref, CaseEventRecord.kind == USER_TURN)
        .order_by(CaseEventRecord.seq)
    )
    images = {
        r.artifact_ref: view(r)
        for r in session.scalars(
            select(AttachmentRecord).where(AttachmentRecord.case_ref == case_ref)
        )
    }
    return ConversationPage(
        turns=[
            ConversationTurn(
                seq=t.seq,
                message=t.payload["message"],
                created_at=t.created_at.replace(tzinfo=UTC)
                if t.created_at.tzinfo is None
                else t.created_at,
                attached_artifact_refs=t.payload.get("attached_artifact_refs", []),
                attachments=[
                    images[r]
                    for r in t.payload.get("attached_artifact_refs", [])
                    if r in images
                ],
            )
            for t in turns
        ]
    )
