"""
Lightweight EventBus for decoupled communication between modules.

Supports subscribe/emit/unsubscribe and optional once-mode.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional


class EventBus:
    """
    Simple in-process event bus.

    Usage:
        bus = EventBus()
        bus.subscribe("user_state_changed", my_handler)
        bus.emit("user_state_changed", {"state_code": "tired", "confidence": 0.9})
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        once: bool = False,
    ) -> None:
        """
        Register a callback for an event type.

        :param event_type: event type string (e.g. "user_state_changed")
        :param callback: callable accepting a single dict payload
        :param once: if True, auto-unsubscribe after first emit
        """
        event_type = str(event_type).strip()
        if not event_type:
            return
        wrapped = callback
        if once:
            original = callback
            def _once_wrapper(payload: Dict[str, Any]) -> None:
                self.unsubscribe(event_type, _once_wrapper)
                original(payload)
            wrapped = _once_wrapper
        with self._lock:
            self._handlers.setdefault(event_type, []).append(wrapped)

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Remove a specific callback for an event type."""
        event_type = str(event_type).strip()
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            try:
                handlers.remove(callback)
            except ValueError:
                pass

    def emit(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an event, calling all subscribed handlers.

        :param event_type: event type string
        :param payload: dict data (defaults to empty dict)
        """
        event_type = str(event_type).strip()
        if not event_type:
            return
        payload = payload if isinstance(payload, dict) else {}
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                print(f"[EventBus] handler error ({event_type}): {exc}")

    def clear(self) -> None:
        """Remove all handlers."""
        with self._lock:
            self._handlers.clear()

    def handler_count(self, event_type: Optional[str] = None) -> int:
        """
        Return the number of registered handlers.

        :param event_type: if given, only count for that type
        """
        with self._lock:
            if event_type:
                return len(self._handlers.get(event_type, []))
            return sum(len(h) for h in self._handlers.values())


# Singleton
_bus_instance: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get or create the application-wide EventBus singleton."""
    global _bus_instance
    if _bus_instance is None:
        with _bus_lock:
            if _bus_instance is None:
                _bus_instance = EventBus()
    return _bus_instance
