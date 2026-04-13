import uuid
from datetime import datetime

from pydantic import BaseModel


class AgentRegisterRequest(BaseModel):
    hostname: str
    labels: dict | None = None
    max_concurrent_jobs: int = 4


class AgentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    hostname: str
    status: str
    labels: dict | None
    max_concurrent_jobs: int
    last_heartbeat_at: datetime | None
    agent_version: str | None
    created_at: datetime
    updated_at: datetime
