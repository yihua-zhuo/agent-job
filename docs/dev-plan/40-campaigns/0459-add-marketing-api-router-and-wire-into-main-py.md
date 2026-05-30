# Marketing API Router & Wire-in · Add marketing router with campaign + event endpoints

| 元数据 | 值 |
|---|---|
| Issue | #459 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | #450（营销服务基础 — MarketingService 实现） |
| 启用后赋能 | #460（MarketingService integration tests — 依赖活 router） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`MarketingService` 已实现（`services/marketing_service.py`），但 FastAPI 层缺失 — 前端和调用方无 HTTP 入口。CRM 营销模块必须通过 REST API 对外暴露，否则活动管理功能无法使用。

### 1.2 做完后

- **用户视角**：管理员可在前端创建、查看、更新营销活动（campaign）及营销事件（event）；所有请求携带 JWT，认证守卫生效。
- **开发者视角**：`src/api/routers/marketing.py` 导出 `marketing_router`（前缀 `/api/v1/marketing`，标签 `["marketing"]`），通过 `iter_routers()` 自动注册到 `app`；POST/GET/PATCH 端点返回标准 `{"success": true, "data": {...}}` 封套。

### 1.3 不做什么（剔除）

- [ ] 不实现 campaign 或 event 的删除端点（本 issue 仅要求 POST/GET/PATCH）
- [ ] 不修改 `MarketingService` 业务逻辑（本 issue 仅做 router 接入，不改动 service 层）
- [ ] 不新增 Alembic migration（本 issue 不涉及 schema 变更）
- [ ] 不在 router 层直接操作 ORM — 调用 service，由 service 返回 ORM 对象，router 负责 `.to_dict()` 序列化

### 1.4 关键 KPI

- `ruff check src/api/routers/marketing.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_marketing.py -v` → 全 passed（如测试文件已存在）
- `curl -X GET http://localhost:8000/api/v1/marketing/campaigns -H "Authorization: Bearer $TOKEN"` → `{"success": true, "data": ...}` + HTTP 401 未授权时正确拦截
- `curl -X POST http://localhost:8000/api/v1/marketing/campaigns -H "Authorization: Bearer $TOKEN" -d '{...}'` → HTTP 201 + `{"success": true, "data": {...}}`

---

## 2. 当前现状（起点）

### 2.1 现有实现

`src/api/routers/marketing.py` 骨架已存在（L1-L157），已包含 `list_campaigns`（GET）、`create_campaign`（POST）、`get_campaign`（GET by id）、`update_campaign_put`（PUT）、`update_campaign_patch`（PATCH）、`delete_campaign`（DELETE）六个端点，但缺失 event 相关端点。

[`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) L1-L16

```python
from api.routers.marketing import marketing_router
marketing_router = APIRouter(prefix="/api/v1/marketing", tags=["marketing"])
```

[`src/api/__init__.py`](../../../src/api/__init__.py) L19-L26：router auto-discovery 通过 `iter_routers()` 实现，新建 `.py` 文件放入 `api/routers/` 即可自动被发现，无需手动 import 或修改 `main.py`。

`src/main.py` L86-L88：

```python
for router in iter_routers():
    app.include_router(router)
```

所有 router 均通过循环自动注册，`main.py` 无需为单个 router 修改。

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) — 补全 event 端点（POST/GET/PATCH for events）；确认 router prefix 正确
  - [`src/main.py`](../../../src/main.py) — TBD - 待验证：确认 `iter_routers()` 是否已覆盖 `marketing_router`（若已覆盖则无需改动）
- 要建：
  - `tests/unit/test_marketing.py` — router 单元测试（mock MarketingService + auth）
  - `tests/integration/test_marketing_integration.py` — 端到端集成测试

### 2.3 缺什么

- [ ] event CRUD 端点：`POST /api/v1/marketing/events`、`GET /api/v1/marketing/events`、`GET /api/v1/marketing/events/{event_id}`、`PATCH /api/v1/marketing/events/{event_id}` 缺失
- [ ] `MarketingService` 需确认支持 event 列表/创建/更新方法（TBD - 待验证：`services/marketing_service.py` 是否已有 event 相关 service 方法）
- [ ] 无 router 层单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_marketing.py` | Router 单元测试（mock MarketingService + AuthContext，验证端点响应与封套） |
| `tests/integration/test_marketing_integration.py` | 端到端集成测试（real DB，写入 campaign/event，验证 response schema） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) | 新增 event 请求 Schema（`EventCreate`/`EventUpdate`）；新增 4 个 event 端点（POST /events、GET /events、GET /events/{id}、PATCH /events/{id}） |
| [`src/main.py`](../../../src/main.py) | TBD - 待验证：若 `iter_routers()` 已覆盖 `marketing_router` 则无需修改；若未覆盖则在 L88 前添加 `from api.routers.marketing import marketing_router` 并在 for 循环后追加 `app.include_router(marketing_router)` |

### 3.3 新增能力

- **API endpoint**：`POST /api/v1/marketing/events` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /api/v1/marketing/events` → `{"success": true, "data": {"items": [...], "total": N, ...}}`
- **API endpoint**：`GET /api/v1/marketing/events/{event_id}` → `{"success": true, "data": {...}}`
- **API endpoint**：`PATCH /api/v1/marketing/events/{event_id}` → `{"success": true, "data": {...}}`
- **Router auth guard**：所有端点均通过 `require_auth` 注入 `AuthContext`，未授权请求返回 401

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 `_paginated()` helper 而非手写封套**：campaign 端点已在 L19-L30 定义了 `_paginated()`，event 列表端点直接复用，保持封套格式一致。
- **PATCH vs PUT 双端点并存**：PATCH 做部分更新（`exclude_none=True`），PUT 做全量替换（`model_dump()`），与 campaign 端点风格对齐。
- **Auto-discovery 优于手动注册**：`api/__init__.py` 的 `iter_routers()` 自动扫描 `api/routers/` 下所有 `APIRouter` 实例；`marketing.py` 已导出 `marketing_router`，无需修改 `main.py` 循环。

### 4.2 版本约束

无新增外部依赖，所有约束沿用现有 `pyproject.toml` 配置。

### 4.3 兼容性约束

- 多租户：每个 service 调用必须传入 `tenant_id=ctx.tenant_id`（来自 `AuthContext`）
- Session 注入：`session: AsyncSession = Depends(get_db)`，禁止 `async with get_db()`
- Service 错误：router 不 try/catch，`AppException` 由 `main.py` 全局处理器统一转换 JSON 响应
- 序列化：router 调用 `item.to_dict()`，service 返回 ORM 对象，不在 service 层序列化

### 4.4 已知坑

1. **Alembic autogen 生成 JSON 而非 JSONB / TIMESTAMPTZ 而非 DateTime**：本 issue 不涉及 migration，暂不适用；但若后续 event 表 migration 由 autogen 生成，需手动将 `sa.JSON()` 改回 `sa.JSONB()`、`DateTime` 改回 `DateTime(timezone=True)`
2. **`MarketingService` event 方法存在性未确认**：需在开始前 grep `services/marketing_service.py` 确认 `list_events`、`create_event`、`update_event` 方法存在；若缺失则需先在 service 层补齐（本 issue 范围外，需另开 issue）

---

## 5. 实现步骤（按顺序）

### Step 1: 验证 MarketingService event 方法存在

在开始 router 修改前，grep 确认 service 层已支持 event CRUD。

操作：
- a) `grep -n "def list_events\|def create_event\|def update_event" src/services/marketing_service.py`
- b) 若方法缺失，在 `services/marketing_service.py` 中补全 `list_events`、`create_event`、`get_event`、`update_event` 方法（参照 campaign 方法模式，租户过滤 `tenant_id`）

**完成判定**：`grep -n "async def list_events\|async def create_event" src/services/marketing_service.py` 输出 ≥ 2 行

---

### Step 2: 确认 main.py router 注册方式

验证 `iter_routers()` 自动发现 `marketing_router` 是否已生效。

操作：
- a) 确认 `src/api/__init__.py` 中 `iter_routers()` 会 yield `marketing_router`（通过 `pkgutil.iter_modules` 扫描 `api.routers` 包）
- b) 若已生效：无需修改 `main.py`；若未生效：在 `src/main.py` L87 后追加 `app.include_router(marketing_router)` 或在文件顶部 import 后在 for 循环中注册

**完成判定**：`grep -n "marketing_router" src/main.py` 有输出（若不需要改则为 0 行）

---

### Step 3: 补全 event Schema 类

在 `src/api/routers/marketing.py` 中 campaign Schema 之后添加 event 请求模型。

操作：
- 在 `CampaignPaginationQuery` 类之后（L66 附近），插入：

```python
# ---------------------------------------------------------------------------
# Event request schemas
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="事件名称")
    campaign_id: int = Field(..., ge=1, description="关联活动 ID")
    event_type: str = Field(..., description="事件类型: opened, clicked, replied, bounced, unsubscribed")
    triggered_at: str | None = Field(None, description="触发时间 (ISO 8601)")
    recipient: str | None = Field(None, max_length=255, description="触发人")
    metadata: dict | None = Field(None, description="附加元数据")


class EventUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    event_type: str | None = Field(None)
    triggered_at: str | None = Field(None)
    recipient: str | None = Field(None, max_length=255)
    metadata: dict | None = Field(None)


class EventPaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    campaign_id: int | None = Field(None, description="按活动 ID 过滤")
```

**完成判定**：`grep -n "class EventCreate\|class EventUpdate" src/api/routers/marketing.py` 输出 ≥ 2 行

---

### Step 4: 实现 event CRUD 端点

在 `src/api/routers/marketing.py` 末尾（L158 之后）添加 4 个 event 端点。

操作：
- 在 `delete_campaign` 之后插入：

```python
# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------

@marketing_router.post("/events", status_code=201)
async def create_event(
    body: EventCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MarketingService(session)
    event = await svc.create_event(
        campaign_id=body.campaign_id,
        event_type=body.event_type,
        tenant_id=ctx.tenant_id,
        name=body.name,
        triggered_at=body.triggered_at,
        recipient=body.recipient,
        event_metadata=body.metadata,
    )
    return {"success": True, "data": event.to_dict()}


@marketing_router.get("/events")
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    campaign_id: int | None = None,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MarketingService(session)
    items, total = await svc.list_events(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        campaign_id=campaign_id,
    )
    return _paginated([item.to_dict() for item in items], total, page, page_size)


@marketing_router.get("/events/{event_id}")
async def get_event(
    event_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MarketingService(session)
    event = await svc.get_event(event_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": event.to_dict()}


@marketing_router.patch("/events/{event_id}")
async def update_event(
    event_id: int,
    body: EventUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = MarketingService(session)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    event = await svc.update_event(event_id, tenant_id=ctx.tenant_id, **kwargs)
    return {"success": True, "data": event.to_dict()}
```

**完成判定**：`grep -n "@marketing_router.post\|@marketing_router.get\|@marketing_router.patch" src/api/routers/marketing.py` 输出 ≥ 10 行（含 campaign 端点）

---

### Step 5: 写 router 单元测试

新建 `tests/unit/test_marketing.py`，mock `MarketingService` 方法，验证 auth guard 和 response envelope。

操作：
- 创建文件 `tests/unit/test_marketing.py`，内容覆盖：
  - `test_create_campaign_requires_auth` — 无 token → 401
  - `test_create_campaign_success` — mock `MarketingService.create_campaign` → HTTP 201 + `{"success": true, "data": {...}}`
  - `test_list_campaigns_paginated` — mock service 返回 → `{"success": true, "data": {"items": [...], "total": N, "page": 1, ...}}`
  - `test_create_event_requires_auth`
  - `test_create_event_success`
  - `test_list_events_paginated`
  - `test_get_event_not_found` — mock service 抛 `NotFoundException` → HTTP 404
  - `test_patch_event_success`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_marketing.py -v` → 全部 passed（或 `test file not yet created` 跳过此步）

---

### Step 6: 验证 auth guard 生效

手动 curl 测试认证拦截。

操作：
- a) `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/marketing/campaigns` → 预期 `401`
- b) `curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/marketing/campaigns -H "Content-Type: application/json" -d '{"name":"test"}'` → 预期 `401`
- c) 获取有效 token 后重试 → 预期 `200` 或 `201`

**完成判定**：步骤 a) 返回 `401` 且响应体包含 `"success": false`

---

## 6. 验收

- [ ] `ruff check src/api/routers/marketing.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors（如有改动）
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing.py -v` → 全 passed（如测试文件存在）
- [ ] `PYTHONPATH=src pytest tests/integration/test_marketing_integration.py -v` → 全 passed（如涉及 DB）
- [ ] 端到端：无 token → `curl http://localhost:8000/api/v1/marketing/campaigns` 返回 `{"success": false, "message": "..."}` + HTTP 401
- [ ] 端到端：有效 token → `curl -X POST http://localhost:8000/api/v1/marketing/campaigns -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"test campaign","type":"email","campaign_type":"email","content":"body","created_by":1}'` 返回 HTTP 201 + `{"success": true, "data": {"id": N, "name": "test campaign", ...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `MarketingService` 无 event 方法，需先补 service 层 | 中 | 高 | 先完成 service 层 event CRUD（可在本 issue 内或拆分 #N），router 端点依赖 service 方法存在 |
| `iter_routers()` 已覆盖 marketing_router 但 router 有 import 错误导致 app 启动失败 | 低 | 高 | 回退：删除 `src/api/routers/marketing.py` 中的 event 端点，仅保留 campaign 端点；先保证 app 启动，再用 `ruff check` 逐步修 |
| event 端点与现有 campaign 端点命名冲突（如 path overlap） | 低 | 中 | 检查 `marketing_router` 中所有 path 确保 `/events/{id}` 与 `/campaigns/{id}` 不重叠；FastAPI 按最长路径匹配，无歧义 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/marketing.py src/main.py tests/unit/test_marketing.py tests/integration/test_marketing_integration.py
git commit -m "feat(marketing): add campaign + event REST endpoints and wire into app"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#459): add Marketing API router (campaigns + events)" --body "Closes #459"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — POST/GET/PATCH 模式、Schema 类、`_paginated` helper、service 注入方式完全一致
- 父 issue / 关联：#450（营销服务父 issue，定义 MarketingService 能力）
- 依赖 issue：#458（TBD — 为本 issue 提供前置依赖确认）
- 被赋能 issue：#460（MarketingService integration tests，依赖活 router）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
