import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class CalendarType(StrEnum):
    BUSINESS = "business"
    FINANCIAL = "financial"
    HOLIDAY = "holiday"
    CUSTOM = "custom"


class Calendar(TimestampMixin, Base):
    __tablename__ = "calendars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    calendar_type: Mapped[CalendarType] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    dates: Mapped[list["CalendarDate"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
    rules: Mapped[list["CalendarRule"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
    job_associations: Mapped[list["JobCalendarAssociation"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_calendars_type", "calendar_type"),
    )


class CalendarDate(Base):
    __tablename__ = "calendar_dates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    is_business_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    label: Mapped[str | None] = mapped_column(String(255))

    calendar: Mapped["Calendar"] = relationship(back_populates="dates")

    __table_args__ = (
        UniqueConstraint("calendar_id", "date", name="uq_calendar_date"),
        Index("ix_calendar_dates_calendar_id", "calendar_id"),
        Index("ix_calendar_dates_date", "date"),
    )


class RuleType(StrEnum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class CalendarRule(TimestampMixin, Base):
    __tablename__ = "calendar_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[RuleType] = mapped_column(String(32), nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Mon, 6=Sun
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-12
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-31
    description: Mapped[str | None] = mapped_column(Text)

    calendar: Mapped["Calendar"] = relationship(back_populates="rules")

    __table_args__ = (
        Index("ix_calendar_rules_calendar_id", "calendar_id"),
    )


class ConstraintType(StrEnum):
    RUN_ONLY_ON_BUSINESS_DAYS = "run_only_on_business_days"
    SKIP_HOLIDAYS = "skip_holidays"
    CUSTOM = "custom"


class DSTPolicy(StrEnum):
    SKIP = "skip"
    RUN_AFTER = "run_after"


class JobCalendarAssociation(Base):
    __tablename__ = "job_calendar_associations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False
    )
    constraint_type: Mapped[ConstraintType] = mapped_column(String(64), nullable=False)
    dst_policy: Mapped[DSTPolicy] = mapped_column(
        String(32), nullable=False, default=DSTPolicy.SKIP
    )

    job: Mapped["Job"] = relationship()
    calendar: Mapped["Calendar"] = relationship(back_populates="job_associations")

    __table_args__ = (
        UniqueConstraint("job_id", "calendar_id", name="uq_job_calendar"),
        Index("ix_job_calendar_job_id", "job_id"),
        Index("ix_job_calendar_calendar_id", "calendar_id"),
    )


from reliant_scheduler.models.job import Job  # noqa: E402
