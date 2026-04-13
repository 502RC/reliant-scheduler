"""Credential API schemas.

Secrets are NEVER returned in responses. Only field names that have
secrets stored are included in `secret_fields`.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CredentialCreate(BaseModel):
    name: str
    credential_type: str
    description: str | None = None
    # All field values including secrets. Server separates secret vs non-secret
    # based on the template definition.
    fields: dict[str, str | int | bool]


class CredentialUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    # Partial field updates. Omitted secret fields are NOT modified.
    # Include a secret field only if changing its value.
    fields: dict[str, str | int | bool] | None = None


class CredentialResponse(BaseModel):
    """API response — secrets are NEVER returned."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    credential_type: str
    description: str | None
    fields: dict | None  # Non-secret fields only
    secret_fields: list[str]  # Names of fields that have secrets stored
    usage_count: int
    created_at: datetime
    updated_at: datetime


class CredentialTemplateFieldResponse(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool
    is_secret: bool
    default: str | None
    placeholder: str | None
    options: list[dict] | None


class CredentialTemplateResponse(BaseModel):
    type_key: str
    display_name: str
    description: str
    fields: list[CredentialTemplateFieldResponse]
