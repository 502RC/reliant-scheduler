"""Integration tests for the output manager (local filesystem fallback).

Azure Blob Storage tests are skipped unless connection string is configured.
"""

import os

import pytest

from reliant_scheduler.workers.output_manager import upload_log


@pytest.mark.asyncio
async def test_upload_log_local_fallback() -> None:
    """Without Azure config, logs should be written to local filesystem."""
    log_url = await upload_log(
        job_id="test-job-1",
        run_id="test-run-1",
        output="Hello from test\nLine 2",
        status="success",
        correlation_id="test-local",
    )
    assert log_url.startswith("file://")
    local_path = log_url.replace("file://", "")
    assert os.path.exists(local_path)

    with open(local_path) as f:
        content = f.read()
    assert "Hello from test" in content
    assert "Line 2" in content

    # Cleanup
    os.remove(local_path)


@pytest.mark.asyncio
async def test_upload_log_path_structure() -> None:
    """Log path should follow job-outputs/{job_id}/{run_id}/output.log pattern."""
    log_url = await upload_log(
        job_id="j-abc",
        run_id="r-def",
        output="test",
    )
    assert "j-abc" in log_url
    assert "r-def" in log_url
    assert "output.log" in log_url

    # Cleanup
    local_path = log_url.replace("file://", "")
    if os.path.exists(local_path):
        os.remove(local_path)
