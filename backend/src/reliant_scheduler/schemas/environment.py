import uuid
from datetime import datetime

from pydantic import BaseModel


class EnvironmentCreate(BaseModel):
    name: str
    description: str | None = None
    variables: dict | None = None
    is_production: bool = False


class EnvironmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    variables: dict | None = None
    is_production: bool | None = None


class EnvironmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    variables: dict | None
    is_production: bool
    created_at: datetime
    updated_at: datetime
