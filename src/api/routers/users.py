"""Users router — /api/v1/users and /api/v1/auth endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from db.connection import get_db
from dependencies.auth import get_current_user
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ResponseStatus
from pkg.response.schemas import ErrorEnvelope, SuccessEnvelope
from services.auth_service import AuthService
from services.user_service import UserService

users_router = APIRouter(prefix='/api/v1', tags=['users'])


def _http_status(status) -> int:
    # Handle both ResponseStatus enum and string values
    if isinstance(status, str):
        m = {
            "success": 200, "error": 400, "warning": 200,
            "unauthorized": 401, "forbidden": 403,
            "not_found": 404, "validation_error": 400, "server_error": 500,
        }
        return m.get(status, 400)
    m = {
        ResponseStatus.SUCCESS: 200,
        ResponseStatus.NOT_FOUND: 404,
        ResponseStatus.VALIDATION_ERROR: 400,
        ResponseStatus.UNAUTHORIZED: 401,
        ResponseStatus.FORBIDDEN: 403,
        ResponseStatus.SERVER_ERROR: 500,
        ResponseStatus.ERROR: 400,
        ResponseStatus.WARNING: 200,
    }
    return m.get(status, 400)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=200)
    role: str | None = Field(default="user")


class UserUpdate(BaseModel):
    email: str | None = Field(None, max_length=255)
    full_name: str | None = Field(None, max_length=200)
    status: str | None = None
    bio: str | None = Field(None, max_length=1000)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    """Standard OAuth2 token response for Swagger UI Authorize button."""
    access_token: str
    token_type: str = "bearer"


# OAuth2 scheme — tokenUrl MUST match the login endpoint path.
# This is what powers Swagger UI's "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class UserData(BaseModel):
    id: int
    tenant_id: int
    username: str
    email: str
    role: str
    status: str
    full_name: str | None = None
    bio: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UserResponse(SuccessEnvelope):
    data: UserData | None = None


class UserListData(BaseModel):
    items: list[UserData]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class UserListResponse(SuccessEnvelope):
    data: UserListData


class LoginResponse(SuccessEnvelope):
    data: dict


# ---------------------------------------------------------------------------
# User CRUD endpoints (requires auth)
# ---------------------------------------------------------------------------

@users_router.post(
    '/users',
    status_code=201,
    response_model=UserResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_user(
    body: UserCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    resp = await service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        tenant_id=ctx.tenant_id or 0,
        full_name=body.full_name,
        role=body.role,
    )
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    user_data = resp.data
    if user_data is None:
        return UserResponse(message=resp.message, data=None)
    # user_data is a dict (from real DB)
    return UserResponse(
        message=resp.message,
        data=UserData(
            id=user_data["id"],
            tenant_id=user_data["tenant_id"],
            username=user_data["username"],
            email=user_data["email"],
            role=str(user_data["role"]),
            status=str(user_data["status"]),
            full_name=user_data.get("full_name"),
            bio=user_data.get("bio"),
            created_at=str(user_data.get("created_at")) if user_data.get("created_at") else None,
            updated_at=str(user_data.get("updated_at")) if user_data.get("updated_at") else None,
        ),
    )


@users_router.get(
    '/users',
    response_model=UserListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, max_length=50),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    resp = await service.list_users(
        page=page,
        page_size=page_size,
        q=q,
        role=role,
        tenant_id=ctx.tenant_id or 0,
    )
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    _pd = resp.data
    items = []
    for u in _pd.items:
        items.append(UserData(
            id=u["id"],
            tenant_id=u["tenant_id"],
            username=u["username"],
            email=u["email"],
            role=u["role"].value if hasattr(u["role"], "value") else str(u["role"]),
            status=u["status"].value if hasattr(u["status"], "value") else str(u["status"]),
            full_name=u.get("full_name"),
            bio=u.get("bio"),
            created_at=u["created_at"].isoformat() if u.get("created_at") else None,
            updated_at=u["updated_at"].isoformat() if u.get("updated_at") else None,
        ))
    return UserListResponse(
        message=resp.message,
        data=UserListData(
            items=items,
            total=_pd.total,
            page=_pd.page,
            page_size=_pd.page_size,
            total_pages=_pd.total_pages,
            has_next=_pd.has_next,
            has_prev=_pd.has_prev,
        ),
    )


@users_router.get(
    '/users/me',
    response_model=UserResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Get current authenticated user",
)
async def get_current_active_user(
    current_user: AuthContext = Depends(get_current_user),
    session=Depends(get_db),
):
    """Return the user profile for the currently authenticated user.
    Powered by the JWT token obtained via the /auth/login endpoint.
    """
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    service = UserService(session)
    user = await service.get_user_by_id(current_user.user_id, tenant_id=current_user.tenant_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    # user is a dict (from real DB)
    return UserResponse(
        message="查询成功",
        data=UserData(
            id=user["id"],
            tenant_id=user["tenant_id"],
            username=user["username"],
            email=user["email"],
            role=str(user["role"]),
            status=str(user["status"]),
            full_name=user.get("full_name"),
            bio=user.get("bio"),
            created_at=str(user.get("created_at")) if user.get("created_at") else None,
            updated_at=str(user.get("updated_at")) if user.get("updated_at") else None,
        ),
    )


@users_router.get(
    '/users/{user_id}',
    response_model=UserResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def get_user(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    user = await service.get_user_by_id(user_id, tenant_id=ctx.tenant_id or 0)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    # user is a dict (from real DB)
    return UserResponse(
        message="查询成功",
        data=UserData(
            id=user["id"],
            tenant_id=user["tenant_id"],
            username=user["username"],
            email=user["email"],
            role=str(user["role"]),
            status=str(user["status"]),
            full_name=user.get("full_name"),
            bio=user.get("bio"),
            created_at=str(user.get("created_at")) if user.get("created_at") else None,
            updated_at=str(user.get("updated_at")) if user.get("updated_at") else None,
        ),
    )


@users_router.put(
    '/users/{user_id}',
    response_model=UserResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def update_user(
    user_id: int,
    body: UserUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    update_data = body.model_dump(exclude_none=True)
    resp = await service.update_user(user_id, tenant_id=ctx.tenant_id or 0, **update_data)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    user_data = resp.data
    if user_data is None:
        return UserResponse(message=resp.message, data=None)
    return UserResponse(
        message=resp.message,
        data=UserData(
            id=user_data["id"],
            tenant_id=user_data["tenant_id"],
            username=user_data["username"],
            email=user_data["email"],
            role=str(user_data["role"]),
            status=str(user_data["status"]),
            full_name=user_data.get("full_name"),
            bio=user_data.get("bio"),
            created_at=str(user_data.get("created_at")) if user_data.get("created_at") else None,
            updated_at=str(user_data.get("updated_at")) if user_data.get("updated_at") else None,
        ),
    )


@users_router.delete(
    '/users/{user_id}',
    response_model=UserResponse,
    responses={404: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def delete_user(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    resp = await service.delete_user(user_id, tenant_id=ctx.tenant_id or 0)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return UserResponse(message=resp.message, data=None)


@users_router.post(
    '/users/search',
    response_model=UserListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def search_users(
    keyword: str = Query(..., min_length=1, max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    resp = await service.search_users(keyword, tenant_id=ctx.tenant_id or 0)
    status_code = _http_status(resp.status)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=resp.message)
    _pd = resp.data
    items = []
    for u in _pd.items:
        items.append(UserData(
            id=u["id"],
            tenant_id=u["tenant_id"],
            username=u["username"],
            email=u["email"],
            role=u["role"].value if hasattr(u["role"], "value") else str(u["role"]),
            status=u["status"].value if hasattr(u["status"], "value") else str(u["status"]),
            full_name=u.get("full_name"),
            bio=u.get("bio"),
            created_at=u["created_at"].isoformat() if u.get("created_at") else None,
            updated_at=u["updated_at"].isoformat() if u.get("updated_at") else None,
        ))
    return UserListResponse(
        message=resp.message,
        data=UserListData(
            items=items,
            total=_pd.total,
            page=_pd.page,
            page_size=_pd.page_size,
            total_pages=_pd.total_pages,
            has_next=_pd.has_next,
            has_prev=_pd.has_prev,
        ),
    )


@users_router.post(
    '/users/{user_id}/password',
    response_model=UserResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def change_password(
    user_id: int,
    body: PasswordChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    resp = await service.change_password(user_id, body.old_password, body.new_password)
    status = _http_status(resp.status)
    if status != 200:
        raise HTTPException(status_code=status, detail=resp.message)
    return UserResponse(message=resp.message, data=None)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=1000)


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# PATCH /users/me — update current user's profile
# ---------------------------------------------------------------------------

@users_router.patch(
    '/users/me',
    response_model=UserResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_my_profile(
    body: ProfileUpdate,
    current_user: AuthContext = Depends(get_current_user),
    session=Depends(get_db),
):
    """Update the authenticated user's own profile (full_name, email, bio)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    service = UserService(session)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    resp = await service.update_user(current_user.user_id, tenant_id=current_user.tenant_id, **update_data)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    user_data = resp.data
    if user_data is None:
        return UserResponse(message=resp.message, data=None)
    return UserResponse(
        message=resp.message,
        data=UserData(
            id=user_data["id"],
            tenant_id=user_data["tenant_id"],
            username=user_data["username"],
            email=user_data["email"],
            role=str(user_data["role"]),
            status=str(user_data["status"]),
            full_name=user_data.get("full_name"),
            bio=user_data.get("bio"),
            created_at=str(user_data.get("created_at")) if user_data.get("created_at") else None,
            updated_at=str(user_data.get("updated_at")) if user_data.get("updated_at") else None,
        ),
    )


# ---------------------------------------------------------------------------
# POST /auth/change-password — change own password
# ---------------------------------------------------------------------------

@users_router.post(
    '/auth/change-password',
    response_model=UserResponse,
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def change_my_password(
    body: PasswordChangeRequest,
    current_user: AuthContext = Depends(get_current_user),
    session=Depends(get_db),
):
    """Change the authenticated user's own password."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    service = UserService(session)
    resp = await service.change_password(current_user.user_id, body.old_password, body.new_password)
    status = _http_status(resp.status)
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message)
    return UserResponse(message=resp.message, data=None)


# ---------------------------------------------------------------------------
# Auth endpoints (no JWT required for register/login)
# ---------------------------------------------------------------------------

@users_router.post(
    '/auth/register',
    status_code=201,
    response_model=UserResponse,
    responses={400: {"model": ErrorEnvelope}},
)
async def register(
    body: UserCreate,
    session=Depends(get_db),
):
    from configs.settings import settings
    service = AuthService(session, secret_key=settings.jwt_secret)
    resp = await service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        role=body.role or "user",
        tenant_id=0,
        full_name=body.full_name,
    )
    status = _http_status(resp.status) if hasattr(resp, "status") else 400
    if status >= 400:
        raise HTTPException(status_code=status, detail=resp.message if hasattr(resp, "message") else "Registration failed")
    user_data = resp.data if hasattr(resp, "data") and resp.data else None
    if user_data is None:
        return UserResponse(message=resp.message if hasattr(resp, "message") else "注册成功", data=None)
    # user_data is a dict (ApiResponse.data was a dict from real DB)
    return UserResponse(
        message=resp.message if hasattr(resp, "message") else "注册成功",
        data=UserData(
            id=user_data["id"],
            tenant_id=user_data["tenant_id"],
            username=user_data["username"],
            email=user_data["email"],
            role=str(user_data["role"]),
            status=str(user_data["status"]),
            full_name=user_data.get("full_name"),
            bio=user_data.get("bio"),
            created_at=user_data["created_at"].isoformat() if hasattr(user_data["created_at"], "isoformat") else str(user_data.get("created_at")) if user_data.get("created_at") else None,
            updated_at=user_data["updated_at"].isoformat() if hasattr(user_data["updated_at"], "isoformat") else str(user_data.get("updated_at")) if user_data.get("updated_at") else None,
        ),
    )


@users_router.post(
    '/auth/login',
    response_model=Token,
    responses={401: {"model": ErrorEnvelope}},
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session=Depends(get_db),
):
    """Standard OAuth2 password flow — accepts form data (username + password).
    Swagger UI 'Authorize' button sends credentials here as form-encoded.
    """
    from configs.settings import settings
    auth_svc = AuthService(session, secret_key=settings.jwt_secret)
    user_dict = await auth_svc.authenticate_user(form_data.username, form_data.password)
    if user_dict is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = auth_svc.generate_token(
        user_id=user_dict["id"],
        username=user_dict["username"],
        role=user_dict["role"],
        tenant_id=user_dict.get("tenant_id"),
    )
    return Token(access_token=token, token_type="bearer")


