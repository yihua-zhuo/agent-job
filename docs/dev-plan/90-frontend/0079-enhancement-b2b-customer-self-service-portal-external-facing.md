# B2B 客户自助门户 · 外部客户自助 Portal

| 元数据 | 值 |
|---|---|
| Issue | #79 |
| 分类 | [40-frontend](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 8-10 工作日 |
| 依赖 | 无 |
| 启用后赋能 | CRM 内部面板（减少客服/销售手动操作工单） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

目前 CRM 只有一个内部管理界面，B 端客户（采购/决策人）无法自助完成查报价、提工单、看合同等操作。所有请求都压到销售和客服团队，导致：
- 重复性工单消耗大量人力（客服每天处理大量"查一下报价进度"类工单）
- 合同签署靠销售手动发 PDF，客户无法自行下载
- 客户联系信息更新要走内部流程，无法自助

从技术现状看，多租户架构（`tenant_id` 隔离）和 `customers` 表的 `portal_user_id` 关联能力已存在，只需建设 Portal UI 层和权限控制。

### 1.2 做完后

- **用户视角**：B 端客户用自己的账号登录 `portal.example.com`，看到专属 UI（非内部 CRM 复杂界面）：仪表板展示工单数/报价数/合同状态；可以提交工单、查看报价进度、下载合同 PDF、修改账户设置。整个流程无需联系客服。
- **开发者视角**：新增 `src/portal/` 路由模块（与 `src/api/routers/` 解耦），`PortalAuth` 中间件验证 `user_type=portal_customer`，Service 层通过现有 CRM services（如 `TicketService`、`QuoteService`）获取数据但过滤 `tenant_id` 隔离。

### 1.3 不做什么（剔除）

- [ ] 不修改内部 CRM UI（`/admin/*` 路径保持原样）
- [ ] 不新建后端 API endpoint — 复用现有 CRM API，加 `scope: portal` 权限控制
- [ ] 不实现 DocuSign 集成 — e-signature flow UI 预留接入点，后端 PDF 下载先做
- [ ] 不做 SSO/SAML 接入 — 密码登录 + JWT 先做，后续迭代

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_portal_*.py tests/unit/test_portal.py -v` → ≥ 15 passed
- `PYTHONPATH=src pytest tests/integration/test_portal_integration.py -v` → 全 passed
- `ruff check src/portal/ src/api/routers/portal.py` → 0 errors
- 新增 portal 页面 5xx 错误率 < 0.1%（可用 Playwright E2E 测试）
- 首次内容绘制（FCP）< 1.5s（Portal 页面）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/` 下是否有现有的 `tickets.py`、`quotes.py`、`contracts.py` router，以及它们返回的数据格式（确认后可填入具体路径和行号）

现有 CRM 内部 API 端点（待查证路径）：
- `GET /api/v1/tickets` — 工单列表（有 tenant_id 过滤）
- `POST /api/v1/tickets` — 创建工单
- `GET /api/v1/quotes` — 报价列表
- `GET /api/v1/contracts` — 合同列表
- `GET /api/v1/customers/{id}` — 客户详情（含 `portal_user_id`）

认证方式：JWT Bearer token（现有 `src/middleware/fastapi_auth.py`），需扩展 `user_type` 字段支持 `portal_customer`。

### 2.2 涉及文件清单

- 要改：
  - `src/middleware/fastapi_auth.py` — 增加 `PortalAuth` 中间件，验证 portal_user token
  - `src/services/customer_service.py` — 增加 `get_portal_customer` 方法（按 `portal_user_id` 查询）
  - `tests/unit/conftest.py` — 新增 `make_portal_user_handler` 辅助
- 要建：
  - `src/portal/` — Portal 前端页面（React 组件）
  - `src/api/routers/portal.py` — Portal 专用路由（登录、session 管理）
  - `src/db/models/portal_session.py` — Portal 会话表（存储 portal JWT refresh token）
  - `alembic/versions/<id>_add_portal_session.py` — PortalSession 表 migration
  - `tests/unit/test_portal.py` — Portal router 单元测试
  - `tests/unit/test_portal_service.py` — Portal service 单元测试
  - `tests/integration/test_portal_integration.py` — Portal E2E 集成测试

### 2.3 缺什么

- [ ] Portal 独立路由模块（`src/portal/` 及其 FastAPI router）
- [ ] Portal 专属认证流程（与内部 CRM 登录解耦，支持 `portal_customer` user_type）
- [ ] Portal 用户 session 存储（`PortalSession` 表 — refresh token 管理）
- [ ] 前端页面组：Dashboard / Tickets / Quotes / Contracts / Settings
- [ ] 权限隔离：Portal 用户只能访问自己 `tenant_id` 下的数据，不能跨越
- [ ] Portal 页面组件库（与内部 CRM 组件解耦的简洁 UI 风格）
- [ ] PDF 下载能力（报价单、合同 PDF 生成 — 复用现有 PDF 生成逻辑）
- [ ] 工单满意度调研（已解决工单后的评分表单）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/portal/` | Portal 前端页面目录（React 组件：Dashboard、Tickets、Quotes、Contracts、Settings） |
| `src/api/routers/portal.py` | Portal 专用路由（`/portal/login`、`/portal/logout`、`/portal/me`） |
| `src/db/models/portal_session.py` | PortalSession ORM model（存储 portal JWT refresh token 与 tenant_id 关联） |
| `src/services/portal_service.py` | Portal 业务逻辑（login、logout、session 刷新） |
| `alembic/versions/<id>_add_portal_session.py` | 创建 `portal_sessions` 表 migration |
| `tests/unit/test_portal.py` | Portal router 单元测试 |
| `tests/unit/test_portal_service.py` | Portal service 单元测试 |
| `tests/integration/test_portal_integration.py` | Portal E2E 集成测试（完整登录 → 操作 → 登出流程） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/middleware/fastapi_auth.py` | 新增 `PortalAuth` 依赖，`require_portal_auth` 验证 `user_type=portal_customer` |
| `src/services/customer_service.py` | 新增 `get_portal_customer(self, portal_user_id: str, tenant_id: int)` 方法 |
| `tests/unit/conftest.py` | 新增 `make_portal_user_handler`、`MockPortalSession` 等测试辅助 |

### 3.3 新增能力

- **Service method**：`PortalService.login(self, portal_user_id: str, password: str, tenant_id: int) -> tuple[PortalUserModel, str]`
- **Service method**：`PortalService.logout(self, session_id: str, tenant_id: int) -> None`
- **API endpoint**：`POST /portal/login` → `{"success": true, "data": {"token": "...", "user": {...}}}`
- **API endpoint**：`POST /portal/logout` → `{"success": true}`
- **API endpoint**：`GET /portal/me` → `{"success": true, "data": {"portal_user": {...}}}`
- **API endpoint**：`GET /portal/dashboard` → 工单数/报价数/合同状态聚合数据
- **API endpoint**：`GET /portal/tickets` → 客户视角工单列表（分页、状态过滤）
- **API endpoint**：`POST /portal/tickets` → 客户提交工单
- **API endpoint**：`GET /portal/quotes` → 客户视角报价列表
- **API endpoint**：`GET /portal/contracts` → 客户视角合同列表
- **API endpoint**：`PUT /portal/settings` → 更新联系信息、通知偏好
- **ORM model**：`PortalSession` in `src/db/models/portal_session.py`
- **Migration**：`alembic upgrade head` 创建 `portal_sessions` 表（含 `tenant_id` 索引）
- **前端路由**：`/portal/*`（Dashboard / Tickets / Quotes / Contracts / Settings）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Portal 独立域名部署（`portal.example.com`）不选子路径（`crm.example.com/portal`）**：明确隔离 COOKIE 域和安全策略，客户无法通过子路径穿越到内部 CRM；降低 XSS 风险（portal 和 admin 完全不同 origin）
- **选 JWT（access token + refresh token）不选 Session Cookie**：Portal SPA 需要 stateless auth；access token 放内存，refresh token 存 `PortalSession` 表（可主动 revocation）
- **选复用现有 CRM API 不造新后端**：避免重复建设，`tenant_id` 隔离已保证数据安全，只需在 API 层加 `scope: portal` 权限过滤（禁止访问内部字段如 `internal_notes`）
- **选 React SPA 不选 SSR**：Portal 流量相对低（已登录客户），SSR 收益小；React SPA 与现有 CRM 前端技术栈一致，团队无需学新框架

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `react-router-dom` | `^6.20` | 需支持 nested routes for `/portal/*` |
| `jose` | `^5.0` | JWT 签名/验证（Edge runtime 兼容） |
| `@tanstack/react-query` | `^5.0` | API 数据获取与缓存 |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询和 API 响应必须 `WHERE tenant_id = :tenant_id`（硬隔离，portal 无例外）
- Portal 用户 `user_type = portal_customer`，不属于内部 employee；`require_auth` 中间件不认可此类型，Portal 需用单独的 `require_portal_auth`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Portal API 响应格式与内部 CRM 一致：`{"success": true, "data": {...}}` — 方便前端统一处理
- Portal 用户只能访问自己公司的数据，不允许跨 `tenant_id` 读取引擎盖
- API 响应中过滤敏感字段：`internal_notes`、`cost_margin`、`employee_salary` 等内部字段不对 portal 暴露

### 4.4 已知坑

1. **Portal SPA 的 JWT access token 存内存，刷新页面白屏** → 规避：access token 存 `sessionStorage`（非 `localStorage`，关闭标签页即清除）；刷新页面时检测 token 有效性，过期则用 refresh token 自动续期
2. **Portal 用户登出后 JWT 仍有效（stateless）** → 规避：`PortalSession` 表记录 active session_id；每次请求验证 session 未被 revoke；登出时删除 session record 使 token 失效
3. **复用 CRM API 时内部字段泄露给 portal** → 规避：统一在 router 层做字段过滤（`exclude_fields=["internal_notes", ...]`），不在 service 层处理（service 不知道调用方身份）
4. **Alembic autogen 把 `portal_sessions.last_active_at` 写成 `DateTime` 而非 `TIMESTAMPTZ`** → 规避：migration 提交前手动检查，`last_active_at` 列必须加 `timezone=True`
5. **`PortalSession` Model 的列名避免用 `metadata`** → 规避：用 `session_metadata` 或 `attrs` 代替；`Base.metadata` 是 SQLAlchemy 元对象，列名冲突会导致运行时崩溃

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 PortalSession ORM 模型和数据库 Migration

新增 `PortalSession` model 用于存储 portal 用户的 refresh token 和 session 状态。

在 `src/db/models/portal_session.py` 创建：

```python
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portal_user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_portal_sessions_tenant_id", "tenant_id"),
        Index("ix_portal_sessions_tenant_active", "tenant_id", "is_active"),
    )
```

生成 migration：

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade head
alembic revision --autogenerate -m "add portal_sessions table"
# 手动检查生成的 migration：last_active_at 列必须是 TIMESTAMPTZ (DateTime(timezone=True))
# 如 autogen 写成了 DateTime，手动改为 DateTime(timezone=True)
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
alembic revision --autogenerate -m "drift_check"
# 如果新 migration 只有 `pass`，删除它
```

**完成判定**：`alembic upgrade head` exit 0；`alembic history --verbose` 显示新 migration；`ruff check src/db/models/portal_session.py` exit 0

---

### Step 2: 新增 PortalAuth 中间件和 PortalService

在 `src/middleware/fastapi_auth.py` 新增：

```python
class PortalUserContext(BaseModel):
    portal_user_id: int
    tenant_id: int
    user_type: Literal["portal_customer"]

async def require_portal_auth(
    authorization: str = Header(None),
) -> PortalUserContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid portal token")
    token = authorization.replace("Bearer ", "")
    payload = decode_jwt(token)  # 复用现有 JWT 解码
    if payload.get("user_type") != "portal_customer":
        raise ForbiddenException("Portal access required")
    return PortalUserContext(
        portal_user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        user_type="portal_customer",
    )
```

在 `src/services/portal_service.py` 新增：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta, timezone
import secrets

class PortalService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def login(self, portal_user_id: int, password: str, tenant_id: int) -> tuple[str, str]:
        # 验证 portal 用户 + 密码
        # 生成 session_id + refresh_token
        # 写入 PortalSession 表
        session_id = secrets.token_hex(32)
        refresh_token = secrets.token_urlsafe(64)
        # ... (insert into portal_sessions)
        access_token = create_jwt({
            "sub": portal_user_id,
            "tenant_id": tenant_id,
            "user_type": "portal_customer",
        })
        return access_token, refresh_token

    async def logout(self, session_id: str, tenant_id: int) -> None:
        await self.session.execute(
            update(PortalSession)
            .where(PortalSession.session_id == session_id, PortalSession.tenant_id == tenant_id)
            .values(is_active=False)
        )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_portal_service.py -v` → ≥ 5 passed；`ruff check src/services/portal_service.py src/middleware/fastapi_auth.py` exit 0

---

### Step 3: 创建 Portal Router 和 API 端点

在 `src/api/routers/portal.py` 新建：

```python
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from src.services.portal_service import PortalService
from src.middleware.fastapi_auth import require_portal_auth, PortalUserContext

router = APIRouter(prefix="/portal", tags=["Portal"])

@router.post("/login")
async def portal_login(
    portal_user_id: int,
    password: str,
    tenant_id: int,
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    access_token, refresh_token = await svc.login(portal_user_id, password, tenant_id)
    return {"success": True, "data": {"token": access_token, "refresh_token": refresh_token}}

@router.post("/logout")
async def portal_logout(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    await svc.logout(portal_ctx.session_id, tenant_id=portal_ctx.tenant_id)
    return {"success": True}

@router.get("/me")
async def portal_me(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CustomerService(session)
    customer = await svc.get_portal_customer(portal_ctx.portal_user_id, portal_ctx.tenant_id)
    return {"success": True, "data": customer.to_dict()}

@router.get("/dashboard")
async def portal_dashboard(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    # 聚合：open_tickets, pending_quotes, active_contracts
    ticket_count = await TicketService(session).count_by_tenant(portal_ctx.tenant_id, status="open")
    quote_count = await QuoteService(session).count_by_tenant(portal_ctx.tenant_id, status="pending")
    contract_count = await ContractService(session).count_by_tenant(portal_ctx.tenant_id, status="active")
    return {"success": True, "data": {"tickets": ticket_count, "quotes": quote_count, "contracts": contract_count}}
```

在 `src/main.py` 的 `include_router` 部分添加：

```python
from api.routers.portal import router as portal_router
app.include_router(portal_router)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_portal.py -v` → ≥ 8 passed；`ruff check src/api/routers/portal.py` exit 0

---

### Step 4: Portal 工单模块（列表 + 提交 + 详情）

在 `src/api/routers/portal_tickets.py` 新建（`portal.py` 子路由）：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from src.services.ticket_service import TicketService
from src.middleware.fastapi_auth import require_portal_auth, PortalUserContext

router = APIRouter(prefix="/portal/tickets", tags=["Portal Tickets"])

@router.get("/")
async def list_portal_tickets(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    status: str | None = None,
):
    svc = TicketService(session)
    # 复用现有 list 方法，但加 portal scope 过滤
    items, total = await svc.list_for_portal(tenant_id=portal_ctx.tenant_id, page=page, page_size=page_size, status=status)
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total, "page": page, "page_size": page_size}}

@router.post("/")
async def create_portal_ticket(
    ticket_in: TicketCreatePortal,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = TicketService(session)
    ticket = await svc.create_for_portal(ticket_in, tenant_id=portal_ctx.tenant_id, portal_user_id=portal_ctx.portal_user_id)
    return {"success": True, "data": ticket.to_dict()}

@router.get("/{ticket_id}")
async def get_portal_ticket(
    ticket_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = TicketService(session)
    ticket = await svc.get_for_portal(ticket_id, portal_ctx.tenant_id)
    return {"success": True, "data": ticket.to_dict()}

@router.post("/{ticket_id}/satisfaction")
async def submit_satisfaction(
    ticket_id: int,
    survey: SatisfactionSurvey,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = TicketService(session)
    await svc.submit_satisfaction(ticket_id, portal_ctx.tenant_id, survey)
    return {"success": True}
```

在 `src/services/ticket_service.py` 新增方法：

```python
async def list_for_portal(self, tenant_id: int, page: int, page_size: int, status: str | None) -> tuple[list[TicketModel], int]:
    # 与现有 list 方法相同，但额外过滤 internal 字段
    ...

async def create_for_portal(self, ticket_in: TicketCreatePortal, tenant_id: int, portal_user_id: int) -> TicketModel:
    # source="portal"，不允许设置 internal 字段
    ...

async def submit_satisfaction(self, ticket_id: int, tenant_id: int, survey: SatisfactionSurvey) -> None:
    # 更新 ticket.satisfaction_score
    ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ticket_service.py -v` → 新增 ≥ 3 passed（portal 相关）；`ruff check src/api/routers/portal_tickets.py src/services/ticket_service.py` exit 0

---

### Step 5: Portal 报价和合同模块（列表 + 详情 + PDF 下载）

在 `src/api/routers/portal_quotes.py` 新建：

```python
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from src.services.quote_service import QuoteService
from src.middleware.fastapi_auth import require_portal_auth, PortalUserContext

router = APIRouter(prefix="/portal/quotes", tags=["Portal Quotes"])

@router.get("/")
async def list_portal_quotes(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
):
    svc = QuoteService(session)
    items, total = await svc.list_for_portal(tenant_id=portal_ctx.tenant_id, page=page, page_size=page_size)
    return {"success": True, "data": {"items": [i.to_dict(exclude_internal=True) for i in items], "total": total}}

@router.get("/{quote_id}")
async def get_portal_quote(
    quote_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    quote = await svc.get_for_portal(quote_id, portal_ctx.tenant_id)
    return {"success": True, "data": quote.to_dict(exclude_internal=True)}

@router.post("/{quote_id}/accept")
async def accept_quote(
    quote_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    await svc.accept_for_portal(quote_id, portal_ctx.tenant_id)
    return {"success": True}

@router.post("/{quote_id}/decline")
async def decline_quote(
    quote_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    await svc.decline_for_portal(quote_id, portal_ctx.tenant_id)
    return {"success": True}

@router.get("/{quote_id}/pdf")
async def download_quote_pdf(
    quote_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = QuoteService(session)
    pdf_bytes = await svc.generate_pdf(quote_id, portal_ctx.tenant_id)
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=quote_{quote_id}.pdf"})
```

在 `src/api/routers/portal_contracts.py` 新建（结构与 portal_quotes.py 类似）：

```python
# GET /portal/contracts/ — 合同列表
# GET /portal/contracts/{id} — 合同详情
# POST /portal/contracts/{id}/sign — e-signature 预留（先返回 501 Not Implemented，后续接 DocuSign）
# GET /portal/contracts/{id}/pdf — PDF 下载
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_quote_service.py tests/unit/test_contract_service.py -v` → 新增 ≥ 4 passed；`ruff check src/api/routers/portal_quotes.py src/api/routers/portal_contracts.py` exit 0

---

### Step 6: Portal 账户设置模块

在 `src/api/routers/portal_settings.py` 新建：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from src.services.portal_service import PortalService
from src.middleware.fastapi_auth import require_portal_auth, PortalUserContext

router = APIRouter(prefix="/portal/settings", tags=["Portal Settings"])

@router.put("/contact")
async def update_contact(
    contact: PortalContactUpdate,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    await svc.update_contact(portal_ctx.portal_user_id, portal_ctx.tenant_id, contact)
    return {"success": True}

@router.put("/password")
async def change_password(
    pw: PortalPasswordChange,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    await svc.change_password(portal_ctx.portal_user_id, portal_ctx.tenant_id, pw)
    return {"success": True}

@router.put("/notifications")
async def update_notifications(
    prefs: NotificationPrefs,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    await svc.update_notification_prefs(portal_ctx.portal_user_id, portal_ctx.tenant_id, prefs)
    return {"success": True}

@router.get("/team")
async def list_team_members(
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    members = await svc.list_team_members(portal_ctx.tenant_id)
    return {"success": True, "data": [m.to_dict() for m in members]}

@router.post("/team")
async def add_team_member(
    member: AddTeamMember,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    new_member = await svc.add_team_member(portal_ctx.tenant_id, member)
    return {"success": True, "data": new_member.to_dict()}

@router.delete("/team/{user_id}")
async def remove_team_member(
    user_id: int,
    portal_ctx: PortalUserContext = Depends(require_portal_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = PortalService(session)
    await svc.remove_team_member(user_id, portal_ctx.tenant_id)
    return {"success": True}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_portal_settings.py -v` → ≥ 5 passed；`ruff check src/api/routers/portal_settings.py` exit 0

---

### Step 7: Portal 前端页面（React SPA）

在 `src/portal/` 目录下创建 React 组件：

```
src/portal/
├── App.tsx                    # Router 定义：/dashboard, /tickets, /quotes, /contracts, /settings
├── components/
│   ├── PortalLayout.tsx       # 通用 Layout（Header 含 Logo + 退出按钮，Sidebar 导航）
│   ├── PortalLoginPage.tsx   # 品牌化登录页（公司 Logo + 颜色主题 + 表单）
│   └── PortalRouteGuard.tsx  # 未登录重定向到 /portal/login
├── pages/
│   ├── DashboardPage.tsx     # 仪表板：工单数/报价数/合同状态卡片
│   ├── TicketsPage.tsx       # 工单列表 + 分页
│   ├── TicketDetailPage.tsx  # 工单详情 + 对话线程 + 满意度调研
│   ├── CreateTicketPage.tsx  # 提交工单表单（category + subject + description + attachment）
│   ├── QuotesPage.tsx        # 报价列表 + 状态 badge
│   ├── QuoteDetailPage.tsx   # 报价详情（行项目 + 金额 + 有效期）+ Accept/Decline 按钮 + PDF 下载
│   ├── ContractsPage.tsx     # 合同列表 + 状态 + 到期日
│   ├── ContractDetailPage.tsx# 合同详情 + e-signature 预留 + PDF 下载
│   └── SettingsPage.tsx      # 账户设置（联系信息 + 密码 + 通知偏好 + 团队成员）
└── api/
    └── portalApi.ts           # API 客户端（axios instance with portal JWT interceptor）
```

PortalLayout.tsx 示例：

```tsx
export function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="portal-layout">
      <header className="portal-header">
        <img src="/portal-logo.svg" alt="Company Logo" className="portal-logo" />
        <nav className="portal-nav">
          <Link to="/portal/dashboard">仪表板</Link>
          <Link to="/portal/tickets">我的工单</Link>
          <Link to="/portal/quotes">我的报价</Link>
          <Link to="/portal/contracts">我的合同</Link>
          <Link to="/portal/settings">账户设置</Link>
        </nav>
        <button onClick={handleLogout} className="btn-logout">退出</button>
      </header>
      <main className="portal-main">{children}</main>
    </div>
  );
}
```

DashboardPage.tsx 示例（调用 `/portal/dashboard` API）：

```tsx
export function DashboardPage() {
  const { data } = useQuery({
    queryKey: ['portal-dashboard'],
    queryFn: () => portalApi.get('/portal/dashboard').then(r => r.data.data),
  });
  return (
    <div className="dashboard-grid">
      <StatCard title="我的工单" value={data?.tickets ?? 0} icon="ticket" />
      <StatCard title="待处理报价" value={data?.quotes ?? 0} icon="quote" />
      <StatCard title="有效合同" value={data?.contracts ?? 0} icon="contract" />
    </div>
  );
}
```

**完成判定**：`ls src/portal/pages/` 列出所有 7 个页面文件；`ruff check src/portal/` exit 0（如有 JS/TS lint 配置）；Playwright E2E：`page.goto('/portal/dashboard')` → 无 404

---

### Step 8: 端到端测试覆盖

在 `tests/integration/test_portal_integration.py` 创建完整流程测试：

```python
@pytest.mark.integration
class TestPortalIntegration:
    async def test_login_and_dashboard(self, db_schema, tenant_id, async_session):
        # 1. 用 portal 用户登录
        login_resp = await api_client.post("/portal/login", json={
            "portal_user_id": 1, "password": "test123", "tenant_id": tenant_id
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["data"]["token"]

        # 2. 访问 dashboard
        dash = await api_client.get("/portal/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert dash.status_code == 200
        assert "tickets" in dash.json()["data"]

        # 3. 提交工单
        ticket = await api_client.post("/portal/tickets", headers={"Authorization": f"Bearer {token}"}, json={
            "category": "technical", "subject": "API error", "description": "..."
        })
        assert ticket.status_code == 200

        # 4. 登出
        logout = await api_client.post("/portal/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 200

        # 5. token 已 revoke，后续请求应 401
        bad = await api_client.get("/portal/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert bad.status_code == 401
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_portal_integration.py -v` → 全 passed（预计 ≥ 8 passed）

---

## 6. 验收

- [ ] `ruff check src/api/routers/portal.py src/api/routers/portal_tickets.py src/api/routers/portal_quotes.py src/api/routers/portal_contracts.py src/api/routers/portal_settings.py src/services/portal_service.py src/middleware/fastapi_auth.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_portal.py tests/unit/test_portal_service.py -v` → ≥ 13 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_portal_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如有 migration 变更）
- [ ] 端到端：注册一个 portal 用户，登录 → Dashboard → 提交工单 → 查看报价 → 下载 PDF → 登出，完整链路无 401/403
- [ ] Portal 页面 `GET /portal/dashboard` 响应时间 < 500ms（在 demo 数据下）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Portal 用户通过 API 路径穿越到内部 CRM 数据 | 低 | 高 | 部署前做 security review：在所有 portal 路由的 service 方法中加 `user_type` 检查；自动化测试覆盖跨 tenant 隔离（`tenant_id=1` 的 portal 用户访问 `tenant_id=2` 的数据应返回 404） |
| Portal JWT refresh token 被窃取（XSS 读取 sessionStorage） | 中 | 中 | refresh token 设置短过期时间（7 天）；添加 IP 绑定（`PortalSession.ip_address`）；异常登录检测告警 |
| Portal 页面性能拖累（CRM API 慢影响 Portal） | 中 | 低 | Portal 前端加 skeleton loading；关键数据做 client-side 缓存（TanStack Query `staleTime: 60_000`） |
| DocuSign e-signature 集成无法按时完成 | 高 | 中 | Portal 合同页面保留"联系销售签署"fallback 按钮（mailto）；e-signature 作为后续迭代，不在本阶段 scope 内 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/portal/ src/api/routers/portal*.py src/services/portal_service.py src/middleware/fastapi_auth.py src/db/models/portal_session.py alembic/versions/ tests/
git commit -m "feat(portal): add B2B customer self-service portal (#79)

- PortalSession model + migration for portal JWT session management
- PortalAuth middleware (require_portal_auth)
- PortalService login/logout with tenant isolation
- Portal API routes: /portal/login, /portal/logout, /portal/me, /portal/dashboard
- /portal/tickets CRUD + satisfaction survey
- /portal/quotes list + accept/decline + PDF download
- /portal/contracts list + PDF download
- /portal/settings: contact, password, notifications, team management
- React SPA: Dashboard, Tickets, Quotes, Contracts, Settings pages
- Unit + integration test coverage
Closes #79"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(portal): B2B Customer Self-Service Portal (#79)" --body "## Summary
- External-facing customer portal (portal.example.com) with React SPA + FastAPI
- Customer self-service: tickets, quotes, contracts, account settings
- Multi-tenant isolation via tenant_id + portal_customer user_type
- PortalSession model for JWT refresh token management

## Test plan
- [x] Unit tests: portal router, service, middleware (≥ 13 passed)
- [x] Integration tests: full E2E flow login → dashboard → ticket → logout (≥ 8 passed)
- [x] Security review: cross-tenant isolation verified
- [x] ruff check 0 errors

Closes #79"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/api/routers/tickets.py`（现有工单 router 结构和权限模式）
- 第三方文档：[FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/), [React Router v6](https://reactrouter.com/en/main), [TanStack Query](https://tanstack.com/query/latest)
- 父 issue / 关联：CRM 内部面板（多租户架构已有 `#78` 或类似 issue）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
