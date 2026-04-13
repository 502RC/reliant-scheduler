"""Add calendar tables: calendars, calendar_dates, calendar_rules, job_calendar_associations

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Calendars
    op.create_table(
        "calendars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("calendar_type", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calendars_type", "calendars", ["calendar_type"])

    # Calendar Dates
    op.create_table(
        "calendar_dates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "calendar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("is_business_day", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("label", sa.String(255), nullable=True),
        sa.UniqueConstraint("calendar_id", "date", name="uq_calendar_date"),
    )
    op.create_index("ix_calendar_dates_calendar_id", "calendar_dates", ["calendar_id"])
    op.create_index("ix_calendar_dates_date", "calendar_dates", ["date"])

    # Calendar Rules
    op.create_table(
        "calendar_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "calendar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=True),
        sa.Column("month", sa.Integer, nullable=True),
        sa.Column("day_of_month", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calendar_rules_calendar_id", "calendar_rules", ["calendar_id"])

    # Job Calendar Associations
    op.create_table(
        "job_calendar_associations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "calendar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("constraint_type", sa.String(64), nullable=False),
        sa.Column("dst_policy", sa.String(32), nullable=False, server_default="skip"),
        sa.UniqueConstraint("job_id", "calendar_id", name="uq_job_calendar"),
    )
    op.create_index("ix_job_calendar_job_id", "job_calendar_associations", ["job_id"])
    op.create_index("ix_job_calendar_calendar_id", "job_calendar_associations", ["calendar_id"])


def downgrade() -> None:
    op.drop_table("job_calendar_associations")
    op.drop_table("calendar_rules")
    op.drop_table("calendar_dates")
    op.drop_table("calendars")
