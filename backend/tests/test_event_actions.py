"""Integration tests for event-action automation.

Covers event type CRUD, action CRUD, event-action binding CRUD,
action execution history, test-action endpoint, event emitter/router
pipeline, and recovery job depth limiting. All tests run against a
real PostgreSQL database via testcontainers.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.event_action import (
    Action,
    ActionExecution,
    ActionExecutionStatus,
    EventActionBinding,
    EventType,
)
from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.services.event_emitter import clear_handlers, emit_event, register_handler
from reliant_scheduler.services.event_router import EventRouter


pytestmark = pytest.mark.asyncio


# ── Helpers ─────────────────────────────────────────────────────────


async def _create_event_type(client: AsyncClient, name: str, **kw) -> dict:
    payload = {"name": name, "description": kw.get("description", f"Test event: {name}")}
    resp = await client.post("/api/event-types", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_action(client: AsyncClient, name: str, action_type: str = "webhook", **kw) -> dict:
    payload = {
        "name": name,
        "type": action_type,
        "config_json": kw.get("config_json", {"url": "https://example.com/hook"}),
    }
    resp = await client.post("/api/actions", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_binding(
    client: AsyncClient, event_type_id: str, action_id: str, **kw
) -> dict:
    payload = {
        "event_type_id": event_type_id,
        "action_id": action_id,
        "enabled": kw.get("enabled", True),
        "filter_json": kw.get("filter_json"),
    }
    resp = await client.post("/api/event-action-bindings", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── Event Type CRUD ────────────────────────────────────────────────


async def test_create_event_type(client: AsyncClient) -> None:
    body = await _create_event_type(client, "test.event.create")
    assert body["name"] == "test.event.create"
    assert body["description"] == "Test event: test.event.create"
    assert "id" in body
    assert "created_at" in body


async def test_list_event_types(client: AsyncClient) -> None:
    await _create_event_type(client, "test.list.a")
    await _create_event_type(client, "test.list.b")
    resp = await client.get("/api/event-types")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    names = [i["name"] for i in body["items"]]
    assert "test.list.a" in names
    assert "test.list.b" in names


async def test_create_duplicate_event_type(client: AsyncClient) -> None:
    await _create_event_type(client, "test.duplicate")
    resp = await client.post("/api/event-types", json={"name": "test.duplicate"})
    assert resp.status_code == 409


# ── Action CRUD ────────────────────────────────────────────────────


async def test_create_action(client: AsyncClient) -> None:
    body = await _create_action(client, "my-webhook", "webhook", config_json={"url": "https://hook.test"})
    assert body["name"] == "my-webhook"
    assert body["type"] == "webhook"
    assert body["config_json"]["url"] == "https://hook.test"


async def test_create_action_invalid_type(client: AsyncClient) -> None:
    resp = await client.post("/api/actions", json={"name": "bad", "type": "invalid_type"})
    assert resp.status_code == 422


async def test_get_action(client: AsyncClient) -> None:
    created = await _create_action(client, "get-test")
    resp = await client.get(f"/api/actions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-test"


async def test_update_action(client: AsyncClient) -> None:
    created = await _create_action(client, "update-test")
    resp = await client.patch(
        f"/api/actions/{created['id']}",
        json={"name": "updated-name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated-name"


async def test_delete_action(client: AsyncClient) -> None:
    created = await _create_action(client, "delete-test")
    resp = await client.delete(f"/api/actions/{created['id']}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/actions/{created['id']}")
    assert resp.status_code == 404


async def test_list_actions_with_type_filter(client: AsyncClient) -> None:
    await _create_action(client, "email-action", "email", config_json={"to_addresses": ["a@b.com"]})
    await _create_action(client, "webhook-action", "webhook")
    resp = await client.get("/api/actions", params={"action_type": "email"})
    assert resp.status_code == 200
    body = resp.json()
    assert all(i["type"] == "email" for i in body["items"])


async def test_get_action_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/actions/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Binding CRUD ───────────────────────────────────────────────────


async def test_create_binding(client: AsyncClient) -> None:
    et = await _create_event_type(client, "bind.test.event")
    action = await _create_action(client, "bind-test-action")
    binding = await _create_binding(client, et["id"], action["id"])
    assert binding["event_type_id"] == et["id"]
    assert binding["action_id"] == action["id"]
    assert binding["enabled"] is True


async def test_create_binding_missing_event_type(client: AsyncClient) -> None:
    action = await _create_action(client, "orphan-bind-action")
    resp = await client.post("/api/event-action-bindings", json={
        "event_type_id": str(uuid.uuid4()),
        "action_id": action["id"],
    })
    assert resp.status_code == 404


async def test_create_binding_missing_action(client: AsyncClient) -> None:
    et = await _create_event_type(client, "bind.missing.action")
    resp = await client.post("/api/event-action-bindings", json={
        "event_type_id": et["id"],
        "action_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 404


async def test_update_binding(client: AsyncClient) -> None:
    et = await _create_event_type(client, "bind.update.event")
    action = await _create_action(client, "bind-update-action")
    binding = await _create_binding(client, et["id"], action["id"])
    resp = await client.patch(
        f"/api/event-action-bindings/{binding['id']}",
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


async def test_delete_binding(client: AsyncClient) -> None:
    et = await _create_event_type(client, "bind.delete.event")
    action = await _create_action(client, "bind-delete-action")
    binding = await _create_binding(client, et["id"], action["id"])
    resp = await client.delete(f"/api/event-action-bindings/{binding['id']}")
    assert resp.status_code == 204


async def test_list_bindings_with_filters(client: AsyncClient) -> None:
    et = await _create_event_type(client, "bind.filter.event")
    a1 = await _create_action(client, "bind-filter-a1")
    a2 = await _create_action(client, "bind-filter-a2")
    await _create_binding(client, et["id"], a1["id"])
    await _create_binding(client, et["id"], a2["id"], enabled=False)
    resp = await client.get("/api/event-action-bindings", params={"enabled": True, "event_type_id": et["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert all(i["enabled"] is True for i in body["items"])


# ── Action Executions ──────────────────────────────────────────────


async def test_list_action_executions_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/action-executions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_action_executions_populated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that action executions created by the router appear in the API."""
    # Create event type + action + binding in DB
    et = EventType(name="exec.test.event", description="test")
    db_session.add(et)
    await db_session.flush()

    action = Action(name="exec-test-action", type="webhook", config_json={"url": "https://example.com"})
    db_session.add(action)
    await db_session.flush()

    binding = EventActionBinding(event_type_id=et.id, action_id=action.id, enabled=True)
    db_session.add(binding)
    await db_session.flush()

    # Insert an execution record
    execution = ActionExecution(
        event_action_binding_id=binding.id,
        event_data_json={"test": True},
        status=ActionExecutionStatus.SENT,
        attempt_number=1,
    )
    db_session.add(execution)
    await db_session.commit()

    resp = await client.get("/api/action-executions", params={"status": "sent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(i["status"] == "sent" for i in body["items"])


# ── Test Action ────────────────────────────────────────────────────


async def test_test_action_endpoint(client: AsyncClient) -> None:
    action = await _create_action(client, "test-action-test", "webhook", config_json={"url": "https://httpbin.org/post"})
    resp = await client.post(
        f"/api/actions/{action['id']}/test",
        json={"sample_event_data": {"job_name": "my-job"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    # We expect either success or a connection error (no real httpbin in test)
    assert "success" in body


async def test_test_action_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/actions/{uuid.uuid4()}/test",
        json={},
    )
    assert resp.status_code == 404


# ── Event Emitter ──────────────────────────────────────────────────


async def test_emit_event_calls_handlers() -> None:
    """Verify that emitting an event calls all registered handlers."""
    clear_handlers()
    captured = []

    async def handler(event_type: str, data: dict) -> None:
        captured.append((event_type, data))

    register_handler(handler)
    await emit_event("test.event", {"key": "value"})
    clear_handlers()

    assert len(captured) == 1
    assert captured[0] == ("test.event", {"key": "value"})


async def test_emit_event_handler_error_does_not_propagate() -> None:
    """Verify that a handler error doesn't prevent other handlers from running."""
    clear_handlers()
    captured = []

    async def bad_handler(event_type: str, data: dict) -> None:
        raise RuntimeError("boom")

    async def good_handler(event_type: str, data: dict) -> None:
        captured.append(True)

    register_handler(bad_handler)
    register_handler(good_handler)
    await emit_event("test.error", {})
    clear_handlers()

    assert len(captured) == 1


# ── Event Router (filter matching) ────────────────────────────────


async def test_event_router_filter_matching() -> None:
    """Verify filter logic for event-action bindings."""
    from reliant_scheduler.services.event_router import EventRouter

    router = EventRouter(session_factory=None)

    # No filter = always matches
    assert router._matches_filter({"any": "data"}, None) is True
    assert router._matches_filter({"any": "data"}, {}) is True

    # Exact match
    assert router._matches_filter({"job_id": "abc"}, {"job_id": "abc"}) is True
    assert router._matches_filter({"job_id": "abc"}, {"job_id": "xyz"}) is False

    # List match (any of)
    assert router._matches_filter({"status": "failed"}, {"status": ["failed", "timed_out"]}) is True
    assert router._matches_filter({"status": "success"}, {"status": ["failed", "timed_out"]}) is False


# ── Event Router (end-to-end with DB) ─────────────────────────────


async def test_event_router_processes_event(
    test_session_factory, db_session: AsyncSession
) -> None:
    """Full pipeline: emit event → router finds binding → executes action → records execution."""
    # Set up event type, action, and binding
    et = EventType(name="router.test.event", description="test")
    db_session.add(et)
    await db_session.flush()

    action = Action(name="router-webhook", type="webhook", config_json={"url": "https://example.com"})
    db_session.add(action)
    await db_session.flush()

    binding = EventActionBinding(event_type_id=et.id, action_id=action.id, enabled=True)
    db_session.add(binding)
    await db_session.commit()

    router = EventRouter(session_factory=test_session_factory)

    # Mock the actual HTTP call to avoid network dependency
    with patch("reliant_scheduler.services.event_router.execute_action", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = (True, None)
        await router.handle_event("router.test.event", {"job_name": "test"})

    # Verify execution was recorded
    result = await db_session.execute(
        select(ActionExecution).where(
            ActionExecution.event_action_binding_id == binding.id
        )
    )
    executions = list(result.scalars().all())
    assert len(executions) == 1
    assert executions[0].status == ActionExecutionStatus.SENT


async def test_event_router_skips_disabled_binding(
    test_session_factory, db_session: AsyncSession
) -> None:
    """Disabled bindings should not trigger action execution."""
    et = EventType(name="router.disabled.event", description="test")
    db_session.add(et)
    await db_session.flush()

    action = Action(name="disabled-action", type="webhook", config_json={"url": "https://example.com"})
    db_session.add(action)
    await db_session.flush()

    binding = EventActionBinding(event_type_id=et.id, action_id=action.id, enabled=False)
    db_session.add(binding)
    await db_session.commit()

    router = EventRouter(session_factory=test_session_factory)

    with patch("reliant_scheduler.services.event_router.execute_action", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = (True, None)
        await router.handle_event("router.disabled.event", {"job_name": "test"})

    mock_exec.assert_not_called()


async def test_event_router_records_failure(
    test_session_factory, db_session: AsyncSession
) -> None:
    """Failed actions after retries should be recorded with error details."""
    et = EventType(name="router.fail.event", description="test")
    db_session.add(et)
    await db_session.flush()

    action = Action(name="fail-action", type="webhook", config_json={"url": "https://example.com"})
    db_session.add(action)
    await db_session.flush()

    binding = EventActionBinding(event_type_id=et.id, action_id=action.id, enabled=True)
    db_session.add(binding)
    await db_session.commit()

    router = EventRouter(session_factory=test_session_factory)

    with patch("reliant_scheduler.services.event_router.execute_action", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = (False, "Connection refused")
        # Patch sleep to avoid real delay during retries
        with patch("reliant_scheduler.services.event_router.asyncio.sleep", new_callable=AsyncMock):
            await router.handle_event("router.fail.event", {"job_name": "test"})

    result = await db_session.execute(
        select(ActionExecution).where(ActionExecution.event_action_binding_id == binding.id)
    )
    executions = list(result.scalars().all())
    assert len(executions) == 1
    assert executions[0].status == ActionExecutionStatus.FAILED
    assert "Connection refused" in executions[0].error_message


# ── Recovery Job Depth Limiting ────────────────────────────────────


async def test_recovery_job_depth_limiting(
    test_session_factory, db_session: AsyncSession
) -> None:
    """Recovery jobs should be blocked when max_recovery_depth is exceeded."""
    # Create a job to recover to
    job = Job(name="recovery-target", job_type="shell", command="echo recover", timeout_seconds=60)
    db_session.add(job)
    await db_session.flush()

    et = EventType(name="recovery.depth.event", description="test")
    db_session.add(et)
    await db_session.flush()

    action = Action(
        name="recovery-action",
        type="recovery_job",
        config_json={"recovery_job_id": str(job.id), "pass_context": True},
    )
    db_session.add(action)
    await db_session.flush()

    binding = EventActionBinding(event_type_id=et.id, action_id=action.id, enabled=True)
    db_session.add(binding)
    await db_session.commit()

    router = EventRouter(session_factory=test_session_factory)

    # Emit with depth=0 (should create recovery run)
    await router.handle_event("recovery.depth.event", {"recovery_depth": 0})

    runs_result = await db_session.execute(
        select(JobRun).where(JobRun.job_id == job.id)
    )
    runs = list(runs_result.scalars().all())
    assert len(runs) == 1
    assert runs[0].parameters.get("recovery_depth") == 1

    # Emit with depth=3 (at max — should NOT create another run)
    await router.handle_event("recovery.depth.event", {"recovery_depth": 3})

    runs_result2 = await db_session.execute(
        select(JobRun).where(JobRun.job_id == job.id)
    )
    runs2 = list(runs_result2.scalars().all())
    assert len(runs2) == 1  # still just the one from depth=0


# ── Job Lifecycle Event Emission ───────────────────────────────────


async def test_job_run_update_emits_events(client: AsyncClient) -> None:
    """Updating a job run to a terminal status should emit lifecycle events."""
    # Create a job
    job_resp = await client.post("/api/jobs", json={
        "name": "emit-test-job",
        "job_type": "shell",
        "command": "echo test",
        "timeout_seconds": 60,
    })
    assert job_resp.status_code == 201
    job = job_resp.json()

    # Trigger a run
    trigger_resp = await client.post(f"/api/jobs/{job['id']}/trigger", json={})
    assert trigger_resp.status_code == 201
    run = trigger_resp.json()

    # Capture emitted events
    captured_events = []
    clear_handlers()

    async def capture_handler(event_type: str, data: dict) -> None:
        captured_events.append((event_type, data))

    register_handler(capture_handler)

    # Update run to FAILED
    resp = await client.patch(
        f"/api/jobs/{job['id']}/runs/{run['id']}",
        json={"status": "failed", "error_message": "test failure"},
    )
    assert resp.status_code == 200

    clear_handlers()

    # Verify event was emitted
    assert any(et == "job.failed" for et, _ in captured_events)
    failed_event = next(d for et, d in captured_events if et == "job.failed")
    assert failed_event["job_id"] == job["id"]
    assert failed_event["error"] == "test failure"
