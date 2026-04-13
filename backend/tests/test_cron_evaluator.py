from datetime import datetime, timezone

import pytest

from reliant_scheduler.services.cron_evaluator import CronEvaluator


@pytest.fixture
def evaluator() -> CronEvaluator:
    return CronEvaluator()


def test_get_next_run_daily(evaluator: CronEvaluator) -> None:
    """'0 2 * * *' after midnight should be 2 AM same day."""
    base = datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc)
    next_run = evaluator.get_next_run("0 2 * * *", "UTC", base)
    assert next_run.hour == 2
    assert next_run.day == 9


def test_get_next_run_past_time(evaluator: CronEvaluator) -> None:
    """If base is after the cron time, next run should be next day."""
    base = datetime(2026, 4, 9, 3, 0, tzinfo=timezone.utc)
    next_run = evaluator.get_next_run("0 2 * * *", "UTC", base)
    assert next_run.day == 10


def test_get_next_run_weekly(evaluator: CronEvaluator) -> None:
    """Weekly on Monday at 6 AM."""
    # 2026-04-09 is Thursday
    base = datetime(2026, 4, 9, 0, 0, tzinfo=timezone.utc)
    next_run = evaluator.get_next_run("0 6 * * 1", "UTC", base)
    assert next_run.weekday() == 0  # Monday
    assert next_run.hour == 6
