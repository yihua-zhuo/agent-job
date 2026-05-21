from __future__ import annotations

import asyncio
from typing import Any


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[Any]] = {}
        self._lock = asyncio.Lock()

    async def join(self, room: str, websocket: Any) -> None:
        async with self._lock:
            self._rooms.setdefault(room, set()).add(websocket)

    async def leave(self, room: str, websocket: Any) -> None:
        async with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(websocket)
                if not self._rooms[room]:
                    del self._rooms[room]

    async def broadcast(self, room: str, message: str) -> None:
        async with self._lock:
            websockets = list(self._rooms.get(room, []))

        for ws in websockets:
            await ws.send_text(message)

    async def subscribe(self, channel: str, websocket: Any) -> None:
        async with self._lock:
            self._rooms.setdefault(channel, set()).add(websocket)

    async def unsubscribe(self, channel: str, websocket: Any) -> None:
        async with self._lock:
            if channel in self._rooms:
                self._rooms[channel].discard(websocket)
                if not self._rooms[channel]:
                    del self._rooms[channel]
