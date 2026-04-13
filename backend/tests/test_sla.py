"""Integration tests for SLA management.

Covers SLA policy CRUD, job constraints, critical path computation,
risk/breach event detection, and the status endpoint. All tests run
against a real PostgreSQL database via testcontainers.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.job import Job
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.sla import SLAEventType, SLAJobConstraint, SLAPolicy
from reliant_scheduler.services.sla_service import SLAService


pytestmark = pytest.mark.asyncio


# ── Helpers ─────────────────────────────────────────────────────────


def _policy_payload(name: str = "test-sla", **overrides) -> dict:
    target = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    base = {
        "name": name,
        "description": "Test SLA policy",
        "target_completion_time": target,
        "risk_window_minutes": 60,
        "breach_window_minutes": 30,
    }
    base.update(overrides)
    return base


def _job_payload(name: str, **overrides) -> dict:
    base = {
        "name": name,
        "job_type": "shell",
        "command": "echo hello",
        "timeout_seconds": 600,
    }
    base.update(overrides)
    return base


async def _create_job(client: AsyncClient, name: str, **kw) -> dict:
    resp = await client.post("/api/jobs", json=_job_payload(name, **kw))
    assert resp.status_code == 201
    return resp.json()


async def _create_policy(client: AsyncClient, name: str, **kw) -> dict:
    resp = await client.post("/api/sla-policies", json=_policy_payload(name, **kw))
    assert resp.status_code == 201
    return resp.json()


# ── Policy CRUD ─────────────────────────────────────────────────────


async def test_create_sla_policy(client: AsyncClient) -> None:
    resp = await client.post("/api/sla-policies", json=_policy_payload("sla-create"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "sla-create"
    assert body["description"] == "Test SLA policy"
    assert body["risk_window_minutes"] == 60
    assert body["breach_window_minutes"] == 30
    assert "id" in body
    assert "created_at" in body


async def test_list_sla_policies_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/sla-policies")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


async def test_list_sla_policies_with_data(client: AsyncClient) -> None:
    await _create_policy(client, "sla-list-1")
    await _create_policy(client, "sla-list-2")
    resp = await client.get("/api/sla-policies")
    assert resp.json()["total"] == 2


async def test_get_sla_policy(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-get")
    resp = await client.get(f"/api/sla-policies/{policy['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "sla-get"


async def test_update_sla_policy(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-update")
    resp = await client.patch(f"/api/sla-policies/{policy['id']}", json={
        "description": "Updated description",
        "risk_window_minutes": 120,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Updated description"
    assert body["risk_window_minutes"] == 120


async def test_delete_sla_policy(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-delete")
    resp = await client.delete(f"/api/sla-policies/{policy['id']}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/sla-policies/{policy['id']}")
    assert get_resp.status_code == 404


async def test_get_policy_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/api/sla-policies/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_create_duplicate_policy_name(client: AsyncClient) -> None:
    await _create_policy(client, "sla-dup")
    resp = await client.post("/api/sla-policies", json=_policy_payload("sla-dup"))
    assert resp.status_code == 409


async def test_create_policy_invalid_window(client: AsyncClient) -> None:
    resp = await client.post("/api/sla-policies", json=_policy_payload(
        "sla-invalid", risk_window_minutes=-1,
    ))
    assert resp.status_code == 422


# ── Job Constraints ─────────────────────────────────────────────────


async def test_add_and_list_constraints(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-constraints")
    job = await _create_job(client, "sla-job-1")

    resp = await client.post(f"/api/sla-policies/{policy['id']}/constraints", json={
        "job_id": job["id"],
        "track_critical_path": True,
        "max_duration_minutes": 30,
    })
    assert resp.status_code == 201
    constraint = resp.json()
    assert constraint["job_id"] == job["id"]
    assert constraint["track_critical_path"] is True
    assert constraint["max_duration_minutes"] == 30

    list_resp = await client.get(f"/api/sla-policies/{policy['id']}/constraints")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_remove_constraint(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-rm-constraint")
    job = await _create_job(client, "sla-rm-job")
    constraint = (await client.post(
        f"/api/sla-policies/{policy['id']}/constraints",
        json={"job_id": job["id"]},
    )).json()

    resp = await client.delete(
        f"/api/sla-policies/{policy['id']}/constraints/{constraint['id']}"
    )
    assert resp.status_code == 204

    list_resp = await client.get(f"/api/sla-policies/{policy['id']}/constraints")
    assert len(list_resp.json()) == 0


async def test_add_constraint_nonexistent_policy(client: AsyncClient) -> None:
    job = await _create_job(client, "sla-bad-policy-job")
    resp = await client.post(
        f"/api/sla-policies/{uuid.uuid4()}/constraints",
        json={"job_id": job["id"]},
    )
    assert resp.status_code == 404


async def test_add_constraint_nonexistent_job(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-bad-job")
    resp = await client.post(
        f"/api/sla-policies/{policy['id']}/constraints",
        json={"job_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# ── Critical Path ───────────────────────────────────────────────────


async def test_critical_path_empty(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-cp-empty")
    resp = await client.get(f"/api/sla-policies/{policy['id']}/critical-path")
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == []
    assert body["total_duration_minutes"] == 0


async def test_critical_path_single_job(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-cp-single")
    job = await _create_job(client, "sla-cp-job-1", timeout_seconds=1800)

    await client.post(f"/api/sla-policies/{policy['id']}/constraints", json={
        "job_id": job["id"],
        "track_critical_path": True,
        "max_duration_minutes": 20,
    })

    resp = await client.get(f"/api/sla-policies/{policy['id']}/critical-path")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["path"]) == 1
    assert body["total_duration_minutes"] == 20
    assert body["path"][0]["job_name"] == "sla-cp-job-1"


async def test_critical_path_chain(client: AsyncClient) -> None:
    """Three jobs in a chain: A -> B -> C. Critical path = A + B + C."""
    policy = await _create_policy(client, "sla-cp-chain")
    job_a = await _create_job(client, "sla-cp-a")
    job_b = await _create_job(client, "sla-cp-b")
    job_c = await _create_job(client, "sla-cp-c")

    # Create dependencies: B depends on A, C depends on B
    await client.post(f"/api/jobs/{job_b['id']}/dependencies", json={
        "depends_on_job_id": job_a["id"],
    })
    await client.post(f"/api/jobs/{job_c['id']}/dependencies", json={
        "depends_on_job_id": job_b["id"],
    })

    # Add all three as tracked critical path jobs
    for job, dur in [(job_a, 10), (job_b, 15), (job_c, 20)]:
        await client.post(f"/api/sla-policies/{policy['id']}/constraints", json={
            "job_id": job["id"],
            "track_critical_path": True,
            "max_duration_minutes": dur,
        })

    resp = await client.get(f"/api/sla-policies/{policy['id']}/critical-path")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_duration_minutes"] == 45  # 10 + 15 + 20
    assert len(body["path"]) == 3


async def test_critical_path_selects_longest(client: AsyncClient) -> None:
    """Two parallel branches, critical path picks the longer one.

    A (10min) --> C (20min)
    B (5min)  --> C (20min)

    Critical path: A -> C = 30min (not B -> C = 25min)
    """
    policy = await _create_policy(client, "sla-cp-longest")
    job_a = await _create_job(client, "sla-cp-long-a")
    job_b = await _create_job(client, "sla-cp-long-b")
    job_c = await _create_job(client, "sla-cp-long-c")

    # C depends on both A and B
    await client.post(f"/api/jobs/{job_c['id']}/dependencies", json={
        "depends_on_job_id": job_a["id"],
    })
    await client.post(f"/api/jobs/{job_c['id']}/dependencies", json={
        "depends_on_job_id": job_b["id"],
    })

    for job, dur in [(job_a, 10), (job_b, 5), (job_c, 20)]:
        await client.post(f"/api/sla-policies/{policy['id']}/constraints", json={
            "job_id": job["id"],
            "track_critical_path": True,
            "max_duration_minutes": dur,
        })

    resp = await client.get(f"/api/sla-policies/{policy['id']}/critical-path")
    body = resp.json()
    assert body["total_duration_minutes"] == 30  # A(10) + C(20)
    assert len(body["path"]) == 2


async def test_critical_path_nonexistent_policy(client: AsyncClient) -> None:
    resp = await client.get(f"/api/sla-policies/{uuid.uuid4()}/critical-path")
    assert resp.status_code == 404


# ── SLA Events ──────────────────────────────────────────────────────


async def test_list_events_empty(client: AsyncClient) -> None:
    policy = await _create_policy(client, "sla-events-empty")
    resp = await client.get(f"/api/sla-policies/{policy['id']}/events")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_events_nonexistent_policy(client: AsyncClient) -> None:
    resp = await client.get(f"/api/sla-policies/{uuid.uuid4()}/events")
    assert resp.status_code == 404


# ── SLA Status ──────────────────────────────────────────────────────


async def test_sla_status_on_track(client: AsyncClient) -> None:
    """Policy with a target well in the future should be on_track."""
    policy = await _create_policy(client, "sla-status-ok", risk_window_minutes=30)

    resp = await client.get(f"/api/sla-policies/{policy['id']}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "on_track"
    assert body["sla_policy_id"] == policy["id"]


async def test_sla_status_nonexistent(client: AsyncClient) -> None:
    resp = await client.get(f"/api/sla-policies/{uuid.uuid4()}/status")
    assert resp.status_code == 404


# ── SLA Service: risk/breach detection ──────────────────────────────


async def test_service_detects_at_risk(db_session: AsyncSession) -> None:
    """When estimated completion falls within the risk window, status is at_risk."""
    sla_service = SLAService()

    # Create a policy with target 30 min from now, risk window = 60 min
    # This means anything finishing within 60 min of target is at_risk
    now = datetime.now(timezone.utc)
    policy = SLAPolicy(
        name="sla-risk-test",
        target_completion_time=now + timedelta(minutes=30),
        risk_window_minutes=60,
        breach_window_minutes=10,
    )
    db_session.add(policy)

    # Create a job with 20 min estimated duration
    job = Job(name="risk-job", job_type="shell", command="echo hi", timeout_seconds=1200)
    db_session.add(job)
    await db_session.flush()

    # Add constraint tracking critical path
    constraint = SLAJobConstraint(
        sla_policy_id=policy.id,
        job_id=job.id,
        track_critical_path=True,
        max_duration_minutes=20,
    )
    db_session.add(constraint)
    await db_session.flush()

    # Estimated completion = now + 20min. Target = now + 30min.
    # Risk threshold = target - 60min = now - 30min.
    # Since now+20 > now-30, this is at_risk
    status, est_completion, remaining = await sla_service.evaluate_sla_status(
        db_session, policy.id
    )
    assert status == "at_risk"
    assert remaining == 20


async def test_service_detects_breach(db_session: AsyncSession) -> None:
    """When estimated completion exceeds target, status is breached."""
    sla_service = SLAService()

    now = datetime.now(timezone.utc)
    # Target is 10 minutes ago — already breached
    policy = SLAPolicy(
        name="sla-breach-test",
        target_completion_time=now - timedelta(minutes=10),
        risk_window_minutes=30,
        breach_window_minutes=10,
    )
    db_session.add(policy)

    job = Job(name="breach-job", job_type="shell", command="echo hi", timeout_seconds=600)
    db_session.add(job)
    await db_session.flush()

    constraint = SLAJobConstraint(
        sla_policy_id=policy.id,
        job_id=job.id,
        track_critical_path=True,
        max_duration_minutes=15,
    )
    db_session.add(constraint)
    await db_session.flush()

    status, _, _ = await sla_service.evaluate_sla_status(db_session, policy.id)
    assert status == "breached"


async def test_service_emits_breach_event(db_session: AsyncSession) -> None:
    """check_and_emit_events should create an SLA event record for breaches."""
    sla_service = SLAService()

    now = datetime.now(timezone.utc)
    policy = SLAPolicy(
        name="sla-emit-test",
        target_completion_time=now - timedelta(minutes=10),
        risk_window_minutes=30,
        breach_window_minutes=10,
    )
    db_session.add(policy)

    job = Job(name="emit-job", job_type="shell", command="echo hi", timeout_seconds=600)
    db_session.add(job)
    await db_session.flush()

    constraint = SLAJobConstraint(
        sla_policy_id=policy.id,
        job_id=job.id,
        track_critical_path=True,
        max_duration_minutes=15,
    )
    db_session.add(constraint)
    await db_session.flush()

    events = await sla_service.check_and_emit_events(db_session, policy.id)
    assert len(events) == 1
    assert events[0].event_type == SLAEventType.BREACHED
    assert events[0].details_json is not None


async def test_service_deduplicates_events(db_session: AsyncSession) -> None:
    """Calling check_and_emit_events twice within an hour should not duplicate events."""
    sla_service = SLAService()

    now = datetime.now(timezone.utc)
    policy = SLAPolicy(
        name="sla-dedup-test",
        target_completion_time=now - timedelta(minutes=10),
        risk_window_minutes=30,
        breach_window_minutes=10,
    )
    db_session.add(policy)

    job = Job(name="dedup-job", job_type="shell", command="echo hi", timeout_seconds=600)
    db_session.add(job)
    await db_session.flush()

    constraint = SLAJobConstraint(
        sla_policy_id=policy.id,
        job_id=job.id,
        track_critical_path=True,
        max_duration_minutes=15,
    )
    db_session.add(constraint)
    await db_session.flush()

    events1 = await sla_service.check_and_emit_events(db_session, policy.id)
    await db_session.flush()
    events2 = await sla_service.check_and_emit_events(db_session, policy.id)

    assert len(events1) == 1
    assert len(events2) == 0  # Deduplicated


async def test_service_met_event_when_complete(db_session: AsyncSession) -> None:
    """When all jobs are complete and on track, emit a 'met' event."""
    sla_service = SLAService()

    now = datetime.now(timezone.utc)
    policy = SLAPolicy(
        name="sla-met-test",
        target_completion_time=now + timedelta(hours=4),
        risk_window_minutes=30,
        breach_window_minutes=10,
    )
    db_session.add(policy)

    job = Job(name="met-job", job_type="shell", command="echo hi", timeout_seconds=600)
    db_session.add(job)
    await db_session.flush()

    constraint = SLAJobConstraint(
        sla_policy_id=policy.id,
        job_id=job.id,
        track_critical_path=True,
        max_duration_minutes=10,
    )
    db_session.add(constraint)

    # Create a successful completed run
    run = JobRun(
        job_id=job.id,
        status=RunStatus.SUCCESS,
        triggered_by="schedule",
        started_at=now - timedelta(minutes=10),
        finished_at=now,
    )
    db_session.add(run)
    await db_session.flush()

    events = await sla_service.check_and_emit_events(db_session, policy.id)
    assert len(events) == 1
    assert events[0].event_type == SLAEventType.MET


async def test_evaluate_all_policies(db_session: AsyncSession) -> None:
    """evaluate_all_policies should process all policies without error."""
    sla_service = SLAService()

    now = datetime.now(timezone.utc)
    for i in range(3):
        policy = SLAPolicy(
            name=f"sla-all-{i}",
            target_completion_time=now + timedelta(hours=4),
            risk_window_minutes=30,
            breach_window_minutes=10,
        )
        db_session.add(policy)
    await db_session.flush()

    # Should not raise
    count = await sla_service.evaluate_all_policies(db_session)
    assert count >= 0


# ── Pagination ──────────────────────────────────────────────────────


async def test_pagination(client: AsyncClient) -> None:
    for i in range(5):
        await _create_policy(client, f"sla-page-{i}")

    resp = await client.get("/api/sla-policies", params={"page": 2, "page_size": 2})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["pages"] == 3
    assert body["page"] == 2
