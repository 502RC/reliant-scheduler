import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class RunStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class JobRun(TimestampMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(String(32), nullable=False, default=RunStatus.PENDING)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="schedule")
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_code: Mapped[int | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    log_url: Mapped[str | None] = mapped_column(String(1024))
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    attempt_number: Mapped[int] = mapped_column(default=1)

    job: Mapped["Job"] = relationship(back_populates="runs")
    agent: Mapped["Agent | None"] = relationship()

    __table_args__ = (
        Index("ix_job_runs_job_id_status", "job_id", "status"),
        Index("ix_job_runs_started_at", "started_at"),
        Index("ix_job_runs_agent_id", "agent_id"),
    )


from reliant_scheduler.models.job import Job  # noqa: E402
from reliant_scheduler.models.agent import Agent  # noqa: E402
