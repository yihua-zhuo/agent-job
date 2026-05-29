Now I have a thorough picture of the codebase. Here is the implementation plan:

---

# Implementation Plan — Issue #503

## Goal
Create `src/api/routers/websocket.py` with a FastAPI WebSocket router that validates a JWT on handshake (from query param `?token=` or `Authorization` header), accepts the connection, calls `ConnectionManager.join()` on connect and `ConnectionManager.leave()` on disconnect, and is wired into `main.py` under the `/ws` prefix. Unit tests cover valid token → accept, missing token → reject, invalid token → reject with 401.

## Source Contract
Dev-plan target: `docs/dev-plan/00-foundations/0503-add-websocket-auth-handshake-router-in-src-api-routers-webso.md`
Template depth: `deep`
Reading order followed:
1. `docs/dev-plan/README.md`
2. `docs/dev-plan/_template-deep.md`
3. `docs/dev-plan/00-foundations/0503-add-websocket-auth-handshake-router-in-src-api-routers-webso.md`

## Affected Files
- `src/internal/middleware/fastapi_auth.py` — extract reusable JWT decode into `_decode_jwt(token) -> AuthContext`
- `src/api/routers/websocket.py` — **new** — WebSocket router with JWT handshake, join/leave
- `src/api/routers/__init__.py` — **new** — exports `router`; auto-discovered by `src/api/__init__.py`'s `iter_routers()`, no `main.py` change needed
- `tests/unit/test_websocket.py` — **new** — unit tests for the three handshake scenarios

## Implementation Steps

**Step 1: Extract `_decode_jwt` in `fastapi_auth.py`**

Refactor the JWT decode logic from `require_auth` into a standalone `_decode_jwt(token: str) -> AuthContext` function that raises `HTTPException(401)` on any decode error. Both `require_auth` and the upcoming WebSocket router will call this function.

```python
def _decode_jwt(token: str) -> AuthContext:
    secret = get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="无效的 Token")

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token 缺少 user_id")

    raw_tenant_id = payload.get("tenant_id")
    tenant_id = int(raw_tenant_id) if raw_tenant_id is not None else None
    roles = payload.get("roles", [])
    return AuthContext(user_id=user_id, tenant_id=tenant_id, roles=roles)
```

Update `require_auth` to call `_decode_jwt(auth_header[7:])`. **Complete判定**: `ruff check src/internal/middleware/fastapi_auth.py` → 0 errors.

**Step 2: Create `src/api/routers/websocket.py`**

Create the new file. Import `ConnectionManager` from `websocket.manager` (resolved from Step 3 of the dev-plan and confirmed at `src/websocket/manager.py`). Import `_decode_jwt` from `internal.middleware.fastapi_auth`.

Implement `verify_ws_token(websocket: WebSocket) -> AuthContext | None`:
- Prefer `websocket.query_params.get("token")`
- Fall back to `Authorization` header stripping `"Bearer "`
- Call `_decode_jwt(raw_token)` wrapped in try/except; return `None` on any exception

Implement the WebSocket endpoint at `/{resource_type}/{resource_id}`:
1. Call `verify_ws_token(websocket)`; if `None`, `await websocket.close(code=1008, reason="Unauthorized")` and return
2. `await websocket.accept()`
3. Build channel key: `f"{ctx.tenant_id}:{resource_type}:{resource_id}"` (multitenancy isolation)
4. `await ConnectionManager.join(channel, websocket)`
5. `try: while True: await websocket.receive_text() except WebSocketDisconnect: await ConnectionManager.leave(channel, websocket)`

`router` is exported as a plain `APIRouter` — no prefix (prefix is set at include time).

**Complete判定**: `ruff check src/api/routers/websocket.py` → 0 errors; `PYTHONPATH=src mypy src/api/routers/websocket.py` → 0 errors (if mypy configured).

**Step 3: Create `src/api/routers/__init__.py`**

Create the file exporting `router`:
```python
from .websocket import router
__all__ = ["router"]
```
This makes the router discoverable by `iter_routers()` in `src/api/__init__.py` without any change to `main.py` — the existing `for router in iter_routers(): app.include_router(router)` loop already picks up all `APIRouter` exports in the package.

**Complete判定**: `PYTHONPATH=src python -c "from api.routers.websocket import router; print('import ok')"` → no `ImportError`.

**Step 4: Write `tests/unit/test_websocket.py`**

Create the test file with `verify_ws_token` tests and integration-style WebSocket connection tests using `fastapi.testclient.TestClient`:

- `TestVerifyWsToken.test_valid_token_returns_context` — mock `query_params` with a real JWT generated via `AuthService`; assert `ctx.tenant_id == 1`
- `TestVerifyWsToken.test_missing_token_returns_none` — both `query_params.get` and `headers.get` return empty; assert `None`
- `TestVerifyWsToken.test_invalid_token_returns_none` — return `"not.valid.jwt"`; assert `None`
- `TestWsChannel.test_valid_token_accepts_and_joins` — use `TestClient.websocket_connect("/ws/ticket/42?token=...")`; mock `ConnectionManager`; assert `join` was called
- `TestWsChannel.test_missing_token_closes_connection` — mock `verify_ws_token` to return `None`; assert `websocket.close` was called with `code=1008`; assert `websocket.accept` was **not** called
- `TestWsChannel.test_invalid_token_closes_connection` — same as above with invalid token

Mock `ConnectionManager` via `monkeypatch.setattr` on the `websocket.manager` module path so the real `ConnectionManager` class is replaced with an `AsyncMock`.

**Complete判定**: `PYTHONPATH=src pytest tests/unit/test_websocket.py -v` → all passed.

**Step 5: Run full lint/format check**

```bash
ruff check src/internal/middleware/fastapi_auth.py src/api/routers/websocket.py src/api/routers/__init__.py
ruff format --check src/internal/middleware/fastapi_auth.py src/api/routers/websocket.py tests/unit/test_websocket.py
```

**Complete判定**: all commands exit 0.

## Test Plan
- **Unit tests in `tests/unit/`**:
  - `tests/unit/test_websocket.py` — new file: `verify_ws_token` (3 cases: valid returns context, missing returns none, invalid returns none) + `TestWsChannel` (valid token → accept+join, missing token → close without accept, invalid token → close with 401 reason)
- **Integration tests in `tests/integration/`**: none — WebSocket auth handshake is covered by unit tests (no real DB required)
- **Dev-plan verification commands** (from dev-plan §6):
  - `ruff check src/api/routers/websocket.py src/api/routers/__init__.py` → 0 errors
  - `ruff format --check src/api/routers/websocket.py tests/unit/test_websocket.py` → 0 diffs
  - `PYTHONPATH=src pytest tests/unit/test_websocket.py -v` → all passed
  - `PYTHONPATH=src mypy src/api/routers/websocket.py` → 0 errors
  - `PYTHONPATH=src python -c "from api.routers.websocket import router; print('import ok')"` → `import ok`

## Acceptance Criteria
- `src/api/routers/websocket.py` exists and exports a `router` of type `APIRouter`
- `verify_ws_token` returns `AuthContext` for a valid JWT from query param, returns `None` for missing/invalid token
- `ws_channel` endpoint: missing/invalid token → `close(1008)` without `accept()`; valid token → `accept()` then `ConnectionManager.join(channel, websocket)`
- `WebSocketDisconnect` triggers `ConnectionManager.leave(channel, websocket)`
- Channel key includes `tenant_id` for multi-tenancy isolation
- `src/api/routers/__init__.py` is created; no change to `main.py` required — router auto-discovered via existing `iter_routers()` loop
- All 6 unit test cases pass
- `ruff check` and `ruff format --check` pass on all modified files
- Unit tests run in < 5s (no DB, mocked)
