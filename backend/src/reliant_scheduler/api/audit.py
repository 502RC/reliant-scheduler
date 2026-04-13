"""Audit logging middleware and helpers.

Logs all mutating API calls (POST, PUT, PATCH, DELETE) to the audit_log
table with user context, correlation ID, and request details.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from reliant_scheduler.models.user import AuditLog

logger = structlog.get_logger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _extract_resource_info(path: str, method: str) -> tuple[str, str | None]:
    """Extract resource type and ID from the request path.

    Expects paths like /api/jobs/{id}, /api/users/{id}, etc.
    Returns (resource_type, resource_id_or_none).
    """
    parts = [p for p in path.split("/") if p]
    # Skip "api" prefix
    if parts and parts[0] == "api":
        parts = parts[1:]

    resource_type = parts[0] if parts else "unknown"
    # Normalize plural to singular
    if resource_type.endswith("ies"):
        resource_type = resource_type[:-3] + "y"  # e.g., "policies" -> "policy"
    elif resource_type.endswith("s") and resource_type not in ("bus",):
        resource_type = resource_type[:-1]

    resource_id = None
    if len(parts) >= 2:
        try:
            uuid.UUID(parts[1])
            resource_id = parts[1]
        except ValueError:
            pass

    return resource_type, resource_id


def _get_session_factory(request: Request):
    """Get the session factory, respecting dependency overrides in tests."""
    from reliant_scheduler.core.database import get_db, async_session

    # Check for dependency override (used in tests)
    overrides = getattr(request.app, "dependency_overrides", {})
    override_fn = overrides.get(get_db)
    if override_fn:
        return override_fn
    # Default: use the module-level async_session
    return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Log mutating API calls to the audit_log table."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if request.method not in MUTATING_METHODS:
            return response

        # Skip non-API paths and health/auth endpoints
        path = request.url.path
        if not path.startswith("/api/") or path.startswith("/api/auth/"):
            return response

        # Only log successful mutations (2xx status codes)
        if response.status_code < 200 or response.status_code >= 300:
            return response

        try:
            resource_type, resource_id = _extract_resource_info(path, request.method)

            # Map HTTP method to action
            action_map = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
            action = action_map.get(request.method, request.method.lower())

            # Get user ID from request state (set by auth dependency)
            user_id = getattr(request.state, "user_id", None)
            correlation_id = getattr(request.state, "correlation_id", None)

            # Get client IP
            ip_address = request.client.host if request.client else None

            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details_json={
                    "method": request.method,
                    "path": path,
                    "status_code": response.status_code,
                },
                ip_address=ip_address,
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
            )

            # Use test-override session factory when available, otherwise default
            override_fn = _get_session_factory(request)
            if override_fn:
                async for session in override_fn():
                    session.add(entry)
                    await session.commit()
            else:
                from reliant_scheduler.core.database import async_session

                async with async_session() as session:
                    session.add(entry)
                    await session.commit()

        except Exception:
            # Audit logging must never break the request
            logger.warning("audit_log_write_failed", path=path, exc_info=True)

        return response
