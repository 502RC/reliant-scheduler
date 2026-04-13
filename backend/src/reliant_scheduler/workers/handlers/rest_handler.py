"""REST API job handler — make HTTP calls to external APIs.

Supports GET/POST/PUT/PATCH/DELETE with templated URL and body.
Auth types: api_key, oauth2, basic. Credentials from Key Vault.
"""

import asyncio
import json
import re
import time
from datetime import datetime, timezone

import httpx
import structlog

from reliant_scheduler.workers.handlers.base import BaseHandler, HandlerResult

logger = structlog.get_logger(__name__)


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


def _render_template(template: str, variables: dict | None) -> str:
    """Replace ${var_name} placeholders with values from variables dict."""
    if not variables or not template:
        return template

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return re.sub(r"\$\{(\w+)}", replacer, template)


class RESTHandler(BaseHandler):
    """Execute HTTP calls to external REST APIs."""

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
            handler="rest_api",
        )
        log.info("rest_execute_start")

        started_at = datetime.now(timezone.utc)
        extra = connection_config.get("extra", {}) or {}
        base_url = extra.get("base_url", connection_config.get("host", ""))

        if not command:
            finished_at = datetime.now(timezone.utc)
            return HandlerResult(
                exit_code=0,
                stdout="(no REST command configured)",
                stderr="",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        try:
            # Parse command: "METHOD /path" or just "/path" (defaults to GET)
            # or a JSON config: {"method": "POST", "path": "/api/data", "body": {...}}
            request_config = self._parse_command(command, parameters)

            # Build auth headers
            headers = dict(extra.get("default_headers", {}) or {})
            headers.update(await self._build_auth_headers(extra))

            url = base_url.rstrip("/") + "/" + request_config["path"].lstrip("/")
            url = _render_template(url, parameters)

            body = request_config.get("body")
            if isinstance(body, str):
                body = _render_template(body, parameters)
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    pass

            method = request_config.get("method", "GET").upper()

            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if isinstance(body, str) else None,
                )

            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()

            exit_code = 0 if response.is_success else 1
            result_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:50000],
            }

            log.info(
                "rest_execute_complete",
                status_code=response.status_code,
                duration_seconds=duration,
            )

            return HandlerResult(
                exit_code=exit_code,
                stdout=json.dumps(result_data, default=str),
                stderr="" if response.is_success else f"HTTP {response.status_code}",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
            )

        except httpx.TimeoutException:
            finished_at = datetime.now(timezone.utc)
            log.warning("rest_timeout", timeout_seconds=timeout_seconds)
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=f"REST request timed out after {timeout_seconds}s",
                timed_out=True,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            log.exception("rest_execute_error")
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
        base_url = extra.get("base_url", connection_config.get("host", ""))
        start = time.monotonic()

        try:
            headers = dict(extra.get("default_headers", {}) or {})
            headers.update(await self._build_auth_headers(extra))

            # Attempt a HEAD request to the base URL
            test_path = extra.get("health_check_path", "/")
            url = base_url.rstrip("/") + test_path

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(url, headers=headers)

            latency_ms = round((time.monotonic() - start) * 1000, 1)
            capabilities = ["GET", "POST", "PUT", "PATCH", "DELETE"]
            return {
                "status": "ok" if response.is_success else "error",
                "latency_ms": latency_ms,
                "message": f"HTTP {response.status_code}",
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

    def _parse_command(self, command: str, parameters: dict | None) -> dict:
        """Parse command string into request config.

        Supports:
        - "GET /api/endpoint"
        - "/api/endpoint" (defaults to GET)
        - JSON: {"method": "POST", "path": "/api/data", "body": {...}}
        """
        command = command.strip()

        # Try JSON first
        if command.startswith("{"):
            try:
                return json.loads(command)
            except json.JSONDecodeError:
                pass

        # "METHOD /path" format
        parts = command.split(None, 1)
        if len(parts) == 2 and parts[0].upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            return {"method": parts[0].upper(), "path": parts[1]}

        # Just a path
        return {"method": "GET", "path": command}

    async def _build_auth_headers(self, extra: dict) -> dict:
        """Build authentication headers from connection extra config."""
        auth_type = extra.get("auth_type", "")
        auth_secret_name = extra.get("auth_secret_name")
        headers = {}

        if not auth_type or not auth_secret_name:
            return headers

        secret_value = await _get_secret(auth_secret_name)

        if auth_type == "api_key":
            header_name = extra.get("api_key_header", "X-API-Key")
            headers[header_name] = secret_value
        elif auth_type == "bearer" or auth_type == "oauth2":
            headers["Authorization"] = f"Bearer {secret_value}"
        elif auth_type == "basic":
            import base64
            headers["Authorization"] = f"Basic {base64.b64encode(secret_value.encode()).decode()}"

        return headers
