import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from reliant_scheduler.models.job_run import RunStatus


class JobRunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    job_id: uuid.UUID
    agent_id: uuid.UUID | None
    status: str
    triggered_by: str
    parameters: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    error_message: str | None
    log_url: str | None
    metrics: dict | None
    attempt_number: int
    created_at: datetime
    updated_at: datetime


class JobRunUpdate(BaseModel):
    """Schema for workers to report execution results."""

    status: str
    exit_code: int | None = None
    error_message: str | None = None
    log_url: str | None = None
    metrics: dict | None = None
    agent_id: uuid.UUID | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {s.value for s in RunStatus}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v
