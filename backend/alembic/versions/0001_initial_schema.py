"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Environments
    op.create_table(
        "environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("variables", postgresql.JSONB),
        sa.Column("is_production", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Connections
    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("connection_type", sa.String(64), nullable=False),
        sa.Column("host", sa.String(512)),
        sa.Column("port", sa.Integer),
        sa.Column("description", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_connections_type", "connections", ["connection_type"])

    # Agents
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hostname", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="offline"),
        sa.Column("labels", postgresql.JSONB),
        sa.Column("max_concurrent_jobs", sa.Integer, default=4),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("agent_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agents_status", "agents", ["status"])

    # Jobs
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("command", sa.Text),
        sa.Column("parameters", postgresql.JSONB),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("environments.id")),
        sa.Column("max_retries", sa.Integer, default=0),
        sa.Column("timeout_seconds", sa.Integer, default=3600),
        sa.Column("tags", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_environment_id", "jobs", ["environment_id"])

    # Job Dependencies
    op.create_table(
        "job_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dependent_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_job_deps_dependent", "job_dependencies", ["dependent_job_id"])
    op.create_index("ix_job_deps_depends_on", "job_dependencies", ["depends_on_job_id"])

    # Schedules
    op.create_table(
        "schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("cron_expression", sa.String(128)),
        sa.Column("timezone", sa.String(64), server_default="UTC"),
        sa.Column("event_source", sa.String(255)),
        sa.Column("event_filter", postgresql.JSONB),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Job Runs
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(64), nullable=False, server_default="schedule"),
        sa.Column("parameters", postgresql.JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("exit_code", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("log_url", sa.String(1024)),
        sa.Column("metrics", postgresql.JSONB),
        sa.Column("attempt_number", sa.Integer, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_runs_job_id_status", "job_runs", ["job_id", "status"])
    op.create_index("ix_job_runs_started_at", "job_runs", ["started_at"])
    op.create_index("ix_job_runs_agent_id", "job_runs", ["agent_id"])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("schedules")
    op.drop_table("job_dependencies")
    op.drop_table("jobs")
    op.drop_table("agents")
    op.drop_table("connections")
    op.drop_table("environments")
