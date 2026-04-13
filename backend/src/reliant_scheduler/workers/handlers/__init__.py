"""Connection-aware job handlers.

Each handler implements execution against a specific connection type
(SSH, database, REST API, file transfer). The handler registry maps
connection types to their executor classes.
"""

from reliant_scheduler.workers.handlers.base import BaseHandler, HandlerResult
from reliant_scheduler.workers.handlers.registry import get_handler, register_handler

__all__ = ["BaseHandler", "HandlerResult", "get_handler", "register_handler"]
