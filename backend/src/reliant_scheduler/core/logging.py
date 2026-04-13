"""Structured JSON logging configuration using structlog.

Call ``setup_logging()`` once at application startup to configure
JSON-formatted structured logging across all services.  Every log entry
includes ``service_name`` for Log Analytics KQL queries and a
``correlation_id`` propagated via structlog context variables (set by the
correlation-ID middleware).
"""

import logging
import os
import sys

import structlog

SERVICE_NAME = os.getenv("RELIANT_SERVICE_NAME", "reliant-scheduler")


def _add_service_context(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Inject service-level fields required for Azure Log Analytics KQL queries."""
    event_dict.setdefault("service_name", SERVICE_NAME)
    return event_dict


def setup_logging(*, log_level: str = "INFO") -> None:
    """Configure structlog for JSON-formatted structured logging.

    Fields guaranteed on every log line:
    - ``service_name`` – identifies the emitting service
    - ``correlation_id`` – present when set by request middleware
    - ``timestamp`` – ISO-8601
    - ``logger`` / ``level``
    """

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            _add_service_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
