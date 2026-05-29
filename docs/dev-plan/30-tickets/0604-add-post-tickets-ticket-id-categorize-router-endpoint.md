# [tickets] · Add POST /tickets/{ticket_id}/categorize endpoint

| 元数据 | 值 |
|---|---|
| Issue | #604 |
| 分类 | 30-tickets |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [板块名](../30-tickets/0603-add-ticket-categorization-service.md), 无 |
| 启用后赋能 | [板块名](../50-automation/0605-automation-trigger-on-category-detected.md), 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently lacks a way to programmatically classify a support ticket after it has been created. Issue #603 ships `TicketCategorizationService` in the service layer — this board exposes that capability over HTTP and wires the auto-categorize-on-create flag into the ticket creation path.

### 1.2 做完后

- **用户视角**: No direct user-facing UI change — this is a backend-only capability consumed by API callers or automation flows.
- **开发者视角**: Any client can call `POST /tickets/{ticket_id}/categorize` to receive a classification. The ticket creation endpoint accepts `auto_categorize_on_create: true` to trigger a synchronous categorization pass as part of the create flow.

### 1.3 不做什么（剔除）

- [ ] Automatic batch re-categorization of existing historical tickets (future automation board).
- [ ] Any UI / admin-panel changes — pure API and service layer only.
- [ ] Persistent storage of categorization results (results returned in response envelope only; if persistence is needed a separate board will be filed).

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_tickets_categorize.py -v` → all passed
- `PYTHONPATH=src pytest tests/unit/test_tickets_router.py -v` → all passed (covers the auto_categorize_on_create flag)
- `ruff check src/api/routers/tickets.py src/services/ticket_categorization_service.py src/models/schemas/ticket_categorize.py` →0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/tickets.py` — 现有 `POST /tickets` 创建端点；需确认 `auto_categorize_on_create` 字段是否已存在

TBD - 待验证：`src/services/ticket_categorization_service.py` L? — #603 交付的 service；需确认方法签名 `categorize_ticket(self, ticket_id: int, tenant_id: int) -> ...`

TBD - 待验证：`src/models/schemas/ticket.py` — `TicketCreate` Pydantic schema；需确认字段定义

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/api/routers/tickets.py` — 新增 `/tickets/{ticket_id}/categorize` 路由 + `auto_categorize_on_create` 参数透传
  - TBD - 待验证：`src/models/schemas/ticket.py` — 在 `TicketCreate` 中加入 `auto_categorize_on_create: bool = False`
  - TBD - 待验证：`tests/unit/test_tickets_router.py` — 更新现有创建测试 + 新增 categorize 路由测试- 要建：
  - `src/models/schemas/ticket_categorize.py` — `CategorizeTicketRequest` + `CategorizeTicketResponse` Pydantic 模型
  - TBD - 待验证：`tests/unit/test_tickets_categorize.py` —端点 response shape 单元测试，命名以实际 router 文件为准

### 2.3 缺什么

- [ ] `POST /tickets/{ticket_id}/categorize` router endpoint (not yet wired in `tickets.py`)
- [ ] `CategorizeTicketRequest` / `CategorizeTicketResponse` schema (new file)
- [ ] `auto_categorize_on_create` field not present in `TicketCreate` schema
- [ ] Unit test coverage for the categorize endpoint response shape
- [ ] Unit test for the `auto_categorize_on_create` flag on the create flow

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/schemas/ticket_categorize.py` | `CategorizeTicketRequest` + `CategorizeTicketResponse` Pydantic models |
| `tests/unit/test_tickets_categorize.py` | Unit tests for categorize endpoint response shape |
| `alembic/versions/<id>_add_categorize_fields_to_tickets.py` | Migration to add categorization-related columns if needed (see §4.4) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/api/routers/tickets.py` | 新增 `POST /tickets/{ticket_id}/categorize` + `auto_categorize_on_create` 参数透传 |
| TBD - 待验证：`src/models/schemas/ticket.py` | `TicketCreate` 增加 `auto_categorize_on_create: bool = False` |
| TBD - 待验证：`tests/unit/test_tickets_router.py` | 增加 auto_categorize_on_create 场景的 router单元测试 |

### 3.3 新增能力

- **API endpoint**：`POST /tickets/{ticket_id}/categorize` → `{"success": true, "data": {"ticket_id": n, "category": "...", "confidence": 0.9, "reason": "..."}}`
- **API flag**：创建端点 `POST /tickets`接受 `auto_categorize_on_create: bool = False`
- **ORM model**：N/A — 不新建 model，结果通过 response 返回- **Migration**：TBD — 如 #603 引入了新的 DB 列，在此 migration 中确认 schema完整

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Response envelope 使用 `ApiResponse`**：与项目路由约定一致（所有 router 返回 `{"success": true, "data": {...}}`），不做裸 dict 返回。
- **`auto_categorize_on_create` 默认 `False`**：避免对现有调用方引入意外行为；显式 opt-in 才触发分类。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `postgresql+asyncpg` | 适配现有 DATABASE_URL | 无变更 |
| `sqlalchemy` 2.x async | 适配现有 | 无变更 |

### 4.3 兼容性约束

- 多租户：`tenant_id` 从 `AuthContext` 注入，每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- Router 使用 `session: AsyncSession = Depends(get_db)`，**不**使用 `async with get_db() as session:`
- Import路径：`from models.schemas.ticket_categorize import ...`，**不**写 `from src.models...`

### 4.4 已知坑

1. **Alembic autogen 会把 JSONB 写成 `JSON()`、把 `timezone=True` 的 DateTime 写成 `DateTime`** →手动改回；如 #603 引入了 JSONB 列，迁移文件中确认使用 `sa.JSONB()` 而非 `sa.JSON()`
2. **SQLAlchemy Base 子类的列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ 如新增列命名避免使用 `metadata`，用 `event_metadata`、`payload` 等
3. **PYTHONPATH=src**：所有测试和运行命令前必须 `export PYTHONPATH=src`，否则 `from db.models...` 等导入会失败---

## 5. 实现步骤（按顺序）

### Step 1: Add `auto_categorize_on_create` to TicketCreate schema

在 `TicketCreate` Pydantic schema 中加入 `auto_categorize_on_create: bool = False`，附默认值确保向后兼容。

操作：
- a) 在 TBD - 待验证：`src/models/schemas/ticket.py` 的 `TicketCreate` 类中添加一行 `auto_categorize_on_create: bool = False`
- b) 验证其他 import 正常```python
# src/models/schemas/ticket.pyclass TicketCreate(BaseModel):
    title: str
    description: str | None = None
    priority: TicketPriority = TicketPriority.MEDIUM
    auto_categorize_on_create: bool = False  # 新增
```

**完成判定**：`PYTHONPATH=src python -c "from models.schemas.ticket import TicketCreate; print(TicketCreate.model_fields)"` → 输出包含 `auto_categorize_on_create`

---

### Step 2: Create ticket_categorize schemas

新建 `src/models/schemas/ticket_categorize.py`，定义请求/响应模型。

操作：
- a) 创建 `src/models/schemas/ticket_categorize.py`
- b) 定义 `CategorizeTicketRequest(BaseModel)`：类别选项（category_ids / auto模式等，视 #603 service 接口而定）
- c) 定义 `CategorizeTicketResponse(BaseModel)`：`ticket_id: int`、`category: str`、`confidence: float`、`reason: str | None`

```python
# src/models/schemas/ticket_categorize.py
from pydantic import BaseModel


class CategorizeTicketRequest(BaseModel):
    """Options for ticket categorization."""
    force_recategorize: bool = False


class CategorizeTicketResponse(BaseModel):
    ticket_id: int
    category: str
    confidence: float
    reason: str | None = None
```

**完成判定**：`PYTHONPATH=src python -c "from models.schemas.ticket_categorize import CategorizeTicketRequest, CategorizeTicketResponse; print('ok')"` → `ok`

---

### Step 3: Wire POST /tickets/{ticket_id}/categorize in the tickets router

确认 TBD - 待验证：`src/api/routers/tickets.py` 中存在 `router = APIRouter(prefix="/tickets", ...)`，在文件末尾追加新端点，并确认 `TicketCategorizationService` 已由 #603 交付。

操作：
- a) 在 `tickets.py` 新增 import：`from models.schemas.ticket_categorize import CategorizeTicketRequest, CategorizeTicketResponse`
- b)追加 `@router.post("/{ticket_id}/categorize", ...)` 端点：
  - 注入 `ctx: AuthContext = Depends(require_auth)` 和 `session: AsyncSession = Depends(get_db)`
  - 调用 `TicketCategorizationService(session).categorize_ticket(ticket_id, tenant_id=ctx.tenant_id)`
  - 转换返回值 → `CategorizeTicketResponse`
  - 返回 `ApiResponse(data=response.model_dump())` envelope

```python
# src/api/routers/tickets.py
@router.post("/{ticket_id}/categorize", response_model=ApiResponse[CategorizeTicketResponse])
async def categorize_ticket(
    ticket_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = TicketCategorizationService(session)
    result = await svc.categorize_ticket(ticket_id, tenant_id=ctx.tenant_id)
    response = CategorizeTicketResponse(
        ticket_id=result.ticket_id,
        category=result.category,
        confidence=result.confidence,
        reason=result.reason,
    )
    return ApiResponse(data=response)
```

**完成判定**：`ruff check src/api/routers/tickets.py` → 0 errors；端点已注册 `POST /tickets/{ticket_id}/categorize`

---

### Step 4: Connect auto_categorize_on_create in ticket creation endpoint

在 TBD - 待验证：`src/api/routers/tickets.py` 的 `POST /tickets` 端点中透传 `auto_categorize_on_create` 参数：如为 `True` 则在创建成功后立即调用 `TicketCategorizationService.categorize_ticket(...)` 并将结果附加到 response 的 `data` 字段。

操作：
- a) 确认创建端点签名中已包含 `auto_categorize_on_create` 字段（来自 Step 1 对 schema 的修改）
- b) 在 router 处理函数中解包该字段，创建票据后若 `auto_categorize_on_create is True` 则调用 service```python
# src/api/routers/tickets.py  POST /tickets 端点内auto_categorize: bool = data.auto_categorize_on_create
ticket = await ticket_svc.create_ticket(tenant_id=ctx.tenant_id, **data.model_dump(exclude={"auto_categorize_on_create"}))
result = {"ticket": ticket.to_dict()}
if auto_categorize:
    cat_svc = TicketCategorizationService(session)
    cat_result = await cat_svc.categorize_ticket(ticket.id, tenant_id=ctx.tenant_id)
    result["categorization"] = {
        "ticket_id": cat_result.ticket_id,
        "category": cat_result.category,
        "confidence": cat_result.confidence,
        "reason": cat_result.reason,
    }
return ApiResponse(data=result)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tickets_router.py -v -k "categorize" --tb=short` → all passed

---

### Step 5: Write unit tests for categorize endpoint response shape

创建 `tests/unit/test_tickets_categorize.py`（或视 router 文件命名在 test_tickets_router.py 中新增 fixture），测试 categorize端点返回 ApiResponse envelope 结构。

操作：
- a) 定义 `mock_db_session` fixture（用 `tests/unit/conftest.py` 中的 `make_mock_session` + `MockState`）
- b) Mock `TicketCategorizationService.categorize_ticket` 返回模拟结果- c) 测试用例：
  - 成功路径：response envelope包含 `success: true` 且 `data.category` 为字符串
  - 租户隔离：`ForbiddenException` 当 ticket 不属于当前 tenant
  - 请求体验证：发送空 body 时不崩溃（有默认值）

```python
# tests/unit/test_tickets_categorize.py（概要）
async def test_categorize_returns_envelope(mock_db_session, httpx_mock):
    mock_db_session.add_result("SELECT", MockRow({"id": 1, "category": "billing", "confidence": 0.85, "reason": "keywords matched"}))
    await categorize_ticket(ticket_id=1, ctx=auth_ctx(tenant_id=1), session=mock_db_session)
    # 断言：response["success"] is True, "data" in response, "category" in response["data"]
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tickets_categorize.py -v` → all passed；无 `TypeError` / `ValidationError`

---

## 6. 验收

- [ ] `ruff check src/api/routers/tickets.py src/models/schemas/ticket_categorize.py src/models/schemas/ticket.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from models.schemas.ticket import TicketCreate; assert 'auto_categorize_on_create' in TicketCreate.model_fields"` → exit 0
- [ ] `PYTHONPATH=src python -c "from models.schemas.ticket_categorize import CategorizeTicketRequest, CategorizeTicketResponse; print('ok')"` → `ok`
- [ ] `PYTHONPATH=src pytest tests/unit/test_tickets_categorize.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_tickets_router.py -v -k "categorize" --tb=short` → all passed（如测试写在 router 测试文件中）
- [ ] TBD - 如有 migration：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] TBD - 端到端：`curl -X POST http://localhost:8000/tickets/{id}/categorize` 返回 `{...}`（路由已注册后手动验证）

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #603 尚未完成导致 `TicketCategorizationService` 不存在 | 中 | 高—本板无法集成 |阻塞本板直至 #603 合并；本板依赖声明中已注明 |
| `auto_categorize_on_create` flag 设计变更（service 接口不匹配） | 低 | 中 | 接口对齐后仅修改 router透传逻辑，不影响 schema |
| 新增 categorization 列导致迁移文件与 #603 迁移冲突（alembic 链断裂） | 低 | 中 | 由 CI 报错触发；手动调整迁移顺序解决（先用 #603 migration 再用本板） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/schemas/ticket_categorize.py src/models/schemas/ticket.py src/api/routers/tickets.py tests/unit/test_tickets_categorize.py
git commit -m "feat(tickets): add POST /tickets/{ticket_id}/categorize and auto_categorize_on_create flag"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#604): add categorize endpoint and auto_categorize_on_create flag" --body "Closes #604"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/opportunities.py` —现有 `POST /opportunities/{id}/close` 端点（response envelope 模式）
- 父 issue / 关联：#45（父），#603（直接依赖），#605（启用后赋能）
- #603 service 层交付物（待确认）TBD - 待验证：`src/services/ticket_categorization_service.py` L?

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
