"""Add RBAC tables: users, workgroups, workgroup_members, security_policies, audit_log

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entra_object_id", sa.String(128), unique=True, nullable=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="inquiry"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_entra_object_id", "users", ["entra_object_id"])
    op.create_index("ix_users_role", "users", ["role"])

    # Workgroups
    op.create_table(
        "workgroups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Workgroup Members
    op.create_table(
        "workgroup_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workgroup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workgroups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.UniqueConstraint("user_id", "workgroup_id", name="uq_workgroup_member"),
    )
    op.create_index("ix_workgroup_members_user_id", "workgroup_members", ["user_id"])
    op.create_index("ix_workgroup_members_workgroup_id", "workgroup_members", ["workgroup_id"])

    # Security Policies
    op.create_table(
        "security_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("principal_type", sa.String(32), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_policies_principal", "security_policies", ["principal_type", "principal_id"])
    op.create_index("ix_security_policies_resource", "security_policies", ["resource_type", "resource_id"])

    # Audit Log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details_json", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_resource", "audit_log", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("security_policies")
    op.drop_table("workgroup_members")
    op.drop_table("workgroups")
    op.drop_table("users")
