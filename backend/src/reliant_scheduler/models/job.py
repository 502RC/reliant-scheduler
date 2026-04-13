import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class JobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(String(32), nullable=False, default=JobStatus.ACTIVE)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    command: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connections.id"), nullable=True
    )
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id"), nullable=True
    )
    max_retries: Mapped[int] = mapped_column(default=0)
    timeout_seconds: Mapped[int] = mapped_column(default=3600)
    tags: Mapped[dict | None] = mapped_column(JSONB)

    connection: Mapped["Connection | None"] = relationship()
    schedule: Mapped["Schedule | None"] = relationship(back_populates="job", uselist=False)
    runs: Mapped[list["JobRun"]] = relationship(back_populates="job", order_by="JobRun.started_at.desc()")
    dependencies: Mapped[list["JobDependency"]] = relationship(
        back_populates="dependent_job", foreign_keys="JobDependency.dependent_job_id"
    )

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_environment_id", "environment_id"),
        Index("ix_jobs_connection_id", "connection_id"),
    )


class JobDependency(Base):
    __tablename__ = "job_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dependent_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )

    dependent_job: Mapped["Job"] = relationship(foreign_keys=[dependent_job_id])
    depends_on_job: Mapped["Job"] = relationship(foreign_keys=[depends_on_job_id])

    __table_args__ = (
        Index("ix_job_deps_dependent", "dependent_job_id"),
        Index("ix_job_deps_depends_on", "depends_on_job_id"),
    )


from reliant_scheduler.models.connection import Connection  # noqa: E402
from reliant_scheduler.models.schedule import Schedule  # noqa: E402
from reliant_scheduler.models.job_run import JobRun  # noqa: E402
