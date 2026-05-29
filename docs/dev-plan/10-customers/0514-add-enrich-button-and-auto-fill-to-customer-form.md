# 客户表单 · Enrich 按钮与自动填充

| 元数据 | 值 |
|---|---|
| Issue | #514 |
| 分类 | 10-customers |
| 优先级 | 推荐 |
| 工作量 | 2 工作日 |
| 依赖 | [客户表单字段完善](30-tickets/0513-add-company-industry-fields-to-customer-form.md) |
| 启用后赋能 | [客户详情页强化](50-automation/), [线索 Enrich 流程](20-sales/) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

客户记录中 domain 字段（公司网站）本身已存在，但表单没有利用它自动填充公司信息（公司名、行业、规模、营收、LinkedIn）。用户每次都要手动录入这些可推断的字段，既耗时又容易出错。这是一个可选项增强——有 domain 的客户可以通过一次点击省去大量重复录入工作。

### 1.2 做完后

- **用户视角**：在客户创建/编辑表单中，当 `domain` 字段有值时，Enrich 按钮可见。点击后出现加载指示器，2-5 秒内自动填充 company_name、industry、employee_count、revenue、linkedin_url 五个字段。用户仍可手动覆盖任意字段。表单顶部显示 Enrich 状态徽章（None / Enriched / Stale）。
- **开发者视角**：新增 `EnrichmentService` 和 `POST /api/v1/enrichment/lookup` endpoint，支持按 domain 查询外部公司数据并写入客户字段。新增 `CustomerEnrichmentStatus` 枚举（none / enriched / stale）。

### 1.3 不做什么（剔除）

- [ ] 不实现批量 Enrich（仅支持单条客户记录的手动触发）
- [ ] 不实现定时刷新 stale 状态（仅记录 Enrich 时间戳，供后续定时任务使用）
- [ ] 不实现公司 logo 或地址等 Enrich API 未返回的字段
- [ ] 不在 enrichment 失败时阻止表单提交（静默失败，用户仍可手动填写）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_enrichment_service.py tests/unit/test_customer_form.py -v` → ≥ 8 passed
- `ruff check src/services/enrichment_service.py src/api/routers/enrichment.py` → 0 errors
- Playwright 测试：domain → 点击 Enrich → 等待加载完成 → 验证五个字段均已填充

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/customers.py` L? — 现有客户表单相关 router，查看 `create_customer` / `update_customer` handler 及字段定义
TBD - 待验证：`src/services/customer_service.py` L? — 现有 `CustomerService` 类，查看 `create` / `update` 方法签名

### 2.2 涉及文件清单

- 要改：
  - `src/app/(app)/automation/rules/[id]/page.tsx` — TBD — 需确认是否有客户表单组件可参考
  - `frontend/src/app/(app)/customers/[id]/page.tsx` 或 `form.tsx` — 添加 Enrich 按钮和状态徽章
  - `frontend/src/lib/api/queries.ts` — 添加 `enrichCustomer` mutation hook
- 要建：
  - `src/services/enrichment_service.py` — 调用外部 Enrich API 并更新客户字段
  - `src/api/routers/enrichment.py` — `POST /api/v1/enrichment/lookup` 路由
  - `src/db/models/customer.py` — 新增 `enrichment_status` 枚举字段及 `last_enriched_at` 时间戳
  - `alembic/versions/<id>_add_enrichment_status_to_customer.py` — 迁移脚本
  - `tests/unit/test_enrichment_service.py` — Service 层单元测试
  - `tests/integration/test_enrichment_integration.py` — 集成测试
  - `frontend/tests/e2e/enrich-customer.spec.ts` — Playwright 端到端测试

### 2.3 缺什么

- [ ] `POST /api/v1/enrichment/lookup` API endpoint（尚不存在）
- [ ] `EnrichmentService`（尚不存在）
- [ ] 客户模型的 `enrichment_status` / `last_enriched_at` 字段（尚不存在）
- [ ] 前端 `customer/[id]/page.tsx` 的 Enrich 按钮 UI（尚不存在）
- [ ] 加载状态（loading spinner）和 Enrich 后字段可编辑（override）逻辑
- [ ] Enrich 状态徽章（badge）组件
- [ ] Playwright 端到端测试（happy path）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/enrichment_service.py` | 调用外部 Enrich API，根据 domain 拉取公司数据并写入客户字段 |
| `src/api/routers/enrichment.py` | `POST /api/v1/enrichment/lookup` 路由，接收 `{ domain }` 返回 enrichment 数据 |
| `src/db/models/customer.py`（修改） | 新增 `enrichment_status` 枚举列和 `last_enriched_at` 时间戳列 |
| `alembic/versions/<id>_add_enrichment_fields.py` | 添加 `enrichment_status`、`last_enriched_at`、`enrichment_data` JSON 列 |
| `tests/unit/test_enrichment_service.py` | 覆盖：正常 Enrich、domain 不存在、API 超时、tenant 隔离 |
| `tests/integration/test_enrichment_integration.py` | 覆盖：完整 Enrich 流程（建客户 → Enrich → 验证 DB 字段） |
| `frontend/tests/e2e/enrich-customer.spec.ts` | Playwright happy path：输入 domain → 点击 Enrich → 验证五个字段非空 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/models/customer.py`](../../src/models/customer.py) | 新增 `enrichment_status` 枚举和 `last_enriched_at` 字段 |
| [`src/services/customer_service.py`](../../src/services/customer_service.py) | 新增 `enrich_from_domain` 方法调用 EnrichmentService |
| [`src/api/routers/customers.py`](../../src/api/routers/customers.py) | 新增 `POST /customers/{id}/enrich` 路由（或复用 enrichment router） |
| `frontend/src/app/(app)/customers/[id]/page.tsx` | 添加 Enrich 按钮、加载状态、状态徽章；Enrich 后自动填充字段 |
| `frontend/src/lib/api/queries.ts` | 添加 `useEnrichCustomer` mutation hook |

### 3.3 新增能力

- **Service method**：`EnrichmentService.enrich(self, customer_id: int, tenant_id: int) -> CustomerModel`
- **API endpoint**：`POST /api/v1/enrichment/lookup` → `{"success": true, "data": {"company_name": "...", "industry": "...", "employee_count": ..., "revenue": "...", "linkedin_url": "..."}}`
- **ORM model**：`Customer` 新增 `enrichment_status: Enum('none', 'enriched', 'stale')` 和 `last_enriched_at: datetime` 及 `enrichment_data: JSON`
- **Migration**：`alembic upgrade head` 添加三列并建索引

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Enrich 触发放在后端**（`POST /api/v1/enrichment/lookup`）而不是前端直接调用第三方 API：避免在前端泄露第三方 API 密钥；统一错误处理；便于添加 tenant 级别的 rate limit / 缓存。
- **Enrich 数据写入客户字段，不单独建表**：company_name、industry 等字段本来就是 customer 表的列，直接更新这些列即可。保留一份 `enrichment_data: JSONB` 存储原始返回数据供调试和后续扩展，不需要单独的 enrichment 表。
- **Stale 由外部定时任务判断，不在本 PR 实现**：`last_enriched_at` 记录时间戳，stale 逻辑（如"超过 90 天标记为 stale"）留给后续定时任务板块。这样本 PR 只聚焦"点击 → 填充"的核心体验。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | `>=0.25` | 异步 HTTP 客户端，FastAPI 生态首选，替代 `aiohttp`（本 repo 已使用 httpx） |

### 4.3 兼容性约束

- 多租户：`POST /api/v1/enrichment/lookup` 必须在 SQL 中加入 `WHERE tenant_id = :tenant_id`（从 AuthContext.tenant_id 取得）
- Service 返回 ORM 对象，不调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`ValidationException` 当 domain 格式无效、`NotFoundException` 当客户不存在）
- 前端：Enrich button 仅在 `domain` 字段有值且非空时显示（trim 后长度 > 0）
- 前端：Enrich 完成后字段默认填充，用户可自由编辑（不受 Enrich 操作影响）

### 4.4 已知坑

1. **Alembic autogenerate 会把 `JSONB` 列写成 `JSON`，把 `DateTime(timezone=True)` 写成 `DateTime`** → 规避：检查 migration 文件中的 `sa.JSON()` 改为 `sa.JSONB().with_variant(postgresql.JSONB(), 'postgresql')`，DateTime 列加 `timezone=True`
2. **Enrich API 超时或返回 5xx 时静默失败，前端仍显示"失败"但允许用户继续填写** → 规避：Service 层 catch 所有异常并记录 log，不向上抛出；Router 返回 200 但 `data` 为 null，前端 toast 提示"Enrich 失败，请手动填写"
3. **并发 Enrich（用户在加载中再次点击）** → 规避：前端在加载期间禁用按钮（`disabled={isEnriching}`）；后端不加额外锁（Enrich 是幂等的，最终状态一致即可）

---

## 5. 实现步骤（按顺序）

### Step 1: 添加客户模型 enrichment 字段

在 `src/db/models/customer.py` 中的 `Customer` 类添加三列：

```python
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 新增
    enrichment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="none", index=True
    )
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

注意：不能用 `metadata` 作为列名（与 `Base.metadata` 冲突）。这里用 `enrichment_data` JSONB 存储原始 API 返回。

**完成判定**：`ruff check src/db/models/customer.py` → 0 errors

### Step 2: 生成 Alembic 迁移

操作：
a) 启动干净数据库：`docker compose -f configs/docker-compose.test.yml up -d test-db`
b) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
c) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
d) `alembic upgrade head`
e) `alembic revision --autogenerate -m "add_enrichment_fields_to_customer"`
f) 手动修正生成的文件：将 `sa.JSON()` 改为 `sa.JSONB().with_variant(postgresql.JSONB(), 'postgresql')`，DateTime 加 `timezone=True`
g) `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: 实现 EnrichmentService

创建 `src/services/enrichment_service.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.customer import Customer
from pkg.errors.app_exceptions import NotFoundException, ValidationException
import httpx
import os

ENRICHMENT_API_URL = os.getenv("ENRICHMENT_API_URL", "https://api.enrichment.example.com/v1/lookup")
ENRICHMENT_API_KEY = os.getenv("ENRICHMENT_API_KEY", "")

class EnrichmentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enrich(self, customer_id: int, tenant_id: int) -> Customer:
        result = await self.session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")

        if not customer.domain or not customer.domain.strip():
            raise ValidationException("Customer domain is required for enrichment")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                ENRICHMENT_API_URL,
                json={"domain": customer.domain.strip()},
                headers={"Authorization": f"Bearer {ENRICHMENT_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Map API fields to customer fields
        customer.company_name = data.get("company_name")
        customer.industry = data.get("industry")
        customer.employee_count = data.get("employee_count")
        customer.revenue = data.get("revenue")
        customer.linkedin_url = data.get("linkedin_url")
        customer.enrichment_status = "enriched"
        customer.last_enriched_at = datetime.now(timezone.utc)
        customer.enrichment_data = data  # store raw response

        await self.session.commit()
        await self.session.refresh(customer)
        return customer
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_service.py -v` → ≥ 4 passed

### Step 4: 添加 API 路由

在 `src/api/routers/enrichment.py` 新建：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.enrichment_service import EnrichmentService

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])

@router.post("/lookup")
async def enrich_customer(
    body: dict,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    domain = body.get("domain", "").strip()
    if not domain:
        return {"success": True, "data": None, "message": "No domain provided"}
    # Enrichment is triggered via POST /customers/{id}/enrich internally;
    # this public endpoint is for direct domain lookup by domain (no customer_id).
    return {"success": True, "data": None, "message": "Use POST /customers/{id}/enrich"}
```

在 `src/api/routers/customers.py` 添加 `POST /customers/{id}/enrich` 路由：

```python
@router.post("/{customer_id}/enrich")
async def enrich_customer(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentService(session)
    try:
        customer = await svc.enrich(customer_id, tenant_id=ctx.tenant_id)
        return {"success": True, "data": customer.to_dict(), "message": "Enrichment successful"}
    except AppException:
        # Log and return null data — user can still fill manually
        return {"success": True, "data": None, "message": "Enrichment failed"}
```

**完成判定**：`ruff check src/api/routers/enrichment.py src/api/routers/customers.py` → 0 errors

### Step 5: 前端 — Enrich 按钮、状态徽章、自动填充

在 `frontend/src/app/(app)/customers/[id]/page.tsx` 中：
- Enrich 按钮：`domain` 字段存在时显示，加载中 `disabled`
- 状态徽章：`enrichment_status === 'none'` 灰、"Enriched" 绿、"stale" 黄
- Enrich 成功后字段自动填充，用户可编辑

```typescript
// Add to customer form
const [enrichStatus, setEnrichStatus] = useState<'none'|'enriched'|'stale'>(customer.enrichment_status || 'none')
const [isEnriching, setIsEnriching] = useState(false)

const handleEnrich = async () => {
  setIsEnriching(true)
  try {
    const res = await fetch(`/api/v1/customers/${customer.id}/enrich`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    const json = await res.json()
    if (json.data) {
      setForm(prev => ({
        ...prev,
        company_name: json.data.company_name ?? prev.company_name,
        industry: json.data.industry ?? prev.industry,
        employee_count: json.data.employee_count ?? prev.employee_count,
        revenue: json.data.revenue ?? prev.revenue,
        linkedin_url: json.data.linkedin_url ?? prev.linkedin_url,
      }))
      setEnrichStatus('enriched')
    } else {
      alert('Enrichment failed — please fill in manually')
    }
  } finally {
    setIsEnriching(false)
  }
}
```

Enrich 按钮仅在 `form.domain && form.domain.trim().length > 0` 时渲染。

**完成判定**：`ruff check frontend/src/app/(app)/customers/` → 0 errors（前端 lint）

### Step 6: Playwright 端到端测试

创建 `frontend/tests/e2e/enrich-customer.spec.ts`：

```typescript
import { test, expect } from '@playwright/test'

test('enrich button fills company fields from domain', async ({ page }) => {
  await page.goto('/customers/new')
  await page.fill('[name="name"]', 'TestCorp Contact')
  await page.fill('[name="domain"]', 'example.com')

  // Enrich button should appear
  const enrichBtn = page.getByRole('button', { name: 'Enrich' })
  await expect(enrichBtn).toBeVisible()

  await enrichBtn.click()
  // Loading state
  await expect(enrichBtn).toBeDisabled()

  // Fields should be auto-filled
  await expect(page.locator('[name="company_name"]')).not.toBeEmpty()
  await expect(page.locator('[name="industry"]')).not.toBeEmpty()
  await expect(page.locator('[name="employee_count"]')).not.toBeEmpty()

  // Badge shows enriched
  await expect(page.locator('[data-testid="enrich-badge"]')).toContainText('Enriched')

  // User can override
  await page.fill('[name="company_name"]', 'My Override')
  await expect(page.locator('[name="company_name"]')).toHaveValue('My Override')
})
```

**完成判定**：`npx playwright test frontend/tests/e2e/enrich-customer.spec.ts` → 1 passed

---

## 6. 验收

- [ ] `ruff check src/services/enrichment_service.py src/api/routers/enrichment.py src/api/routers/customers.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_service.py -v` → ≥ 4 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_enrichment_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `npx playwright test frontend/tests/e2e/enrich-customer.spec.ts` → 1 passed
- [ ] 端到端（本地）：`POST http://localhost:8000/api/v1/customers/1/enrich` → `{"success": true, "data": {...}}` 且 DB 中 `enrichment_status = 'enriched'`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 外部 Enrich API 返回格式与预期不符（字段名不一致） | 低 | 中 | Service 层 catch `KeyError`，用 `data.get()` 兼容缺失字段；仍记录 `enrichment_status = 'enriched'`（部分字段可能为空） |
| Enrich 按钮在已有 enriched/stale 客户上被误用导致数据覆盖 | 低 | 中 | 前端在 `enrichment_status !== 'none'` 时显示确认 dialog："重新 Enrich 将覆盖现有字段，确认继续？" |
| JSONB 列在 SQLite 测试环境（unit test）不支持 | 中 | 低 | Unit test 使用 MockResult / MockRow，绕过 ORM 定义；集成测试在真实 PG 中运行 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/enrichment_service.py src/api/routers/enrichment.py src/db/models/customer.py alembic/versions/
git add tests/unit/test_enrichment_service.py tests/integration/test_enrichment_integration.py
git add frontend/src/app/(app)/customers/ frontend/src/lib/api/queries.ts frontend/tests/e2e/enrich-customer.spec.ts
git commit -m "feat(customers): add enrich button and auto-fill to customer form"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#514): add enrich button and auto-fill to customer form" --body "Closes #514"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/customer_service.py` — 现有 CustomerService 结构，参考其 `__init__` / 方法签名规范
- 第三方文档：[Clearbit Enrichment API](https://clearbit.com/docs) — 字段映射参考（company_name, industry, metrics.employees, metrics.annualRevenue, linkedin.handle）
- 父 issue / 关联：#74（父），#513（依赖，客户表单字段完善）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
