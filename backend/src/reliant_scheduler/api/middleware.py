"""Request middleware for correlation ID propagation, request logging, and metrics."""

import re
import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from reliant_scheduler.core.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)

CORRELATION_ID_HEADER = "X-Correlation-ID"

logger = structlog.get_logger(__name__)

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_NUMERIC_ID_RE = re.compile(r"/\d+(?=/|$)")


def _normalize_path(path: str) -> str:
    """Replace UUIDs and numeric IDs with {id} to prevent metric cardinality explosion."""
    path = _UUID_RE.sub("{id}", path)
    path = _NUMERIC_ID_RE.sub("/{id}", path)
    return path


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Extract or generate a correlation ID for every request.

    The ID is propagated via structlog context variables so all log entries
    emitted during the request automatically include it.  The ID is also
    returned in the response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        metric_path = _normalize_path(path)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=metric_path).inc()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(method=method, path=metric_path, status="500").inc()
            raise
        finally:
            duration = time.perf_counter() - start
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=metric_path).dec()

        status_code = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=metric_path, status=status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=metric_path).observe(duration)

        response.headers[CORRELATION_ID_HEADER] = correlation_id

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_seconds=round(duration, 4),
        )

        structlog.contextvars.clear_contextvars()
        return response
