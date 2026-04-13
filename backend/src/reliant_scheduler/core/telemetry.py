"""Azure Application Insights / OpenTelemetry integration.

Configures ``azure-monitor-opentelemetry`` for automatic request tracing,
dependency tracking, and exception telemetry.  Uses Managed Identity via
``DefaultAzureCredential`` — the connection string should come from Key
Vault, never hardcoded.

Call ``configure_telemetry()`` once at application startup (in the
FastAPI lifespan).  It is a no-op when the Application Insights
connection string is not configured (local development).
"""

import structlog

from reliant_scheduler.core.config import settings

logger = structlog.get_logger(__name__)


def configure_telemetry() -> None:
    """Set up Azure Monitor OpenTelemetry exporter if configured."""
    connection_string = settings.applicationinsights_connection_string
    if not connection_string:
        logger.info("telemetry_skipped", reason="APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
        )
        logger.info("telemetry_configured", target="application_insights")
    except Exception:
        logger.exception("telemetry_configuration_failed")
