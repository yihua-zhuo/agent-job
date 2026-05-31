from __future__ import annotations

import asyncio
import logging
from typing import Any

_logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by room or channel.

    Rooms and channels share the same underlying namespace
    (``self._rooms``); callers must use distinct names to avoid
    collisions (e.g. a client joining room ``"foo"`` and subscribing to
    channel ``"foo"`` will occupy the same entry).
    """

    def __init__(self) -> None:
        self._rooms: dict[str, set[Any]] = {}
        self._lock = asyncio.Lock()

    async def join(self, room: str, websocket: Any) -> None:
        """Add ``websocket`` to ``room``. Silently succeeds if already present."""
        async with self._lock:
            self._rooms.setdefault(room, set()).add(websocket)
        _logger.debug("WebSocket joined room %s", room)

    async def leave(self, room: str, websocket: Any) -> None:
        """Remove ``websocket`` from ``room``. Silently succeeds if absent."""
        async with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(websocket)
                if not self._rooms[room]:
                    del self._rooms[room]
        _logger.debug("WebSocket left room %s", room)

    async def broadcast(self, room: str, message: str) -> None:
        """Send ``message`` to every WebSocket in ``room``. Silently skips if room is empty or absent."""
        async with self._lock:
            websockets = list(self._rooms.get(room, []))
            # Re-acquire the lock to protect send-and-remove from concurrent join/leave.
            for ws in websockets:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    if isinstance(e, asyncio.CancelledError):
                        raise
                    _logger.warning("Failed to send to WebSocket in room %s, removing", room)
                    self._rooms[room].discard(ws)
                    if not self._rooms[room]:
                        del self._rooms[room]
        _logger.debug("Broadcast to room %s completed", room)

    async def subscribe(self, channel: str, websocket: Any) -> None:
        """Add ``websocket`` to ``channel`` (alias for :meth:`join` with a different namespace)."""
        async with self._lock:
            self._rooms.setdefault(channel, set()).add(websocket)

    async def unsubscribe(self, channel: str, websocket: Any) -> None:
        """Remove ``websocket`` from ``channel`` (alias for :meth:`leave` with a different namespace)."""
        async with self._lock:
            if channel in self._rooms:
                self._rooms[channel].discard(websocket)
                if not self._rooms[channel]:
                    del self._rooms[channel]
