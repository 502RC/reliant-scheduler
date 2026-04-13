import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.environment import Environment
from reliant_scheduler.schemas.environment import EnvironmentCreate, EnvironmentUpdate, EnvironmentResponse

router = APIRouter(prefix="/api/environments", tags=["environments"])


@router.get("", response_model=dict)
async def list_environments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_production: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Environment)
    count_query = select(func.count(Environment.id))
    if is_production is not None:
        query = query.where(Environment.is_production == is_production)
        count_query = count_query.where(Environment.is_production == is_production)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Environment.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    environments = result.scalars().all()
    return {
        "items": [EnvironmentResponse.model_validate(e).model_dump() for e in environments],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{env_id}", response_model=EnvironmentResponse)
async def get_environment(env_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Environment:
    result = await db.execute(select(Environment).where(Environment.id == env_id))
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(body: EnvironmentCreate, db: AsyncSession = Depends(get_db)) -> Environment:
    env = Environment(**body.model_dump())
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


@router.patch("/{env_id}", response_model=EnvironmentResponse)
async def update_environment(
    env_id: uuid.UUID, body: EnvironmentUpdate, db: AsyncSession = Depends(get_db)
) -> Environment:
    result = await db.execute(select(Environment).where(Environment.id == env_id))
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(env, field, value)
    await db.commit()
    await db.refresh(env)
    return env


@router.delete("/{env_id}", status_code=204)
async def delete_environment(env_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Environment).where(Environment.id == env_id))
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    await db.delete(env)
    await db.commit()
