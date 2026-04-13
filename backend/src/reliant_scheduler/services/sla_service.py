"""SLA management service.

Provides critical path computation over job dependency graphs,
risk/breach window evaluation, and SLA event emission during
scheduler ticks.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reliant_scheduler.core.metrics import SLA_BREACHES_TOTAL, SLA_AT_RISK_TOTAL
from reliant_scheduler.models.job import Job, JobDependency
from reliant_scheduler.models.job_run import JobRun, RunStatus
from reliant_scheduler.models.sla import SLAEvent, SLAEventType, SLAJobConstraint, SLAPolicy
from reliant_scheduler.services.apm_publisher import publish_sla_event
from reliant_scheduler.services.event_emitter import emit_event

logger = structlog.get_logger(__name__)


@dataclass
class CriticalPathNode:
    job_id: uuid.UUID
    job_name: str
    estimated_duration_minutes: int
    dependencies: list[uuid.UUID]


class SLAService:
    """Evaluates SLA policies: critical path, risk windows, breach detection."""

    async def compute_critical_path(
        self, session: AsyncSession, policy_id: uuid.UUID
    ) -> tuple[list[CriticalPathNode], int]:
        """Compute the critical path for an SLA policy.

        The critical path is the longest dependent chain by estimated duration
        among jobs linked to this policy with ``track_critical_path=True``.

        Returns (path_nodes, total_duration_minutes).
        """
        # Load constraints for this policy
        result = await session.execute(
            select(SLAJobConstraint)
            .where(
                SLAJobConstraint.sla_policy_id == policy_id,
                SLAJobConstraint.track_critical_path.is_(True),
            )
            .options(selectinload(SLAJobConstraint.job))
        )
        constraints = list(result.scalars().all())

        if not constraints:
            return [], 0

        # Build a set of tracked job IDs and a map from job_id to constraint
        tracked_ids = {c.job_id for c in constraints}
        constraint_map = {c.job_id: c for c in constraints}
        job_map = {c.job_id: c.job for c in constraints if c.job}

        # Load dependencies between tracked jobs
        deps_result = await session.execute(
            select(JobDependency).where(
                JobDependency.dependent_job_id.in_(tracked_ids),
                JobDependency.depends_on_job_id.in_(tracked_ids),
            )
        )
        deps = list(deps_result.scalars().all())

        # Build adjacency: dependent -> [depends_on]
        dep_map: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for d in deps:
            dep_map[d.dependent_job_id].append(d.depends_on_job_id)

        # Compute duration for each job: use max_duration_minutes from constraint,
        # or fall back to timeout_seconds from the job definition
        def _get_duration(job_id: uuid.UUID) -> int:
            c = constraint_map.get(job_id)
            if c and c.max_duration_minutes:
                return c.max_duration_minutes
            job = job_map.get(job_id)
            if job:
                return max(1, job.timeout_seconds // 60)
            return 1

        # Longest-path DP using memoization (DAG assumed acyclic)
        memo: dict[uuid.UUID, tuple[int, list[uuid.UUID]]] = {}

        def _longest_path(node_id: uuid.UUID) -> tuple[int, list[uuid.UUID]]:
            """Return (total_duration, path_list) for the longest path ending at node_id."""
            if node_id in memo:
                return memo[node_id]

            duration = _get_duration(node_id)
            upstream_ids = dep_map.get(node_id, [])

            if not upstream_ids:
                memo[node_id] = (duration, [node_id])
                return memo[node_id]

            best_dur = 0
            best_path: list[uuid.UUID] = []
            for up_id in upstream_ids:
                up_dur, up_path = _longest_path(up_id)
                if up_dur > best_dur:
                    best_dur = up_dur
                    best_path = up_path

            total = best_dur + duration
            path = best_path + [node_id]
            memo[node_id] = (total, path)
            return memo[node_id]

        # Find the longest path across all tracked jobs
        best_total = 0
        best_full_path: list[uuid.UUID] = []
        for jid in tracked_ids:
            total, path = _longest_path(jid)
            if total > best_total:
                best_total = total
                best_full_path = path

        # Build response nodes
        nodes = []
        for jid in best_full_path:
            job = job_map.get(jid)
            nodes.append(
                CriticalPathNode(
                    job_id=jid,
                    job_name=job.name if job else "unknown",
                    estimated_duration_minutes=_get_duration(jid),
                    dependencies=dep_map.get(jid, []),
                )
            )

        return nodes, best_total

    async def evaluate_sla_status(
        self, session: AsyncSession, policy_id: uuid.UUID
    ) -> tuple[str, datetime | None, int]:
        """Evaluate current SLA status for a policy.

        Returns (status, estimated_completion_time, remaining_duration_minutes).
        Status is one of: on_track, at_risk, breached.
        """
        result = await session.execute(
            select(SLAPolicy).where(SLAPolicy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            return "unknown", None, 0

        now = datetime.now(timezone.utc)
        _, total_duration = await self.compute_critical_path(session, policy_id)

        # Check progress: find completed runs for constrained jobs
        constraints_result = await session.execute(
            select(SLAJobConstraint).where(SLAJobConstraint.sla_policy_id == policy_id)
        )
        constraints = list(constraints_result.scalars().all())
        job_ids = [c.job_id for c in constraints]

        completed_duration = 0
        if job_ids:
            for job_id in job_ids:
                latest_run_result = await session.execute(
                    select(JobRun)
                    .where(JobRun.job_id == job_id, JobRun.status == RunStatus.SUCCESS)
                    .order_by(JobRun.finished_at.desc())
                    .limit(1)
                )
                run = latest_run_result.scalar_one_or_none()
                if run and run.started_at and run.finished_at:
                    elapsed = (run.finished_at - run.started_at).total_seconds() / 60.0
                    completed_duration += elapsed

        remaining = max(0, total_duration - int(completed_duration))
        estimated_completion = now + timedelta(minutes=remaining)

        target = policy.target_completion_time
        risk_threshold = target - timedelta(minutes=policy.risk_window_minutes)

        if estimated_completion > target:
            status = "breached"
        elif estimated_completion > risk_threshold:
            status = "at_risk"
        else:
            status = "on_track"

        return status, estimated_completion, remaining

    async def check_and_emit_events(
        self, session: AsyncSession, policy_id: uuid.UUID
    ) -> list[SLAEvent]:
        """Check SLA policy and emit at_risk/breached/met events as needed.

        Called during each scheduler tick.
        """
        sla_status, estimated_completion, remaining = await self.evaluate_sla_status(
            session, policy_id
        )

        result = await session.execute(
            select(SLAPolicy).where(SLAPolicy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            return []

        emitted: list[SLAEvent] = []
        now = datetime.now(timezone.utc)

        # Check if we already emitted this event type recently (within last hour)
        # to avoid duplicate spam
        recent_result = await session.execute(
            select(SLAEvent)
            .where(
                SLAEvent.sla_policy_id == policy_id,
                SLAEvent.triggered_at > now - timedelta(hours=1),
            )
            .order_by(SLAEvent.triggered_at.desc())
        )
        recent_events = list(recent_result.scalars().all())
        recent_types = {e.event_type for e in recent_events}

        if sla_status == "at_risk" and SLAEventType.AT_RISK not in recent_types:
            event = SLAEvent(
                sla_policy_id=policy_id,
                event_type=SLAEventType.AT_RISK,
                triggered_at=now,
                details_json={
                    "estimated_completion": estimated_completion.isoformat() if estimated_completion else None,
                    "remaining_minutes": remaining,
                    "target": policy.target_completion_time.isoformat(),
                },
            )
            session.add(event)
            emitted.append(event)
            SLA_AT_RISK_TOTAL.inc()
            await publish_sla_event(
                job_id="",
                sla_status="at_risk",
                breach_window=str(policy.risk_window_minutes),
                correlation_id=str(policy_id),
            )
            await emit_event("sla.at_risk", {
                "policy_id": str(policy_id),
                "policy_name": policy.name,
                "remaining_minutes": remaining,
                "target": policy.target_completion_time.isoformat(),
            })
            logger.warning(
                "sla_at_risk",
                policy_id=str(policy_id),
                policy_name=policy.name,
                remaining_minutes=remaining,
            )

        elif sla_status == "breached" and SLAEventType.BREACHED not in recent_types:
            event = SLAEvent(
                sla_policy_id=policy_id,
                event_type=SLAEventType.BREACHED,
                triggered_at=now,
                details_json={
                    "estimated_completion": estimated_completion.isoformat() if estimated_completion else None,
                    "remaining_minutes": remaining,
                    "target": policy.target_completion_time.isoformat(),
                },
            )
            session.add(event)
            emitted.append(event)
            SLA_BREACHES_TOTAL.inc()
            await publish_sla_event(
                job_id="",
                sla_status="breached",
                breach_window=str(policy.breach_window_minutes),
                correlation_id=str(policy_id),
            )
            await emit_event("sla.breached", {
                "policy_id": str(policy_id),
                "policy_name": policy.name,
                "remaining_minutes": remaining,
                "target": policy.target_completion_time.isoformat(),
            })
            logger.error(
                "sla_breached",
                policy_id=str(policy_id),
                policy_name=policy.name,
                remaining_minutes=remaining,
            )

        elif sla_status == "on_track":
            # If all jobs are complete and we're on track, emit "met" once
            if remaining == 0 and SLAEventType.MET not in recent_types:
                event = SLAEvent(
                    sla_policy_id=policy_id,
                    event_type=SLAEventType.MET,
                    triggered_at=now,
                    details_json={
                        "target": policy.target_completion_time.isoformat(),
                    },
                )
                session.add(event)
                emitted.append(event)
                await publish_sla_event(
                    job_id="",
                    sla_status="met",
                    correlation_id=str(policy_id),
                )
                await emit_event("sla.met", {
                    "policy_id": str(policy_id),
                    "policy_name": policy.name,
                    "target": policy.target_completion_time.isoformat(),
                })
                logger.info(
                    "sla_met",
                    policy_id=str(policy_id),
                    policy_name=policy.name,
                )

        return emitted

    async def evaluate_all_policies(self, session: AsyncSession) -> int:
        """Evaluate all SLA policies. Called from the scheduler tick.

        Returns the number of events emitted.
        """
        result = await session.execute(select(SLAPolicy))
        policies = list(result.scalars().all())

        total_events = 0
        for policy in policies:
            try:
                events = await self.check_and_emit_events(session, policy.id)
                total_events += len(events)
            except Exception:
                logger.exception("sla_evaluation_failed", policy_id=str(policy.id))

        if total_events:
            await session.flush()
        return total_events
