"""Credential type templates — defines field schemas for each credential type.

Templates are structural metadata, not user data. They define what fields
each credential type requires, which are secret (stored in Key Vault),
and how to render them in the UI.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class FieldDefinition:
    """A single field in a credential template."""
    name: str
    label: str
    field_type: str  # "string" | "password" | "textarea" | "number" | "boolean" | "select"
    required: bool = False
    is_secret: bool = False
    default: str | None = None
    placeholder: str | None = None
    options: list[dict] | None = None  # for select: [{"value": "...", "label": "..."}]


@dataclass
class CredentialTemplate:
    """A credential type template with its field definitions."""
    type_key: str
    display_name: str
    description: str = ""
    fields: list[FieldDefinition] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type_key": self.type_key,
            "display_name": self.display_name,
            "description": self.description,
            "fields": [asdict(f) for f in self.fields],
        }

    def secret_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.is_secret]

    def non_secret_field_names(self) -> list[str]:
        return [f.name for f in self.fields if not f.is_secret]


TEMPLATES: dict[str, CredentialTemplate] = {
    "windows_ad": CredentialTemplate(
        type_key="windows_ad",
        display_name="Windows / Active Directory",
        description="Credentials for Windows Remote Management (WinRM) and Active Directory authentication",
        fields=[
            FieldDefinition(name="domain", label="Domain", field_type="string", placeholder="MYDOMAIN"),
            FieldDefinition(name="username", label="Username", field_type="string", required=True, placeholder="svc_account"),
            FieldDefinition(name="password", label="Password", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="auth_method", label="Auth Method", field_type="select", default="negotiate",
                            options=[
                                {"value": "negotiate", "label": "Negotiate (recommended)"},
                                {"value": "kerberos", "label": "Kerberos"},
                                {"value": "ntlm", "label": "NTLM"},
                                {"value": "basic", "label": "Basic"},
                            ]),
        ],
    ),

    "ssh_password": CredentialTemplate(
        type_key="ssh_password",
        display_name="SSH Password",
        description="Username and password for SSH connections",
        fields=[
            FieldDefinition(name="username", label="Username", field_type="string", required=True, placeholder="svc_account"),
            FieldDefinition(name="password", label="Password", field_type="password", required=True, is_secret=True),
        ],
    ),

    "ssh_private_key": CredentialTemplate(
        type_key="ssh_private_key",
        display_name="SSH Private Key",
        description="SSH key-based authentication",
        fields=[
            FieldDefinition(name="username", label="Username", field_type="string", required=True, placeholder="svc_account"),
            FieldDefinition(name="private_key", label="Private Key", field_type="textarea", required=True, is_secret=True,
                            placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"),
            FieldDefinition(name="passphrase", label="Passphrase", field_type="password", is_secret=True,
                            placeholder="Leave empty if key has no passphrase"),
        ],
    ),

    "api_key": CredentialTemplate(
        type_key="api_key",
        display_name="API Key",
        description="Single API key authentication (header-based)",
        fields=[
            FieldDefinition(name="api_key", label="API Key", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="header_name", label="Header Name", field_type="string", default="X-API-Key",
                            placeholder="X-API-Key"),
            FieldDefinition(name="prefix", label="Value Prefix", field_type="string", default="",
                            placeholder="Bearer (optional)"),
        ],
    ),

    "api_key_secret": CredentialTemplate(
        type_key="api_key_secret",
        display_name="API Key + Secret",
        description="API key and secret pair (e.g., Twilio, AWS access keys)",
        fields=[
            FieldDefinition(name="api_key", label="API Key / Access Key", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="api_secret", label="API Secret / Secret Key", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="account_id", label="Account ID", field_type="string",
                            placeholder="Optional account/organization ID"),
        ],
    ),

    "bearer_token": CredentialTemplate(
        type_key="bearer_token",
        display_name="Bearer Token",
        description="OAuth2 bearer token or personal access token",
        fields=[
            FieldDefinition(name="token", label="Token", field_type="password", required=True, is_secret=True),
        ],
    ),

    "oauth2_client": CredentialTemplate(
        type_key="oauth2_client",
        display_name="OAuth2 Client Credentials",
        description="OAuth2 client credentials flow for service-to-service authentication",
        fields=[
            FieldDefinition(name="client_id", label="Client ID", field_type="string", required=True),
            FieldDefinition(name="client_secret", label="Client Secret", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="token_url", label="Token URL", field_type="string", required=True,
                            placeholder="https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token"),
            FieldDefinition(name="scopes", label="Scopes", field_type="string",
                            placeholder="https://graph.microsoft.com/.default"),
        ],
    ),

    "database": CredentialTemplate(
        type_key="database",
        display_name="Database",
        description="Database connection credentials (PostgreSQL, MySQL, SQL Server, etc.)",
        fields=[
            FieldDefinition(name="host", label="Host", field_type="string", required=True, placeholder="dbserver.example.local"),
            FieldDefinition(name="port", label="Port", field_type="number", default="1433"),
            FieldDefinition(name="database", label="Database Name", field_type="string", required=True),
            FieldDefinition(name="username", label="Username", field_type="string", required=True),
            FieldDefinition(name="password", label="Password", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="ssl_mode", label="SSL Mode", field_type="select", default="prefer",
                            options=[
                                {"value": "disable", "label": "Disable"},
                                {"value": "prefer", "label": "Prefer"},
                                {"value": "require", "label": "Require"},
                                {"value": "verify-ca", "label": "Verify CA"},
                                {"value": "verify-full", "label": "Verify Full"},
                            ]),
        ],
    ),

    "smtp": CredentialTemplate(
        type_key="smtp",
        display_name="SMTP",
        description="Email server credentials for sending notifications",
        fields=[
            FieldDefinition(name="host", label="SMTP Host", field_type="string", required=True, placeholder="smtp.example.com"),
            FieldDefinition(name="port", label="Port", field_type="number", default="587"),
            FieldDefinition(name="username", label="Username", field_type="string", required=True),
            FieldDefinition(name="password", label="Password", field_type="password", required=True, is_secret=True),
            FieldDefinition(name="use_tls", label="Use TLS", field_type="boolean", default="true"),
        ],
    ),

    "azure_service_principal": CredentialTemplate(
        type_key="azure_service_principal",
        display_name="Azure Service Principal",
        description="Azure AD app registration credentials for Azure resource access",
        fields=[
            FieldDefinition(name="tenant_id", label="Tenant ID", field_type="string", required=True,
                            placeholder="00000000-0000-0000-0000-000000000000"),
            FieldDefinition(name="client_id", label="Client ID", field_type="string", required=True),
            FieldDefinition(name="client_secret", label="Client Secret", field_type="password", required=True, is_secret=True),
        ],
    ),

    "certificate": CredentialTemplate(
        type_key="certificate",
        display_name="Certificate",
        description="TLS/SSL certificate with private key",
        fields=[
            FieldDefinition(name="certificate", label="Certificate (PEM)", field_type="textarea", required=True,
                            placeholder="-----BEGIN CERTIFICATE-----"),
            FieldDefinition(name="private_key", label="Private Key (PEM)", field_type="textarea", required=True, is_secret=True,
                            placeholder="-----BEGIN PRIVATE KEY-----"),
            FieldDefinition(name="passphrase", label="Key Passphrase", field_type="password", is_secret=True),
            FieldDefinition(name="ca_certificate", label="CA Certificate (PEM)", field_type="textarea",
                            placeholder="-----BEGIN CERTIFICATE----- (optional)"),
        ],
    ),

    "custom": CredentialTemplate(
        type_key="custom",
        display_name="Custom",
        description="User-defined credential with arbitrary fields",
        fields=[],
    ),
}


def get_template(credential_type: str) -> CredentialTemplate | None:
    """Get a credential template by type key."""
    return TEMPLATES.get(credential_type)


def list_templates() -> list[CredentialTemplate]:
    """List all available credential templates."""
    return list(TEMPLATES.values())
