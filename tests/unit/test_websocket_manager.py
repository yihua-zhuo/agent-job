from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.websocket.manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.fixture
def ws_a():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def ws_b():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def ws_c():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


class TestJoin:
    async def test_join_adds_connection(self, manager, ws_a, ws_b):
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_b)
        await manager.broadcast("room1", "hello")
        ws_a.send_text.assert_called_once_with("hello")
        ws_b.send_text.assert_called_once_with("hello")


class TestLeave:
    async def test_leave_removes_connection(self, manager, ws_a, ws_b):
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_b)
        await manager.leave("room1", ws_a)
        await manager.broadcast("room1", "hello")
        ws_a.send_text.assert_not_called()
        ws_b.send_text.assert_called_once_with("hello")


class TestBroadcast:
    async def test_broadcast_sends_to_all_in_room(self, manager, ws_a, ws_b, ws_c):
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_b)
        await manager.join("room1", ws_c)
        await manager.broadcast("room1", "hello")
        ws_a.send_text.assert_called_once_with("hello")
        ws_b.send_text.assert_called_once_with("hello")
        ws_c.send_text.assert_called_once_with("hello")

    async def test_broadcast_to_empty_room_is_noop(self, manager, ws_a, ws_b):
        await manager.broadcast("nonexistent", "msg")
        ws_a.send_text.assert_not_called()
        ws_b.send_text.assert_not_called()

    async def test_client_in_room_a_does_not_receive_broadcast_to_room_b(
        self, manager, ws_a, ws_b
    ):
        await manager.join("roomA", ws_a)
        await manager.join("roomB", ws_b)
        await manager.broadcast("roomA", "hello")
        ws_a.send_text.assert_called_once_with("hello")
        ws_b.send_text.assert_not_called()
