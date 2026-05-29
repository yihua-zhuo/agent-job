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
        assert len(manager._rooms["room1"]) == 1

    async def test_join_deduplicates(self, manager, ws_a, ws_b):
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_a)
        await manager.join("room1", ws_b)
        assert len(manager._rooms["room1"]) == 2
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


class TestSubscribe:
    async def test_subscribe_adds_connection(self, manager, ws_a):
        await manager.subscribe("channel1", ws_a)
        assert "channel1" in manager._rooms
        assert len(manager._rooms["channel1"]) == 1

    async def test_subscribe_deduplicates(self, manager, ws_a, ws_b):
        await manager.subscribe("channel1", ws_a)
        await manager.subscribe("channel1", ws_a)
        await manager.subscribe("channel1", ws_b)
        assert len(manager._rooms["channel1"]) == 2

    async def test_subscribe_channel_sends_to_all(self, manager, ws_a, ws_b, ws_c):
        """Subscribe mirrors join/leave pattern — verify broadcast reaches all subscribers."""
        await manager.subscribe("channel1", ws_a)
        await manager.subscribe("channel1", ws_b)
        await manager.subscribe("channel1", ws_c)
        await manager.broadcast("channel1", "hello")
        ws_a.send_text.assert_called_once_with("hello")
        ws_b.send_text.assert_called_once_with("hello")
        ws_c.send_text.assert_called_once_with("hello")


class TestUnsubscribe:
    async def test_unsubscribe_removes_connection(self, manager, ws_a, ws_b):
        await manager.subscribe("channel1", ws_a)
        await manager.subscribe("channel1", ws_b)
        await manager.unsubscribe("channel1", ws_a)
        assert len(manager._rooms["channel1"]) == 1
        assert ws_a not in manager._rooms["channel1"]
        assert ws_b in manager._rooms["channel1"]

    async def test_unsubscribe_nonexistent_is_noop(self, manager, ws_a):
        await manager.unsubscribe("nonexistent", ws_a)

    async def test_unsubscribe_prevents_future_broadcast(self, manager, ws_a, ws_b):
        """Unsubscribe mirrors leave — unsubscribed client must not receive future broadcasts."""
        await manager.subscribe("channel1", ws_a)
        await manager.subscribe("channel1", ws_b)
        await manager.unsubscribe("channel1", ws_a)
        await manager.broadcast("channel1", "hello")
        ws_a.send_text.assert_not_called()
        ws_b.send_text.assert_called_once_with("hello")

    async def test_client_in_room_a_does_not_receive_broadcast_to_room_b(
        self, manager, ws_a, ws_b
    ):
        """Deduplication: clients in the same room must not receive duplicate messages."""
        await manager.join("roomA", ws_a)
        await manager.join("roomA", ws_a)  # join twice — set deduplication
        await manager.broadcast("roomA", "hello")
        ws_a.send_text.assert_called_once_with("hello")

    async def test_ws_in_room_b_isolation(self, manager, ws_a, ws_b):
        """Cross-room isolation: ws_b in roomB must never be called when broadcasting to roomA."""
        await manager.join("roomA", ws_a)
        await manager.join("roomB", ws_b)
        await manager.broadcast("roomA", "hello")
        ws_a.send_text.assert_called_once_with("hello")
        ws_b.send_text.assert_not_called()
