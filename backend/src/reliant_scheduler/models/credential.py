import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class CredentialType(StrEnum):
    WINDOWS_AD = "windows_ad"
    SSH_PASSWORD = "ssh_password"
    SSH_PRIVATE_KEY = "ssh_private_key"
    API_KEY = "api_key"
    API_KEY_SECRET = "api_key_secret"
    BEARER_TOKEN = "bearer_token"
    OAUTH2_CLIENT = "oauth2_client"
    DATABASE = "database"
    SMTP = "smtp"
    AZURE_SERVICE_PRINCIPAL = "azure_service_principal"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


class Credential(TimestampMixin, Base):
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    credential_type: Mapped[CredentialType] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Non-secret fields stored directly: {"username": "svc_reliant", "domain": "CUROHS"}
    fields: Mapped[dict | None] = mapped_column(JSONB)
    # Key Vault secret name references: {"password": "reliant-cred-abc123-password"}
    secret_refs: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_credentials_type", "credential_type"),
        Index("ix_credentials_name", "name"),
    )
