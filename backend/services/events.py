"""
Event system for notifying workers of configuration changes.
Replaces Redis pub/sub with in-memory asyncio events.
"""
import asyncio
from typing import Dict, Set, Callable
from enum import Enum


class EventType(Enum):
    """Types of events that can be emitted."""
    ROUTE_CREATED = "route_created"
    ROUTE_UPDATED = "route_updated"
    ROUTE_DELETED = "route_deleted"
    SESSION_CREATED = "session_created"
    SESSION_UPDATED = "session_updated"
    SESSION_INVALIDATED = "session_invalidated"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"


class EventEmitter:
    """
    Global event emitter for application-wide events.
    Workers subscribe to events and react accordingly.
    """

    def __init__(self):
        # Event listeners: event_type -> set of async callbacks
        self._listeners: Dict[EventType, Set[Callable]] = {}
        # User-specific listeners: (event_type, user_id) -> set of async callbacks
        self._user_listeners: Dict[tuple, Set[Callable]] = {}

    def on(self, event_type: EventType, callback: Callable):
        """Register a global event listener."""
        if event_type not in self._listeners:
            self._listeners[event_type] = set()
        self._listeners[event_type].add(callback)

    def on_user(self, event_type: EventType, user_id: str, callback: Callable):
        """Register a user-specific event listener."""
        key = (event_type, user_id)
        if key not in self._user_listeners:
            self._user_listeners[key] = set()
        self._user_listeners[key].add(callback)

    def off(self, event_type: EventType, callback: Callable):
        """Unregister a global event listener."""
        if event_type in self._listeners:
            self._listeners[event_type].discard(callback)

    def off_user(self, event_type: EventType, user_id: str, callback: Callable):
        """Unregister a user-specific event listener."""
        key = (event_type, user_id)
        if key in self._user_listeners:
            self._user_listeners[key].discard(callback)

    async def emit(self, event_type: EventType, data: dict = None):
        """Emit a global event to all listeners."""
        if data is None:
            data = {}

        # Call global listeners
        if event_type in self._listeners:
            tasks = [callback(data) for callback in self._listeners[event_type]]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def emit_user(self, event_type: EventType, user_id: str, data: dict = None):
        """Emit a user-specific event."""
        if data is None:
            data = {}

        data["user_id"] = user_id

        # Call user-specific listeners
        key = (event_type, user_id)
        if key in self._user_listeners:
            tasks = [callback(data) for callback in self._user_listeners[key]]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        # Also call global listeners
        await self.emit(event_type, data)

    def clear(self):
        """Clear all listeners (useful for testing)."""
        self._listeners.clear()
        self._user_listeners.clear()


# Global event emitter instance
_event_emitter: EventEmitter = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = EventEmitter()
    return _event_emitter


# Public event emitter instance accessible directly
event_emitter = get_event_emitter()


# Convenience functions
async def emit_route_change():
    """Emit event when routes are modified (create/update/delete)."""
    emitter = get_event_emitter()
    await emitter.emit(EventType.ROUTE_UPDATED)


async def emit_session_created(user_id: str):
    """Emit event when a new session is created."""
    emitter = get_event_emitter()
    await emitter.emit_user(EventType.SESSION_CREATED, user_id)


async def emit_session_invalidated(user_id: str):
    """Emit event when a session is invalidated."""
    emitter = get_event_emitter()
    await emitter.emit_user(EventType.SESSION_INVALIDATED, user_id)


async def emit_user_created(user_id: str):
    """Emit event when a new user is created."""
    emitter = get_event_emitter()
    await emitter.emit(EventType.USER_CREATED, {"user_id": user_id})


async def emit_user_deleted(user_id: str):
    """Emit event when a user is deleted."""
    emitter = get_event_emitter()
    await emitter.emit(EventType.USER_DELETED, {"user_id": user_id})
