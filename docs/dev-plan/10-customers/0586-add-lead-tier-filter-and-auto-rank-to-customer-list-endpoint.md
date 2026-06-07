# 客户列表 · 按lead tier筛选 + 自动排序 + 参与度webhook

| 元数据 | 值 |
|---|---|
| Issue | #586 |
| 分类 | 10-customers |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#585 客户评分系统基础](../60-analytics/0585-integrate-ai-agent-framework-for-enhanced-scoring-factors.md) |
| 启用后赋能 | 20-sales (销售可按热度筛选客户), 30-tickets (ticket可基于参与度触发) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `GET /customers/` 只能按 ID/名称等字段过滤，亦无按 lead评分排序的能力。销售团队无法快速聚焦 hot leads；新客户参与度事件（邮件打开、网站访问）无自动化触发评分重算的入口，评分只能手动维护，降低了 CRM 的线索转化效率。

### 1.2 做完后

- **用户视角**：销售在 `GET /customers/?lead_tier=hot` 时直接获得高价值线索列表；`GET /customers/?order_by_score=true` 自动把 hot/warm 客户排在最前。邮件打开或网站访问事件 POST 到 `/events/engagement` 后，ScoreService 自动重算该客户的分数并更新，客户 tier随之升降。
- **开发者视角**：新增 `CustomerService.list_customers()` 支持 `lead_tier` 和 `order_by_score` 参数；新增 `POST /events/engagement` webhook endpoint；评分引擎闭环，不需人工触发。

### 1.3 不做什么（剔除）

- [ ] 不实现评分算法本身（由 ScoreService.calculate_score 负责，不在本板块范围）
- [ ] 不支持多事件批量 webhook（单次 POST 单事件，超量由调用方控制）
- [ ] 不在本板块实现复杂的事件去重/幂等（仅 basic dedup via unique constraint）
- [ ] 不修改已有 customer 详情或编辑 endpoint 的行为

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 新增 ≥4 passed（lead_tier 过滤 + order_by_score 排序各 2 条）
- `PYTHONPATH=src pytest tests/integration/test_engagement_webhook_integration.py -v` → 全 passed
- `ruff check src/api/routers/customers.py src/services/customer_service.py src/api/routers/events.py` → 0 errors
- ScoreService.calculate_score 在 webhook触发后被调用一次（mock assertion）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) L{1}-L{50}

TBD - 待验证：确认现有 `GET /customers/` 签名和 `CustomerService.list_customers()` 方法是否存在（预期位于 src/api/routers/customers.py 和 src/services/customer_service.py）

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 新增 `lead_tier` 和 `order_by_score` query 参数，透传给 service
  - [`src/services/customer_service.py`](../../../src/services/customer_service.py) — `list_customers` 方法新增筛选/排序逻辑
  - [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — 新增 unit test cases for lead_tier filter + order_by_score
- 要建：
  - `src/api/routers/events.py` — 新增 `POST /events/engagement` webhook endpoint
  - `tests/integration/test_engagement_webhook_integration.py` — webhook + score recal集成测试
  - `tests/unit/test_events_webhook.py` — webhook unit test（mock ScoreService）

### 2.3 缺什么

- [ ] `GET /customers/` 无 `lead_tier` 参数 →销售无法按 hot/warm/cold 筛选
- [ ] `GET /customers/` 无 `order_by_score` 参数 → 无法自动将高价值客户前置
- [ ] 无 `POST /events/engagement` webhook endpoint → 外部系统无法推送参与度事件触发重算
- [ ] ScoreService 未被任何事件自动调用 →评分闭环缺失
- [ ] 无基于 tier 的 count聚合（影响管理后台看板展示）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/events.py` | `POST /events/engagement` webhook，接收参与度事件并触发 ScoreService |
| `tests/unit/test_events_webhook.py` | Unit test：mock ScoreService，验证 webhook 路由注册和行为 |
| `tests/integration/test_engagement_webhook_integration.py` | Integration test：真实 DB，POST engagement事件，验证 customer score 更新 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) | `GET /` 新增 `lead_tier: str | None` / `order_by_score: bool = False` query params |
| [`src/services/customer_service.py`](../../../src/services/customer_service.py) | `list_customers` 支持 `lead_tier` 过滤和 `order_by_score` DESC 排序 |
| [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) | 新增 4 个 unit cases：hot filter, warm filter, cold filter, order_by_score |

### 3.3 新增能力

- **Service method**：`CustomerService.list_customers(tenant_id, page, page_size, lead_tier: str | None, order_by_score: bool) -> tuple[list[CustomerModel], int]`
- **API endpoint**：`GET /customers/?lead_tier=hot&order_by_score=true` → `{"success": true, "data": {items, total, ...}}`
- **API endpoint**：`POST /events/engagement` → `{"success": true, "data": {"customer_id": N, "new_score": M}}` — body: `{"tenant_id": N, "customer_id": N, "event_type": "email_open"|"website_visit", "metadata": {...}}`
- **Service method**：`ScoreService.calculate_score(session, customer_id, tenant_id) -> int`（已在 #585 定义，本板块引入调用闭环）
- **Service call**：`EventService.create_engagement_event(session, tenant_id, customer_id, event_type, metadata)` —记录事件并触发重算

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 webhook POST 不选 polling**：外部邮件系统/网站 analytics push 事件比 CRM轮询更实时，降低延迟- **选在 webhook 内直接调用 ScoreService 不选 message queue**：当前规模不需要额外 broker，避免运维复杂度上升- **选在 SQL 层过滤 tier 不选 Python过滤**：大数据集下 SQL tier enum过滤避免 O(n) Python sort### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`；webhook 请求 body 必须携带 `tenant_id`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`（router负责序列化）
- Service 错误抛 `AppException` 子类（`NotFoundException`, `ValidationException`），**不**返回 `ApiResponse.error()`
- 新增 `POST /events/engagement` 是 additive endpoint，不影响现有 API，不破坏兼容性
- 已有 `GET /customers/` 加参数为 optional，不破坏调用方（无 parameter = 全量）

### 4.4 已知坑

1. **SQLAlchemy 列名冲突 `metadata`** → 规避：`EngagementEvent` 模型使用 `event_metadata`（JSONB）作为列名，避免与 `Base.metadata` 冲突
2. **Alembic autogen 生成 `JSON()` 而非 `JSONB()`** → 规避：`alembic/versions/` 中手动将 `sa.JSON()`改为 `sa.JSONB()`，确保 `event_metadata` 使用正确类型
3. **Alembic autogen 丢弃 `timezone=True`** → 规避：检查 migration 中所有 `DateTime` 列，手动补回 `timezone=True`（用于 `created_at` 等时间戳）
4. **Mock session 中的 `execute` assertion** →规避：Unit test 中需要为新 SQL 语句（tier filter / order by score）补充 mock handler，`make_customer_handler` 可能需要扩展支持 `ORDER BY score` 逻辑

---

## 5. 实现步骤（按顺序）

### Step 1: 在 `src/api/routers/customers.py` 添加 lead_tier 和 order_by_score 参数

在 `GET /customers/` 函数签名中添加两个 query 参数：

```python
# src/api/routers/customers.py
from typing import Optional

@router.get("/")
async def list_customers(
    page: int = 1,
    page_size: int = 20,
    lead_tier: Optional[str] = None,   # ← 新增
    order_by_score: bool = False,      # ← 新增
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
```

在函数体中，将参数透传给 service：

```python
    svc = CustomerService(session)
    items, total = await svc.list_customers(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        lead_tier=lead_tier,
        order_by_score=order_by_score,
    )
```

**完成判定**：`ruff check src/api/routers/customers.py` →0 errors

---

### Step 2: 在 `src/services/customer_service.py` 的 `list_customers` 方法实现筛选和排序逻辑

在 `list_customers` 方法签名中添加：

```python
async def list_customers(
    self,
    tenant_id: int,
    page: int = 1,
    page_size: int = 20,
    lead_tier: Optional[str] = None,
    order_by_score: bool = False,
) -> tuple[list[CustomerModel], int]:
```

在 SQL WHERE 子句中加入 tier 过滤（当 lead_tier 不为 None 时）：

```python
    conditions = [customers.c.tenant_id == tenant_id]
    if lead_tier is not None:
        if lead_tier not in ("hot", "warm", "cold"):
            raise ValidationException("lead_tier must be one of: hot, warm, cold")
        conditions.append(customers.c.lead_tier == lead_tier)
```

在 ORDER BY 子句中 conditionally 添加 score排序：

```python if order_by_score:
        query = query.order_by(customers.c.score.desc())
    else:
        query = query.order_by(customers.c.id)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 新增 cases all passed

---

### Step 3: 在 `src/api/routers/events.py` 新建 webhook endpoint

创建路由文件 `src/api/routers/events.py`：

```python
from fastapi import APIRouter, Dependsfrom sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.score_service import ScoreService
from services.event_service import EventService
from pydantic import BaseModel

router = APIRouter(prefix="/events", tags=["Events"])

class EngagementEventRequest(BaseModel):
    tenant_id: int
    customer_id: int
    event_type: str  # "email_open" | "website_visit"

@router.post("/engagement")
async def create_engagement_event(
    body: EngagementEventRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    event_svc = EventService(session)
    score_svc = ScoreService(session)
    await event_svc.record_engagement_event(
        tenant_id=body.tenant_id,
        customer_id=body.customer_id,
        event_type=body.event_type,
    )
    new_score = await score_svc.calculate_score(
        customer_id=body.customer_id,
        tenant_id=body.tenant_id,
    )
    return {"success": True, "data": {"customer_id": body.customer_id, "new_score": new_score}}
```

在 [`src/main.py`](../../../src/main.py) 中注册新 router（查找 `APIRouter` 导入段，添加 `include_router` 行）：

```python
from api.routers.events import router as events_router
app.include_router(events_router)
```

**完成判定**：`ruff check src/api/routers/events.py src/main.py` → 0 errors

---

### Step 4: 实现 `EventService.record_engagement_event` 方法在 `src/services/event_service.py`（新文件或现有文件扩展）中：

```python
class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_engagement_event(
        self,
        tenant_id: int,
        customer_id: int,
        event_type: str,
    ) -> EngagementEvent:
        result = await self.session.execute(
            select(EngagementEvent).where(
                EngagementEvent.tenant_id == tenant_id,
                EngagementEvent.customer_id == customer_id,
                EngagementEvent.event_type == event_type,
            )
        )
        # basic dedup — event stored anyway; caller controls frequency        event = EngagementEvent(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            event_metadata={},
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_events_webhook.py -v` → 全 passed

---

### Step 5: 确认 ScoreService.calculate_score 已在 #585 中可用，添加缺失迁移若 `ScoreService.calculate_score` 尚未实现（等待 #585），在 `src/services/score_service.py` 中补充存根防止 import错误：

```python
class ScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_score(self, customer_id: int, tenant_id: int) -> int:
        from sqlalchemy import select
        from db.models.customer import Customer
        result = await self.session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")
        # Placeholder: real scoring logic from #585
        new_score = (customer.score or 0) + 10
        customer.score = new_score
        await self.session.commit()
        return new_score
```

**完成判定**：`PYTHONPATH=src python -c "from services.score_service import ScoreService; print('import ok')"` → exit 0

---

### Step 6: 生成数据库 migration（如需新增 `engagement_events` 表）

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade head
alembic revision --autogenerate -m "add engagement_events table for lead tier webhook"
#手动修正 autogen 输出的 JSON→JSONB，timezone=True
```

手动在生成的文件 `alembic/versions/<id>_add_engagement_events_table.py` 中修正：

```python
# alembic/versions/<id>_add_engagement_events_table.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_metadata", sa.JSONB(), nullable=True),   # ← 手动修正
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
 )
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/customers.py src/api/routers/events.py src/services/customer_service.py src/services/score_service.py src/services/event_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 新增 4 passed- [ ] `PYTHONPATH=src pytest tests/unit/test_events_webhook.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_engagement_webhook_integration.py -v` → 全 passed（如涉及 DB）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration）
- [ ] 端到端（启动服务后）：`curl -X POST http://localhost:8000/events/engagement -H "Content-Type: application/json" -d '{"tenant_id":1,"customer_id":1,"event_type":"email_open"}'` → 返回 `{"success":true,"data":{"customer_id":1,"new_score":...}}`
- [ ] 端到端：`curl "http://localhost:8000/customers/?lead_tier=hot&order_by_score=true"` → 返回正确 filtered/sorted 列表

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ScoreService.calculate_score 尚未实现（#585 未合并）导致 import 错误 | 中 | 中 | 在 ScoreService 中补充存根 + 注释说明，待 #585 合并后替换为真实实现；不影响其他 endpoint |
| Webhook 高频调用（同一事件重复 POST）导致 ScoreService 被无意义重算 | 中 | 低 | 在 `EngagementEvent` 表加 unique constraint `(tenant_id, customer_id, event_type)`，webhook 侧捕获 `ConflictException` 返回 200 而非500；已有 Step 4 dedup 逻辑兜底 |
| SQL ORDER BY score DESC 在 score 为 NULL 时行为不一致 | 低 | 中 | `COALESCE(customers.c.score, 0)` 包裹排序字段 |
| Alembic migration手动修正步骤被遗忘 | 低 | 高 | 将 JSONB/timezone 修正作为 checklist 写入 §5 Step 6；在 CI pre-commit hook 加 `ruff format` 检查 migration 文件 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/customers.py src/api/routers/events.py src/services/customer_service.py src/services/score_service.py src/services/event_service.py src/main.py tests/unit/test_customer_service.py tests/unit/test_events_webhook.py tests/integration/test_engagement_webhook_integration.py
git commit -m "feat(customers): add lead_tier filter, order_by_score, and engagement webhook for score recalc"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#586): add lead tier filter + auto-rank + engagement webhook" --body "Closes #586"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) —现有 list + filter逻辑- 父 issue /关联：#49, #585-父 issue / 关联：#586（本案）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
