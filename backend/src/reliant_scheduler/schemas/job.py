import uuid
from datetime import datetime

from pydantic import BaseModel


class JobCreate(BaseModel):
    name: str
    description: str | None = None
    job_type: str
    command: str | None = None
    parameters: dict | None = None
    connection_id: uuid.UUID | None = None
    environment_id: uuid.UUID | None = None
    max_retries: int = 0
    timeout_seconds: int = 3600
    tags: dict | None = None


class JobUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    job_type: str | None = None
    command: str | None = None
    parameters: dict | None = None
    connection_id: uuid.UUID | None = None
    environment_id: uuid.UUID | None = None
    max_retries: int | None = None
    timeout_seconds: int | None = None
    tags: dict | None = None


class JobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    job_type: str
    command: str | None
    parameters: dict | None
    connection_id: uuid.UUID | None
    environment_id: uuid.UUID | None
    max_retries: int
    timeout_seconds: int
    tags: dict | None
    created_at: datetime
    updated_at: datetime


class JobWithRunInfoResponse(JobResponse):
    """Job response enriched with latest run info and next schedule time."""

    last_run_status: str | None = None
    last_run_time: datetime | None = None
    last_run_id: uuid.UUID | None = None
    next_scheduled_run: datetime | None = None
    is_running: bool = False


class JobTriggerRequest(BaseModel):
    parameters: dict | None = None


class JobDependencyCreate(BaseModel):
    depends_on_job_id: uuid.UUID


class JobDependencyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    dependent_job_id: uuid.UUID
    depends_on_job_id: uuid.UUID
