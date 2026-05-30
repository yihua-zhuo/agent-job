# Auth Middleware Board · Wire JWT cookie Auth + Auto-Refresh for /api/* Routes

# Auth Middleware · Wire JWT Cookie Auth + Auto-Refresh for /api/* Routes

| 元数据 | 值 |
|---|---|
| Issue | #539 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：关联 0538-wire-auth-models-and-services.md |
| 启用后赋能 | TBD - 待验证：关联 0502-implement-rbac-permission-system.md, TBD - 待验证：关联 0505-automation-rules-engine.md, 所有受保护 API 路由 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/dependencies/auth.py` 中的 `get_current_user` 目前仅从 `Authorization: Bearer <token>` 请求头读取 JWT，生产环境却通过 `HttpOnly` cookie 下发刷新令牌，用户每次请求都需要前端手动携带Bearer header 或重新刷新，体验割裂。更重要的是 access token 10 分钟过期但无任何主动续期机制，当用户在长会话中操作时token静默过期直接导致 401。需要在 `main.py` 层面统一兜底：对所有 `/api/*` 路由统一读取 cookie 中的 access token，过期或缺失时返回 401，临近过期时自动调用 `/api/v1/auth/refresh` 完成无感续期。

### 1.2 做完后

- **用户视角**：登录后用户在10 分钟内发起任何 `/api/*` 请求，若 token即将过期（如剩余< 2 分钟），后端静默续期并在响应中返回新的 access token cookie（HttpOnly）；token 完全失效时返回 401 JSON，不再出现「操作一半突然401」。
- **开发者视角**：`require_auth` dependency保持不变（仍从 `Authorization` header 读取），新增 `AuthMiddleware` 作为全局中间件负责 cookie 读取 + JWT 校验 + 主动刷新兜底，所有 router 不需要改动；`AuthContext` 新增字段 `access_token: str` 供需要传递 token 的场景使用。

### 1.3 不做什么（剔除）

- [ ] 前端改动（cookie 设置 /刷新逻辑在前端不在后端）
- [ ] 新增 auth 表或 migration，依赖 #538 已建立的模型
- [ ] 修改 `LoginForm` / `OAuth2PasswordRequestForm` 接口
- [ ] 支持非 `/api/*` 路由（如 `/docs`、`/health`）走 JWT校验

### 1.4 关键 KPI

- [ `PYTHONPATH=src pytest tests/unit/test_dependencies_auth.py tests/unit/test_internal_middleware_fastapi_auth.py -v` → 全 passed]
- [ `ruff check src/dependencies/auth.py src/internal/middleware/fastapi_auth.py src/main.py` → 0 errors]
- [ `PYTHONPATH=src mypy src/internal/middleware/fastapi_auth.py` → 0 errors]
- [ 端到端（见 §6）：带过期 cookie 请求 → 返回 401 `{success: false, code: "TOKEN_EXPIRED"}`；带有效 cookie 请求 → 返回 200]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/main.py`](../../../src/main.py) L{24}-L{46}

```{python}:24:46:src/main.py
def create_app() -> FastAPI:
    app.state.jwt_secret = settings.jwt_secret
    app.state.jwt_algorithm = settings.jwt_algorithm
    # ── Middleware ──────────────────────────────────────────────────────────
    app.add_middleware(LoggingMiddleware)
    # CORS
    allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

`require_auth` 依赖读取 Bearer header：[`src/dependencies/auth.py`](../../../src/dependencies/auth.py) L{1}-L{25}

```{python}:1:25:src/dependencies/auth.py
JWT_SECRET = settings.jwt_secret or "dev-jwt-secret"
JWT_ALGORITHM = "HS256"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())) -> AuthContext:
    if not credentials:
 raise HTTPException(status_code=401, detail="Missing credentials")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("user_id") or payload.get("sub")
    tenant_id = payload.get("tenant_id", 0)
    roles = payload.get("roles", [])
    return AuthContext(user_id=int(user_id), tenant_id=int(tenant_id), roles=roles)

class RequireRole:
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

 async def __call__(self, current_user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not set(current_user.roles) & set(self.allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
```

刷新端点（已有但未被自动调用）：[`src/api/routers/auth.py`](../../../src/api/routers/auth.py) L{1}-L{30}

```{python}:1:30:src/api/routers/auth.py
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = 60*60*24*7   # 7 days# POST /api/v1/auth/refresh   — reads refresh_token cookie, rotates, returns new access_token JSON
```

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — `app.add_middleware(AuthMiddleware)` + 配置 cookie 名
  - [`src/internal/middleware/fastapi_auth.py`](../../../src/internal/middleware/fastapi_auth.py) — 新增 `AuthMiddleware`，支持 cookie 读取 + 主动刷新
- 要建：
  - `tests/unit/test_internal_middleware_fastapi_auth.py` — 中间件行为单元测试
  - `tests/unit/test_dependencies_auth.py` — 扩展现有 auth 依赖测试
  - `src/internal/middleware/auth_middleware.py` —独立全局中间件模块（单文件，职责单一）

### 2.3 缺什么

- [ ] 全局 FastAPI 中间件 — 未注册到 `main.py`，所有请求均不校验 cookie
- [ ] Cookie读取逻辑 — `get_current_user` 目前只读 Bearer header，不读 `HttpOnly` cookie
- [ ] Access token 自动刷新（主动刷新，而非等401）—缺少「剩余<2分钟时提前刷新」兜底逻辑
- [ ]主动刷新时更新 Response Set-Cookie — 将新的 access token写回 HttpOnly cookie
- [ ] 单元测试 — 无覆盖当前 auth 中间件行为的测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/internal/middleware/auth_middleware.py` | 全局 FastAPI 中间件：读取 access_token cookie、校验 JWT、返回401、自动刷新临近过期 token 并写回 response cookie |
| `tests/unit/test_internal_middleware_fastapi_auth.py` |覆盖 `AuthMiddleware` 核心行为：有效 token /过期 token / 缺失 token /主动刷新的单元测试 |
| `tests/unit/test_dependencies_auth.py` | 扩展现有 auth依赖测试：覆盖 cookie 读取 path 的新增测试用例 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | 注册 `AuthMiddleware`，配置 `access_token_cookie_name` / `refresh_endpoint` 等参数到 `app.state` |
| [`src/internal/middleware/fastapi_auth.py`](../../../src/internal/middleware/fastapi_auth.py) | `AuthContext` 新增 `access_token: str` 字段；`require_auth` 支持从 `request.state.auth_context` 读取已校验的上下文（避免重复校验）|

### 3.3 新增能力

- **FastAPI Middleware**：`AuthMiddleware` — 全局插入，读 cookie，校验 JWT，临近过期时调用 TokenService 刷新，写入 response Set-Cookie
- **Response增强**：自动刷新成功后，在 `Set-Cookie: access_token=<new>` 中下发新 access token（HttpOnly, Secure, SameSite=Strict）
- **路由零改动**：现有路由的 `Depends(require_auth)` 行为保持不变，`AuthMiddleware` 注入 `request.state.auth_context`，`require_auth` 检测后直接复用

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **中间件方案而非 dependency方案**：FastAPI `BaseHTTPMiddleware` 可全局应用至所有 `/api/*` 路由，无需改每个 router；而 `Depends` 需要每个 endpoint重复声明，中间件方案更 DRY 且可统一处理401响应- **在中间件层「提前刷新」而非401 后刷新**：若等 token过期才触发刷新，用户会感知到 1 次 401 再跳转，体验差；中间件检测剩余 TTL < 2 分钟时主动刷新，返回正常响应，前端无感知
- **Jwt-cache: 不在中间件内调用 DB**：轮转刷新调用 `/api/v1/auth/refresh` 需要 DB session，直接在中间件调用 `TokenService.rotate_access_token()` 比 HTTP 重定向更高效，且避免循环调用

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `PyJWT>=2.8` | `>=2.8` | 已在 pyproject.toml；支持 `expired` / `InvalidTokenError`可靠解析 |
| `python-jose>=3.3` | `>=3.3` | 无新增依赖；Jwt-cached 直接使用 PyJWT 无需 jose |

### 4.3 兼容性约束

- 多租户：JWT payload 内含 `tenant_id`，中间件校验通过即携带 `tenant_id`存入 `request.state`
- Service 返回 ORM 对象；本中间件不操作 DB，只调用 `TokenService`静态方法（不涉及 session）
- `AuthContext` 新增字段需向后兼容；原有 `user_id / tenant_id / roles` 字段保持不变
- `app.state.jwt_secret` / `app.state.jwt_algorithm` 已在 main.py 设置，中间件从中读取，不重复读取 settings### 4.4 已知坑

1. **Cookie 名不一致导致读不到** → 规避：中间件从 `app.state.access_token_cookie_name` 读取 cookie 名，默认 `"access_token"`，与 auth router 的 `COOKIE_NAME = "refresh_token"` 严格区分
2. **PyJWT `jwt.ExpiredSignatureError`**只在 token严格过期时抛出，`iat + exp` 计算由 PyJWT 内部完成，不依赖系统时钟偏移 →规避：无特殊处理，PyJWT 自动处理
3. **主动刷新时 token 已过期但 refresh_token cookie仍有效** →规避：刷新成功后立即写入新 access token cookie；若 refresh_token 也已过期则返回 401（触发现有前端刷新流程）
4. **中间件执行序：** `CORSMiddleware` 在 `AuthMiddleware` 之后执行，若 preflight OPTIONS 请求带错误 cookie 不应触发 401 →规避：中间件在匹配到 `/api/` 前缀且非 OPTIONS 时才执行校验逻辑；`/api/v1/auth/refresh` 本身跳过刷新（防止循环）
5. **PYTHONPATH=src**，import 拼写 `from internal.middleware.fastapi_auth import AuthContext` 而不是 `from src.internal...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建全局 AuthMiddleware 模块

在 `src/internal/middleware/auth_middleware.py` 新建文件，实现 `AuthMiddleware`（继承 `BaseHTTPMiddleware`）：

- 从 `app.state` 读取 `jwt_secret`、`jwt_algorithm`、`access_token_cookie_name`（默认 `"access_token"`）
- 对所有 `/api/` 路径且非 `OPTIONS` 请求：读取 named cookie
- 调用 `jwt.decode(token, secret, algorithms=[alg])` —过期则 `jwt.ExpiredSignatureError` → 返回 401 JSON `{"success": false, "message": "Token expired", "code": "TOKEN_EXPIRED"}`
- 解包 payload，取 `user_id / tenant_id / roles`，存入 `request.state.auth_context = AuthContext(...)`
- 检查 `exp - now< REFRESH_THRESHOLD_SECONDS（120s）`：调用 `TokenService.create_access_token(...)` 生成新 access token，写入 response `Set-Cookie` header- 路径 `/api/v1/auth/refresh` 跳过刷新逻辑，防止循环```python
# src/internal/middleware/auth_middleware.py（≤15 行结构示例）
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import ResponseCOOKIE_NAME = "access_token"
REFRESH_THRESHOLD_SECONDS = 120


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cookie_name: str = COOKIE_NAME, refresh_threshold: int = REFRESH_THRESHOLD_SECONDS):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.refresh_threshold = refresh_threshold

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or request.method == "OPTIONS":
            return await call_next(request)
        token = request.cookies.get(self.cookie_name)
        if not token:
            return JSONResponse(status_code=401, content={"success": False, "message": "Missing token", "code": "TOKEN_MISSING"})
        try:
            payload = jwt.decode(token, ...)
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"success": False, "message": "Token expired", "code": "TOKEN_EXPIRED"})
        # ...注入 request.state.auth_context +主动刷新逻辑```

**完成判定**：`ruff check src/internal/middleware/auth_middleware.py` → 0 errors

---

### Step 2: 扩展 AuthContext + 改造 require_auth 复用 middleware注入的上下文

修改 `src/internal/middleware/fastapi_auth.py`：

- `AuthContext.__init__` 新增参数 `access_token: str = ""`，`__slots__` 加入 `"access_token"`
- `require_auth` 函数检测 `request.state` 是否已有 `.auth_context`：有则直接返回（跳过重复校验），无则走原有 Bearer header 路径- 兼容无 middleware 注册的测试场景（`request.state` 无 `auth_context` 时 fallback走 `HTTPBearer`）

```python
# src/internal/middleware/fastapi_auth.py — AuthContext 扩展
class AuthContext:
    __slots__ = ("user_id", "tenant_id", "roles", "access_token")
    def __init__(self, user_id: int, tenant_id: int | None, roles: list, access_token: str = ""):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles self.access_token = access_token
```

**完成判定**：`ruff check src/internal/middleware/fastapi_auth.py && mypy src/internal/middleware/fastapi_auth.py` → 均 0 errors

---

### Step 3: 在 main.py 注册 AuthMiddleware

修改 `src/main.py` — 在 `app.add_middleware(LoggingMiddleware)` 之前插入：

```python
from internal.middleware.auth_middleware import AuthMiddleware

# 在 create_app() 函数体内，LoggingMiddleware 之前添加：
app.add_middleware(
    AuthMiddleware,
    cookie_name=settings.access_token_cookie_name or "access_token",
    refresh_threshold=120,
)
```

- `access_token_cookie_name` 从 settings读取，默认 `"access_token"`
- 确保 `CORSMiddleware` 在 `AuthMiddleware`之后（Starlette 中间件按注册顺序倒序执行，CORSMiddleware 需要最后执行）

**完成判定**：`ruff check src/main.py && PYTHONPATH=src python -c "from main import app; print('OK')"` → OK---

### Step 4: 编写单元测试

新建 `tests/unit/test_internal_middleware_fastapi_auth.py`：

测试用例（使用 `make_mock_session` + `httpx.AsyncClient` 或 Starlette TestClient）：

- `test_valid_token_returns_200`：签发有效 JWT cookie → 中间件放行 → status 200
- `test_missing_token_returns_401`：无 cookie → status 401, code TOKEN_MISSING
- `test_expired_token_returns_401`：过期 JWT cookie → status 401, code TOKEN_EXPIRED
- `test_refresh_triggered_within_threshold`：剩余 TTL < 120s 的 token → 检查 response Set-Cookie header存在新 access_token
- `test_auth_refresh_endpoint_skips_refresh`：GET /api/v1/auth/refresh 请求跳过刷新逻辑（不返回 401）

```python
# tests/unit/test_internal_middleware_fastapi_auth.py — 结构占位import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from main import appfrom internal.middleware.auth_middleware import AuthMiddleware

def test_missing_token_returns_401():
    client = TestClient(app, cookies={})
    response = client.get("/api/v1/customers")
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "TOKEN_MISSING"
```

修改 `tests/unit/test_dependencies_auth.py`：新增测试用例覆盖 cookie 读取 path（模拟 `request.cookies`注入）

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_internal_middleware_fastapi_auth.py tests/unit/test_dependencies_auth.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/internal/middleware/auth_middleware.py src/internal/middleware/fastapi_auth.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_internal_middleware_fastapi_auth.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_dependencies_auth.py -v` → 全 passed
- [ ] `PYTHONPATH=src mypy src/internal/middleware/auth_middleware.py src/internal/middleware/fastapi_auth.py src/main.py` → 0 errors
- [ ] 端到端（TestClient）：

 ```bash
  # 无 cookie 请求 /api/v1/customers →401 TOKEN_MISSING
  #过期 cookie 请求 /api/v1/customers → 401 TOKEN_EXPIRED
  # 有效 cookie 请求 /api/v1/customers →200 成功放行
  #剩余 TTL < 2min 的 cookie 请求 → response Set-Cookie 含新的 access_token
  ```

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 中间件导致循环刷新（中间件刷新后新 token 有效期仍短，下一次请求再次刷新） | 低 | 中 | 中间件仅当 payload.exp - now < 120s 时刷新，刷新后 exp = now + 10min，下次请求不会触发；设置 `refreshed_at` flag 避免同一次请求内重复刷新 |
| 刷新 cookie 与原有 Bearer header冲突（前端同时用两种方式传 token） | 中 | 低 | `require_auth` 读取优先级：request.state.auth_context（cookie 中间件）> HTTPBearer header；两路径最终都验证同一 JWT payload，无逻辑冲突 |
| 中间件注册顺序导致 CORSMiddleware 无法读取自定义401 body | 低 | 中 | Starlette 中间件顺序中，CORS 在 AuthMiddleware 之后注册（倒序执行 → CORS 先），CORS preflight OPTIONS跳过 auth校验，正常放行；CORS响应200，不会触发 401 |
| TokenService 内部 DB 操作失败导致 500 | 低 | 中 | 中间件捕获 `Exception`，降级为「刷新失败但原 token 仍有效则放行」，仅在 token 完全无效时返回 401 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/internal/middleware/auth_middleware.py \
 src/internal/middleware/fastapi_auth.py \
       src/main.py \
       tests/unit/test_internal_middleware_fastapi_auth.py \
       tests/unit/test_dependencies_auth.py
git commit -m "feat(auth): wire global JWT cookie middleware with auto-refresh for /api/* routes"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#539): wire auth middleware for protected routes and global token refresh" --body "Closes #539"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/internal/middleware/fastapi_auth.py`](../../src/internal/middleware/fastapi_auth.md) L{1}-L{95} — `AuthContext` + `require_auth`现有实现
- 同类参考实现：[`src/dependencies/auth.py`](../../../src/dependencies/auth.py) L{1}-L{102} — `get_current_user` + `RequireRole` 依赖注入模式
- 同类参考实现：[`src/api/routers/auth.py`](../../../src/api/routers/auth.py) L{1}-L{30} — `/api/v1/auth/refresh`端点（已有刷新逻辑）
- 第三方文档：[PyJWT — Validating Claims](https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode)
- 父 issue / 关联：#58, #538

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
