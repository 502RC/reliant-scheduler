import uuid
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.job import Job, JobDependency
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.schedule import Schedule
from reliant_scheduler.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobWithRunInfoResponse,
    JobTriggerRequest,
    JobDependencyCreate,
    JobDependencyResponse,
)
from reliant_scheduler.schemas.job_run import JobRunResponse, JobRunUpdate
from reliant_scheduler.services.dag_resolver import CircularDependencyError, DagResolver
from reliant_scheduler.services.retry_handler import RetryHandler
from reliant_scheduler.services.event_emitter import emit_event

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=dict)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List jobs with latest run status, last run time, and next scheduled run.

    The response includes real-time metadata so the frontend jobs page can
    display live indicators without extra API calls.
    """
    query = select(Job)
    count_query = select(func.count(Job.id))
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = list(result.scalars().all())

    if not jobs:
        return {
            "items": [],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": 0,
        }

    job_ids = [j.id for j in jobs]

    # Subquery: latest run per job (most recent by created_at)
    latest_run_sq = (
        select(
            JobRun.job_id,
            JobRun.id.label("run_id"),
            JobRun.status.label("run_status"),
            func.coalesce(JobRun.finished_at, JobRun.started_at, JobRun.created_at).label("run_time"),
            func.row_number()
            .over(partition_by=JobRun.job_id, order_by=JobRun.created_at.desc())
            .label("rn"),
        )
        .where(JobRun.job_id.in_(job_ids))
        .subquery()
    )
    latest_runs_result = await db.execute(
        select(
            latest_run_sq.c.job_id,
            latest_run_sq.c.run_id,
            latest_run_sq.c.run_status,
            latest_run_sq.c.run_time,
        ).where(latest_run_sq.c.rn == 1)
    )
    latest_runs = {row.job_id: row for row in latest_runs_result.all()}

    # Active runs (pending/queued/running) per job
    active_result = await db.execute(
        select(JobRun.job_id)
        .where(
            JobRun.job_id.in_(job_ids),
            JobRun.status.in_([RunStatus.PENDING, RunStatus.QUEUED, RunStatus.RUNNING]),
        )
        .distinct()
    )
    active_job_ids = {row[0] for row in active_result.all()}

    # Next scheduled run per job
    schedule_result = await db.execute(
        select(Schedule.job_id, Schedule.next_run_at)
        .where(Schedule.job_id.in_(job_ids), Schedule.enabled.is_(True))
    )
    schedules = {row.job_id: row.next_run_at for row in schedule_result.all()}

    items = []
    for j in jobs:
        data = JobResponse.model_validate(j).model_dump()
        run_info = latest_runs.get(j.id)
        data["last_run_status"] = run_info.run_status if run_info else None
        data["last_run_time"] = run_info.run_time.isoformat() if run_info and run_info.run_time else None
        data["last_run_id"] = str(run_info.run_id) if run_info else None
        data["next_scheduled_run"] = schedules[j.id].isoformat() if j.id in schedules and schedules[j.id] else None
        data["is_running"] = j.id in active_job_ids
        items.append(data)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/status-summary", response_model=dict)
async def jobs_status_summary(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lightweight summary of active job runs for real-time dashboards.

    Returns counts by run status and a list of currently active runs with
    their job name, so the frontend can show live indicators.
    """
    # Counts by run status for active (non-terminal) runs
    active_statuses = [RunStatus.PENDING, RunStatus.QUEUED, RunStatus.RUNNING]
    count_result = await db.execute(
        select(JobRun.status, func.count(JobRun.id))
        .where(JobRun.status.in_(active_statuses))
        .group_by(JobRun.status)
    )
    counts = {row[0]: row[1] for row in count_result.all()}

    # Active runs with job context
    active_result = await db.execute(
        select(
            JobRun.id,
            JobRun.job_id,
            JobRun.status,
            JobRun.started_at,
            JobRun.attempt_number,
            Job.name.label("job_name"),
        )
        .join(Job, JobRun.job_id == Job.id)
        .where(JobRun.status.in_(active_statuses))
        .order_by(JobRun.created_at.desc())
        .limit(100)
    )
    active_runs = [
        {
            "run_id": str(row.id),
            "job_id": str(row.job_id),
            "job_name": row.job_name,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "attempt_number": row.attempt_number,
        }
        for row in active_result.all()
    ]

    return {
        "pending": counts.get(RunStatus.PENDING, 0),
        "queued": counts.get(RunStatus.QUEUED, 0),
        "running": counts.get(RunStatus.RUNNING, 0),
        "active_runs": active_runs,
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)) -> Job:
    job = Job(**body.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID, body: JobUpdate, db: AsyncSession = Depends(get_db)
) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()


@router.post("/{job_id}/trigger", response_model=JobRunResponse, status_code=201)
async def trigger_job(
    job_id: uuid.UUID, body: JobTriggerRequest, db: AsyncSession = Depends(get_db)
) -> JobRun:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    run = JobRun(
        job_id=job.id,
        status=RunStatus.PENDING,
        triggered_by="manual",
        parameters=body.parameters,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/{job_id}/runs", response_model=dict)
async def list_job_runs(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, alias="run_status"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(JobRun).where(JobRun.job_id == job_id)
    count_query = select(func.count(JobRun.id)).where(JobRun.job_id == job_id)
    if status:
        query = query.where(JobRun.status == status)
        count_query = count_query.where(JobRun.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(JobRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    runs = result.scalars().all()
    return {
        "items": [JobRunResponse.model_validate(r).model_dump() for r in runs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


# ------------------------------------------------------------------
# Run update endpoint (used by worker agents to report results)
# ------------------------------------------------------------------


@router.patch("/{job_id}/runs/{run_id}", response_model=JobRunResponse)
async def update_job_run(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    body: JobRunUpdate,
    db: AsyncSession = Depends(get_db),
) -> JobRun:
    """Update a job run's status, exit code, error message, log URL, and metrics.

    Used by worker agents to report execution results back to the scheduler.
    Broadcasts a ``job.status_changed`` WebSocket event on every status
    transition so the frontend jobs page updates in real time.
    """
    result = await db.execute(
        select(JobRun).where(JobRun.id == run_id, JobRun.job_id == job_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")

    previous_status = run.status

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(run, field, value)

    # Set finished_at when transitioning to a terminal status
    terminal = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT}
    if RunStatus(body.status) in terminal and run.finished_at is None:
        from datetime import datetime, timezone
        run.finished_at = datetime.now(timezone.utc)

    # Trigger retry on failure if applicable
    if RunStatus(body.status) in (RunStatus.FAILED, RunStatus.TIMED_OUT):
        retry_handler = RetryHandler()
        await retry_handler.handle_failure(db, run)

    await db.commit()
    await db.refresh(run)

    # Fetch job for event context
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    job_name = job.name if job else "unknown"

    # Broadcast real-time status change via WebSocket
    from reliant_scheduler.api.routes.ws_events import publish_job_status_change

    await publish_job_status_change(
        job_id=str(job_id),
        job_name=job_name,
        run_id=str(run_id),
        previous_status=previous_status,
        status=body.status,
        agent_id=str(body.agent_id) if body.agent_id else None,
        exit_code=body.exit_code,
        error_message=body.error_message,
    )

    # Emit to event-action system for terminal statuses
    status_event_map = {
        RunStatus.SUCCESS: "job.succeeded",
        RunStatus.FAILED: "job.failed",
        RunStatus.TIMED_OUT: "job.timed_out",
    }
    event_name = status_event_map.get(RunStatus(body.status))
    if event_name:
        await emit_event(event_name, {
            "job_id": str(job_id),
            "job_name": job_name,
            "run_id": str(run_id),
            "status": body.status,
            "error": body.error_message,
            "exit_code": body.exit_code,
        })

    return run


# ------------------------------------------------------------------
# Job dependency endpoints
# ------------------------------------------------------------------


@router.get("/{job_id}/dependencies", response_model=list[JobDependencyResponse])
async def list_job_dependencies(
    job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[JobDependency]:
    result = await db.execute(
        select(JobDependency).where(JobDependency.dependent_job_id == job_id)
    )
    return list(result.scalars().all())


@router.post("/{job_id}/dependencies", response_model=JobDependencyResponse, status_code=201)
async def add_job_dependency(
    job_id: uuid.UUID,
    body: JobDependencyCreate,
    db: AsyncSession = Depends(get_db),
) -> JobDependency:
    # Validate both jobs exist
    for jid, label in [(job_id, "Dependent job"), (body.depends_on_job_id, "Upstream job")]:
        result = await db.execute(select(Job).where(Job.id == jid))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"{label} not found")

    if job_id == body.depends_on_job_id:
        raise HTTPException(status_code=400, detail="A job cannot depend on itself")

    dep = JobDependency(dependent_job_id=job_id, depends_on_job_id=body.depends_on_job_id)
    db.add(dep)
    await db.flush()

    # Check for circular dependencies using the DAG resolver
    dag = DagResolver()
    graph = await dag.build_graph(db)
    try:
        dag.topological_sort(graph)
    except CircularDependencyError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    await db.refresh(dep)
    return dep


@router.delete("/{job_id}/dependencies/{dep_id}", status_code=204)
async def remove_job_dependency(
    job_id: uuid.UUID, dep_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    result = await db.execute(
        select(JobDependency).where(
            JobDependency.id == dep_id,
            JobDependency.dependent_job_id == job_id,
        )
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")
    await db.delete(dep)
    await db.commit()


@router.get("/{job_id}/runs/{run_id}/logs/stream")
async def stream_run_logs(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from pathlib import Path
    from fastapi.responses import PlainTextResponse, StreamingResponse
    import asyncio

    result = await db.execute(
        select(JobRun).where(JobRun.id == run_id, JobRun.job_id == job_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    log_path = Path(f"/tmp/reliant-scheduler-logs/job-outputs/{job_id}/{run_id}/output.log")

    # For completed runs, return the full log
    if run.status in ("success", "failed", "cancelled", "timed_out"):
        if not log_path.exists():
            return PlainTextResponse("No log output captured.", status_code=200)
        return PlainTextResponse(log_path.read_text(), status_code=200)

    # For active runs, stream via SSE
    async def event_generator():
        offset = 0
        while True:
            if log_path.exists():
                content = log_path.read_text()
                if len(content) > offset:
                    new_data = content[offset:]
                    offset = len(content)
                    yield f"data: {new_data}\n\n"
            # Check if run finished
            await db.refresh(run)
            if run.status in ("success", "failed", "cancelled", "timed_out"):
                # Send remaining content
                if log_path.exists():
                    content = log_path.read_text()
                    if len(content) > offset:
                        yield f"data: {content[offset:]}\n\n"
                yield "event: complete\ndata: done\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
