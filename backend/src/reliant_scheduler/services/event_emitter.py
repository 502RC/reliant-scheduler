"""Centralized event bus for the event-action automation system.

All components emit events via ``emit_event(event_type_name, data)``.
The emitter persists the event and forwards it to the event router
for action dispatch.
"""

import asyncio
from typing import Any, Callable, Awaitable

import structlog

logger = structlog.get_logger(__name__)

# Type alias for event handler callbacks
EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]

# Global handler list — the event router registers itself at startup
_handlers: list[EventHandler] = []


def register_handler(handler: EventHandler) -> None:
    """Register a handler to be called for every emitted event."""
    _handlers.append(handler)


def clear_handlers() -> None:
    """Remove all registered handlers (useful for tests)."""
    _handlers.clear()


async def emit_event(event_type_name: str, data: dict[str, Any] | None = None) -> None:
    """Emit an event to all registered handlers.

    Parameters
    ----------
    event_type_name:
        Dotted event name, e.g. ``job.failed``, ``sla.breached``, ``agent.offline``.
    data:
        Arbitrary context dict (job_id, run_id, error, etc.).
    """
    event_data = data or {}
    logger.info("event_emitted", event_type=event_type_name, event_data=event_data)

    for handler in _handlers:
        try:
            await handler(event_type_name, event_data)
        except Exception:
            logger.exception(
                "event_handler_error",
                event_type=event_type_name,
                handler=handler.__qualname__,
            )
