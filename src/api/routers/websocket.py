"""WebSocket router — JWT-authenticated channel subscription."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.status import WS_1008_POLICY_VIOLATION

from internal.middleware.fastapi_auth import AuthContext, _decode_jwt
from websocket.manager import ConnectionManager

router = APIRouter()

# Module-level singleton so tests can patch it
_connection_manager = ConnectionManager()


def verify_ws_token(websocket: WebSocket) -> AuthContext | None:
    """Extract and validate a JWT from a WebSocket connection.

    Checks ``?token=`` query param first, then falls back to the
    ``Authorization`` header (Bearer scheme).  Returns an
    ``AuthContext`` on success, or ``None`` if the token is absent or
    invalid.
    """
    raw_token = websocket.query_params.get("token")
    if not raw_token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:]

    if not raw_token:
        return None

    try:
        return _decode_jwt(raw_token)
    except Exception:
        return None


@router.websocket("/{resource_type}/{resource_id}")
async def ws_channel(websocket: WebSocket, resource_type: str, resource_id: str) -> None:
    """Accept a WebSocket connection after JWT authentication and subscribe to a channel.

    The channel key is ``{tenant_id}:{resource_type}:{resource_id}`` for
    multi-tenancy isolation.  On ``WebSocketDisconnect`` the connection is
    removed from the channel.
    """
    ctx = verify_ws_token(websocket)
    if ctx is None:
        await websocket.close(code=WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    if ctx.tenant_id is None:
        await websocket.close(code=WS_1008_POLICY_VIOLATION, reason="Invalid tenant context")
        return

    if not resource_type or not resource_id:
        await websocket.close(code=WS_1008_POLICY_VIOLATION, reason="Invalid path")
        return

    await websocket.accept()

    channel = f"{ctx.tenant_id}:{resource_type}:{resource_id}"
    await _connection_manager.join(channel, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _connection_manager.leave(channel, websocket)
