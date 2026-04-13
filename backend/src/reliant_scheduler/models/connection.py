import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class ConnectionType(StrEnum):
    SSH = "ssh"
    DATABASE = "database"
    REST_API = "rest_api"
    SFTP = "sftp"
    AZURE_BLOB = "azure_blob"
    AZURE_SERVICEBUS = "azure_servicebus"
    AZURE_EVENTHUB = "azure_eventhub"
    WINRM = "winrm"
    CUSTOM = "custom"


class Connection(TimestampMixin, Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    connection_type: Mapped[ConnectionType] = mapped_column(String(64), nullable=False)
    host: Mapped[str | None] = mapped_column(String(512))
    port: Mapped[int | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credentials.id"), nullable=True
    )
    credential: Mapped["Credential | None"] = relationship()

    __table_args__ = (
        Index("ix_connections_type", "connection_type"),
        Index("ix_connections_credential_id", "credential_id"),
    )


from reliant_scheduler.models.credential import Credential  # noqa: E402
