# 通知模块 · 添加通知 API 路由

| 元数据 | 值 |
|---|---|
| Issue | #648 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#647 通知服务层](../10-sales/0647-notification-service.md) |
| 启用后赋能 | [#39 通知中心](../README.md#39) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

#647 已实现通知业务逻辑层（`NotificationService`），但缺少 API 路由暴露给前端。现有系统没有统一的 HTTP 接口供前端/客户端查询通知、标记已读或管理偏好设置，导致通知能力无法被消费。

### 1.2 做完后

- **用户视角**：
  - 前端可调用 `POST /api/v1/notifications/send` 触发通知发送
  - 可通过 `GET /api/v1/notifications?user_id=X&status=unread` 拉取当前租户的通知列表
  - 可调用 `PUT /api/v1/notifications/{id}/read` 将单条通知标记为已读
  - 可调用 `POST /api/v1/notifications/mark-all-read` 批量标记已读
  - 可查询和更新个人通知偏好（`GET/PUT /api/v1/notifications/preferences`）
- **开发者视角**：
  - 新增 [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py)，提供 7 个 RESTful 端点
  - 所有端点统一返回 `{"success": true, "data": {...}}` 封装，兼容前端 Axios 拦截器

### 1.3 不做什么（剔除）

- [ ] 不实现通知的数据库存储逻辑（由 #647 NotificationService 负责）
- [ ] 不实现通知渠道的实际投递（邮件/短信/WebSocket push）— 框架层预留 `channel` 字段
- [ ] 不实现通知的删除接口（DELETE）
- [ ] 不实现定时通知（scheduled notifications）或队列逻辑

### 1.4 关键 KPI

- [`ruff check src/api/routers/notifications.py`](../../src/api/routers/notifications.py) → 0 errors
- [`PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v`](../../tests/unit/test_notifications_router.py) → ≥ 7 passed（每端点 1 个测试 + 额外边界测试）
- [`PYTHONPATH=src pytest tests/integration/test_notifications_integration.py -v`](../../tests/integration/test_notifications_integration.py) → ≥ 5 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0（如有 migration 文件）
- 端到端：`curl -s http://localhost:8000/api/v1/notifications` 返回 `{"success": true, "data": {...}}`

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/api/routers/customers.py`](../../src/api/routers/customers.py) L{1-30} — 参考现有路由的通用模式（依赖注入、返回封装、错误处理）

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("/")
async def list_customers(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CustomerService(session)
    items, total = await svc.list_customers(tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}
```

[`src/services/notification_service.py`](../../src/services/notification_service.py) — #647 产物，需通过路由暴露其能力（具体行号待 #647 完成后确认，暂以 TBD 标记）

TBD — 待验证：#647 完成后 `NotificationService` 的确切方法签名和所在行号，预期包含 `send_notification`、`list_notifications`、`get_notification`、`mark_read`、`mark_all_read`、`get_preferences`、`update_preferences`。

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../src/main.py) — 注册 `notifications` 路由到 `/api/v1` 前缀
- 要建：
  - `src/api/routers/notifications.py` — 7 个 RESTful 端点
  - `src/models/response.py` — 如 `ApiResponse` 未从现有模块导出，需新增通用响应模型（待确认是否有现成实现）
  - `tests/unit/test_notifications_router.py` — 路由层单元测试（mock session + service）
  - `tests/integration/test_notifications_integration.py` — 集成测试（real DB，fixture: db_schema / async_session）
  - `docs/dev-plan/40-campaigns/0648-add-notification-api-router.md` — 本文档

### 2.3 缺什么

- [ ] `src/api/routers/notifications.py` — 路由文件，#647 未涵盖 HTTP 层
- [ ] `src/main.py` 中未注册 notifications 路由 — 端点对前端不可达
- [ ] 无通知偏好设置的 GET/PUT 端点 — 用户无法管理偏好
- [ ] 无批量已读接口 `POST /notifications/mark-all-read`
- [ ] 现有 `require_auth` / `get_db` 依赖注入模式在通知模块尚未应用

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/notifications.py` | 通知模块路由：7 个 HTTP 端点，统一返回 `ApiResponse` 封装 |
| `tests/unit/test_notifications_router.py` | 单元测试：mock NotificationService + mock session，验证每端点响应格式 |
| `tests/integration/test_notifications_integration.py` | 集成测试：真实 DB 操作，覆盖租户隔离、边界条件 |
| `src/models/response.py` | 通用响应模型（如 `ApiResponse[T]` 未在现有代码中定义，新建此文件） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | import `notifications_router`，注册到 `app.include_router(..., prefix="/api/v1")` |

### 3.3 新增能力

- **API endpoint**：`POST /api/v1/notifications/send` → 创建并发送通知，返回 `{"success": true, "data": {...}}`
- **API endpoint**：`GET /api/v1/notifications` → 支持 `user_id`、`status`、`channel` 过滤，租户范围，返回分页数据
- **API endpoint**：`GET /api/v1/notifications/{id}` → 获取单条通知详情
- **API endpoint**：`PUT /api/v1/notifications/{id}/read` → 标记单条通知为已读
- **API endpoint**：`POST /api/v1/notifications/mark-all-read` → 批量标记当前用户所有通知为已读
- **API endpoint**：`GET /api/v1/notifications/preferences` → 获取当前用户通知偏好
- **API endpoint**：`PUT /api/v1/notifications/preferences` → 更新当前用户通知偏好
- **Router**：`notifications` 已注册至 `main.py` 的 `/api/v1` 前缀下

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **返回 `ApiResponse` 封装而非裸字典**：前端 Axios 拦截器统一期望 `{success, data, message}` 结构，各端点保持一致便于前端处理。
- **session 通过 `Depends(get_db)` 注入而非 `async with get_db()`**：遵循 CLAUDE.md §Router Pattern，避免 session 生命周期管理错误。
- **auth 通过 `require_auth` → `AuthContext` 获取 `tenant_id` 和 `user_id`**：多租户隔离，每个 SQL 必须 `WHERE tenant_id = :tenant_id`；列表端点同时过滤 `user_id`。
- **preferneces 用 PUT 全量替换而非 PATCH**：简化实现，前端传完整偏好对象，避免部分更新语义歧义。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`；列表/偏好端点额外 `WHERE user_id = :user_id`
- Service 层返回 ORM/dataclass 对象，router 负责 `.to_dict()` 序列化；Service 层不调用 `.to_dict()`
- Service 错误抛 `AppException` 子类，router 不需要 try/catch，全局异常处理器转换
- 现有 `ApiResponse` 封装：统一 `{"success": True, "data": ..., "message": ...}` 结构
- 所有端点路径前缀 `/api/v1/notifications/...`

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不可用 `metadata`** → 与 `Base.metadata` 冲突。通知模型若需元数字段，用 `event_metadata` / `prefs_payload` 等名称。
2. **`ApiResponse` 需确认是否已存在** → 检查 `src/models/response.py` 是否已有 `ApiResponse[T]` 定义；若无，参照 `src/models/response.py` 现有结构新建，避免重复定义冲突。
3. **`mark-all-read` 的 SQL 需同时过滤 `tenant_id` 和 `user_id`** → 避免跨租户数据污染；边界：用户无未读通知时返回空列表而非报错。
4. **测试 mock 的 service 方法名需与 #647 实际方法签名一致** → 建议在 #647 合并后再编写单元测试，或先写基于接口约定的 mock。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/notifications.py` 骨架

在 `src/api/routers/` 下新建 `notifications.py`，实现全部 7 个端点的路由骨架（方法体暂不调用 service，仅 return mock data 验证路由可达）。

7 个端点：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from models.response import ApiResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/send")
async def send_notification(
    body: NotificationSendRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    # TODO: 调用 NotificationService
    return {"success": True, "data": {}}

@router.get("/")
async def list_notifications(
    user_id: int | None = None,
    status: str | None = None,
    channel: str | None = None,
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    # TODO: 调用 NotificationService
    return {"success": True, "data": {"items": [], "total": 0}}

@router.get("/preferences")
async def get_preferences(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    # TODO: 调用 NotificationService
    return {"success": True, "data": {}}

@router.put("/preferences")
async def update_preferences(
    body: PreferencesUpdateRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    # TODO: 调用 NotificationService
    return {"success": True, "data": {}}
```

其余 3 个端点（`GET /{id}`、`PUT /{id}/read`、`POST /mark-all-read`）同理。

**完成判定**：`ruff check src/api/routers/notifications.py` → 0 errors

### Step 2: 在 `src/main.py` 注册路由

在 `src/main.py` 中添加 import 并注册 router：

```python
from api.routers.notifications import router as notifications_router

app.include_router(notifications_router, prefix="/api/v1")
```

确保注册语句在 `get_db` dependency 之后、app startup 事件之外。

**完成判定**：`ruff check src/main.py` → 0 errors；启动 `PYTHONPATH=src uvicorn src.main:app --reload` 不报 ImportError

### Step 3: 实现全部端点逻辑（调用 NotificationService）

填充 Step 1 中各端点的 method body，以 `POST /notifications/send` 为例：

```python
@router.post("/send")
async def send_notification(
    body: NotificationSendRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    svc = NotificationService(session)
    notification = await svc.send_notification(
        tenant_id=ctx.tenant_id,
        user_id=body.user_id,
        title=body.title,
        message=body.message,
        channel=body.channel,
    )
    return {"success": True, "data": notification.to_dict()}
```

`GET /notifications` 过滤参数透传给 `svc.list_notifications(...)`：

```python
filters = {"user_id": user_id, "status": status, "channel": channel}
items, total = await svc.list_notifications(
    tenant_id=ctx.tenant_id, page=page, page_size=page_size, **filters
)
return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total, "page": page, "page_size": page_size}}
```

`PUT /notifications/{id}/read`：

```python
@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    svc = NotificationService(session)
    notification = await svc.mark_read(notification_id, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    return {"success": True, "data": notification.to_dict()}
```

`POST /notifications/mark-all-read`：

```python
@router.post("/mark-all-read")
async def mark_all_read(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    svc = NotificationService(session)
    count = await svc.mark_all_read(tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    return {"success": True, "data": {"marked_count": count}}
```

`GET/PUT /preferences` 透传给 `svc.get_preferences` / `svc.update_preferences`。

**完成判定**：`ruff check src/api/routers/notifications.py` → 0 errors；`PYTHONPATH=src mypy src/api/routers/notifications.py` → 0 errors（如配置了 mypy）

### Step 4: 编写单元测试 `tests/unit/test_notifications_router.py`

Mock `NotificationService` 各方法，按端点逐一验证响应格式。

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Mock NotificationService methods
@pytest.fixture
def mock_notification_service():
    svc = MagicMock()
    svc.send_notification = AsyncMock(return_value=MockNotification(id=1))
    svc.list_notifications = AsyncMock(return_value=([MockNotification(id=2)], 1))
    svc.get_notification = AsyncMock(return_value=MockNotification(id=5))
    svc.mark_read = AsyncMock(return_value=MockNotification(id=5, status="read"))
    svc.mark_all_read = AsyncMock(return_value=3)
    svc.get_preferences = AsyncMock(return_value=MockPreferences(id=1))
    svc.update_preferences = AsyncMock(return_value=MockPreferences(id=1, email_enabled=True))
    return svc

# Happy path: POST /notifications/send
async def test_send_notification_returns_201(mock_notification_service, ...):
    response = await ac.post("/api/v1/notifications/send", json={...})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "id" in data["data"]

# Boundary: GET /notifications with no results
async def test_list_notifications_empty(mock_notification_service, ...):
    ...

# Error: GET /notifications/{id} not found
async def test_get_notification_not_found(mock_notification_service, ...):
    ...
```

至少 3 个测试用例：happy path（发送通知）、boundary（空列表）、error（404）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → ≥ 3 passed

### Step 5: 编写集成测试 `tests/integration/test_notifications_integration.py`

使用真实 DB fixture（`db_schema`、`tenant_id`、`async_session`），覆盖：

- `POST /api/v1/notifications/send` → 写入 DB，验证返回 `success: true`
- `GET /api/v1/notifications` → 验证租户隔离（跨 tenant 查不到）
- `PUT /api/v1/notifications/{id}/read` → 验证 status 变更
- `POST /api/v1/notifications/mark-all-read` → 验证批量更新计数
- `GET /api/v1/notifications/preferences` → 验证默认值返回

```python
@pytest.mark.integration
class TestNotificationsIntegration:
    async def test_send_and_list(self, db_schema, tenant_id, async_session):
        client = TestClient(app)
        resp = client.post("/api/v1/notifications/send", json={...}, headers=auth_header(tenant_id))
        assert resp.json()["success"] is True

    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        other_tenant_id = 99999
        # 发一条通知给 other_tenant
        # 用当前 tenant 查，不应出现 other_tenant 的通知
        ...
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_notifications_integration.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/notifications.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → ≥ 7 passed（7 个端点各 1 个测试 + 边界/错误测试）
- [ ] `DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_notifications_integration.py -v` → ≥ 5 passed
- [ ] `curl -s http://localhost:8000/api/v1/notifications/preferences -H "Authorization: Bearer <token>"` → `{"success": true, "data": {...}}`
- [ ] `curl -s http://localhost:8000/api/v1/notifications -H "Authorization: Bearer <token>"` → `{"success": true, "data": {"items": [], "total": 0, ...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #647 NotificationService 方法签名与本路由预期不一致 | 低 | 中 | 路由层保持接口兼容；如签名不同步，在本路由中做字段映射，不阻塞 main.py 注册 |
| `ApiResponse` 模型位置不明，需新建导致 import 路径变更 | 低 | 低 | 在 `src/models/response.py` 新建，main.py 中确认 import 路径正确即可 |
| 集成测试因 DB schema 未就绪（NotificationService 未完成 migration）而失败 | 中 | 中 | 先跑单元测试验证路由逻辑；集成测试标记为 `@pytest.mark.integration`，CI 中单独跑 |
| 租户隔离测试覆盖不足，前端发现跨租户数据泄漏 | 低 | 高 | 回退：临时关闭通知路由注册；修复：确保所有 SQL 查询包含 `WHERE tenant_id = :tenant_id` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/notifications.py src/main.py tests/unit/test_notifications_router.py tests/integration/test_notifications_integration.py src/models/response.py
git commit -m "feat(notifications): add API router with 7 endpoints (#648)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#648): add notification API router" --body "Closes #648

## Summary
- POST /api/v1/notifications/send
- GET /api/v1/notifications (filter by user_id/status/channel, tenant-scoped)
- GET /api/v1/notifications/{id}
- PUT /api/v1/notifications/{id}/read
- POST /api/v1/notifications/mark-all-read
- GET /api/v1/notifications/preferences
- PUT /api/v1/notifications/preferences

## Test plan
- [ ] ruff check src/api/routers/notifications.py → 0 errors
- [ ] pytest tests/unit/test_notifications_router.py -v → ≥ 7 passed
- [ ] pytest tests/integration/test_notifications_integration.py -v → ≥ 5 passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../src/api/routers/customers.py) — 路由模式、依赖注入、返回封装参考
- 同类参考实现：[`src/api/routers/opportunities.py`](../../src/api/routers/opportunities.py) — 分页 + 过滤列表端点参考
- 第三方文档：[FastAPI - Router](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- 第三方文档：[FastAPI - Depends](https://fastapi.tiangolo.com/tutorial/dependencies/)
- 父 issue：#39
- 依赖：#647（NotificationService）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
