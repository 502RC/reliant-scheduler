from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # Database — postgres_password is required (no default to prevent insecure deployments)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "reliant_scheduler"
    postgres_user: str = "reliant"
    postgres_password: str

    # API
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:5173"
    api_key: str = ""  # Empty = dev mode (no auth required)

    # Azure Service Bus
    azure_servicebus_connection_string: str = ""  # Data path (from Key Vault)
    azure_servicebus_namespace: str = ""  # Namespace for Managed Identity health checks
    azure_servicebus_queue_name: str = "workload-jobs"

    # Azure Event Hubs
    azure_eventhub_connection_string: str = ""  # Data path (from Key Vault)
    azure_eventhub_namespace: str = ""  # Namespace for Managed Identity health checks
    azure_eventhub_name: str = "workload-events"

    # Azure Blob Storage
    azure_storage_connection_string: str = ""  # Data path (from Key Vault)
    azure_storage_account_name: str = ""  # Account name for Managed Identity health checks
    azure_storage_container: str = "workload-artifacts"

    # Azure Key Vault
    azure_keyvault_url: str = ""

    # Azure Application Insights (connection string retrieved from Key Vault at runtime)
    applicationinsights_connection_string: str = ""

    # APM Event Hubs (separate hub for operational telemetry)
    azure_apm_eventhub_connection_string: str = ""
    azure_apm_eventhub_name: str = "apm-telemetry"

    # Microsoft Entra ID (Azure AD) — retrieved from Key Vault in prod
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_authority: str = ""  # Computed from tenant_id if empty

    @property
    def entra_authority_url(self) -> str:
        if self.entra_authority:
            return self.entra_authority
        if self.entra_tenant_id:
            return f"https://login.microsoftonline.com/{self.entra_tenant_id}"
        return ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]


settings = Settings()
