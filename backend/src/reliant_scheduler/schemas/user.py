import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: str
    display_name: str
    role: str = "inquiry"
    entra_object_id: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    status: str | None = None


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    entra_object_id: str | None
    email: str
    display_name: str
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkgroupCreate(BaseModel):
    name: str
    description: str | None = None


class WorkgroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkgroupResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorkgroupMemberAdd(BaseModel):
    user_id: uuid.UUID
    role: str = "member"


class WorkgroupMemberResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    workgroup_id: uuid.UUID
    role: str


class SecurityPolicyCreate(BaseModel):
    name: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    principal_type: str
    principal_id: uuid.UUID
    permission: str


class SecurityPolicyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    resource_type: str
    resource_id: uuid.UUID | None
    principal_type: str
    principal_id: uuid.UUID
    permission: str
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details_json: dict | None
    ip_address: str | None
    correlation_id: str | None
    timestamp: datetime


class AuthTokenRequest(BaseModel):
    authorization_code: str
    redirect_uri: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthMeResponse(BaseModel):
    user: UserResponse
    permissions: list[str]
