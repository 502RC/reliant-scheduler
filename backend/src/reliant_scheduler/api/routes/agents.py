import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.agent import Agent
from reliant_scheduler.schemas.agent import AgentRegisterRequest, AgentResponse
from reliant_scheduler.services.agent_registry import AgentRegistry

router = APIRouter(prefix="/api/agents", tags=["agents"])
registry = AgentRegistry()


@router.get("", response_model=dict)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Agent)
    count_query = select(func.count(Agent.id))
    if status:
        query = query.where(Agent.status == status)
        count_query = count_query.where(Agent.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Agent.hostname)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    agents = result.scalars().all()
    return {
        "items": [AgentResponse.model_validate(a).model_dump() for a in agents],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/register", response_model=AgentResponse, status_code=201)
async def register_agent(body: AgentRegisterRequest, db: AsyncSession = Depends(get_db)) -> Agent:
    agent = await registry.register(db, body.hostname, body.labels, body.max_concurrent_jobs)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/heartbeat", status_code=204)
async def agent_heartbeat(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    await registry.heartbeat(db, agent_id)
    await db.commit()
