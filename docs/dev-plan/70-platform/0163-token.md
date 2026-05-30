# 安全增强 · 登录认证重构 — 多因素 + 分层 Token 存储

| 元数据 | 值 |
|---|---|
| Issue | #163 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 3-5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 所有依赖认证的板块（Customers, Sales, Campaigns 等） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前登录系统仅依赖 JWT，存在以下结构性安全缺陷：
- Access Token 明文存储于 `localStorage`，任何 XSS 漏洞可直接读取并冒用身份
- 无设备信任机制，任一 session 泄露均可被恶意方利用
- 无渐进式认证体系，敏感操作（如修改密码、删除资源）无二次验证

此外，Refresh Token 无 HttpOnly Cookie 保护，Cookie 被窃取后攻击者可长期持有。

### 1.2 做完后

- **用户视角**：
  - 新设备首次登录需完成 WebAuthn 注册（支持 Windows Hello / TouchID / YubiKey）
  - 可疑活动（新 IP、异地登录）触发强制二次验证，但不中断已有 session
  - 正常使用时无感知 — Access Token 在后台静默续期，无需用户操作
- **开发者视角**：
  - 新增 `AuthService.refresh_access_token()` — 用 HttpOnly Cookie 中的 refresh token 换新的 Access Token
  - 新增 `WebAuthnService.register_begin() / register_complete()` — WebAuthn 注册流程
  - 新增 `WebAuthnService.verify_assertion()` — WebAuthn 断言验证
  - 新增 `DeviceTrustService.evaluate()` — 设备信任评估与可疑活动检测

### 1.3 不做什么（剔除）

- [ ] 第三方 SSO 集成（SSO 登录入口只做占位，WebAuthn 注册流程在密码登录后触发）
- [ ] 短信 / 邮件二次验证（MFA 仅支持 WebAuthn/FIDO2）
- [ ] 前端移动端原生 App 适配（仅限 Web 端）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 所有新增 case passed]
- [指标 2：`PYTHONPATH=src pytest tests/integration/test_webauthn_integration.py -v` → WebAuthn 完整流程 passed]
- [指标 3：`ruff check src/services/auth_service.py src/services/webauthn_service.py src/api/routers/auth.py` → 0 errors]
- [指标 4：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/middleware/fastapi_auth.py` — 现有 JWT 解析与 AuthContext 构建逻辑
TBD - 待验证：`src/dependencies/auth.py` — `require_auth` / `get_current_user` 依赖注入
TBD - 待验证：`src/api/routers/auth.py` — 现有 `/auth/login` 端点（返回 JWT token 在 body 中）

当前认证流程（推测）：
```
POST /auth/login → {username, password} → 检查 DB → 返回 JWT → 前端存 localStorage
Authorization: Bearer <jwt> → 中间件解析 → AuthContext
```

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/auth.py` — 新增 `/auth/refresh`、`/auth/webauthn/*` 端点；移除 JWT 在 body 中返回的旧逻辑
  - `src/middleware/fastapi_auth.py` — 改为从请求上下文字典取 Access Token（内存），不读 localStorage
  - `src/dependencies/auth.py` — 新增 `require_webauthn_verified()` 依赖
  - `tests/unit/test_auth_service.py` — 新增 token refresh 与 WebAuthn 测试
  - `tests/integration/test_auth_integration.py` — 新增 HttpOnly Cookie 流程测试
- 要建：
  - `src/services/auth_service.py` — Token refresh 逻辑（从 Cookie 读 refresh token，换发 Access Token）
  - `src/services/webauthn_service.py` — WebAuthn 注册/验证全流程
  - `src/services/device_trust_service.py` — 设备信任评估
  - `src/db/models/user_credential.py` — WebAuthn credential 存储
  - `src/db/models/device_trust.py` — 设备信任记录
  - `src/db/models/refresh_token.py` — Refresh token 撤销列表（如实现黑名单）
  - `alembic/versions/<id>_add_webauthn_and_device_trust_tables.py` — 三个新表的 migration
  - `tests/integration/test_webauthn_integration.py` — WebAuthn 完整流程集成测试

### 2.3 缺什么

- [ ] Access Token 内存存储方案（前端 React Context / Zustand，后端 AuthContext）
- [ ] HttpOnly Cookie 中的 Refresh Token 解析与验证机制
- [ ] WebAuthn 注册/断言的完整后端实现
- [ ] 设备指纹采集与后端存储
- [ ] 可疑活动检测（IP / 地理位置变更）
- [ ] `user_credentials` / `device_trust` / `refresh_tokens` 三张数据库表及 ORM model
- [ ] Re-auth 触发中间件（敏感操作路由守卫）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/auth_service.py` | Refresh token 换发 Access Token；token 撤销管理 |
| `src/services/webauthn_service.py` | WebAuthn 注册开始/完成、断言验证全流程 |
| `src/services/device_trust_service.py` | 设备信任评估；可疑活动检测（IP/地理变更） |
| `src/db/models/user_credential.py` | WebAuthn credential（public key, credential_id, counter） |
| `src/db/models/device_trust.py` | 受信任设备指纹 + 最后验证时间 |
| `src/db/models/refresh_token.py` | Refresh token 黑名单（撤销列表） |
| `alembic/versions/<id>_add_webauthn_device_trust_tables.py` | 三张新表的 migration |
| `tests/unit/test_auth_service.py` | Token refresh + 撤销逻辑单元测试 |
| `tests/unit/test_webauthn_service.py` | WebAuthn service 单元测试 |
| `tests/integration/test_webauthn_integration.py` | WebAuthn 注册/验证完整流程集成测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/auth.py`](../../../src/api/routers/auth.py) | 新增 `/auth/refresh`（POST）、`/auth/webauthn/register`（POST/GET）、`/auth/webauthn/verify`（POST）；`/auth/login` 改为设置 HttpOnly Cookie |
| TBD - 待验证：`src/middleware/fastapi_auth.py` | Access Token 从请求 state（内存）读取，移除 localStorage 相关假设 |
| [`src/dependencies/auth.py`](../../../src/dependencies/auth.py) | 新增 `require_webauthn_verified` 依赖，用于敏感操作路由守卫 |
| [`src/main.py`](../../../src/main.py) | 注册新的 auth 相关依赖和中间件 |
| [`tests/unit/test_auth_service.py`](../../../tests/unit/test_auth_service.py) | 新增 token refresh 测试用例 |
| [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) | 新增 `db_schema` fixture 支持三张新表 |

### 3.3 新增能力

- **Service method**：`AuthService.refresh_access_token(self, request: Request, tenant_id: int) -> str` — 从 HttpOnly Cookie 解析 refresh token，换发 Access Token
- **Service method**：`WebAuthnService.register_begin(self, user_id: int, tenant_id: int) -> dict` — 启动 WebAuthn 注册，返回 challenge 和 options
- **Service method**：`WebAuthnService.register_complete(self, user_id: int, credential_data: dict, tenant_id: int) -> UserCredential` — 完成注册，存储 public key
- **Service method**：`WebAuthnService.verify_assertion(self, credential_data: dict, tenant_id: int) -> bool` — 验证 WebAuthn 断言
- **Service method**：`DeviceTrustService.evaluate(self, device_fingerprint: str, tenant_id: int, user_id: int) -> TrustLevel` — 评估设备信任等级（决定是否触发 re-auth）
- **API endpoint**：`POST /auth/refresh` — 用 Cookie 中的 refresh token 换新 Access Token
- **API endpoint**：`POST /auth/webauthn/register/begin` — 开始 WebAuthn 注册
- **API endpoint**：`POST /auth/webauthn/register/complete` — 完成 WebAuthn 注册
- **API endpoint**：`POST /auth/webauthn/verify` — 验证 WebAuthn 断言（re-auth 时调用）
- **ORM model**：`UserCredential` in `src/db/models/user_credential.py`
- **ORM model**：`DeviceTrust` in `src/db/models/device_trust.py`
- **ORM model**：`RefreshToken` in `src/db/models/refresh_token.py`
- **Migration**：`alembic upgrade head` 创建 `user_credentials`、`device_trusts`、`refresh_tokens` 三表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `@simplewebauthn/server`（Python）不选 Node.js `@simplewebauthn/server`**：后端为 Python FastAPI，直接用 Python 库避免跨语言调用和依赖复杂化
- **选 HttpOnly Cookie 存储 Refresh Token 不选 localStorage**：HttpOnly 禁止 JS 读取，XSS 无法窃取 Refresh Token
- **选 Access Token 存内存（Python dict / FastAPI request.state）不选任何持久化**：Access Token 生命周期短（5-15 分钟），持久化无意义且增加泄露风险；前端同样存入内存（React Context），不落磁盘
- **选设备指纹后端存储不选前端 localStorage**：设备指纹为敏感安全数据，任何前端存储均可被 XSS 读取，应存后端

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `simplewebauthn` | `≥9.0` | 支持 FIDO2，Python 最新稳定版，与 PyCryptodome 兼容 |
| `Fido2Lib` | `≥4.0` | 备选 WebAuthn 库；如 simplewebauthn 不可用时使用 |

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`（`user_credentials`、`device_trusts`、`refresh_tokens` 均需 `tenant_id` 列）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- WebAuthn credential public key 存储使用 `Fido2Lib` 序列化后的原始字节，不做 Base64 编码存储
- Refresh token 存储时需 bcrypt hash，不存储明文

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不能用 `metadata`** → 规避：`UserCredential` 表使用 `credential_metadata` / `public_key_bytes` 列名，避免与 `Base.metadata` 冲突
2. **Alembic autogen 会把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 规避：migration 生成后手动检查，对 `JSON` 列改为 `JSONB`，`DateTime` 改为 `TIMESTAMP(timezone=True)`
3. **PYTHONPATH=src，import 写 `from db.models...` 而不是 `from src.db.models...`** → 所有新文件严格遵循此规则
4. **Async session 不要用 `async with get_db()`，用 `Depends(get_db)`** → 所有 router 注入使用 `session: AsyncSession = Depends(get_db)`
5. **WebAuthn challenge 必须为随机 bytes，长度 ≥ 16 字节** → 每次注册/验证前动态生成，存入 Redis 或 DB 用于验证（防止 replay attack）
6. **device_fingerprint 生成需兼容无 JS fingerprint 环境** → 后端 fallback 方案：使用 User-Agent + IP 哈希作为降级指纹，不依赖前端 JS

---

## 5. 实现步骤（按顺序）

### Step 1: 实现数据库层 — 新增三张表及 ORM Model

新增 `user_credentials`、`device_trusts`、`refresh_tokens` 三张表及对应 ORM Model。

在 `src/db/models/user_credential.py` 中：

```python
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    public_key_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    credential_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True)
    counter: Mapped[int] = mapped_column(BigInteger, default=0)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_user_credentials_tenant_user", "tenant_id", "user_id"),
    )
```

同理创建 `device_trust.py` 和 `refresh_token.py`。

**完成判定**：`ruff check src/db/models/user_credential.py src/db/models/device_trust.py src/db/models/refresh_token.py` → 0 errors

### Step 2: 生成 Alembic Migration

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade head
alembic revision --autogenerate -m "add webauthn device_trust refresh_token tables"
# 手动修改：JSON → JSONB，DateTime → TIMESTAMP(timezone=True)
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
alembic revision --autogenerate -m "drift_check"
# 删除空 migration
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: 实现 AuthService — Token Refresh

在 `src/services/auth_service.py` 实现：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from pkg.errors.app_exceptions import UnauthorizedException, ForbiddenException

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def refresh_access_token(self, request: Request, tenant_id: int) -> str:
        cookie_value = request.cookies.get("refresh_token")
        if not cookie_value:
            raise UnauthorizedException("Missing refresh token")
        # 解析并验证 refresh token（如使用 signed httponly cookie）
        # 从 refresh_tokens 表检查是否已撤销
        # 生成新的 access token，返回
        ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 新增 refresh 测试 passed

### Step 4: 实现 WebAuthnService — 注册与验证

在 `src/services/webauthn_service.py` 实现 WebAuthn 全流程：

```python
from simplewebauthn import generateRegistrationOptions, verifyRegistrationResponse
from simplewebauthn.types import PublicKeyCredentialDescriptor
import secrets

class WebAuthnService:
    CHALLENGE_BYTES = 32

    async def register_begin(self, user_id: int, tenant_id: int) -> dict:
        options = generateRegistrationOptions(
            rp={"name": "CRM", "id": "crm.example.com"},
            user={"id": str(user_id).encode(), "name": "...", "displayName": "..."},
            challenge=secrets.token_bytes(self.CHALLENGE_BYTES),
            pubKeyCredParams=[{"alg": -7, "type": "public-key"}, {"alg": -257, "type": "public-key"}],
            authenticatorSelection={"resident_key": "discouraged", "userVerification": "preferred"},
        )
        # 将 challenge 存入 DB（或 Redis）供后续验证
        return {"challenge": options.challenge, "options": options}

    async def register_complete(self, user_id: int, credential_data: dict, tenant_id: int) -> UserCredential:
        # 验证 attestation，提取 public key，存入 user_credentials 表
        ...

    async def verify_assertion(self, credential_data: dict, tenant_id: int) -> bool:
        # 验证 assertion，update counter 防 replay
        ...
```

**完成判定**：`ruff check src/services/webauthn_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_webauthn_service.py -v` → passed

### Step 5: 实现 DeviceTrustService — 设备信任评估

在 `src/services/device_trust_service.py` 实现：

```python
from enum import Enum

class TrustLevel(Enum):
    TRUSTED = "trusted"          # 受信任设备，无需 re-auth
    NEEDS_REAUTH = "needs_reauth"  # 需要 WebAuthn re-auth
    BLOCKED = "blocked"          # 被撤销的设备

class DeviceTrustService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate(
        self,
        device_fingerprint: str,
        tenant_id: int,
        user_id: int,
        current_ip: str | None = None,
    ) -> TrustLevel:
        # 查 device_trusts 表
        # 检测 IP 变更、地理变更
        # 返回 TrustLevel
        ...
```

**完成判定**：`ruff check src/services/device_trust_service.py` → 0 errors

### Step 6: 修改 Auth Router — 新增端点，适配 HttpOnly Cookie

在 `src/api/routers/auth.py` 修改 `/auth/login` 并新增端点：

```python
@router.post("/auth/login")
async def login(request: LoginRequest, response: Response, session: AsyncSession = Depends(get_db), ...):
    # 验证密码成功后
    # 生成 refresh_token，存入 DB（bcrypt hash），设置 HttpOnly Cookie
    refresh_token = generate_refresh_token()
    # store hash in refresh_tokens table
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=30 * 24 * 3600,
    )
    return {"success": True, "data": {"access_token": access_token}}

@router.post("/auth/refresh")
async def refresh(request: Request, session: AsyncSession = Depends(get_db)):
    svc = AuthService(session)
    new_access_token = await svc.refresh_access_token(request, tenant_id=...)
    return {"success": True, "data": {"access_token": new_access_token}}

@router.post("/auth/webauthn/register/begin")
async def webauthn_register_begin(ctx: AuthContext = Depends(require_auth), session: AsyncSession = Depends(get_db)):
    svc = WebAuthnService(session)
    options = await svc.register_begin(ctx.user_id, ctx.tenant_id)
    return {"success": True, "data": options}
```

**完成判定**：`ruff check src/api/routers/auth.py` → 0 errors

### Step 7: 新增 Re-auth 中间件与敏感操作守卫

在 `src/dependencies/auth.py` 新增：

```python
async def require_webauthn_verified(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not ctx.webauthn_verified:
        device_service = DeviceTrustService(session)
        trust_level = await device_service.evaluate(
            ctx.device_fingerprint, ctx.tenant_id, ctx.user_id, ctx.current_ip
        )
        if trust_level == TrustLevel.NEEDS_REAUTH:
            raise ForbiddenException("WebAuthn re-authentication required")
    return ctx
```

在敏感操作路由（如 `PATCH /users/{id}/password`）上使用 `Depends(require_webauthn_verified)`。

**完成判定**：`ruff check src/dependencies/auth.py` → 0 errors

### Step 8: 编写单元测试与集成测试

在 `tests/unit/test_auth_service.py` 新增：

```python
async def test_refresh_access_token_from_cookie(mock_db_session, sample_tenant):
    svc = AuthService(mock_db_session)
    # mock request with refresh_token cookie
    token = await svc.refresh_access_token(mock_request, tenant_id=sample_tenant)
    assert len(token) > 20

async def test_refresh_token_revoked_raises(mock_db_session, revoked_token, sample_tenant):
    svc = AuthService(mock_db_session)
    with pytest.raises(UnauthorizedException):
        await svc.refresh_access_token(mock_request_revoked, tenant_id=sample_tenant)
```

在 `tests/integration/test_webauthn_integration.py` 实现完整 WebAuthn 流程测试。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_auth_service.py tests/unit/test_webauthn_service.py -v` → 全 passed；`PYTHONPATH=src pytest tests/integration/test_webauthn_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/auth_service.py src/services/webauthn_service.py src/services/device_trust_service.py src/api/routers/auth.py src/dependencies/auth.py src/db/models/user_credential.py src/db/models/device_trust.py src/db/models/refresh_token.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_auth_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_webauthn_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_device_trust_service.py -v` → 全 passed（如有）
- [ ] `PYTHONPATH=src pytest tests/integration/test_webauthn_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：登录后 `POST /auth/refresh` 返回新的 access token（无 localStorage 依赖）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| WebAuthn 库（simplewebauthn）与现有密码学依赖冲突 | 低 | 中 | 降级到 password-only 登录；WebAuthn 注册/验证跳过；不影响现有 JWT 流程 |
| Refresh token HttpOnly Cookie 在测试环境跨域问题 | 中 | 中 | 测试使用 `pytest-httpbin` fixture 模拟 Cookie；CI 环境配置 `SameSite=Lax` |
| 新设备首次登录 WebAuthn 注册流程失败导致所有新设备无法登录 | 中 | 高 | 保留密码登录作为 fallback；WebAuthn 注册失败不阻止登录，仅记录警告 |
| Alembic migration 覆盖已有 `refresh_tokens` 表结构 | 低 | 高 | migration 前先检查 `alembic history`；如有冲突，写数据迁移脚本而非覆盖 |
| 前端 Access Token 内存存储方案与现有框架（React）集成复杂 | 中 | 中 | 前端内存存储作为内部实现细节，后端 API 不感知；降级：短期沿用 localStorage Token（注明风险） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/auth_service.py src/services/webauthn_service.py src/services/device_trust_service.py \
       src/db/models/user_credential.py src/db/models/device_trust.py src/db/models/refresh_token.py \
       src/api/routers/auth.py src/dependencies/auth.py src/main.py \
       alembic/versions/<id>_add_webauthn_device_trust_tables.py \
       tests/unit/test_auth_service.py tests/unit/test_webauthn_service.py \
       tests/integration/test_webauthn_integration.py
git commit -m "feat(auth): layered token storage + WebAuthn MFA (closes #163)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(auth): login security enhancement — HttpOnly refresh token + WebAuthn MFA" --body "## Summary
- Refresh Token 迁移至 HttpOnly Cookie（不再存 localStorage）
- Access Token 改为内存存储（前端 React Context）
- 新增 WebAuthn 注册/验证流程（FIDO2 支持）
- 新增设备信任评估与可疑活动检测
- 新增 3 张 DB 表：user_credentials / device_trusts / refresh_tokens

## Test plan
- [ ] `pytest tests/unit/test_auth_service.py tests/unit/test_webauthn_service.py` passed
- [ ] `pytest tests/integration/test_webauthn_integration.py` passed
- [ ] `alembic upgrade head && alembic downgrade -1` clean

Closes #163🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/customer_service.py` — 现有 Service 模式参考（`__init__` 接收 `AsyncSession`，返回 ORM 对象，抛 AppException）
- 第三方文档：[WebAuthn spec](https://www.w3.org/TR/webauthn-2/)
- 第三方文档：[OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- 第三方文档：[simplewebauthn Python library](https://simplewebauthn.readthedocs.io/)
- 父 issue / 关联：无

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
