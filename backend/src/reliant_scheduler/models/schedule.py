import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class TriggerType(StrEnum):
    CRON = "cron"
    EVENT = "event"
    DEPENDENCY = "dependency"
    MANUAL = "manual"


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    trigger_type: Mapped[TriggerType] = mapped_column(String(32), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    event_source: Mapped[str | None] = mapped_column(String(255))
    event_filter: Mapped[dict | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped["Job"] = relationship(back_populates="schedule")


from reliant_scheduler.models.job import Job  # noqa: E402
