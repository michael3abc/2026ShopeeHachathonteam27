"""Image metadata registered with its case foreign-key dependency."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .case import CaseRecord
from .models import Base


class AttachmentRecord(Base):
    """API-owned sanitized file, optionally claimed by one case."""

    __tablename__ = "image_attachments"
    attachment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    artifact_ref: Mapped[str] = mapped_column(String(512), unique=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence_items.evidence_id"))
    user_ref: Mapped[str] = mapped_column(String(128))
    order_ref: Mapped[str] = mapped_column(String(128))
    case_ref: Mapped[str | None] = mapped_column(
        ForeignKey(CaseRecord.case_ref), index=True
    )
    subject: Mapped[str] = mapped_column(String(128))
    media_type: Mapped[str] = mapped_column(String(32))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64))
