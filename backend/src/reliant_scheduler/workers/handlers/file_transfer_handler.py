"""File transfer job handler — transfer files between systems.

Supports: SFTP (via asyncssh), Azure Blob <-> local, S3-compatible.
File paths are validated against an allowlist to prevent path traversal.
"""

import asyncio
import fnmatch
import json
import os
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

import structlog

from reliant_scheduler.workers.handlers.base import BaseHandler, HandlerResult

logger = structlog.get_logger(__name__)

# Default path allowlist — jobs can only transfer from/to these prefixes
DEFAULT_ALLOWED_PREFIXES = ["/data/", "/tmp/reliant/", "/opt/reliant/"]


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


def _validate_path(path: str, allowed_prefixes: list[str]) -> None:
    """Validate a file path against the allowlist to prevent path traversal."""
    resolved = str(PurePosixPath(path))
    # Check for traversal attempts
    if ".." in resolved:
        raise ValueError(f"Path traversal detected in: {path}")
    if not any(resolved.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(
            f"Path '{path}' not in allowed prefixes: {allowed_prefixes}"
        )


class FileTransferHandler(BaseHandler):
    """Transfer files between Azure Blob Storage, SFTP, and local storage."""

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
            handler="file_transfer",
        )
        log.info("file_transfer_start")

        started_at = datetime.now(timezone.utc)
        extra = connection_config.get("extra", {}) or {}

        if not command:
            finished_at = datetime.now(timezone.utc)
            return HandlerResult(
                exit_code=0,
                stdout="(no transfer command configured)",
                stderr="",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        try:
            transfer_config = self._parse_command(command, parameters)
            allowed_prefixes = extra.get("allowed_prefixes", DEFAULT_ALLOWED_PREFIXES)

            # Validate paths
            source_path = transfer_config["source_path"]
            dest_path = transfer_config["destination_path"]
            transfer_type = transfer_config.get("type", "sftp_download")

            # Validate local paths against allowlist
            if transfer_type in ("sftp_download", "blob_download"):
                _validate_path(dest_path, allowed_prefixes)
            elif transfer_type in ("sftp_upload", "blob_upload"):
                _validate_path(source_path, allowed_prefixes)

            result = await asyncio.wait_for(
                self._do_transfer(
                    transfer_type=transfer_type,
                    source_path=source_path,
                    dest_path=dest_path,
                    pattern=transfer_config.get("pattern"),
                    connection_config=connection_config,
                    log=log,
                ),
                timeout=timeout_seconds,
            )

            finished_at = datetime.now(timezone.utc)
            duration = (finished_at - started_at).total_seconds()

            log.info(
                "file_transfer_complete",
                transfer_type=transfer_type,
                bytes_transferred=result.get("bytes_transferred", 0),
                files_transferred=result.get("files_transferred", 0),
                duration_seconds=duration,
            )

            return HandlerResult(
                exit_code=0,
                stdout=json.dumps(result, default=str),
                stderr="",
                timed_out=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                bytes_transferred=result.get("bytes_transferred", 0),
            )

        except asyncio.TimeoutError:
            finished_at = datetime.now(timezone.utc)
            log.warning("file_transfer_timeout", timeout_seconds=timeout_seconds)
            return HandlerResult(
                exit_code=-1,
                stdout="",
                stderr=f"File transfer timed out after {timeout_seconds}s",
                timed_out=True,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            log.exception("file_transfer_error")
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
        connection_type = connection_config.get("connection_type", "sftp")
        start = time.monotonic()

        try:
            if connection_type == "sftp":
                await self._test_sftp(connection_config)
                capabilities = ["upload", "download", "list", "glob_pattern"]
            elif connection_type == "azure_blob":
                await self._test_blob(extra)
                capabilities = ["upload", "download", "list", "glob_pattern"]
            else:
                capabilities = ["upload", "download"]

            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "message": f"{connection_type} file transfer ready",
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
        """Parse transfer command — expects JSON config.

        Example: {"type": "sftp_download", "source_path": "/remote/file.csv",
                  "destination_path": "/data/file.csv", "pattern": "*.csv"}
        """
        try:
            config = json.loads(command)
        except json.JSONDecodeError:
            raise ValueError(
                "File transfer command must be JSON with keys: "
                "type, source_path, destination_path, pattern (optional)"
            )

        if "source_path" not in config or "destination_path" not in config:
            raise ValueError("source_path and destination_path are required")

        # Template substitution
        if parameters:
            for key in ("source_path", "destination_path", "pattern"):
                if key in config and isinstance(config[key], str):
                    for pkey, pval in parameters.items():
                        config[key] = config[key].replace(f"${{{pkey}}}", str(pval))

        return config

    async def _do_transfer(
        self,
        *,
        transfer_type: str,
        source_path: str,
        dest_path: str,
        pattern: str | None,
        connection_config: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Dispatch to the appropriate transfer method."""
        if transfer_type == "sftp_download":
            return await self._sftp_download(
                source_path, dest_path, pattern, connection_config, log
            )
        elif transfer_type == "sftp_upload":
            return await self._sftp_upload(
                source_path, dest_path, pattern, connection_config, log
            )
        elif transfer_type == "blob_download":
            return await self._blob_download(
                source_path, dest_path, pattern, connection_config, log
            )
        elif transfer_type == "blob_upload":
            return await self._blob_upload(
                source_path, dest_path, pattern, connection_config, log
            )
        else:
            raise ValueError(f"Unknown transfer type: {transfer_type}")

    async def _sftp_download(
        self,
        remote_path: str,
        local_path: str,
        pattern: str | None,
        config: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Download files from SFTP server."""
        import asyncssh

        connect_kwargs = await self._build_sftp_kwargs(config)

        async with asyncssh.connect(**connect_kwargs) as conn:
            async with conn.start_sftp_client() as sftp:
                files_transferred = 0
                bytes_transferred = 0

                if pattern:
                    # Glob pattern transfer
                    entries = await sftp.listdir(remote_path)
                    for entry in entries:
                        if fnmatch.fnmatch(entry, pattern):
                            remote_file = f"{remote_path}/{entry}"
                            local_file = f"{local_path}/{entry}"
                            await sftp.get(remote_file, local_file)
                            stat = await sftp.stat(remote_file)
                            bytes_transferred += stat.size or 0
                            files_transferred += 1
                else:
                    await sftp.get(remote_path, local_path)
                    stat = await sftp.stat(remote_path)
                    bytes_transferred = stat.size or 0
                    files_transferred = 1

                log.info(
                    "sftp_download_complete",
                    files=files_transferred,
                    bytes=bytes_transferred,
                )

                return {
                    "files_transferred": files_transferred,
                    "bytes_transferred": bytes_transferred,
                    "transfer_type": "sftp_download",
                }

    async def _sftp_upload(
        self,
        local_path: str,
        remote_path: str,
        pattern: str | None,
        config: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Upload files to SFTP server."""
        import asyncssh

        connect_kwargs = await self._build_sftp_kwargs(config)

        async with asyncssh.connect(**connect_kwargs) as conn:
            async with conn.start_sftp_client() as sftp:
                files_transferred = 0
                bytes_transferred = 0

                if pattern:
                    import glob as glob_mod

                    matched = glob_mod.glob(os.path.join(local_path, pattern))
                    for local_file in matched:
                        filename = os.path.basename(local_file)
                        remote_file = f"{remote_path}/{filename}"
                        await sftp.put(local_file, remote_file)
                        bytes_transferred += os.path.getsize(local_file)
                        files_transferred += 1
                else:
                    await sftp.put(local_path, remote_path)
                    bytes_transferred = os.path.getsize(local_path)
                    files_transferred = 1

                return {
                    "files_transferred": files_transferred,
                    "bytes_transferred": bytes_transferred,
                    "transfer_type": "sftp_upload",
                }

    async def _blob_download(
        self,
        blob_path: str,
        local_path: str,
        pattern: str | None,
        config: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Download files from Azure Blob Storage."""
        extra = config.get("extra", {}) or {}
        container_name = extra.get("container_name", "")
        blob_client = await self._get_blob_service(extra)

        try:
            container_client = blob_client.get_container_client(container_name)
            files_transferred = 0
            bytes_transferred = 0

            if pattern:
                async for blob in container_client.list_blobs(name_starts_with=blob_path):
                    if fnmatch.fnmatch(os.path.basename(blob.name), pattern):
                        filename = os.path.basename(blob.name)
                        local_file = os.path.join(local_path, filename)
                        download = await container_client.download_blob(blob.name)
                        data = await download.readall()
                        os.makedirs(os.path.dirname(local_file), exist_ok=True)
                        with open(local_file, "wb") as f:
                            f.write(data)
                        bytes_transferred += len(data)
                        files_transferred += 1
            else:
                download = await container_client.download_blob(blob_path)
                data = await download.readall()
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)
                bytes_transferred = len(data)
                files_transferred = 1

            return {
                "files_transferred": files_transferred,
                "bytes_transferred": bytes_transferred,
                "transfer_type": "blob_download",
            }
        finally:
            await blob_client.close()

    async def _blob_upload(
        self,
        local_path: str,
        blob_path: str,
        pattern: str | None,
        config: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> dict:
        """Upload files to Azure Blob Storage."""
        extra = config.get("extra", {}) or {}
        container_name = extra.get("container_name", "")
        blob_client = await self._get_blob_service(extra)

        try:
            container_client = blob_client.get_container_client(container_name)
            files_transferred = 0
            bytes_transferred = 0

            if pattern:
                import glob as glob_mod

                matched = glob_mod.glob(os.path.join(local_path, pattern))
                for local_file in matched:
                    filename = os.path.basename(local_file)
                    blob_name = f"{blob_path}/{filename}"
                    with open(local_file, "rb") as f:
                        data = f.read()
                    await container_client.upload_blob(blob_name, data, overwrite=True)
                    bytes_transferred += len(data)
                    files_transferred += 1
            else:
                with open(local_path, "rb") as f:
                    data = f.read()
                await container_client.upload_blob(blob_path, data, overwrite=True)
                bytes_transferred = len(data)
                files_transferred = 1

            return {
                "files_transferred": files_transferred,
                "bytes_transferred": bytes_transferred,
                "transfer_type": "blob_upload",
            }
        finally:
            await blob_client.close()

    async def _build_sftp_kwargs(self, config: dict) -> dict:
        """Build asyncssh.connect() kwargs from connection config for SFTP."""
        extra = config.get("extra", {}) or {}
        kwargs = {
            "host": config["host"],
            "port": config.get("port", 22),
            "username": extra.get("username", "root"),
            "known_hosts": None,
        }

        secret_name = extra.get("key_vault_secret_name")
        if secret_name:
            secret_value = await _get_secret(secret_name)
            auth_type = extra.get("auth_type", "password")
            if auth_type == "private_key":
                import asyncssh
                kwargs["client_keys"] = [asyncssh.import_private_key(secret_value)]
            else:
                kwargs["password"] = secret_value
        elif extra.get("password"):
            kwargs["password"] = extra["password"]

        if extra.get("known_hosts") != "none":
            kwargs["known_hosts"] = extra.get("known_hosts_path")

        return kwargs

    async def _get_blob_service(self, extra: dict):
        """Get Azure Blob Storage service client."""
        from azure.storage.blob.aio import BlobServiceClient

        connection_string_secret = extra.get("connection_string_secret_name")
        if connection_string_secret:
            conn_str = await _get_secret(connection_string_secret)
            return BlobServiceClient.from_connection_string(conn_str)

        # Use Managed Identity
        from azure.identity.aio import DefaultAzureCredential

        account_url = extra.get("account_url", "")
        credential = DefaultAzureCredential()
        return BlobServiceClient(account_url=account_url, credential=credential)

    async def _test_sftp(self, config: dict) -> None:
        """Test SFTP connectivity."""
        import asyncssh

        connect_kwargs = await self._build_sftp_kwargs(config)
        async with asyncssh.connect(**connect_kwargs) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.listdir(".")

    async def _test_blob(self, extra: dict) -> None:
        """Test Azure Blob connectivity."""
        blob_client = await self._get_blob_service(extra)
        try:
            container_name = extra.get("container_name", "")
            container_client = blob_client.get_container_client(container_name)
            await container_client.get_container_properties()
        finally:
            await blob_client.close()
