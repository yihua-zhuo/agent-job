from __future__ import annotations

import asyncio
import logging
from typing import Any

_logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[Any]] = {}
        self._lock = asyncio.Lock()

    async def join(self, room: str, websocket: Any) -> None:
        async with self._lock:
            self._rooms.setdefault(room, set()).add(websocket)
        _logger.debug("WebSocket joined room %s", room)

    async def leave(self, room: str, websocket: Any) -> None:
        async with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(websocket)
                if not self._rooms[room]:
                    del self._rooms[room]
        _logger.debug("WebSocket left room %s", room)

    async def broadcast(self, room: str, message: str) -> None:
        async with self._lock:
            websockets = list(self._rooms.get(room, []))
            await asyncio.sleep(0)

        delivered = 0
        for ws in websockets:
            try:
                await ws.send_text(message)
                delivered += 1
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    raise
                _logger.warning("Failed to send to WebSocket in room %s, removing", room)
                async with self._lock:
                    if room in self._rooms:
                        self._rooms[room].discard(ws)
                        if not self._rooms[room]:
                            del self._rooms[room]
                continue
        _logger.debug("Broadcast to room %s delivered to %d clients", room, delivered)

    async def subscribe(self, channel: str, websocket: Any) -> None:
        async with self._lock:
            self._rooms.setdefault(channel, set()).add(websocket)

    async def unsubscribe(self, channel: str, websocket: Any) -> None:
        async with self._lock:
            if channel in self._rooms:
                self._rooms[channel].discard(websocket)
                if not self._rooms[channel]:
                    del self._rooms[channel]
