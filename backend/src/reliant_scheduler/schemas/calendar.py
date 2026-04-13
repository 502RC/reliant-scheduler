import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Calendar ---

class CalendarCreate(BaseModel):
    name: str = Field(max_length=255)
    calendar_type: str  # business, financial, holiday, custom
    timezone: str = "UTC"
    description: str | None = None


class CalendarUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    calendar_type: str | None = None
    timezone: str | None = None
    description: str | None = None


class CalendarResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    calendar_type: str
    timezone: str
    description: str | None
    created_by: uuid.UUID | None
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


# --- Calendar Dates ---

class CalendarDateCreate(BaseModel):
    date: date
    is_business_day: bool = True
    label: str | None = None


class CalendarDateBulkCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    weekdays_only: bool = True
    holidays: list[CalendarDateCreate] = []


class CalendarDateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    calendar_id: uuid.UUID
    date: date
    is_business_day: bool
    label: str | None


# --- Calendar Rules ---

class CalendarRuleCreate(BaseModel):
    rule_type: str  # recurring, one_time
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    month: int | None = Field(default=None, ge=1, le=12)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    description: str | None = None


class CalendarRuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    calendar_id: uuid.UUID
    rule_type: str
    day_of_week: int | None
    month: int | None
    day_of_month: int | None
    description: str | None
    created_at: datetime
    updated_at: datetime


# --- Job Calendar Association ---

class JobCalendarAssociationCreate(BaseModel):
    calendar_id: uuid.UUID
    constraint_type: str  # run_only_on_business_days, skip_holidays, custom
    dst_policy: str = "skip"  # skip, run_after


class JobCalendarAssociationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    job_id: uuid.UUID
    calendar_id: uuid.UUID
    constraint_type: str
    dst_policy: str
