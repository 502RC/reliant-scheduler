"""Integration tests for Azure Event Hubs event trigger service.

Tests the EventTrigger filter matching logic used for event-driven job triggers.
The filter matching is the core logic that determines whether an incoming event
should trigger a job, and runs identically whether events come from a real
Event Hubs namespace or a Kafka-compatible test container.
"""

import pytest

from reliant_scheduler.services.event_trigger import EventTrigger

pytestmark = pytest.mark.asyncio


@pytest.fixture
def trigger() -> EventTrigger:
    return EventTrigger()


async def test_no_filter_matches_all(trigger: EventTrigger) -> None:
    """A schedule with no event_filter matches any event."""
    assert trigger.matches_filter({"source": "blob", "action": "upload"}, None) is True


async def test_exact_match(trigger: EventTrigger) -> None:
    """All filter keys must match exactly."""
    event_filter = {"source": "blob_storage", "container": "uploads"}
    assert trigger.matches_filter(
        {"source": "blob_storage", "container": "uploads", "file": "data.csv"},
        event_filter,
    ) is True


async def test_mismatch(trigger: EventTrigger) -> None:
    """A filter that doesn't match should return False."""
    event_filter = {"source": "blob_storage", "container": "uploads"}
    assert trigger.matches_filter(
        {"source": "blob_storage", "container": "downloads"},
        event_filter,
    ) is False


async def test_list_membership(trigger: EventTrigger) -> None:
    """Filter values that are lists match if the event value is in the list."""
    event_filter = {"severity": ["critical", "high"]}
    assert trigger.matches_filter({"severity": "critical"}, event_filter) is True
    assert trigger.matches_filter({"severity": "low"}, event_filter) is False


async def test_missing_key_in_event(trigger: EventTrigger) -> None:
    """If the event doesn't have a key that the filter requires, no match."""
    event_filter = {"source": "blob_storage"}
    assert trigger.matches_filter({"action": "upload"}, event_filter) is False


async def test_complex_filter(trigger: EventTrigger) -> None:
    """Combined exact and list matching."""
    event_filter = {
        "source": "eventhub",
        "event_type": ["file.created", "file.updated"],
        "region": "eastus2",
    }
    assert trigger.matches_filter(
        {"source": "eventhub", "event_type": "file.created", "region": "eastus2"},
        event_filter,
    ) is True
    assert trigger.matches_filter(
        {"source": "eventhub", "event_type": "file.deleted", "region": "eastus2"},
        event_filter,
    ) is False


async def test_empty_filter_matches_all(trigger: EventTrigger) -> None:
    """An empty dict filter matches all events."""
    assert trigger.matches_filter({"any": "data"}, {}) is True
