import pytest

from reliant_scheduler.services.job_queue import JobMessage, JobQueue


@pytest.fixture
def queue() -> JobQueue:
    return JobQueue()


def test_job_message_roundtrip() -> None:
    msg = JobMessage(
        run_id="run-1",
        job_id="job-1",
        job_name="test-job",
        command="echo hello",
        parameters={"key": "value"},
        attempt_number=1,
        timeout_seconds=300,
    )
    json_str = msg.to_json()
    restored = JobMessage.from_json(json_str)
    assert restored.run_id == msg.run_id
    assert restored.parameters == msg.parameters


@pytest.mark.asyncio
async def test_local_queue_enqueue_and_drain(queue: JobQueue) -> None:
    msg = JobMessage(
        run_id="r1", job_id="j1", job_name="test", command=None,
        parameters=None, attempt_number=1, timeout_seconds=60,
    )
    await queue.enqueue(msg)
    assert len(queue._local_queue) == 1

    drained = queue.drain_local()
    assert len(drained) == 1
    assert drained[0].run_id == "r1"
    assert len(queue._local_queue) == 0
