"""Add SLA tables: sla_policies, sla_job_constraints, sla_events

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SLA Policies
    op.create_table(
        "sla_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_completion_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_window_minutes", sa.Integer, nullable=False),
        sa.Column("breach_window_minutes", sa.Integer, nullable=False),
        sa.Column("notification_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sla_policies_name", "sla_policies", ["name"])

    # SLA Job Constraints
    op.create_table(
        "sla_job_constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sla_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sla_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("track_critical_path", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_duration_minutes", sa.Integer, nullable=True),
        sa.Column("priority_override", sa.Integer, nullable=True),
        sa.UniqueConstraint("sla_policy_id", "job_id", name="uq_sla_policy_job"),
    )
    op.create_index("ix_sla_constraints_policy_id", "sla_job_constraints", ["sla_policy_id"])
    op.create_index("ix_sla_constraints_job_id", "sla_job_constraints", ["job_id"])

    # SLA Events
    op.create_table(
        "sla_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sla_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sla_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("details_json", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_sla_events_policy_id", "sla_events", ["sla_policy_id"])
    op.create_index("ix_sla_events_event_type", "sla_events", ["event_type"])
    op.create_index("ix_sla_events_triggered_at", "sla_events", ["triggered_at"])


def downgrade() -> None:
    op.drop_table("sla_events")
    op.drop_table("sla_job_constraints")
    op.drop_table("sla_policies")
