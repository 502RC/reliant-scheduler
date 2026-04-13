"""Tests for cron expression validation at schedule creation time."""

import uuid

import pytest
from pydantic import ValidationError

from reliant_scheduler.schemas.schedule import ScheduleCreate, ScheduleUpdate


def test_valid_cron_expression() -> None:
    """A standard 5-field cron expression should pass validation."""
    schedule = ScheduleCreate(
        job_id=uuid.uuid4(),
        trigger_type="cron",
        cron_expression="0 2 * * *",
    )
    assert schedule.cron_expression == "0 2 * * *"


def test_invalid_cron_expression_rejected() -> None:
    """A malformed cron expression should raise a validation error."""
    with pytest.raises(ValidationError, match="Invalid cron expression"):
        ScheduleCreate(
            job_id=uuid.uuid4(),
            trigger_type="cron",
            cron_expression="not-a-cron",
        )


def test_cron_trigger_requires_expression() -> None:
    """A cron trigger without a cron_expression should raise."""
    with pytest.raises(ValidationError, match="cron_expression is required"):
        ScheduleCreate(
            job_id=uuid.uuid4(),
            trigger_type="cron",
            cron_expression=None,
        )


def test_event_trigger_accepts_no_cron() -> None:
    """Non-cron triggers should not require a cron expression."""
    schedule = ScheduleCreate(
        job_id=uuid.uuid4(),
        trigger_type="event",
        event_source="deployment",
    )
    assert schedule.cron_expression is None


def test_update_with_invalid_cron_rejected() -> None:
    """Updating to an invalid cron expression should fail."""
    with pytest.raises(ValidationError, match="Invalid cron expression"):
        ScheduleUpdate(cron_expression="bad bad bad")


def test_update_with_valid_cron() -> None:
    """Updating with a valid cron expression should pass."""
    update = ScheduleUpdate(cron_expression="*/15 * * * *")
    assert update.cron_expression == "*/15 * * * *"
