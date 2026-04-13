import uuid
from datetime import datetime

from croniter import croniter
from pydantic import BaseModel, model_validator


def _validate_cron(trigger_type: str | None, cron_expression: str | None) -> None:
    """Raise ValueError if a cron trigger has an invalid expression."""
    if trigger_type == "cron" and cron_expression:
        if not croniter.is_valid(cron_expression):
            raise ValueError(
                f"Invalid cron expression: '{cron_expression}'. "
                "Expected 5-field format: minute hour day-of-month month day-of-week"
            )
    if trigger_type == "cron" and not cron_expression:
        raise ValueError("cron_expression is required when trigger_type is 'cron'")


class ScheduleCreate(BaseModel):
    job_id: uuid.UUID
    trigger_type: str
    cron_expression: str | None = None
    timezone: str = "UTC"
    event_source: str | None = None
    event_filter: dict | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_cron_expression(self) -> "ScheduleCreate":
        _validate_cron(self.trigger_type, self.cron_expression)
        return self


class ScheduleUpdate(BaseModel):
    trigger_type: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    event_source: str | None = None
    event_filter: dict | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_cron_expression(self) -> "ScheduleUpdate":
        if self.cron_expression is not None:
            _validate_cron(self.trigger_type or "cron", self.cron_expression)
        return self


class ScheduleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    job_id: uuid.UUID
    trigger_type: str
    cron_expression: str | None
    timezone: str
    event_source: str | None
    event_filter: dict | None
    enabled: bool
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
