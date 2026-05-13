"""Auth router — /api/v1/auth endpoints including WebAuthn and refresh token flow.

Implements issue #163:
- P0: Refresh token → HttpOnly Cookie + DB revocation
- P1: Access token in-memory (client handles this)
- P2: WebAuthn registration / assertion (challenge stored in PostgreSQL)
- P3: Device trust + suspicious activity detection
"""

from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models import UserModel
from dependencies.auth import get_current_user
from internal.middleware.fastapi_auth import AuthContext
from services.auth import (
    DeviceTrustService,
    TokenService,
    WebAuthnService,
    generate_device_fingerprint,
)
from services.auth_service import AuthService

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds


def _get_client_info(request: Request) -> tuple[str | None, str | None, str | None]:
    """Extract IP, UA, Accept-Language from request."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    lang = request.headers.get("accept-language")
    return ip, ua, lang


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class WebAuthnRegisterStartResponse(BaseModel):
    challenge: str
    public_key_options: dict[str, Any]
    credential_nickname: str | None = None


class WebAuthnFinishRequest(BaseModel):
    registration_response: dict[str, Any]
    device_fingerprint: str | None = None
    credential_nickname: str | None = None


class WebAuthnAssertionRequest(BaseModel):
    assertion_response: dict[str, Any]
    device_fingerprint: str | None = None
    username: str | None = None


class WebAuthnAssertionStartResponse(BaseModel):
    challenge: str
    credential_id: str
    rp_id: str
    timeout: int


class DeviceResponse(BaseModel):
    id: int
    device_fingerprint: str
    device_name: str | None
    trusted_ip: str | None
    last_ip: str | None
    last_location: str | None
    last_used_at: str | None
    trusted_at: str | None


class TrustedDevicesResponse(BaseModel):
    devices: list[DeviceResponse]


# ---------------------------------------------------------------------------
# Core auth endpoints
# ---------------------------------------------------------------------------


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
):
    """OAuth2 password flow — issues access token + refresh token cookie.

    - Access token: short-lived (10 min), returned as JSON (client stores in memory)
    - Refresh token: stored hashed in DB, sent via HttpOnly cookie
    - On known trusted device: WebAuthn may be skipped (handled by client)
    """
    from configs.settings import settings

    ip, ua, _ = _get_client_info(request) if request else (None, None, None)

    auth_svc = AuthService(session, secret_key=settings.jwt_secret)
    token_svc = TokenService(session, secret_key=settings.jwt_secret)
    device_svc = DeviceTrustService(session)

    user = await auth_svc.authenticate_user(form_data.username, form_data.password)

    fp = generate_device_fingerprint(
        ip, ua, request.headers.get("accept-language") if request else None
    )

    access_token = token_svc.create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
    )

    raw_refresh, _ = await token_svc.create_refresh_token(
        user_id=user.id,
        device_fingerprint=fp,
        user_agent=ua,
        ip_address=ip,
    )

    await device_svc.update_device_usage(user.id, fp, ip_address=ip)

    requires_webauthn, _ = await device_svc.check_suspicious_activity(user.id, fp, ip)

    response = Response(
        content=LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=600,
        ).model_dump_json(),
        media_type="application/json",
        headers={
            "Set-Cookie": f"{COOKIE_NAME}={raw_refresh}; HttpOnly; Secure; SameSite=Strict; Max-Age={COOKIE_MAX_AGE}; Path=/"
        },
    )

    if requires_webauthn:
        response.headers["X-Require-WebAuthn"] = "1"

    return response


@auth_router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token (from HttpOnly cookie) for a new access token.

    Performs silent rotation: revokes old token, issues new one with remaining TTL.
    """
    from configs.settings import settings

    if not refresh_token:
        raise HTTPException(status_code=401, detail="缺少刷新令牌")

    ip, ua, _ = _get_client_info(request)

    token_svc = TokenService(session, secret_key=settings.jwt_secret)
    auth_svc = AuthService(session, secret_key=settings.jwt_secret)

    rotated = await token_svc.rotate_refresh_token(
        refresh_token,
        device_fingerprint=generate_device_fingerprint(ip, ua),
        user_agent=ua,
        ip_address=ip,
    )

    if rotated is None:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")

    new_raw, _ = rotated

    result = await token_svc.verify_refresh_token(new_raw)
    if result is None:
        raise HTTPException(status_code=401, detail="刷新令牌无效")

    user_model = await auth_svc.get_current_user(
        await auth_svc.create_token(result.user_id, "", "", None)
    )

    access_token = token_svc.create_access_token(
        user_id=result.user_id,
        username=user_model.username,
        role=user_model.role,
        tenant_id=user_model.tenant_id,
    )

    response = Response(
        content=RefreshResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=600,
        ).model_dump_json(),
        media_type="application/json",
        headers={
            "Set-Cookie": f"{COOKIE_NAME}={new_raw}; HttpOnly; Secure; SameSite=Strict; Max-Age={COOKIE_MAX_AGE}; Path=/"
        },
    )
    return response


@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
):
    """Revoke the current refresh token (logout)."""
    from configs.settings import settings

    token_svc = TokenService(session, secret_key=settings.jwt_secret)
    if refresh_token:
        await token_svc.revoke_refresh_token(refresh_token)

    response = Response(
        content='{"success":true,"message":"已退出登录"}',
        media_type="application/json",
        headers={
            "Set-Cookie": f"{COOKIE_NAME}=; HttpOnly; Secure; SameSite=Strict; Max-Age=0; Path=/"
        },
    )
    return response


@auth_router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke all refresh tokens for the current user (logout everywhere)."""
    from configs.settings import settings

    token_svc = TokenService(session, secret_key=settings.jwt_secret)
    await token_svc.revoke_all_user_tokens(current_user.user_id)

    response = Response(
        content='{"success":true,"message":"所有设备已退出登录"}',
        media_type="application/json",
        headers={
            "Set-Cookie": f"{COOKIE_NAME}=; HttpOnly; Secure; SameSite=Strict; Max-Age=0; Path=/"
        },
    )
    return response


# ---------------------------------------------------------------------------
# WebAuthn endpoints (P2) — challenge stored in PostgreSQL
# ---------------------------------------------------------------------------


@auth_router.post("/webauthn/register/start", response_model=WebAuthnRegisterStartResponse)
async def webauthn_register_start(
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Start WebAuthn credential registration.

    Stores challenge in webauthn_challenges table (PG) with 60s TTL.
    Client calls POST /auth/webauthn/register/finish with authenticator response.
    """
    from configs.settings import settings

    ip, ua, _ = _get_client_info(request)
    fp = generate_device_fingerprint(ip, ua, request.headers.get("accept-language"))

    auth_svc = AuthService(session, secret_key=settings.jwt_secret)
    user = await auth_svc.get_current_user(
        auth_svc.create_token(
            current_user.user_id,
            "",
            current_user.roles[0] if current_user.roles else "",
            current_user.tenant_id,
        )
    )

    webauthn_svc = WebAuthnService(
        session,
        rp_id=settings.webauthn_rp_id or "localhost",
        rp_name=settings.webauthn_rp_name or "AgentJob",
    )
    result = await webauthn_svc.start_registration(
        user.id,
        user.username,
        device_fingerprint=fp,
    )

    return WebAuthnRegisterStartResponse(
        challenge=result["challenge"],
        public_key_options=result["publicKeyOptions"],
        credential_nickname=result.get("credential_nickname"),
    )


@auth_router.post("/webauthn/register/finish")
async def webauthn_register_finish(
    body: WebAuthnFinishRequest,
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Finish WebAuthn registration: verify attestation, consume challenge, store credential.

    After this the device can authenticate using WebAuthn instead of password.
    """
    from configs.settings import settings

    ip, ua, _ = _get_client_info(request)
    fp = body.device_fingerprint or generate_device_fingerprint(
        ip, ua, request.headers.get("accept-language")
    )

    auth_svc = AuthService(session, secret_key=settings.jwt_secret)
    webauthn_svc = WebAuthnService(
        session,
        rp_id=settings.webauthn_rp_id or "localhost",
        rp_name=settings.webauthn_rp_name or "AgentJob",
    )
    device_svc = DeviceTrustService(session)

    user = await auth_svc.get_current_user(
        auth_svc.create_token(
            current_user.user_id,
            "",
            current_user.roles[0] if current_user.roles else "",
            current_user.tenant_id,
        )
    )

    try:
        credential = await webauthn_svc.finish_registration(
            user_id=user.id,
            username=user.username,
            registration_response=body.registration_response,
            device_fingerprint=fp,
            credential_nickname=body.credential_nickname,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await device_svc.trust_device(
        user_id=user.id,
        device_fingerprint=fp,
        ip_address=ip,
        device_name=body.credential_nickname,
    )

    return {
        "success": True,
        "message": "WebAuthn 凭证注册成功",
        "credential_id": credential.credential_id,
    }


@auth_router.post("/webauthn/assertion/start", response_model=WebAuthnAssertionStartResponse)
async def webauthn_assertion_start(
    body: WebAuthnAssertionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Start WebAuthn assertion (authentication step 1).

    Looks up user by username, stores challenge in DB with 5min TTL.
    Client calls POST /auth/webauthn/verify with the authenticator response.
    """
    from configs.settings import settings

    if not body.username:
        raise HTTPException(status_code=400, detail="需要用户名")

    result = await session.execute(
        select(UserModel).where(UserModel.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    ip, ua, _ = _get_client_info(request)
    fp = body.device_fingerprint or generate_device_fingerprint(ip, ua, request.headers.get("accept-language"))

    webauthn_svc = WebAuthnService(
        session,
        rp_id=settings.webauthn_rp_id or "localhost",
        rp_name=settings.webauthn_rp_name or "AgentJob",
    )

    credential_id = body.assertion_response.get("credentialId", "")
    result = await webauthn_svc.start_assertion(
        user_id=user.id,
        credential_id=credential_id,
        device_fingerprint=fp,
    )
    return WebAuthnAssertionStartResponse(
        challenge=result["challenge"],
        credential_id=result["credential_id"],
        rp_id=result["rp_id"],
        timeout=result["timeout"],
    )


@auth_router.post("/webauthn/verify", response_model=LoginResponse)
async def webauthn_verify(
    body: WebAuthnAssertionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Verify WebAuthn assertion (authentication step 2), issue tokens.

    Returns access token + refresh token cookie on success.
    """
    from configs.settings import settings

    if not body.username:
        raise HTTPException(status_code=400, detail="需要用户名")

    ip, ua, _ = _get_client_info(request)
    fp = body.device_fingerprint or generate_device_fingerprint(ip, ua, request.headers.get("accept-language"))

    webauthn_svc = WebAuthnService(
        session,
        rp_id=settings.webauthn_rp_id or "localhost",
        rp_name=settings.webauthn_rp_name or "AgentJob",
    )
    token_svc = TokenService(session, secret_key=settings.jwt_secret)
    device_svc = DeviceTrustService(session)

    result = await session.execute(
        select(UserModel).where(UserModel.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    try:
        credential, _ = await webauthn_svc.verify_assertion(
            user_id=user.id,
            assertion_response=body.assertion_response,
            device_fingerprint=fp,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    await device_svc.update_device_usage(user.id, fp, ip_address=ip)

    requires_reauth, reasons = await device_svc.check_suspicious_activity(user.id, fp, ip)
    if requires_reauth:
        raise HTTPException(
            status_code=403,
            detail=f"检测到可疑活动: {', '.join(reasons)}，请先通过密码验证",
        )

    access_token = token_svc.create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        tenant_id=user.tenant_id,
    )

    raw_refresh, _ = await token_svc.create_refresh_token(
        user_id=user.id,
        device_fingerprint=fp,
        user_agent=ua,
        ip_address=ip,
    )

    response = Response(
        content=LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=600,
        ).model_dump_json(),
        media_type="application/json",
        headers={
            "Set-Cookie": f"{COOKIE_NAME}={raw_refresh}; HttpOnly; Secure; SameSite=Strict; Max-Age={COOKIE_MAX_AGE}; Path=/"
        },
    )
    return response


# ---------------------------------------------------------------------------
# Device management (P3)
# ---------------------------------------------------------------------------


@auth_router.get("/devices", response_model=TrustedDevicesResponse)
async def list_trusted_devices(
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all trusted devices for the current user."""
    device_svc = DeviceTrustService(session)
    devices = await device_svc.get_trusted_devices(current_user.user_id)
    return TrustedDevicesResponse(
        devices=[
            DeviceResponse(
                id=d.id,
                device_fingerprint=d.device_fingerprint,
                device_name=d.device_name,
                trusted_ip=d.trusted_ip,
                last_ip=d.last_ip,
                last_location=d.last_location,
                last_used_at=d.last_used_at.isoformat() if d.last_used_at else None,
                trusted_at=d.trusted_at.isoformat() if d.trusted_at else None,
            )
            for d in devices
        ]
    )


@auth_router.delete("/devices/{device_fingerprint}")
async def revoke_device(
    device_fingerprint: str,
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke trust for a specific device."""
    device_svc = DeviceTrustService(session)
    ok = await device_svc.distrust_device(current_user.user_id, device_fingerprint)
    if not ok:
        raise HTTPException(status_code=404, detail="设备未找到")
    return {"success": True, "message": "设备已取消信任"}


@auth_router.delete("/devices")
async def revoke_all_devices(
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke trust for all devices (e.g. after password change)."""
    device_svc = DeviceTrustService(session)
    count = await device_svc.distrust_all_devices(current_user.user_id)
    return {"success": True, "message": f"已取消信任 {count} 台设备", "revoked_count": count}


# ---------------------------------------------------------------------------
# Re-auth trigger check (P3)
# ---------------------------------------------------------------------------


@auth_router.get("/check-suspicious")
async def check_suspicious(
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Check if the current session shows suspicious activity signals.

    Returns requires_reauth=true if new IP/device detected.
    The client should trigger password + WebAuthn re-verification.
    """
    ip, ua, _ = _get_client_info(request)
    fp = generate_device_fingerprint(ip, ua, request.headers.get("accept-language"))

    device_svc = DeviceTrustService(session)
    requires_reauth, reasons = await device_svc.check_suspicious_activity(
        current_user.user_id, fp, ip
    )

    return {
        "requires_reauth": requires_reauth,
        "reasons": reasons,
        "device_fingerprint": fp,
    }