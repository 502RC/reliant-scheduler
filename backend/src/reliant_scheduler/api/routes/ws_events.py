"""WebSocket endpoint for live job execution events.

Broadcasts job lifecycle events (started, progress, log_line, completed,
failed) to connected WebSocket clients. Also provides an SSE fallback
endpoint for log streaming.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.job_run import JobRun

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["events"])


# ---------------------------------------------------------------------------
# In-process event broadcast hub
# ---------------------------------------------------------------------------

class EventBroadcaster:
    """Fan-out job lifecycle events to connected WebSocket clients.

    Workers publish events here; connected clients receive them filtered
    by optional job_id / run_id subscriptions.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue] = {}

    def subscribe(self) -> tuple[str, asyncio.Queue]:
        """Register a new subscriber. Returns (subscriber_id, queue)."""
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers[sub_id] = queue
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(sub_id, None)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send an event to all subscribers (non-blocking, drops if full)."""
        for queue in self._subscribers.values():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop events for slow consumers

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Singleton broadcaster — imported by workers to publish events
event_broadcaster = EventBroadcaster()


async def publish_ws_event(
    event_type: str,
    job_id: str,
    run_id: str,
    **extra: Any,
) -> None:
    """Publish a job lifecycle event to all connected WebSocket clients.

    Events are formatted as ``{type, timestamp, payload}`` to match the
    ``WsEvent`` interface expected by the frontend.
    """
    event = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "job_id": job_id,
            "run_id": run_id,
            **extra,
        },
    }
    await event_broadcaster.broadcast(event)


async def publish_job_status_change(
    *,
    job_id: str,
    job_name: str,
    run_id: str,
    previous_status: str | None,
    status: str,
    agent_id: str | None = None,
    exit_code: int | None = None,
    error_message: str | None = None,
) -> None:
    """Broadcast a ``job.status_changed`` event plus the matching specific event.

    This emits **two** WebSocket events so the frontend can react to both
    the generic ``job.status_changed`` (used by the jobs list page) and the
    specific lifecycle event (``job.started``, ``job.completed``, etc.) used
    by the notification system.
    """
    payload: dict[str, Any] = {
        "job_id": job_id,
        "job_name": job_name,
        "run_id": run_id,
        "previous_status": previous_status,
        "status": status,
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if error_message is not None:
        payload["error_message"] = error_message

    ts = datetime.now(timezone.utc).isoformat()

    # 1) Generic status-change event (drives jobs-list live refresh)
    await event_broadcaster.broadcast({
        "type": "job.status_changed",
        "timestamp": ts,
        "payload": payload,
    })

    # 2) Specific lifecycle event (drives notifications / toasts)
    specific_map = {
        "queued": "job.started",
        "running": "job.started",
        "success": "job.completed",
        "failed": "job.failed",
        "timed_out": "job.timed_out",
    }
    specific_type = specific_map.get(status)
    if specific_type:
        await event_broadcaster.broadcast({
            "type": specific_type,
            "timestamp": ts,
            "payload": payload,
        })


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    job_id: str | None = Query(None),
    run_id: str | None = Query(None),
) -> None:
    """WebSocket endpoint for live job execution events.

    Query params ``job_id`` and ``run_id`` filter events to a specific
    job or run. Without filters, all events are forwarded.

    Events emitted:
    - job.started
    - job.progress
    - job.log_line
    - job.completed
    - job.failed
    """
    await websocket.accept()
    sub_id, queue = event_broadcaster.subscribe()
    logger.info(
        "ws_client_connected",
        subscriber_id=sub_id,
        job_id=job_id,
        run_id=run_id,
    )

    async def _send_events() -> None:
        """Forward queued events to the WebSocket client."""
        while True:
            event = await queue.get()

            # Apply filters — match against nested payload for new format
            payload = event.get("payload", event)
            if job_id and payload.get("job_id") != job_id:
                continue
            if run_id and payload.get("run_id") != run_id:
                continue

            await websocket.send_json(event)

    async def _receive_pings() -> None:
        """Handle incoming messages (heartbeat pings) from the client."""
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    try:
        # Run both tasks concurrently; either finishing means disconnect
        await asyncio.gather(_send_events(), _receive_pings())
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", subscriber_id=sub_id)
    except Exception:
        logger.exception("ws_error", subscriber_id=sub_id)
    finally:
        event_broadcaster.unsubscribe(sub_id)


# ---------------------------------------------------------------------------
# SSE fallback — log streaming for a specific run
# ---------------------------------------------------------------------------

@router.get("/api/jobs/{job_id}/runs/{run_id}/logs/stream")
async def stream_run_logs(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream for a specific job run's log lines.

    Falls back to returning the complete log if the run is already finished.
    """
    result = await db.execute(
        select(JobRun).where(JobRun.id == run_id, JobRun.job_id == job_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")

    return StreamingResponse(
        _sse_generator(str(job_id), str(run_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_generator(job_id: str, run_id: str):
    """Yield SSE-formatted events for a specific run."""
    sub_id, queue = event_broadcaster.subscribe()
    try:
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
                continue

            # Only forward events for this run
            if event.get("run_id") != run_id:
                continue

            event_type = event.get("event_type", "message")
            yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

            # Close stream when run completes
            if event_type in ("job.completed", "job.failed", "job.timed_out"):
                yield f"event: done\ndata: {json.dumps({'status': event_type})}\n\n"
                break
    finally:
        event_broadcaster.unsubscribe(sub_id)
