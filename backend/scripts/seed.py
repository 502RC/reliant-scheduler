"""Seed local dev database with sample data."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import async_session, engine, Base
from reliant_scheduler.models import Environment, Connection, Agent, Job, Schedule, JobRun


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Environments
        dev_env = Environment(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="development",
            description="Local development environment",
            variables={"LOG_LEVEL": "DEBUG", "REGION": "local"},
            is_production=False,
        )
        staging_env = Environment(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            name="staging",
            description="Pre-production staging environment",
            variables={"LOG_LEVEL": "INFO", "REGION": "eastus2"},
            is_production=False,
        )
        prod_env = Environment(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            name="production",
            description="Production environment",
            variables={"LOG_LEVEL": "WARN", "REGION": "eastus2"},
            is_production=True,
        )
        session.add_all([dev_env, staging_env, prod_env])

        # Connections
        session.add_all([
            Connection(
                name="primary-postgres",
                connection_type="database",
                host="localhost",
                port=5432,
                description="Primary PostgreSQL database",
            ),
            Connection(
                name="blob-storage",
                connection_type="azure_blob",
                description="Azure Blob Storage for artifacts",
                extra={"container": "workload-artifacts"},
            ),
        ])

        # Agents
        agent1 = Agent(
            id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
            hostname="worker-node-01",
            status="online",
            labels={"pool": "general", "os": "linux"},
            max_concurrent_jobs=4,
            agent_version="0.1.0",
        )
        agent2 = Agent(
            id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
            hostname="worker-node-02",
            status="online",
            labels={"pool": "gpu", "os": "linux"},
            max_concurrent_jobs=2,
            agent_version="0.1.0",
        )
        session.add_all([agent1, agent2])

        # Jobs
        etl_job = Job(
            id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
            name="daily-etl-pipeline",
            description="Extract, transform, and load data from source systems",
            job_type="python_script",
            command="python -m etl.pipeline --full",
            environment_id=dev_env.id,
            max_retries=2,
            timeout_seconds=7200,
            tags={"team": "data-engineering", "priority": "high"},
        )
        report_job = Job(
            id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
            name="weekly-report-generation",
            description="Generate and distribute weekly KPI reports",
            job_type="shell_command",
            command="bash /opt/scripts/generate_reports.sh",
            environment_id=dev_env.id,
            timeout_seconds=3600,
            tags={"team": "analytics"},
        )
        cleanup_job = Job(
            id=uuid.UUID("00000000-0000-0000-0000-000000000022"),
            name="nightly-cleanup",
            description="Clean up temporary files and expired sessions",
            job_type="shell_command",
            command="bash /opt/scripts/cleanup.sh",
            environment_id=dev_env.id,
            tags={"team": "platform"},
        )
        session.add_all([etl_job, report_job, cleanup_job])

        # Schedules
        session.add_all([
            Schedule(
                job_id=etl_job.id,
                trigger_type="cron",
                cron_expression="0 2 * * *",
                timezone="America/New_York",
                enabled=True,
            ),
            Schedule(
                job_id=report_job.id,
                trigger_type="cron",
                cron_expression="0 6 * * 1",
                timezone="America/New_York",
                enabled=True,
            ),
            Schedule(
                job_id=cleanup_job.id,
                trigger_type="cron",
                cron_expression="0 3 * * *",
                timezone="UTC",
                enabled=True,
            ),
        ])

        # Sample job runs
        session.add_all([
            JobRun(
                job_id=etl_job.id,
                agent_id=agent1.id,
                status="success",
                triggered_by="schedule",
                exit_code=0,
                metrics={"rows_processed": 150000, "duration_sec": 423},
            ),
            JobRun(
                job_id=cleanup_job.id,
                agent_id=agent2.id,
                status="success",
                triggered_by="schedule",
                exit_code=0,
            ),
        ])

        await session.commit()
        print("Seed data loaded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
