Now I have enough context. Here is the plan.

# Implementation Plan — Issue #502

## Goal
Create `src/websocket/manager.py` with a `ConnectionManager` class that manages WebSocket connections in named rooms using an in-memory dict mapping room identifiers to sets of WebSocket clients. The class provides `join`, `leave`, `broadcast`, and channel subscribe/unsubscribe methods. All methods are `async`, return nothing, and raise no errors. A corresponding unit test suite in `tests/unit/test_websocket_manager.py` covers the five required behavioral cases.

## Affected Files
- `src/websocket/manager.py` — **new** — `ConnectionManager` class implementing in-memory room → set[WebSocket] mapping
- `tests/unit/test_websocket_manager.py` — **new** — unit tests for all `ConnectionManager` methods

## Implementation Steps
1. Create the `src/websocket/` directory (it does not exist yet; `src/` has no `websocket` subdirectory).
2. Write `src/websocket/manager.py` with:
   - `class ConnectionManager` stored in `src.websocket.manager`.
   - Internal state: `self._rooms: dict[str, set[Any]]` — a `dict` mapping room name strings to a `set` of WebSocket objects. Use `Any` or a minimal `Protocol` for the WebSocket type to avoid a hard FastAPI/Starlette import dependency in the class itself.
   - `async def join(self, room: str, websocket: Any) -> None` — adds the websocket to `self._rooms.setdefault(room, set())`. Silently succeeds if already present. Returns `None`.
   - `async def leave(self, room: str, websocket: Any) -> None` — removes the websocket from the room's set. Silently succeeds if not present or room doesn't exist. Returns `None`.
   - `async def broadcast(self, room: str, message: str) -> None` — iterates over the room's set, calls `await ws.send_text(message)` for each. Silently skips if room is empty or doesn't exist. Raises nothing.
   - `async def subscribe(self, channel: str, websocket: Any) -> None` and `async def unsubscribe(self, channel: str, websocket: Any) -> None` — identical logic to join/leave but keyed on channel name (can reuse the same `_rooms` dict; "room" and "channel" are the same mechanism with different naming).
3. Use an `asyncio.Lock` (e.g., `self._lock = asyncio.Lock()`) to protect `_rooms` mutations and prevent concurrent modification during iteration in `broadcast`. Initialize it in `__init__`.

## Test Plan
- Unit tests in `tests/unit/test_websocket_manager.py`:
  - `test_join_adds_connection` — call `manager.join("room1", ws)` twice, verify the set has 1 entry (deduplication).
  - `test_leave_removes_connection` — join then leave, verify the set is empty.
  - `test_broadcast_sends_to_all_in_room` — join 3 websockets to "room1", broadcast, assert `send_text` was called exactly once on each.
  - `test_broadcast_to_empty_room_is_noop` — call `manager.broadcast("nonexistent", "msg")`, assert no `send_text` was called on any mock.
  - `test_client_in_room_a_does_not_receive_broadcast_to_room_b` — join ws1 to "roomA" and ws2 to "roomB", broadcast to "roomA", assert ws2's `send_text` was never called.
  - `test_subscribe_adds_connection` — subscribe then verify the channel entry exists with the websocket.
  - `test_unsubscribe_removes_connection` — subscribe then unsubscribe, verify the websocket is removed.
  - Tests use `unittest.mock.MagicMock()` as WebSocket stand-ins with `send_text = AsyncMock()` injected. No database. Requires pytest-asyncio in auto mode (``asyncio_mode = auto`` in ``pytest.ini`` or ``pytestmark = pytest.mark.asyncio`` on the module) so that explicit ``pytest.mark.asyncio`` markers on each ``async def`` test are unnecessary. Import ``ConnectionManager`` from ``src.websocket.manager`` after ensuring ``src/`` is on ``sys.path`` (already handled by the existing conftest.py ``sys.path`` setup).

> **Note:** Rooms and channels share the same internal namespace (``self._rooms``). If a client joins room ``"foo"`` and subscribes to channel ``"foo"``, both entries merge into the same set. This is by design — callers must use distinct names for rooms and channels to avoid collisions.

## Acceptance Criteria
- `manager.join("room", ws)` followed by `manager.leave("room", ws)` results in an empty room — no errors raised.
- `manager.broadcast("room", "msg")` calls `send_text` on every WebSocket that has previously called `join` for that room and has not called `leave`.
- Calling `broadcast` on a room with zero connections completes silently with no errors.
- After `ws_a.join("room1")` and `ws_b.join("room2")`, a `broadcast("room1", "msg")` does not call `ws_b.send_text`.
- All five test cases pass with `pytest tests/unit/test_websocket_manager.py -v`.
