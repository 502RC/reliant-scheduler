import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class SLAEventType(StrEnum):
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"


class SLAPolicy(TimestampMixin, Base):
    __tablename__ = "sla_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    target_completion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    breach_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    notification_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    constraints: Mapped[list["SLAJobConstraint"]] = relationship(
        back_populates="sla_policy", cascade="all, delete-orphan"
    )
    events: Mapped[list["SLAEvent"]] = relationship(
        back_populates="sla_policy", cascade="all, delete-orphan", order_by="SLAEvent.triggered_at.desc()"
    )

    __table_args__ = (
        Index("ix_sla_policies_name", "name"),
    )


class SLAJobConstraint(Base):
    __tablename__ = "sla_job_constraints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    sla_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sla_policies.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    track_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sla_policy: Mapped["SLAPolicy"] = relationship(back_populates="constraints")
    job: Mapped["Job"] = relationship()

    __table_args__ = (
        UniqueConstraint("sla_policy_id", "job_id", name="uq_sla_policy_job"),
        Index("ix_sla_constraints_policy_id", "sla_policy_id"),
        Index("ix_sla_constraints_job_id", "job_id"),
    )


class SLAEvent(Base):
    __tablename__ = "sla_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    sla_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sla_policies.id", ondelete="CASCADE"), nullable=False
    )
    job_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    details_json: Mapped[dict | None] = mapped_column(JSONB)

    sla_policy: Mapped["SLAPolicy"] = relationship(back_populates="events")
    job_run: Mapped["JobRun | None"] = relationship()

    __table_args__ = (
        Index("ix_sla_events_policy_id", "sla_policy_id"),
        Index("ix_sla_events_event_type", "event_type"),
        Index("ix_sla_events_triggered_at", "triggered_at"),
    )


from reliant_scheduler.models.job import Job  # noqa: E402
from reliant_scheduler.models.job_run import JobRun  # noqa: E402
