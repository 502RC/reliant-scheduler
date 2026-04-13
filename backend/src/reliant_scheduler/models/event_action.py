"""Event-action automation models.

Defines event types, actions, event-action bindings, and action execution
history for the notification/recovery automation system.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class ActionType(StrEnum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    ITSM_INCIDENT = "itsm_incident"
    RECOVERY_JOB = "recovery_job"


class ActionExecutionStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class EventType(TimestampMixin, Base):
    __tablename__ = "event_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    bindings: Mapped[list["EventActionBinding"]] = relationship(
        back_populates="event_type", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_event_types_name", "name"),
    )


class Action(TimestampMixin, Base):
    __tablename__ = "actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(255))

    bindings: Mapped[list["EventActionBinding"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_actions_type", "type"),
    )


class EventActionBinding(TimestampMixin, Base):
    __tablename__ = "event_action_bindings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    event_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_types.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.id", ondelete="CASCADE"), nullable=False
    )
    filter_json: Mapped[dict | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    event_type: Mapped["EventType"] = relationship(back_populates="bindings")
    action: Mapped["Action"] = relationship(back_populates="bindings")
    executions: Mapped[list["ActionExecution"]] = relationship(
        back_populates="binding", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_event_action_bindings_event_type_id", "event_type_id"),
        Index("ix_event_action_bindings_action_id", "action_id"),
        Index("ix_event_action_bindings_enabled", "enabled"),
    )


class ActionExecution(Base):
    __tablename__ = "action_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    event_action_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_action_bindings.id", ondelete="CASCADE"), nullable=False
    )
    event_data_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ActionExecutionStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    binding: Mapped["EventActionBinding"] = relationship(back_populates="executions")

    __table_args__ = (
        Index("ix_action_executions_binding_id", "event_action_binding_id"),
        Index("ix_action_executions_status", "status"),
        Index("ix_action_executions_executed_at", "executed_at"),
    )
