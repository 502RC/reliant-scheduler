import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, Index, Boolean, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reliant_scheduler.core.database import Base
from reliant_scheduler.models.base import TimestampMixin, generate_uuid


class UserRole(StrEnum):
    SCHEDULER_ADMINISTRATOR = "scheduler_administrator"
    ADMINISTRATOR = "administrator"
    SCHEDULER = "scheduler"
    OPERATOR = "operator"
    USER = "user"
    INQUIRY = "inquiry"


# Ordered from highest to lowest privilege
ROLE_HIERARCHY: list[UserRole] = [
    UserRole.SCHEDULER_ADMINISTRATOR,
    UserRole.ADMINISTRATOR,
    UserRole.SCHEDULER,
    UserRole.OPERATOR,
    UserRole.USER,
    UserRole.INQUIRY,
]


def role_level(role: UserRole) -> int:
    """Return numeric level for a role (higher = more privileged)."""
    return len(ROLE_HIERARCHY) - ROLE_HIERARCHY.index(role)


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    entra_object_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(32), nullable=False, default=UserRole.INQUIRY)
    status: Mapped[UserStatus] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workgroup_memberships: Mapped[list["WorkgroupMember"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_entra_object_id", "entra_object_id"),
        Index("ix_users_role", "role"),
    )


class Workgroup(TimestampMixin, Base):
    __tablename__ = "workgroups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    members: Mapped[list["WorkgroupMember"]] = relationship(back_populates="workgroup", cascade="all, delete-orphan")


class WorkgroupRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class WorkgroupMember(Base):
    __tablename__ = "workgroup_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workgroup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workgroups.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[WorkgroupRole] = mapped_column(String(32), nullable=False, default=WorkgroupRole.MEMBER)

    user: Mapped["User"] = relationship(back_populates="workgroup_memberships")
    workgroup: Mapped["Workgroup"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "workgroup_id", name="uq_workgroup_member"),
        Index("ix_workgroup_members_user_id", "user_id"),
        Index("ix_workgroup_members_workgroup_id", "workgroup_id"),
    )


class SecurityPolicy(TimestampMixin, Base):
    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)  # job, schedule, connection, calendar, environment
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # None = all resources of type
    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)  # user, workgroup
    principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)  # read, write, execute, admin

    __table_args__ = (
        Index("ix_security_policies_principal", "principal_type", "principal_id"),
        Index("ix_security_policies_resource", "resource_type", "resource_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_log_user_id", "user_id"),
        Index("ix_audit_log_timestamp", "timestamp"),
        Index("ix_audit_log_resource", "resource_type", "resource_id"),
    )
