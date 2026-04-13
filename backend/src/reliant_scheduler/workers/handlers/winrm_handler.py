"""WinRM/PowerShell handler — execute commands on remote Windows hosts via pypsrp.

Uses PowerShell Remoting (WinRM) to run commands on Windows machines.
Credentials are retrieved from Azure Key Vault at runtime.
"""

import os
import time
from datetime import datetime, timezone

import structlog

from reliant_scheduler.workers.handlers.base import BaseHandler, HandlerResult

logger = structlog.get_logger(__name__)

_LOCAL_LOG_DIR = "/tmp/reliant-scheduler-logs"


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


class WinRMHandler(BaseHandler):
    """Execute PowerShell commands on remote Windows hosts via WinRM/pypsrp."""

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
        import asyncio

        log = logger.bind(
            correlation_id=correlation_id,
            job_id=job_id,
            run_id=run_id,
            handler="winrm",
        )
        host = connection_config.get("host", "unknown")
        log.info("winrm_execute_start", host=host)

        started_at = datetime.now(timezone.utc)

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

        # Prepare log file for streaming output
        log_path = os.path.join(
            _LOCAL_LOG_DIR, f"job-outputs/{job_id}/{run_id}/output.log"
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            pass

        try:
            connect_kwargs = await self._build_connect_kwargs(connection_config)

            # Inject parameters as PowerShell variables
            if parameters:
                param_lines = "\n".join(
                    f"${k} = '{v}'" for k, v in parameters.items()
                )
                command = f"{param_lines}\n{command}"

            # Run in a thread since pypsrp is synchronous
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    self._run_powershell,
                    connect_kwargs,
                    command,
                    log_path,
                    log,
                ),
                timeout=timeout_seconds,
            )

            finished_at = datetime.now(timezone.utc)
            log.info(
                "winrm_execute_complete",
                exit_code=result["exit_code"],
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

            return HandlerResult(
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        except TimeoutError:
            finished_at = datetime.now(timezone.utc)
            log.warning("winrm_timeout", timeout_seconds=timeout_seconds)
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=f"WinRM command timed out after {timeout_seconds}s",
                timed_out=True,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            log.exception("winrm_execute_error")
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

    def _run_powershell(
        self,
        connect_kwargs: dict,
        command: str,
        log_path: str,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Execute PowerShell command synchronously (called from executor thread)."""
        from pypsrp.powershell import PowerShell, RunspacePool
        from pypsrp.wsman import WSMan

        host = connect_kwargs["host"]
        port = connect_kwargs.get("port", 5985)
        username = connect_kwargs.get("username")
        password = connect_kwargs.get("password")
        use_ssl = connect_kwargs.get("use_ssl", False)
        auth = connect_kwargs.get("auth", "negotiate")

        wsman = WSMan(
            host,
            port=port,
            username=username,
            password=password,
            ssl=use_ssl,
            auth=auth,
            cert_validation=False,
        )

        all_stdout = []
        all_stderr = []

        with RunspacePool(wsman) as pool:
            ps = PowerShell(pool)
            ps.add_script(command)
            ps.begin_invoke()

            # Poll for output and stream to log file
            while ps.state == 1:  # RUNNING
                ps.poll_invoke()
                # Read output streams
                while ps.output:
                    line = str(ps.output.pop(0))
                    all_stdout.append(line)
                    with open(log_path, "a") as f:
                        f.write(line + "\n")
                while ps.streams.error:
                    err = str(ps.streams.error.pop(0))
                    all_stderr.append(err)
                    with open(log_path, "a") as f:
                        f.write(f"[STDERR] {err}\n")
                import time as _time
                _time.sleep(0.1)

            ps.end_invoke()

            # Collect any remaining output
            while ps.output:
                line = str(ps.output.pop(0))
                all_stdout.append(line)
                with open(log_path, "a") as f:
                    f.write(line + "\n")
            while ps.streams.error:
                err = str(ps.streams.error.pop(0))
                all_stderr.append(err)
                with open(log_path, "a") as f:
                    f.write(f"[STDERR] {err}\n")

            # Get exit code from $LASTEXITCODE if available
            exit_code = 0
            if ps.had_errors:
                exit_code = 1

        stdout = "\n".join(all_stdout)
        stderr = "\n".join(all_stderr)

        return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

    async def test_connection(self, connection_config: dict) -> dict:
        """Test WinRM connectivity."""
        import asyncio

        start = time.monotonic()
        try:
            connect_kwargs = await self._build_connect_kwargs(connection_config)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_powershell,
                connect_kwargs,
                "$env:COMPUTERNAME",
                "/dev/null",
                logger,
            )
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "message": f"WinRM connection successful — host: {result['stdout'].strip()}",
                "capabilities": ["powershell", "command_execution"],
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
        """Build pypsrp connection kwargs from connection config."""
        kwargs: dict = {
            "host": config["host"],
            "port": config.get("port", 5985),
            "username": config.get("username"),
            "use_ssl": False,
            "auth": "negotiate",
        }

        extra = config.get("extra", {}) or {}

        if extra.get("use_ssl"):
            kwargs["use_ssl"] = True
            kwargs["port"] = config.get("port", 5986)

        if extra.get("auth_method"):
            kwargs["auth"] = extra["auth_method"]

        # Prefer resolved credentials from the credential store
        creds = config.get("resolved_credentials")
        if creds:
            kwargs["username"] = creds.get("username", kwargs["username"])
            kwargs["password"] = creds.get("password")
            if creds.get("domain") and kwargs["username"] and "\\" not in kwargs["username"]:
                kwargs["username"] = f"{creds['domain']}\\{kwargs['username']}"
            if creds.get("auth_method"):
                kwargs["auth"] = creds["auth_method"]
        else:
            # Legacy path: read from extra (backward compat)
            secret_name = extra.get("key_vault_secret_name")
            if secret_name:
                kwargs["password"] = await _get_secret(secret_name)
            elif extra.get("password"):
                kwargs["password"] = extra["password"]

        return kwargs
