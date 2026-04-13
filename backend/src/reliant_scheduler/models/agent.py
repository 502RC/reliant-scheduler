import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class AgentStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[AgentStatus] = mapped_column(String(32), nullable=False, default=AgentStatus.OFFLINE)
    labels: Mapped[dict | None] = mapped_column(JSONB)
    max_concurrent_jobs: Mapped[int] = mapped_column(default=4)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_version: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_agents_status", "status"),
    )
