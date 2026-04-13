"""Add event-action automation tables: event_types, actions, event_action_bindings, action_executions

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Event Types
    op.create_table(
        "event_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_event_types_name", "event_types", ["name"])

    # Actions
    op.create_table(
        "actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_actions_type", "actions", ["type"])

    # Event-Action Bindings
    op.create_table(
        "event_action_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filter_json", postgresql.JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_event_action_bindings_event_type_id", "event_action_bindings", ["event_type_id"])
    op.create_index("ix_event_action_bindings_action_id", "event_action_bindings", ["action_id"])
    op.create_index("ix_event_action_bindings_enabled", "event_action_bindings", ["enabled"])

    # Action Executions
    op.create_table(
        "action_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_action_binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event_action_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_data_json", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_action_executions_binding_id", "action_executions", ["event_action_binding_id"])
    op.create_index("ix_action_executions_status", "action_executions", ["status"])
    op.create_index("ix_action_executions_executed_at", "action_executions", ["executed_at"])

    # Seed system event types
    op.execute(
        """
        INSERT INTO event_types (id, name, description) VALUES
            (gen_random_uuid(), 'job.started', 'Emitted when a job run is queued for execution'),
            (gen_random_uuid(), 'job.succeeded', 'Emitted when a job run completes successfully'),
            (gen_random_uuid(), 'job.failed', 'Emitted when a job run fails'),
            (gen_random_uuid(), 'job.timed_out', 'Emitted when a job run exceeds its timeout'),
            (gen_random_uuid(), 'sla.at_risk', 'Emitted when an SLA policy enters the risk window'),
            (gen_random_uuid(), 'sla.breached', 'Emitted when an SLA policy is breached'),
            (gen_random_uuid(), 'sla.met', 'Emitted when an SLA policy target is met'),
            (gen_random_uuid(), 'agent.offline', 'Emitted when a worker agent goes offline'),
            (gen_random_uuid(), 'agent.heartbeat_missed', 'Emitted when a worker agent misses its heartbeat'),
            (gen_random_uuid(), 'schedule.missed', 'Emitted when a scheduled run cannot execute')
        """
    )


def downgrade() -> None:
    op.drop_table("action_executions")
    op.drop_table("event_action_bindings")
    op.drop_table("actions")
    op.drop_table("event_types")
