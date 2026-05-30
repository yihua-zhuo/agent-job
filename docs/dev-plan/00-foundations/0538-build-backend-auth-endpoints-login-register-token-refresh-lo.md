# 修复后的文档

# 构建后台认证接口（登录、注册、Token 刷新、登出）

| 元数据 | 值 |
|---|---|
| Issue | #538 |
| 分类 | 10-customers |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：`../00-foundations/` 下 #537 Auth 基础层文档的实际文件名 |
| 启用后赋能 | TBD - 待验证：`../20-sales/` 下全系统接入 auth 中间件板块文档路径, TBD - 待验证：`../30-tickets/` 下用户角色权限体系板块文档路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

项目缺少用户认证接口，现有系统无注册/登录能力，无法支撑多租户 SaaS 的核心用户身份验证流程。Issue #537 已完成 JWT 加密基础工具（密钥管理、JWT 签发/验证），本板块以此为基础构建完整认证闭环。没有认证接口，#58 及下游所有功能均无法推进。

### 1.2 做完后

- **用户视角**：用户可通过 `POST /auth/register` 创建账号，通过 `POST /auth/login` 登录系统，登录状态由 httpOnly cookie 维护（无需前端手动携带 token），`POST /auth/refresh` 自动续期，`POST /auth/logout` 安全登出。
- **开发者视角**：获得 `AuthService`（login / register / refresh / logout 四个 async 方法）、`POST /auth/*` 路由注册到 `main.py`、每个请求通过 `require_auth` 依赖注入 `AuthContext`（含 tenant_id / user_id），所有 SQL 查询均强制带 `tenant_id` 多租户过滤。

### 1.3 不做什么（剔除）

- [ ] 不新增数据库表或迁移（User ORM model 已存在，issue #537 确认）
- [ ] 不实现基于RBAC的权限检查逻辑（属于后续用户角色权限体系板块）
- [ ] 不实现前端登录页（纯后端 API）

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 所有用例 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_auth_integration.py -v` → 所有用例 passed
- [ ] `ruff check src/services/auth_service.py src/api/routers/auth_router.py` → 0 errors
- [ ] `alembic upgrade head` exit 0（无新 migration 但确保不破坏现有迁移）

---

## 2. 当前现状（起点）

### 2.1 现有实现

Auth 基础工具已在 issue #537 完成，位于 `src/internal/auth/`：

TBD - 待验证：`src/internal/auth/` 目录 — 需确认 #537 完成后是否存在 `jwt_handler.py` 或等效文件（JWT 签发/验证）、`password.py` 或等效文件（bcrypt 哈希）。根据 issue #537 描述，应包含密钥管理、JWT 签发/验证、密码哈希/校验基础函数。

User ORM model 现状：

TBD - 待验证：`src/db/models/user.py` 或等效文件 — 需确认是否存在 `User` ORM model，含字段：`id`, `email`, `password_hash`, `tenant_id`, `created_at`, `updated_at`，`email` 设为 unique + index。

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 注册 auth router 到 app
  - `src/dependencies/auth.py` 或等效文件 — 确认/完善 `require_auth` 依赖注入
  - `src/internal/middleware/fastapi_auth.py` — 确认 `AuthContext` 定义
- 要建：
  - `src/services/auth_service.py` — 认证业务逻辑（login/register/refresh/logout）
  - `src/api/routers/auth_router.py` — 四个 auth 端点路由
  - `tests/unit/test_auth_service.py` — 单元测试（mock DB）
  - `tests/integration/test_auth_integration.py` — 集成测试（真实 DB）

### 2.3 缺什么

- [ ] 无 `AuthService` 类：login / register / refresh / logout 逻辑分散或缺失
- [ ] 无 `POST /auth/login`、`POST /auth/register`、`POST /auth/refresh`、`POST /auth/logout` 路由
- [ ] JWT 未与 httpOnly cookie 联动（现有工具仅完成签发/验证，cookie 设置逻辑未实现）
- [ ] 无登出时的 cookie 清除逻辑（sameSite / secure / httpOnly 属性配置）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/services/auth_service.py` | AuthService：login / register / refresh / logout 四个业务方法 |
| `src/api/routers/auth_router.py` | 四个 auth 端点：POST /auth/login, POST /auth/register, POST /auth/refresh, POST /auth/logout |
| `tests/unit/test_auth_service.py` | AuthService 单元测试（MockRow/MockResult） |
| `tests/integration/test_auth_integration.py` | AuthService 集成测试（真实 PostgreSQL） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/main.py` | 挂载 `auth_router` 到 `app.include_router` |
| `src/dependencies/auth.py` | 完善/确认 `require_auth` 和 `get_current_user` 依赖 |
| `src/internal/middleware/fastapi_auth.py` | 确认/补充 `AuthContext` dataclass（含 user_id, tenant_id） |

### 3.3 新增能力

- **Service method**：`AuthService.login(self, email: str, password: str) -> dict`（返回 user + JWT token）
- **Service method**：`AuthService.register(self, email: str, password: str, tenant_id: int) -> dict`（创建用户 + 返回 JWT）
- **Service method**：`AuthService.refresh(self, request: Request) -> dict`（从 cookie 读取旧 JWT，签发新 JWT）
- **Service method**：`AuthService.logout(self, response: Response) -> None`（清除 httpOnly cookie）
- **API endpoint**：`POST /auth/login` → `{"success": true, "data": {"user": {...}, "token": "..."}}`
- **API endpoint**：`POST /auth/register` → `{"success": true, "data": {"user": {...}, "token": "..."}}`
- **API endpoint**：`POST /auth/refresh` → `{"success": true, "data": {"token": "..."}}`
- **API endpoint**：`POST /auth/logout` → `{"success": true, "message": "logged out"}`
- **Cookie 策略**：JWT 存储于 httpOnly + secure + sameSite=strict cookie，refresh 时自动续期

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JWT 存储在 httpOnly cookie 而非 Authorization header**：防止 XSS 攻击窃取 token，浏览器自动发送同源 cookie，无需前端手动管理 token 存储（localStorage 不安全）
- **密码 bcrypt 而非 plain MD5/SHA**：bcrypt 自带 salt 和 cost factor，暴力破解成本高；issue #537 已选用 bcrypt
- **Refresh 时签发新 JWT 而非原token延期**：JWT 无状态，刷新后旧 token 立即失效，防止 token 泄露后被长期滥用
- **Logout 用清除 cookie 而非黑名单**：JWT 无状态，黑名单需要额外存储；Logout 只需清除客户端 cookie，服务端无状态无需维护

### 4.2 版本约束

<!-- 无新引入依赖，删除本段 -->

### 4.3 兼容性约束

- 多租户：`register` 接受 `tenant_id` 参数，JWT payload 必须包含 `tenant_id`，`require_auth` 返回的 `AuthContext.tenant_id` 用于所有下游查询
- Service 错误抛 `AppException` 子类：`InvalidCredentialsException`（401）、`UserAlreadyExistsException`（409）— 均继承 `AppException`，由 `main.py` 全局 handler 捕获
- Service 不调用 `.to_dict()`，由 router 层负责序列化
- Router 使用 `session: AsyncSession = Depends(get_db)` 注入 session，不手动 `async with get_db()`
- 注册时检查 email 是否已在同一 tenant 下存在（`WHERE tenant_id = :tenant_id AND email = :email`），若存在抛出 `ConflictException`

### 4.4 已知坑

1. **SQLAlchemy `metadata` 列名冲突** → 规避：本板块不涉及新 ORM model，但任何新增 JSON 列时禁止使用 `metadata` 作为列名，应用 `event_metadata` / `payload` / `attrs` 等替代
2. **Alembic autogen 将 JSONB 写成 JSON、将 TIMESTAMPTZ 写成 DateTime** → 规避：本板块无新 migration，无需关注；但 #537 若有 auth 相关迁移需手动校正
3. **JWT secret 必须从环境变量读取** → 规避：`src/internal/auth/jwt_handler.py` 中 secret 不得硬编码，应从 `os.environ["JWT_SECRET"]` 读取，若未配置则启动时 raise 明确错误
4. **cookie sameSite 属性在本地 dev 与生产环境差异** → 规避：本地 dev 环境下 `sameSite="lax"`（非 strict），生产环境 `sameSite="strict"`；cookie 设置逻辑按 `ENVIRONMENT` 环境变量分支处理

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 / 完善 AuthContext 和 require_auth 依赖注入

确认 `src/internal/middleware/fastapi_auth.py` 中 `AuthContext` 包含 `user_id: int` 和 `tenant_id: int`；确认 `src/dependencies/auth.py` 中 `require_auth` 从 cookie 读取 JWT、验证签名、解析 payload 并返回 `AuthContext`。若文件不存在则创建占位 stubs（参考 CLAUDE.md Router Pattern）。

操作：
- a) 检查 `src/internal/middleware/fastapi_auth.py` 是否存在 `AuthContext`
- b) 检查 `src/dependencies/auth.py` 是否存在 `require_auth`
- c) 若缺失：根据现有代码结构补全；若无现有结构则创建

**完成判定**：`ruff check src/dependencies/auth.py src/internal/middleware/fastapi_auth.py` → 0 errors（文件存在且语法正确）

### Step 2: 创建 AuthService（login / register / refresh / logout）

在 `src/services/auth_service.py` 实现 `AuthService` 类，构造函数 `__init__(self, session: AsyncSession)` 无默认值。

操作：
- a) 创建 `src/services/auth_service.py`
- b) `from src.internal.auth.jwt_handler import sign_jwt, verify_jwt`（#537 基础工具）
- c) `from src.internal.auth.password import hash_password, verify_password`（#537 基础工具）
- d) 实现 `login(self, email: str, password: str, tenant_id: int) -> dict`：查询 `User`（`WHERE email=:email AND tenant_id=:tenant_id`），校验密码，签发 JWT，返回 `{"user": user ORM object, "token": jwt_str}`
- e) 实现 `register(self, email: str, password: str, tenant_id: int) -> dict`：检查 email 不存在，创建 `User`（bcrypt hash password），签发 JWT，返回同上
- f) 实现 `refresh(self, token: str) -> dict`：验证 token 未过期，签发新 JWT，返回 `{"token": new_jwt}`
- g) 实现 `logout(self) -> None`：无状态，Logout 由 router 层直接清除 cookie，service 无需处理

错误处理：
- email 不存在或密码错误 → 抛 `UnauthorizedException("Invalid credentials")`
- email 已存在（register）→ 抛 `ConflictException("Email already registered")`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.internal.auth.jwt_handler import sign_jwt, verify_jwt
from src.internal.auth.password import hash_password, verify_password

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def login(self, email: str, password: str, tenant_id: int) -> dict:
        from src.db.models import User
        result = await self.session.execute(
            select(User).where(User.email == email, User.tenant_id == tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid credentials")
        token = sign_jwt({"user_id": user.id, "tenant_id": user.tenant_id})
        return {"user": user, "token": token}
```

**完成判定**：`PYTHONPATH=src ruff check src/services/auth_service.py` → 0 errors

### Step 3: 创建 auth_router（四个端点 + cookie 设置逻辑）

在 `src/api/routers/auth_router.py` 实现四个 POST 端点。JWT 存储在 httpOnly cookie 中由 router 层设置/清除，cookie 属性根据环境变量分支（dev: `sameSite="lax"`；prod: `sameSite="strict"`, `secure=True`）。

操作：
- a) 创建 `src/api/routers/auth_router.py`
- b) `from fastapi import APIRouter, Depends, Response, Request`
- c) `from src.services.auth_service import AuthService`
- d) `from src.dependencies.auth import require_auth`
- e) `POST /auth/login`：调用 `AuthService.login`，在 `response` 设置 `access_token` cookie（httpOnly, samesite, secure），返回 `{"success": true, "data": {"user": user.to_dict()}}`
- f) `POST /auth/register`：调用 `AuthService.register`，同上设置 cookie
- g) `POST /auth/refresh`：从 `request.cookies` 读取 `access_token`，调用 `AuthService.refresh`，设置新 cookie，返回 `{"success": true, "data": {"token": new_token}}`
- h) `POST /auth/logout`：在 `response` 中设置 `access_token` cookie `max-age=0` 清除，返回 `{"success": true, "message": "Logged out"}`

```python
from fastapi import APIRouter, Depends, Response, Request
from src.services.auth_service import AuthService
from src.dependencies.auth import require_auth
from src.internal.middleware.fastapi_auth import AuthContext

router = APIRouter(prefix="/auth", tags=["Auth"])

COOKIE_OPTIONS = {"httpOnly": True, "samesite": "lax"}  # dev default

@router.post("/login")
async def login(request: LoginRequest, response: Response, session: AsyncSession = Depends(get_db)):
    svc = AuthService(session)
    result = await svc.login(request.email, request.password, request.tenant_id)
    response.set_cookie(key="access_token", value=result["token"], **COOKIE_OPTIONS)
    return {"success": True, "data": {"user": result["user"].to_dict()}}
```

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/auth_router.py` → 0 errors

### Step 4: 将 auth_router 注册到 main.py

操作：
- a) 在 `src/main.py` 中添加 `from src.api.routers.auth_router import router as auth_router`
- b) 在 `app = FastAPI()` 之后、`app.include_router` 链中追加 `app.include_router(auth_router)`

**完成判定**：`PYTHONPATH=src ruff check src/main.py` → 0 errors；运行 `python -c "from main import app; print([r.path for r in app.routes])"` 确认 `/auth/login` 等路由存在

### Step 5: 编写 AuthService 单元测试

在 `tests/unit/test_auth_service.py` 中：

操作：
- a) 定义 `mock_db_session` fixture（参考 `tests/unit/conftest.py` 的 `make_mock_session` + `MockState`）
- b) 若 `User` 模型尚无 mock handler，在 conftest.py 添加 `make_user_handler(state)`
- c) 测试 `login` 成功：mock 一个 `User` row，验证返回 user + token
- d) 测试 `login` 失败（错误密码）：验证抛 `UnauthorizedException`
- e) 测试 `login` 失败（用户不存在）：验证抛 `UnauthorizedException`
- f) 测试 `register` 成功：验证 `User` insert + token 返回
- g) 测试 `register` 失败（email 已存在）：验证抛 `ConflictException`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 全部 passed

### Step 6: 编写 AuthService 集成测试

在 `tests/integration/test_auth_integration.py` 中使用 `db_schema`, `tenant_id`, `async_session` fixtures：

操作：
- a) 测试 `POST /auth/register` → 201，返回 user + 设置 cookie
- b) 测试 `POST /auth/register`（重复 email）→ 409
- c) 测试 `POST /auth/login` → 200，返回 user + 设置 cookie
- d) 测试 `POST /auth/login`（错误密码）→ 401
- e) 测试 `POST /auth/refresh`（有效 cookie）→ 200，返回新 token
- f) 测试 `POST /auth/logout` → 200，cookie 被清除

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_auth_integration.py -v` → 全部 passed

---

## 6. 验收

- [ ] `ruff check src/services/auth_service.py src/api/routers/auth_router.py src/main.py src/dependencies/auth.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 全部 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_auth_integration.py -v` → 全部 passed（如 `tests/integration/conftest.py` 提供 app fixture）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（本板块无新 migration，但确保不破坏现有迁移链）
- [ ] 端到端：`curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"Secret123!","tenant_id":1}'` 返回 `{"success": true, "data": {"user": {...}}}`
- [ ] 端到端：`curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"Secret123!","tenant_id":1}'` 返回 `{"success": true, "data": {"user": {...}}}` 且 `Set-Cookie: access_token=...; HttpOnly; SameSite`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| JWT secret 未配置导致服务启动失败 | 低 | 高（所有请求 500） | 在 `src/internal/auth/jwt_handler.py` 中加 try/except，若环境变量缺失则用 `.env` 中默认值（开发用），生产环境拒绝无 secret 启动 |
| Refresh token 时旧 JWT 验证失败（expired）导致用户被迫登出 | 中 | 中（用户需重新登录） | 前端在 401 时引导用户重新登录；短期内可调大 JWT expiry 时间缓解 |
| httpOnly cookie 在跨域场景（前端独立域名）下失效 | 中 | 高（用户无法登录） | 将 `sameSite` 设为 `lax`（非 `strict`），允许来自主域名子路径的请求；生产环境确认前端域名与 API 域名同源或配置正确的 CORS |
| #537 auth 基础工具未按时完成导致本板块阻塞 | 低 | 高（本板块无法开始） | 阻塞时本板块降级为文档完善 + 测试桩编写，#537 完成后立即接入 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/auth_service.py src/api/routers/auth_router.py src/main.py \
       tests/unit/test_auth_service.py tests/integration/test_auth_integration.py
git commit -m "feat(auth): add login/register/refresh/logout endpoints with httpOnly cookie JWT"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(auth): backend auth endpoints (#538)" --body "Closes #538\n\nSubtask of #58\nDepends on #537"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/customer_service.py` — 现有 service 模式（`__init__(self, session: AsyncSession)` + 异常抛出规范）
- 父 issue / 关联：TBD - 待验证：`../00-foundations/` 下 #537 Auth 基础层文档的实际文件名（Auth 基础层：JWT/加密工具）, #58（用户认证与授权体系顶层父 issue）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---

**修改摘要**：

| 位置 | 原内容 | 改为 |
|---|---|---|
| 元数据/依赖行 | `[Auth 基础层（JWT/加密工具）](../00-foundations/0537-build-backend-auth-base-jwt-encrypt-helpers.md)` | `TBD - 待验证：`../00-foundations/` 下 #537 Auth 基础层文档的实际文件名 |
| 元数据/赋能行 | `[全系统接入 auth 中间件](../20-sales/...)` | `TBD - 待验证：`../20-sales/` 下全系统接入 auth 中间件板块文档路径 |
| 元数据/赋能行 | `[用户角色权限体系](../30-tickets/...)` | `TBD - 待验证：`../30-tickets/` 下用户角色权限体系板块文档路径 |
| §9 参考 | `#537（Auth 基础层：JWT/加密工具）` | `TBD - 待验证：`../00-foundations/` 下 #537 Auth 基础层文档的实际文件名（Auth 基础层：JWT/加密工具）` |

---

**修复说明**：三处 broken link 均无法从上下文推导出正确路径（文件名未知、路径片段 `...` 为占位符），故全部按选项 (b) 降级为 plain text `TBD - 待验证` 占位符，与文档其余 `TBD - 待验证` 用法保持一致。
