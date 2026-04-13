"""Integration tests for Azure Service Bus job queue.

Tests the JobQueue service's enqueue/drain behavior with both the local
in-memory queue (when Service Bus is unconfigured) and the JobMessage
serialization used for real Service Bus communication.
"""

import pytest

from reliant_scheduler.services.job_queue import JobQueue, JobMessage

pytestmark = pytest.mark.asyncio


async def test_job_queue_local_enqueue_and_drain() -> None:
    """When no Service Bus is configured, jobs queue to in-memory list."""
    queue = JobQueue()
    msg = JobMessage(
        run_id="run-001",
        job_id="job-001",
        job_name="test-job",
        command="echo hello",
        parameters={"key": "value"},
        attempt_number=1,
        timeout_seconds=600,
    )

    await queue.enqueue(msg)
    messages = queue.drain_local()
    assert len(messages) == 1
    assert messages[0].run_id == "run-001"
    assert messages[0].job_name == "test-job"

    # Queue should be empty after drain
    assert queue.drain_local() == []


async def test_job_message_serialization_roundtrip() -> None:
    """JobMessage can serialize to JSON and deserialize back faithfully."""
    original = JobMessage(
        run_id="run-002",
        job_id="job-002",
        job_name="serialize-test",
        command="python script.py",
        parameters={"input": "data.csv", "retries": 3},
        attempt_number=2,
        timeout_seconds=1800,
    )

    json_str = original.to_json()
    restored = JobMessage.from_json(json_str)

    assert restored.run_id == original.run_id
    assert restored.job_id == original.job_id
    assert restored.job_name == original.job_name
    assert restored.command == original.command
    assert restored.parameters == original.parameters
    assert restored.attempt_number == original.attempt_number
    assert restored.timeout_seconds == original.timeout_seconds


async def test_job_queue_multiple_messages() -> None:
    """Multiple messages can be enqueued and drained in order."""
    queue = JobQueue()

    for i in range(5):
        msg = JobMessage(
            run_id=f"run-{i}",
            job_id=f"job-{i}",
            job_name=f"batch-job-{i}",
            command="echo batch",
            parameters=None,
            attempt_number=1,
            timeout_seconds=300,
        )
        await queue.enqueue(msg)

    messages = queue.drain_local()
    assert len(messages) == 5
    assert [m.run_id for m in messages] == [f"run-{i}" for i in range(5)]


async def test_job_message_null_parameters() -> None:
    """JobMessage handles None parameters correctly."""
    msg = JobMessage(
        run_id="run-null",
        job_id="job-null",
        job_name="null-params",
        command="echo null",
        parameters=None,
        attempt_number=1,
        timeout_seconds=60,
    )

    json_str = msg.to_json()
    restored = JobMessage.from_json(json_str)
    assert restored.parameters is None


async def test_job_message_null_command() -> None:
    """JobMessage handles None command correctly."""
    msg = JobMessage(
        run_id="run-nocmd",
        job_id="job-nocmd",
        job_name="no-command",
        command=None,
        parameters=None,
        attempt_number=1,
        timeout_seconds=60,
    )

    json_str = msg.to_json()
    restored = JobMessage.from_json(json_str)
    assert restored.command is None
