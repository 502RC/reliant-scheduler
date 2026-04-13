"""Add credentials table and credential_id FK to connections

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("credential_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("fields", postgresql.JSONB, nullable=True),
        sa.Column("secret_refs", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_credentials_type", "credentials", ["credential_type"])
    op.create_index("ix_credentials_name", "credentials", ["name"])

    # Add nullable credential_id FK to connections
    op.add_column(
        "connections",
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_connections_credential_id",
        "connections",
        "credentials",
        ["credential_id"],
        ["id"],
    )
    op.create_index("ix_connections_credential_id", "connections", ["credential_id"])


def downgrade() -> None:
    op.drop_index("ix_connections_credential_id", table_name="connections")
    op.drop_constraint("fk_connections_credential_id", "connections", type_="foreignkey")
    op.drop_column("connections", "credential_id")
    op.drop_index("ix_credentials_name", table_name="credentials")
    op.drop_index("ix_credentials_type", table_name="credentials")
    op.drop_table("credentials")
