"""Users router — /api/v1/users and /api/v1/auth endpoints.

Services raise AppException subclasses on errors (caught by global handler in main.py).
Router wraps successful returns in {"success": True, "data": ...} dicts.
"""
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from db.connection import get_db
from dependencies.auth import get_current_user
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.auth_service import AuthService
from services.user_service import UserService

users_router = APIRouter(prefix='/api/v1', tags=['users'])


def _paginated(items, total, page, page_size):
    total_pages = math.ceil(total / page_size) if page_size else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


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


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=1000)


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# User CRUD endpoints (requires auth)
# ---------------------------------------------------------------------------

@users_router.post('/users', status_code=201)
async def create_user(
    body: UserCreate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    result = await service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        tenant_id=ctx.tenant_id or 0,
        full_name=body.full_name,
        role=body.role,
    )
    return {"success": True, "data": result, "message": "用户创建成功"}


@users_router.get('/users')
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, max_length=50),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    items, total = await service.list_users(
        page=page,
        page_size=page_size,
        q=q,
        role=role,
        tenant_id=ctx.tenant_id or 0,
    )
    return _paginated(items, total, page, page_size)


@users_router.get(
    '/users/me',
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
    result = await service.get_user_by_id(current_user.user_id, tenant_id=current_user.tenant_id)
    return {"success": True, "data": result, "message": "查询成功"}


@users_router.get('/users/{user_id}')
async def get_user(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    result = await service.get_user_by_id(user_id, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": result, "message": "查询成功"}


@users_router.put('/users/{user_id}')
async def update_user(
    user_id: int,
    body: UserUpdate,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    update_data = body.model_dump(exclude_none=True)
    result = await service.update_user(user_id, tenant_id=ctx.tenant_id or 0, **update_data)
    return {"success": True, "data": result, "message": "用户更新成功"}


@users_router.delete('/users/{user_id}')
async def delete_user(
    user_id: int,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    await service.delete_user(user_id, tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": None, "message": "用户删除成功"}


@users_router.post('/users/search')
async def search_users(
    keyword: str = Query(..., min_length=1, max_length=200),
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    items, total = await service.search_users(keyword, tenant_id=ctx.tenant_id or 0)
    return _paginated(items, total, 1, total or 20)


@users_router.post('/users/{user_id}/password')
async def change_password(
    user_id: int,
    body: PasswordChange,
    ctx: AuthContext = Depends(require_auth),
    session=Depends(get_db),
):
    service = UserService(session)
    await service.change_password(user_id, body.old_password, body.new_password)
    return {"success": True, "data": None, "message": "密码修改成功"}


# ---------------------------------------------------------------------------
# PATCH /users/me — update current user's profile
# ---------------------------------------------------------------------------

@users_router.patch('/users/me')
async def update_my_profile(
    body: ProfileUpdate,
    current_user: AuthContext = Depends(get_current_user),
    session=Depends(get_db),
):
    """Update the authenticated user's own profile (full_name, email, bio)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    service = UserService(session)
    result = await service.update_user(current_user.user_id, tenant_id=current_user.tenant_id, **update_data)
    return {"success": True, "data": result, "message": "个人信息更新成功"}


# ---------------------------------------------------------------------------
# POST /auth/change-password — change own password
# ---------------------------------------------------------------------------

@users_router.post('/auth/change-password')
async def change_my_password(
    body: PasswordChangeRequest,
    current_user: AuthContext = Depends(get_current_user),
    session=Depends(get_db),
):
    """Change the authenticated user's own password."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    service = UserService(session)
    await service.change_password(current_user.user_id, body.old_password, body.new_password)
    return {"success": True, "data": None, "message": "密码修改成功"}


# ---------------------------------------------------------------------------
# Auth endpoints (no JWT required for register/login)
# ---------------------------------------------------------------------------

@users_router.post('/auth/register', status_code=201)
async def register(
    body: UserCreate,
    session=Depends(get_db),
):
    from configs.settings import settings
    service = AuthService(session, secret_key=settings.jwt_secret)
    result = await service.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        role=body.role or "user",
        tenant_id=0,
        full_name=body.full_name,
    )
    return {"success": True, "data": result, "message": "注册成功"}


@users_router.post('/auth/login', response_model=Token)
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
