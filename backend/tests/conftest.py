"""Shared fixtures for integration tests.

Spins up a real PostgreSQL 16 container via testcontainers and provides
an async httpx client wired to the FastAPI app with a test database.

The container is session-scoped. The engine is created per test function
because asyncpg connections are bound to the event loop that created them,
and pytest-asyncio 0.26 gives each test its own loop by default.
"""

import os
from collections.abc import AsyncGenerator

# Ensure POSTGRES_PASSWORD is set before any app module import triggers Settings()
os.environ.setdefault("POSTGRES_PASSWORD", "testcontainers")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from reliant_scheduler.core.database import Base, get_db
from reliant_scheduler.main import app

# Disable Ryuk (not needed with podman and avoids extra container overhead)
os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"
# Point testcontainers at the podman socket
_uid = os.getuid()
_podman_sock = f"/run/user/{_uid}/podman/podman.sock"
if os.path.exists(_podman_sock):
    os.environ.setdefault("DOCKER_HOST", f"unix:///{_podman_sock}")

# Track if schema has been created (only needs to happen once since the
# container is session-scoped and schema DDL is idempotent).
_schema_initialized = False


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start a PostgreSQL 16 container and return the asyncpg connection URL."""
    with PostgresContainer("postgres:16", driver=None) as pg:
        sync_url = pg.get_connection_url()
        async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        yield async_url


@pytest_asyncio.fixture
async def test_session_factory(postgres_url: str):
    """Per-test engine and session factory.

    Creates the engine on the current test's event loop, initializes the
    schema on first use, and disposes cleanly after the test.
    """
    global _schema_initialized
    engine = create_async_engine(postgres_url, echo=False, pool_size=5)

    if not _schema_initialized:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _schema_initialized = True

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory

    # Truncate all tables after the test for isolation
    async with factory() as session:
        await session.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE action_executions, event_action_bindings, actions, event_types, "
                "sla_events, sla_job_constraints, sla_policies, "
                "job_calendar_associations, calendar_rules, calendar_dates, "
                "calendars, audit_log, security_policies, workgroup_members, "
                "workgroups, users, job_runs, job_dependencies, schedules, jobs, "
                "agents, connections, environments CASCADE"
            )
        )
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests that interact with the DB directly."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session_factory) -> AsyncGenerator[AsyncClient, None]:
    """Async httpx client with the app's get_db overridden to use the test DB."""

    async def _override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
