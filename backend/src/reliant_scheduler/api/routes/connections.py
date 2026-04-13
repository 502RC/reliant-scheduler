import math
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.core.database import get_db
from reliant_scheduler.models.connection import Connection
from reliant_scheduler.schemas.connection import ConnectionCreate, ConnectionUpdate, ConnectionResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("", response_model=dict)
async def list_connections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    connection_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Connection)
    count_query = select(func.count(Connection.id))
    if connection_type:
        query = query.where(Connection.connection_type == connection_type)
        count_query = count_query.where(Connection.connection_type == connection_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Connection.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    connections = result.scalars().all()
    return {
        "items": [ConnectionResponse.model_validate(c).model_dump() for c in connections],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Connection:
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(body: ConnectionCreate, db: AsyncSession = Depends(get_db)) -> Connection:
    conn = Connection(**body.model_dump())
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


@router.patch("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: uuid.UUID, body: ConnectionUpdate, db: AsyncSession = Depends(get_db)
) -> Connection:
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(conn, field, value)
    await db.commit()
    await db.refresh(conn)
    return conn


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(connection_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.commit()


@router.post("/{connection_id}/test")
async def test_connection(connection_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Test connectivity for a connection without running a job.

    Returns latency, auth status, and capability list.
    Connection test results never include raw credentials.
    """
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    from reliant_scheduler.workers.handlers.registry import get_handler

    try:
        handler = get_handler(conn.connection_type)
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"No handler for connection type: {conn.connection_type}",
        )

    connection_config = {
        "host": conn.host,
        "port": conn.port,
        "connection_type": conn.connection_type,
        "extra": conn.extra or {},
    }

    # Resolve credentials from Key Vault if credential_id is set
    if conn.credential_id:
        from reliant_scheduler.services.credential_resolver import resolve_credential
        connection_config["resolved_credentials"] = await resolve_credential(
            conn.credential_id, db
        )

    test_result = await handler.test_connection(connection_config)
    logger.info(
        "connection_test",
        connection_id=str(connection_id),
        connection_type=conn.connection_type,
        status=test_result.get("status"),
    )
    return test_result
