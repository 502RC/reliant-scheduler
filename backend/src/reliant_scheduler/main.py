from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from reliant_scheduler.core.config import settings
from reliant_scheduler.core.logging import setup_logging
from reliant_scheduler.core.telemetry import configure_telemetry
from reliant_scheduler.api.deps import verify_api_key
from reliant_scheduler.api.middleware import CorrelationIdMiddleware
from reliant_scheduler.api.audit import AuditLogMiddleware
from reliant_scheduler.api.auth import get_current_user
from reliant_scheduler.api.permissions import require_permission
from reliant_scheduler.api.routes import health, jobs, schedules, connections, environments, agents
from reliant_scheduler.api.routes import metrics as metrics_route
from reliant_scheduler.api.routes import auth, users, workgroups, security_policies, audit_log
from reliant_scheduler.api.routes.calendars import router as calendars_router
from reliant_scheduler.api.routes.calendars import job_calendar_router
from reliant_scheduler.api.routes.sla import router as sla_router
from reliant_scheduler.api.routes.event_actions import (
    event_types_router,
    actions_router,
    bindings_router,
    executions_router,
)
from reliant_scheduler.api.routes.ws_events import router as ws_events_router
from reliant_scheduler.api.routes.credentials import router as credentials_router
from reliant_scheduler.core.database import async_session
from reliant_scheduler.services.event_emitter import register_handler, clear_handlers
from reliant_scheduler.services.event_router import EventRouter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    configure_telemetry()
    # Wire event-action automation: register the event router as a handler
    event_router = EventRouter(session_factory=async_session)
    register_handler(event_router.handle_event)
    yield
    clear_handlers()


app = FastAPI(
    title="Reliant Scheduler",
    description="Enterprise workload automation and job scheduling platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware — order matters: outermost middleware runs first
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    detail = "A record with that value already exists"
    if exc.orig and hasattr(exc.orig, "args") and exc.orig.args:
        msg = str(exc.orig.args[0]) if exc.orig.args else ""
        if "unique" in msg.lower() or "duplicate" in msg.lower():
            detail = "A record with that unique value already exists"
    return JSONResponse(status_code=409, content={"detail": detail})


# Public routes (no auth)
app.include_router(health.router)
app.include_router(metrics_route.router)

# Auth routes (public — handles token exchange)
app.include_router(auth.router)

# Protected routes (API key required when configured)
api_deps = [Depends(verify_api_key)]
app.include_router(jobs.router, dependencies=api_deps)
app.include_router(schedules.router, dependencies=api_deps)
app.include_router(connections.router, dependencies=api_deps)
app.include_router(credentials_router, dependencies=api_deps)
app.include_router(environments.router, dependencies=api_deps)
app.include_router(agents.router, dependencies=api_deps)

# RBAC routes (protected by per-route auth/permission dependencies)
app.include_router(users.router, dependencies=api_deps)
app.include_router(workgroups.router, dependencies=api_deps)
app.include_router(security_policies.router, dependencies=api_deps)
app.include_router(audit_log.router, dependencies=api_deps)

# Calendar routes
app.include_router(calendars_router, dependencies=api_deps)
app.include_router(job_calendar_router, dependencies=api_deps)

# SLA routes
app.include_router(sla_router, dependencies=api_deps)

# Event-action automation routes
app.include_router(event_types_router, dependencies=api_deps)
app.include_router(actions_router, dependencies=api_deps)
app.include_router(bindings_router, dependencies=api_deps)
app.include_router(executions_router, dependencies=api_deps)

# WebSocket + SSE event streaming (WS endpoint is public, SSE requires API key)
app.include_router(ws_events_router)
