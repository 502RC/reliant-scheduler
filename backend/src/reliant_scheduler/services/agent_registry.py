"""Agent registry with health check tracking.

Manages worker agent registration, heartbeats, and availability.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.agent import Agent, AgentStatus
from reliant_scheduler.services.event_emitter import emit_event

logger = structlog.get_logger(__name__)


HEARTBEAT_TIMEOUT = timedelta(minutes=5)


class AgentRegistry:
    """Manages worker agent lifecycle and health."""

    async def register(
        self, session: AsyncSession, hostname: str, labels: dict | None = None, max_concurrent: int = 4
    ) -> Agent:
        result = await session.execute(select(Agent).where(Agent.hostname == hostname))
        agent = result.scalar_one_or_none()
        if agent:
            agent.status = AgentStatus.ONLINE
            agent.last_heartbeat_at = datetime.now(timezone.utc)
            agent.labels = labels or agent.labels
            agent.max_concurrent_jobs = max_concurrent
        else:
            agent = Agent(
                hostname=hostname,
                status=AgentStatus.ONLINE,
                labels=labels,
                max_concurrent_jobs=max_concurrent,
                last_heartbeat_at=datetime.now(timezone.utc),
            )
            session.add(agent)
        await session.flush()
        return agent

    async def heartbeat(self, session: AsyncSession, agent_id: uuid.UUID) -> None:
        await session.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(
                last_heartbeat_at=datetime.now(timezone.utc),
                status=AgentStatus.ONLINE,
            )
        )

    async def get_available_agents(self, session: AsyncSession) -> list[Agent]:
        result = await session.execute(
            select(Agent).where(Agent.status == AgentStatus.ONLINE)
        )
        return list(result.scalars().all())

    async def mark_stale_agents(self, session: AsyncSession) -> int:
        """Mark agents that haven't sent a heartbeat recently as offline."""
        cutoff = datetime.now(timezone.utc) - HEARTBEAT_TIMEOUT

        # Find stale agents before updating so we can emit events
        stale_result = await session.execute(
            select(Agent).where(
                Agent.status == AgentStatus.ONLINE,
                Agent.last_heartbeat_at < cutoff,
            )
        )
        stale_agents = list(stale_result.scalars().all())

        result = await session.execute(
            update(Agent)
            .where(Agent.status == AgentStatus.ONLINE, Agent.last_heartbeat_at < cutoff)
            .values(status=AgentStatus.OFFLINE)
        )

        for agent in stale_agents:
            await emit_event("agent.offline", {
                "agent_id": str(agent.id),
                "hostname": agent.hostname,
            })
            await emit_event("agent.heartbeat_missed", {
                "agent_id": str(agent.id),
                "hostname": agent.hostname,
                "last_heartbeat": agent.last_heartbeat_at.isoformat() if agent.last_heartbeat_at else None,
            })

        return result.rowcount  # type: ignore[return-value]
