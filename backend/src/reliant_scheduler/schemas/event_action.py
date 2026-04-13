"""Pydantic schemas for event-action automation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

class EventTypeCreate(BaseModel):
    name: str
    description: str | None = None


class EventTypeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionCreate(BaseModel):
    name: str
    type: str
    config_json: dict = {}
    created_by: str | None = None

    @field_validator("type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        allowed = {"email", "webhook", "slack", "teams", "itsm_incident", "recovery_job"}
        if v not in allowed:
            raise ValueError(f"Action type must be one of: {', '.join(sorted(allowed))}")
        return v


class ActionUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    config_json: dict | None = None

    @field_validator("type")
    @classmethod
    def validate_action_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"email", "webhook", "slack", "teams", "itsm_incident", "recovery_job"}
        if v not in allowed:
            raise ValueError(f"Action type must be one of: {', '.join(sorted(allowed))}")
        return v


class ActionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    type: str
    config_json: dict
    created_by: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Event-Action Bindings
# ---------------------------------------------------------------------------

class EventActionBindingCreate(BaseModel):
    event_type_id: uuid.UUID
    action_id: uuid.UUID
    filter_json: dict | None = None
    enabled: bool = True


class EventActionBindingUpdate(BaseModel):
    filter_json: dict | None = None
    enabled: bool | None = None


class EventActionBindingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    event_type_id: uuid.UUID
    action_id: uuid.UUID
    filter_json: dict | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Action Executions
# ---------------------------------------------------------------------------

class ActionExecutionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    event_action_binding_id: uuid.UUID
    event_data_json: dict | None
    status: str
    error_message: str | None
    attempt_number: int
    executed_at: datetime


# ---------------------------------------------------------------------------
# Test Action Request
# ---------------------------------------------------------------------------

class ActionTestRequest(BaseModel):
    sample_event_data: dict = {}
