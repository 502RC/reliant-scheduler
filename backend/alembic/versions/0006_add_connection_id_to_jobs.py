"""Add connection_id FK to jobs table and SSH to connection_type enum

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_connection_id",
        "jobs",
        "connections",
        ["connection_id"],
        ["id"],
    )
    op.create_index("ix_jobs_connection_id", "jobs", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_connection_id", table_name="jobs")
    op.drop_constraint("fk_jobs_connection_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "connection_id")
