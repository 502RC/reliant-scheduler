import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class SLAPolicyCreate(BaseModel):
    name: str
    description: str | None = None
    target_completion_time: datetime
    risk_window_minutes: int
    breach_window_minutes: int
    notification_policy_id: uuid.UUID | None = None

    @field_validator("risk_window_minutes", "breach_window_minutes")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Must be a positive integer")
        return v


class SLAPolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_completion_time: datetime | None = None
    risk_window_minutes: int | None = None
    breach_window_minutes: int | None = None
    notification_policy_id: uuid.UUID | None = None

    @field_validator("risk_window_minutes", "breach_window_minutes")
    @classmethod
    def validate_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("Must be a positive integer")
        return v


class SLAPolicyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    target_completion_time: datetime
    risk_window_minutes: int
    breach_window_minutes: int
    notification_policy_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SLAJobConstraintCreate(BaseModel):
    job_id: uuid.UUID
    track_critical_path: bool = False
    max_duration_minutes: int | None = None
    priority_override: int | None = None

    @field_validator("max_duration_minutes")
    @classmethod
    def validate_max_duration(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("Must be a positive integer")
        return v


class SLAJobConstraintResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    sla_policy_id: uuid.UUID
    job_id: uuid.UUID
    track_critical_path: bool
    max_duration_minutes: int | None
    priority_override: int | None


class SLAEventResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    sla_policy_id: uuid.UUID
    job_run_id: uuid.UUID | None
    event_type: str
    triggered_at: datetime
    details_json: dict | None


class CriticalPathNode(BaseModel):
    job_id: uuid.UUID
    job_name: str
    estimated_duration_minutes: int
    dependencies: list[uuid.UUID]


class CriticalPathResponse(BaseModel):
    sla_policy_id: uuid.UUID
    path: list[CriticalPathNode]
    total_duration_minutes: int


class SLAStatusResponse(BaseModel):
    sla_policy_id: uuid.UUID
    status: str
    target_completion_time: datetime
    estimated_completion_time: datetime | None
    remaining_duration_minutes: int
    risk_window_minutes: int
    breach_window_minutes: int
