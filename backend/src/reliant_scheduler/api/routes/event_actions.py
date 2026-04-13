"""API routes for event-action automation.

Provides CRUD for event types, actions, event-action bindings,
action execution history queries, and test-action endpoint.
"""

import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.event_action import (
    Action,
    ActionExecution,
    EventActionBinding,
    EventType,
)
from reliant_scheduler.schemas.event_action import (
    ActionCreate,
    ActionExecutionResponse,
    ActionResponse,
    ActionTestRequest,
    ActionUpdate,
    EventActionBindingCreate,
    EventActionBindingResponse,
    EventActionBindingUpdate,
    EventTypeCreate,
    EventTypeResponse,
)
from reliant_scheduler.services.action_executor import execute_action

# ---------------------------------------------------------------------------
# Event Types Router
# ---------------------------------------------------------------------------

event_types_router = APIRouter(prefix="/api/event-types", tags=["event-types"])


@event_types_router.get("", response_model=dict)
async def list_event_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count_query = select(func.count(EventType.id))
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        select(EventType)
        .order_by(EventType.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "items": [EventTypeResponse.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@event_types_router.post("", response_model=EventTypeResponse, status_code=201)
async def create_event_type(
    body: EventTypeCreate, db: AsyncSession = Depends(get_db)
) -> EventType:
    et = EventType(**body.model_dump())
    db.add(et)
    await db.commit()
    await db.refresh(et)
    return et


# ---------------------------------------------------------------------------
# Actions Router
# ---------------------------------------------------------------------------

actions_router = APIRouter(prefix="/api/actions", tags=["actions"])


@actions_router.get("", response_model=dict)
async def list_actions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Action)
    count_query = select(func.count(Action.id))

    if action_type:
        query = query.where(Action.type == action_type)
        count_query = count_query.where(Action.type == action_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Action.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "items": [ActionResponse.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@actions_router.post("", response_model=ActionResponse, status_code=201)
async def create_action(
    body: ActionCreate, db: AsyncSession = Depends(get_db)
) -> Action:
    action = Action(**body.model_dump())
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@actions_router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Action:
    result = await db.execute(select(Action).where(Action.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@actions_router.patch("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: uuid.UUID,
    body: ActionUpdate,
    db: AsyncSession = Depends(get_db),
) -> Action:
    result = await db.execute(select(Action).where(Action.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(action, field, value)
    await db.commit()
    await db.refresh(action)
    return action


@actions_router.delete("/{action_id}", status_code=204)
async def delete_action(
    action_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    result = await db.execute(select(Action).where(Action.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    await db.delete(action)
    await db.commit()


@actions_router.post("/{action_id}/test", response_model=dict)
async def test_action(
    action_id: uuid.UUID,
    body: ActionTestRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test notification for an action."""
    result = await db.execute(select(Action).where(Action.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    sample_data = {
        "event_type": "test",
        "job_name": "test-job",
        "status": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **body.sample_event_data,
    }
    success, error = await execute_action(action.type, action.config_json, sample_data)
    return {"success": success, "error": error}


# ---------------------------------------------------------------------------
# Event-Action Bindings Router
# ---------------------------------------------------------------------------

bindings_router = APIRouter(prefix="/api/event-action-bindings", tags=["event-action-bindings"])


@bindings_router.get("", response_model=dict)
async def list_bindings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
    enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(EventActionBinding)
    count_query = select(func.count(EventActionBinding.id))

    if event_type_id:
        query = query.where(EventActionBinding.event_type_id == event_type_id)
        count_query = count_query.where(EventActionBinding.event_type_id == event_type_id)
    if action_id:
        query = query.where(EventActionBinding.action_id == action_id)
        count_query = count_query.where(EventActionBinding.action_id == action_id)
    if enabled is not None:
        query = query.where(EventActionBinding.enabled == enabled)
        count_query = count_query.where(EventActionBinding.enabled == enabled)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(EventActionBinding.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "items": [EventActionBindingResponse.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@bindings_router.post("", response_model=EventActionBindingResponse, status_code=201)
async def create_binding(
    body: EventActionBindingCreate, db: AsyncSession = Depends(get_db)
) -> EventActionBinding:
    # Verify event type exists
    et_result = await db.execute(select(EventType).where(EventType.id == body.event_type_id))
    if not et_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event type not found")

    # Verify action exists
    action_result = await db.execute(select(Action).where(Action.id == body.action_id))
    if not action_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Action not found")

    binding = EventActionBinding(**body.model_dump())
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return binding


@bindings_router.get("/{binding_id}", response_model=EventActionBindingResponse)
async def get_binding(
    binding_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> EventActionBinding:
    result = await db.execute(
        select(EventActionBinding).where(EventActionBinding.id == binding_id)
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    return binding


@bindings_router.patch("/{binding_id}", response_model=EventActionBindingResponse)
async def update_binding(
    binding_id: uuid.UUID,
    body: EventActionBindingUpdate,
    db: AsyncSession = Depends(get_db),
) -> EventActionBinding:
    result = await db.execute(
        select(EventActionBinding).where(EventActionBinding.id == binding_id)
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(binding, field, value)
    await db.commit()
    await db.refresh(binding)
    return binding


@bindings_router.delete("/{binding_id}", status_code=204)
async def delete_binding(
    binding_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    result = await db.execute(
        select(EventActionBinding).where(EventActionBinding.id == binding_id)
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")
    await db.delete(binding)
    await db.commit()


# ---------------------------------------------------------------------------
# Action Executions Router
# ---------------------------------------------------------------------------

executions_router = APIRouter(prefix="/api/action-executions", tags=["action-executions"])


@executions_router.get("", response_model=dict)
async def list_action_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_action_binding_id: uuid.UUID | None = None,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(ActionExecution)
    count_query = select(func.count(ActionExecution.id))

    if event_action_binding_id:
        query = query.where(ActionExecution.event_action_binding_id == event_action_binding_id)
        count_query = count_query.where(ActionExecution.event_action_binding_id == event_action_binding_id)
    if status:
        query = query.where(ActionExecution.status == status)
        count_query = count_query.where(ActionExecution.status == status)
    if start_date:
        query = query.where(ActionExecution.executed_at >= start_date)
        count_query = count_query.where(ActionExecution.executed_at >= start_date)
    if end_date:
        query = query.where(ActionExecution.executed_at <= end_date)
        count_query = count_query.where(ActionExecution.executed_at <= end_date)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(ActionExecution.executed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {
        "items": [ActionExecutionResponse.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }
