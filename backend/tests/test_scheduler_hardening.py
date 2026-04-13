"""Tests for scheduler hardening: error handling, dependency enforcement, event triggers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reliant_scheduler.models.job_run import RunStatus
from reliant_scheduler.services.scheduler import Scheduler


@pytest.fixture
def scheduler() -> Scheduler:
    return Scheduler()


class TestTickErrorHandling:
    """scheduler.tick() should propagate exceptions after logging them."""

    async def test_tick_logs_and_reraises_on_error(self, scheduler: Scheduler) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db gone"))
        # mark_stale_agents will use the session and fail
        scheduler.agents.mark_stale_agents = AsyncMock(side_effect=RuntimeError("db gone"))

        with pytest.raises(RuntimeError, match="db gone"):
            await scheduler.tick(session)


class TestDependencyEnforcement:
    """_dependencies_satisfied checks upstream run status."""

    async def test_no_dependencies_satisfied(self, scheduler: Scheduler) -> None:
        session = AsyncMock()
        # No dependencies for this job
        deps_result = MagicMock()
        deps_result.all.return_value = []
        session.execute = AsyncMock(return_value=deps_result)

        result = await scheduler._dependencies_satisfied(session, uuid.uuid4())
        assert result is True

    async def test_upstream_success_satisfies(self, scheduler: Scheduler) -> None:
        session = AsyncMock()
        job_id = uuid.uuid4()
        upstream_id = uuid.uuid4()

        # First call: get dependencies → returns one upstream
        deps_result = MagicMock()
        deps_result.all.return_value = [(upstream_id,)]

        # Second call: get latest run of upstream → SUCCESS
        latest_run = MagicMock()
        latest_run.status = RunStatus.SUCCESS
        latest_run_result = MagicMock()
        latest_run_result.scalar_one_or_none.return_value = latest_run

        session.execute = AsyncMock(side_effect=[deps_result, latest_run_result])

        result = await scheduler._dependencies_satisfied(session, job_id)
        assert result is True

    async def test_upstream_failure_blocks(self, scheduler: Scheduler) -> None:
        session = AsyncMock()
        job_id = uuid.uuid4()
        upstream_id = uuid.uuid4()

        deps_result = MagicMock()
        deps_result.all.return_value = [(upstream_id,)]

        latest_run = MagicMock()
        latest_run.status = RunStatus.FAILED
        latest_run_result = MagicMock()
        latest_run_result.scalar_one_or_none.return_value = latest_run

        session.execute = AsyncMock(side_effect=[deps_result, latest_run_result])

        result = await scheduler._dependencies_satisfied(session, job_id)
        assert result is False

    async def test_no_upstream_run_blocks(self, scheduler: Scheduler) -> None:
        session = AsyncMock()
        job_id = uuid.uuid4()
        upstream_id = uuid.uuid4()

        deps_result = MagicMock()
        deps_result.all.return_value = [(upstream_id,)]

        latest_run_result = MagicMock()
        latest_run_result.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(side_effect=[deps_result, latest_run_result])

        result = await scheduler._dependencies_satisfied(session, job_id)
        assert result is False


class TestEventTriggerIntegration:
    """handle_event should create runs for matching event schedules."""

    async def test_handle_event_creates_runs(self, scheduler: Scheduler) -> None:
        session = AsyncMock()

        # Simulate one event schedule that matches the filter
        mock_schedule = MagicMock()
        mock_schedule.job_id = uuid.uuid4()
        mock_schedule.event_filter = {"type": "deploy"}
        mock_schedule.event_source = "ci"
        mock_schedule.enabled = True
        mock_schedule.trigger_type = "event"

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [mock_schedule]
        session.execute = AsyncMock(return_value=result_mock)

        created = await scheduler.handle_event(session, {"type": "deploy", "env": "prod"})
        assert created == 1
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_handle_event_skips_non_matching(self, scheduler: Scheduler) -> None:
        session = AsyncMock()

        mock_schedule = MagicMock()
        mock_schedule.job_id = uuid.uuid4()
        mock_schedule.event_filter = {"type": "build"}
        mock_schedule.event_source = "ci"

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [mock_schedule]
        session.execute = AsyncMock(return_value=result_mock)

        created = await scheduler.handle_event(session, {"type": "deploy"})
        assert created == 0
        session.add.assert_not_called()
