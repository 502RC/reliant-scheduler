"""Handler registry: maps connection types to executor classes."""

from reliant_scheduler.workers.handlers.base import BaseHandler

_registry: dict[str, type[BaseHandler]] = {}


def register_handler(connection_type: str, handler_class: type[BaseHandler]) -> None:
    """Register a handler class for a connection type."""
    _registry[connection_type] = handler_class


def get_handler(connection_type: str) -> BaseHandler:
    """Return an instance of the handler for the given connection type.

    Raises KeyError if no handler is registered.
    """
    cls = _registry.get(connection_type)
    if cls is None:
        raise KeyError(f"No handler registered for connection type: {connection_type}")
    return cls()


def _register_defaults() -> None:
    """Register the built-in handlers."""
    from reliant_scheduler.workers.handlers.ssh_handler import SSHHandler
    from reliant_scheduler.workers.handlers.database_handler import DatabaseHandler
    from reliant_scheduler.workers.handlers.rest_handler import RESTHandler
    from reliant_scheduler.workers.handlers.file_transfer_handler import FileTransferHandler
    from reliant_scheduler.workers.handlers.winrm_handler import WinRMHandler

    register_handler("ssh", SSHHandler)
    register_handler("database", DatabaseHandler)
    register_handler("rest_api", RESTHandler)
    register_handler("sftp", FileTransferHandler)
    register_handler("azure_blob", FileTransferHandler)
    register_handler("winrm", WinRMHandler)
    register_handler("powershell", WinRMHandler)


_register_defaults()
