from reliant_scheduler.services.event_trigger import EventTrigger


def test_matches_filter_no_filter() -> None:
    trigger = EventTrigger()
    assert trigger.matches_filter({"type": "deploy"}, None) is True


def test_matches_filter_exact_match() -> None:
    trigger = EventTrigger()
    assert trigger.matches_filter(
        {"type": "deploy", "env": "prod"},
        {"type": "deploy"},
    ) is True


def test_matches_filter_list_match() -> None:
    trigger = EventTrigger()
    assert trigger.matches_filter(
        {"type": "deploy", "env": "staging"},
        {"env": ["staging", "prod"]},
    ) is True


def test_matches_filter_mismatch() -> None:
    trigger = EventTrigger()
    assert trigger.matches_filter(
        {"type": "build"},
        {"type": "deploy"},
    ) is False
