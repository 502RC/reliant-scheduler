import uuid
from datetime import datetime

from pydantic import BaseModel


class ConnectionCreate(BaseModel):
    name: str
    connection_type: str
    host: str | None = None
    port: int | None = None
    description: str | None = None
    extra: dict | None = None
    credential_id: uuid.UUID | None = None


class ConnectionUpdate(BaseModel):
    name: str | None = None
    connection_type: str | None = None
    host: str | None = None
    port: int | None = None
    description: str | None = None
    extra: dict | None = None
    credential_id: uuid.UUID | None = None


class ConnectionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    connection_type: str
    host: str | None
    port: int | None
    description: str | None
    extra: dict | None
    credential_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
