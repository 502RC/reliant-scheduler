"""SSH job handler — execute commands on remote hosts via asyncssh.

Credentials are retrieved from Azure Key Vault at runtime.
Host key validation is enforced via a known_hosts store.
"""

import asyncio
import time
from datetime import datetime, timezone

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


class SSHHandler(BaseHandler):
    """Execute commands on remote hosts via asyncssh."""

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
        import asyncssh

        log = logger.bind(
            correlation_id=correlation_id,
            job_id=job_id,
            run_id=run_id,
            handler="ssh",
        )
        log.info("ssh_execute_start", host=connection_config.get("host"))

        started_at = datetime.now(timezone.utc)
        timed_out = False

        try:
            connect_kwargs = await self._build_connect_kwargs(connection_config)
            log.info("ssh_connecting", host=connect_kwargs.get("host"))

            async with asyncssh.connect(**connect_kwargs) as conn:
                if not command:
                    finished_at = datetime.now(timezone.utc)
                    return HandlerResult(
                        exit_code=0,
                        stdout="(no command configured)",
                        stderr="",
                        timed_out=False,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=(finished_at - started_at).total_seconds(),
                    )

                # Inject parameters as environment variable exports
                full_command = command
                if parameters:
                    exports = " ".join(
                        f"{k}={_shell_escape(str(v))}" for k, v in parameters.items()
                    )
                    full_command = f"export {exports} && {command}"

                try:
                    result = await asyncio.wait_for(
                        conn.run(full_command, check=False),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    timed_out = True
                    finished_at = datetime.now(timezone.utc)
                    log.warning("ssh_timeout", timeout_seconds=timeout_seconds)
                    return HandlerResult(
                        exit_code=-1,
                        stdout="",
                        stderr=f"SSH command timed out after {timeout_seconds}s",
                        timed_out=True,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=(finished_at - started_at).total_seconds(),
                    )

                finished_at = datetime.now(timezone.utc)
                exit_code = result.exit_status if result.exit_status is not None else -1
                stdout = result.stdout or ""
                stderr = result.stderr or ""

                log.info(
                    "ssh_execute_complete",
                    exit_code=exit_code,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                )

                return HandlerResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    timed_out=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                )

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            log.exception("ssh_execute_error")
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=timed_out,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

    async def test_connection(self, connection_config: dict) -> dict:
        import asyncssh

        start = time.monotonic()
        try:
            connect_kwargs = await self._build_connect_kwargs(connection_config)
            async with asyncssh.connect(**connect_kwargs) as conn:
                result = await conn.run("echo ok", check=True)
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                return {
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "message": "SSH connection successful",
                    "capabilities": ["command_execution", "file_upload", "file_download"],
                }
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "message": str(exc),
                "capabilities": [],
            }

    async def _build_connect_kwargs(self, config: dict) -> dict:
        """Build asyncssh.connect() kwargs from connection config."""
        kwargs: dict = {
            "host": config["host"],
            "port": config.get("port", 22),
            "username": config.get("username", "root"),
            "known_hosts": config.get("known_hosts_path"),
        }

        extra = config.get("extra", {}) or {}

        # Prefer resolved credentials from the credential store
        creds = config.get("resolved_credentials")
        if creds:
            kwargs["username"] = creds.get("username", kwargs["username"])
            if creds.get("private_key"):
                kwargs["client_keys"] = [asyncssh.import_private_key(creds["private_key"])]
                if creds.get("passphrase"):
                    kwargs["passphrase"] = creds["passphrase"]
            elif creds.get("password"):
                kwargs["password"] = creds["password"]
        else:
            # Legacy path: read from extra (backward compat)
            secret_name = extra.get("key_vault_secret_name")
            if secret_name:
                secret_value = await _get_secret(secret_name)
                auth_type = extra.get("auth_type", "password")
                if auth_type == "private_key":
                    kwargs["client_keys"] = [asyncssh.import_private_key(secret_value)]
                else:
                    kwargs["password"] = secret_value
            elif extra.get("password"):
                kwargs["password"] = extra["password"]

        if extra.get("known_hosts") == "none":
            kwargs["known_hosts"] = None

        return kwargs


def _shell_escape(value: str) -> str:
    """Escape a value for safe shell variable assignment."""
    return "'" + value.replace("'", "'\"'\"'") + "'"
