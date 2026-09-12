"""Independent case activity audit and durable narration outbox."""

from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .case import CaseRecord
from .models import Base


class ActivityRecord(Base):
    __tablename__ = "case_activities"
    __table_args__ = (UniqueConstraint("case_ref", "seq"),)
    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey(CaseRecord.case_ref), index=True)
    seq: Mapped[int] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSON)


class NarrationOutboxRecord(Base):
    __tablename__ = "activity_narration_outbox"
    source_event_id: Mapped[str] = mapped_column(
        ForeignKey("case_activities.event_id"), primary_key=True
    )
    payload: Mapped[dict] = mapped_column(JSON)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    result_event_id: Mapped[str | None] = mapped_column(String(200))
