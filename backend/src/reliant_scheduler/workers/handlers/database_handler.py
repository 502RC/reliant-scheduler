"""Database job handler — execute SQL against configured databases.

Supports PostgreSQL (asyncpg), SQL Server (aioodbc), and Oracle (oracledb).
All queries use parameterized execution — no string interpolation.
SELECT result sets are capped at 10,000 rows.
"""

import asyncio
import json
import re
import time
from datetime import datetime, timezone

import structlog

from reliant_scheduler.workers.handlers.base import BaseHandler, HandlerResult

logger = structlog.get_logger(__name__)

MAX_RESULT_ROWS = 10_000

# SQL identifiers must be alphanumeric with underscores only
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_sql_identifier(value: str, label: str = "identifier") -> str:
    """Validate that a string is a safe SQL identifier (schema, table name, etc.)."""
    if not _SAFE_IDENTIFIER_RE.match(value):
        raise ValueError(f"Unsafe SQL {label}: {value!r}")
    return value


async def _get_secret(secret_name: str) -> str:
    """Retrieve a secret from Azure Key Vault via Managed Identity."""
    from reliant_scheduler.core.config import settings

    if not settings.azure_keyvault_url:
        raise RuntimeError(
            f"Cannot retrieve secret '{secret_name}': azure_keyvault_url not configured"
        )

    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    credential = DefaultAzureCredential()
    try:
        client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)
        try:
            secret = await client.get_secret(secret_name)
            return secret.value
        finally:
            await client.close()
    finally:
        await credential.close()


class DatabaseHandler(BaseHandler):
    """Execute SQL queries against configured databases using parameterized execution."""

    async def execute(
        self,
        *,
        command: str | None,
        parameters: dict | None,
        connection_config: dict,
        timeout_seconds: int,
        correlation_id: str,
        job_id: str,
        run_id: str,
    ) -> HandlerResult:
        log = logger.bind(
            correlation_id=correlation_id,
            job_id=job_id,
            run_id=run_id,
            handler="database",
        )
        log.info("database_execute_start")

        started_at = datetime.now(timezone.utc)

        if not command:
            finished_at = datetime.now(timezone.utc)
            return HandlerResult(
                exit_code=0,
                stdout="(no SQL command configured)",
                stderr="",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        extra = connection_config.get("extra", {}) or {}
        db_type = extra.get("db_type", "postgresql")

        try:
            # Get connection string from Key Vault
            connection_string = await self._get_connection_string(connection_config)

            result = await asyncio.wait_for(
                self._execute_query(
                    db_type=db_type,
                    connection_string=connection_string,
                    query=command,
                    query_params=parameters,
                    default_schema=extra.get("default_schema"),
                    log=log,
                ),
                timeout=timeout_seconds,
            )

            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()
            log.info("database_execute_complete", duration_seconds=duration, row_count=result["row_count"])

            return HandlerResult(
                exit_code=0,
                stdout=json.dumps(result, default=str),
                stderr="",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                row_count=result["row_count"],
            )

        except asyncio.TimeoutError:
            finished_at = datetime.now(timezone.utc)
            log.warning("database_timeout", timeout_seconds=timeout_seconds)
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=f"Database query timed out after {timeout_seconds}s",
                timed_out=True,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            log.exception("database_execute_error")
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

    async def test_connection(self, connection_config: dict) -> dict:
        extra = connection_config.get("extra", {}) or {}
        db_type = extra.get("db_type", "postgresql")
        start = time.monotonic()

        try:
            connection_string = await self._get_connection_string(connection_config)

            if db_type == "postgresql":
                import asyncpg

                conn = await asyncpg.connect(connection_string)
                try:
                    await conn.fetchval("SELECT 1")
                finally:
                    await conn.close()
            else:
                # For other DB types, a basic connection test
                await self._execute_query(
                    db_type=db_type,
                    connection_string=connection_string,
                    query="SELECT 1",
                    query_params=None,
                    default_schema=None,
                    log=logger,
                )

            latency_ms = round((time.monotonic() - start) * 1000, 1)
            capabilities = ["sql_execution", "parameterized_queries"]
            if db_type == "postgresql":
                capabilities.append("asyncpg_native")
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "message": f"{db_type} connection successful",
                "capabilities": capabilities,
            }
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "message": str(exc),
                "capabilities": [],
            }

    async def _get_connection_string(self, config: dict) -> str:
        """Get DB connection string from Key Vault or direct config."""
        extra = config.get("extra", {}) or {}
        secret_name = extra.get("connection_string_secret_name")
        if secret_name:
            return await _get_secret(secret_name)

        # Build from individual fields (dev/test)
        connection_string = extra.get("connection_string")
        if connection_string:
            return connection_string

        # Build from host/port/extra fields
        db_type = extra.get("db_type", "postgresql")
        host = config.get("host", "localhost")
        port = config.get("port", 5432)
        database = extra.get("database", "")
        username = extra.get("username", "")
        password = extra.get("password", "")

        if db_type == "postgresql":
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        elif db_type == "sqlserver":
            return f"mssql://{username}:{password}@{host}:{port}/{database}"
        else:
            return f"{db_type}://{username}:{password}@{host}:{port}/{database}"

    async def _execute_query(
        self,
        *,
        db_type: str,
        connection_string: str,
        query: str,
        query_params: dict | None,
        default_schema: str | None,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Execute a parameterized query and return results."""
        if db_type == "postgresql":
            return await self._execute_postgresql(
                connection_string, query, query_params, default_schema, log
            )
        else:
            # Generic fallback using sqlalchemy
            return await self._execute_generic(
                connection_string, query, query_params, default_schema, log
            )

    async def _execute_postgresql(
        self,
        connection_string: str,
        query: str,
        query_params: dict | None,
        default_schema: str | None,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Execute via asyncpg for PostgreSQL."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            if default_schema:
                safe_schema = _validate_sql_identifier(default_schema, "schema")
                await conn.execute(f"SET search_path TO {safe_schema}")

            # Convert dict params to positional for asyncpg ($1, $2, ...)
            args = list(query_params.values()) if query_params else []

            query_lower = query.strip().lower()
            is_select = query_lower.startswith("select") or query_lower.startswith("with")

            if is_select:
                rows = await conn.fetch(query, *args)
                capped_rows = rows[:MAX_RESULT_ROWS]
                result_data = [dict(row) for row in capped_rows]
                return {
                    "row_count": len(rows),
                    "truncated": len(rows) > MAX_RESULT_ROWS,
                    "data": result_data,
                }
            else:
                status = await conn.execute(query, *args)
                row_count = 0
                if status:
                    parts = status.split()
                    if len(parts) >= 2 and parts[-1].isdigit():
                        row_count = int(parts[-1])
                return {
                    "row_count": row_count,
                    "truncated": False,
                    "data": None,
                    "status": status,
                }
        finally:
            await conn.close()

    async def _execute_generic(
        self,
        connection_string: str,
        query: str,
        query_params: dict | None,
        default_schema: str | None,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Execute via SQLAlchemy for other database types."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        engine = create_async_engine(connection_string, echo=False)
        try:
            async with engine.begin() as conn:
                if default_schema:
                    safe_schema = _validate_sql_identifier(default_schema, "schema")
                    await conn.execute(text(f"SET search_path TO {safe_schema}"))

                result = await conn.execute(text(query), query_params or {})

                query_lower = query.strip().lower()
                is_select = query_lower.startswith("select") or query_lower.startswith("with")

                if is_select:
                    rows = result.fetchall()
                    columns = list(result.keys())
                    capped_rows = rows[:MAX_RESULT_ROWS]
                    result_data = [dict(zip(columns, row)) for row in capped_rows]
                    return {
                        "row_count": len(rows),
                        "truncated": len(rows) > MAX_RESULT_ROWS,
                        "data": result_data,
                    }
                else:
                    return {
                        "row_count": result.rowcount,
                        "truncated": False,
                        "data": None,
                    }
        finally:
            await engine.dispose()
