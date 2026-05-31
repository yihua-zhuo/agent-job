# EnrichmentAnalyticsService · 实现数据富化统计服务

| 元数据 | 值 |
|---|---|
| Issue | #754 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#753 - 实现富化路由 + 3 个端点](../60-analytics/0755-add-enrichment-router-with-3-endpoints.md) |
| 启用后赋能 | [#755 - EnrichmentAnalyticsService 单元测试](../60-analytics/0756-write-unit-tests-for-enrichmentanalyticsservice.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

#753 已在 API 层实现 3 个富化端点（更新 / 批量更新 / 删除），但这些端点依赖底层统计能力：前台需要展示覆盖率、各提供商分布、陈旧记录列表，后台需要批量刷新入口。当前缺少统一的分析服务，导致路由层无法聚合富化指标，且每次请求都直接击穿 DB 层执行临时 SQL，无法复用业务逻辑。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 Service 组件，为 #753 的端点提供数据聚合支撑。
- **开发者视角**：`EnrichmentAnalyticsService` 可被 `enrichment_router.py` 调用，提供覆盖率统计（`get_stats`）、陈旧记录分页查询（`list_stale`）、批量刷新调度（`bulk_refresh`）三个原子能力，供监控面板或定时任务消费。

### 1.3 不做什么（剔除）

- [ ] 不实现实际的 job 调度（`_dispatch_enrich_job` 为 placeholder，调度逻辑在后续 issue 中实现）
- [ ] 不创建新的 DB 表或 migration（`CustomerEnrichment` 表由已有模型提供，本服务只查询）
- [ ] 不在 Service 层调用 `.to_dict()`（返回 dict 域对象，由 router 负责序列化）

### 1.4 关键 KPI

- `ruff check src/services/enrichment_analytics_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics_service.py -v` → ≥ 5 passed（三个方法各有正向 + 边界用例）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如有 migration 改动）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/` 目录结构 — 需确认已有 `customer_service.py` 等参考实现，以 `session: AsyncSession` 为构造函数参数，无默认值。需确认 `CustomerEnrichment` ORM 模型已在 `src/db/models/` 中定义，并包含 `enriched_at`、`provider`、`tenant_id` 等字段。

### 2.2 涉及文件清单

- 要改：无（纯新建服务）
- 要建：
  - `src/services/enrichment_analytics_service.py` — 富化统计服务，含 get_stats / list_stale / bulk_refresh 三个方法
  - `tests/unit/test_enrichment_analytics_service.py` — 单元测试，使用 MockState + make_mock_session 模拟 DB

### 2.3 缺什么

- [ ] `EnrichmentAnalyticsService` — 统一的统计服务，当前不存在
- [ ] `get_stats` 方法 — 需要 `func.count` 在 Customer 和 CustomerEnrichment 上的 JOIN 查询，按提供商聚合
- [ ] `list_stale` 方法 — 需要分页 + `stale_after_days` 参数过滤，按 `enriched_at ASC` 排序
- [ ] `bulk_refresh` 方法 — 需要查询陈旧 customer_id 列表并通过 placeholder 调度

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/enrichment_analytics_service.py` | 富化统计服务：覆盖率、各提供商分布、陈旧记录查询、批量刷新调度 |
| `tests/unit/test_enrichment_analytics_service.py` | 单元测试：三个方法的正向 / 边界 / 异常用例 |

### 3.2 修改文件

（无修改文件，纯新建）

### 3.3 新增能力

- **Service class**：`EnrichmentAnalyticsService(session: AsyncSession)` — 构造函数无默认值
- **get_stats(tenant_id)**：返回 `dict`，含 `total_customers`、`enriched_count`、`coverage_pct`（浮点百分比）、`by_provider: Dict[str, int]`、`stale_count`
- **list_stale(tenant_id, page, page_size, stale_after_days=30)**：返回 `tuple[list[CustomerEnrichment], int]`，按 `enriched_at ASC` 排序
- **bulk_refresh(tenant_id)**：返回 `dict`，含 `dispatched_count`，内部调用 `_dispatch_enrich_job(customer_ids)` placeholder

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **返回 dict 而非 ORM 对象**：由于 `get_stats` 的返回值无对应 ORM 模型（覆盖率百分比、按提供商聚合），直接返回 dict 更自然；`list_stale` 返回 ORM 对象列表以复用 `CustomerEnrichment` 模型实例
- **不实现真实调度**：调度逻辑为 placeholder，避免本 issue 引入外部依赖（Celery / Redis / RabbitMQ），后续由独立 issue 实现

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须包含 `WHERE tenant_id = :tenant_id`
- Service 构造函数：`session: AsyncSession`，无默认值（`session=None` 禁止）
- Service 错误：抛出 `AppException` 子类，不返回 `ApiResponse.error()`
- Service 返回：域对象（dict / ORM 实例），不调用 `.to_dict()`

### 4.4 已知坑

1. **Alembic autogen 将 JSONB 写成 JSON、将 TIMESTAMPTZ 写成 DateTime** → 如本 issue 涉及 migration，手动将 `sa.JSON()` 改回 `sa.JSONB()`，将 `DateTime` 改回 `DateTime(timezone=True)`
2. **SQLAlchemy Base 子类列名不能用 `metadata`** → 如需存 JSON 元数据，使用 `event_metadata` / `payload` / `attrs` 等字段名（本 issue 查询已有模型，如 `CustomerEnrichment` 使用 `metadata` 列名需先确认）

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/enrichment_analytics_service.py` 框架

在 `src/services/` 下新建文件，定义 `EnrichmentAnalyticsService` 类骨架：构造函数接受 `session: AsyncSession`，三个方法签名预置，import 语句对齐 `from sqlalchemy.ext.asyncio import AsyncSession` 和 `from pkg.errors.app_exceptions import NotFoundException, ValidationException`。

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Dict, List, Tuple
from models.customer import Customer
from models.customer_enrichment import CustomerEnrichment

class EnrichmentAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self, tenant_id: int) -> Dict:
        raise NotImplementedError

    async def list_stale(
        self, tenant_id: int, page: int, page_size: int, stale_after_days: int = 30
    ) -> Tuple[List[CustomerEnrichment], int]:
        raise NotImplementedError

    async def bulk_refresh(self, tenant_id: int) -> Dict:
        raise NotImplementedError
```

**完成判定**：`ruff check src/services/enrichment_analytics_service.py` → 0 errors

---

### Step 2: 实现 `get_stats(tenant_id)`

在 `get_stats` 方法体内：
1. 用 `func.count().label('total')` 查询 `Customer` 表 `WHERE tenant_id = :tenant_id`
2. 用 `func.count(c.id).label('enriched')` 联合 `CustomerEnrichment`（INNER JOIN on customer_id）统计已富化客户数
3. 用 `GROUP BY c.provider` 统计 `by_provider: Dict[str, int]`
4. 计算 `coverage_pct = round(enriched_count / total_customers * 100, 2)`（total=0 时返回 0.0）
5. 用第二个 COUNT 查询 `CustomerEnrichment` WHERE `enriched_at < NOW() - INTERVAL '30 days'` 得出 `stale_count`
6. 返回 dict，含 `total_customers`、`enriched_count`、`coverage_pct`、`by_provider`、`stale_count`

```python
async def get_stats(self, tenant_id: int) -> Dict:
    # total customers
    total_row = await self.session.execute(
        select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)
    )
    total_customers = total_row.scalar_one() or 0

    # enriched count and by-provider breakdown via JOIN
    enriched_rows = await self.session.execute(
        select(
            CustomerEnrichment.provider,
            func.count(CustomerEnrichment.customer_id).label("cnt"),
        )
        .join(Customer, CustomerEnrichment.customer_id == Customer.id)
        .where(Customer.tenant_id == tenant_id)
        .group_by(CustomerEnrichment.provider)
    )
    by_provider: Dict[str, int] = {r.provider: r.cnt for r in enriched_rows}
    enriched_count = sum(by_provider.values())

    # stale count
    stale_row = await self.session.execute(
        select(func.count(CustomerEnrichment.id)).where(
            CustomerEnrichment.tenant_id == tenant_id,
            CustomerEnrichment.enriched_at
            < func.now() - func.make_interval(days=stale_after_days),
        )
    )
    stale_count = stale_row.scalar_one() or 0

    coverage_pct = round(enriched_count / total_customers * 100, 2) if total_customers else 0.0

    return {
        "total_customers": total_customers,
        "enriched_count": enriched_count,
        "coverage_pct": coverage_pct,
        "by_provider": by_provider,
        "stale_count": stale_count,
    }
```

**完成判定**：`ruff check src/services/enrichment_analytics_service.py` → 0 errors；方法逻辑覆盖 total=0 的边界

---

### Step 3: 实现 `list_stale(tenant_id, page, page_size, stale_after_days=30)`

在 `list_stale` 方法体内：
1. 用 `func.now() - func.make_interval(days=stale_after_days)` 计算截止时间
2. COUNT 查询：`select(func.count(CustomerEnrichment.id)).where(CustomerEnrichment.tenant_id == tenant_id, CustomerEnrichment.enriched_at < cutoff)` 得出 total
3. 数据查询：OFFSET = `(page - 1) * page_size`，LIMIT = `page_size`，ORDER BY `enriched_at ASC`
4. 返回 `tuple[list[CustomerEnrichment], int]`

```python
async def list_stale(
    self,
    tenant_id: int,
    page: int,
    page_size: int,
    stale_after_days: int = 30,
) -> Tuple[List[CustomerEnrichment], int]:
    cutoff = func.now() - func.make_interval(days=stale_after_days)

    count_row = await self.session.execute(
        select(func.count(CustomerEnrichment.id)).where(
            CustomerEnrichment.tenant_id == tenant_id,
            CustomerEnrichment.enriched_at < cutoff,
        )
    )
    total = count_row.scalar_one() or 0

    offset = (page - 1) * page_size
    rows = await self.session.execute(
        select(CustomerEnrichment)
        .where(
            CustomerEnrichment.tenant_id == tenant_id,
            CustomerEnrichment.enriched_at < cutoff,
        )
        .order_by(CustomerEnrichment.enriched_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(rows.scalars().all())
    return items, total
```

**完成判定**：`ruff check src/services/enrichment_analytics_service.py` → 0 errors

---

### Step 4: 实现 `bulk_refresh(tenant_id)` + placeholder 调度方法

在 `bulk_refresh` 方法体内：
1. 查询陈旧 customer_id 列表：`select(CustomerEnrichment.customer_id).where(...)` 与 Step 3 相同的 stale 条件，LIMIT 1000（防止一次下发过多）
2. 将 customer_id 列表传入 `_dispatch_enrich_job(customer_ids)` placeholder
3. 返回 `{"dispatched_count": len(customer_ids)}`

```python
async def bulk_refresh(self, tenant_id: int) -> Dict:
    cutoff = func.now() - func.make_interval(days=30)
    rows = await self.session.execute(
        select(CustomerEnrichment.customer_id)
        .where(
            CustomerEnrichment.tenant_id == tenant_id,
            CustomerEnrichment.enriched_at < cutoff,
        )
        .limit(1000)
    )
    customer_ids = [r for r in rows.scalars().all()]
    self._dispatch_enrich_job(customer_ids)
    return {"dispatched_count": len(customer_ids)}

def _dispatch_enrich_job(self, customer_ids: List[int]) -> None:
    # TODO(#N): replace with real job dispatch (Celery task / background queue)
    pass
```

**完成判定**：`ruff check src/services/enrichment_analytics_service.py` → 0 errors

---

### Step 5: 编写 `tests/unit/test_enrichment_analytics_service.py`

按 CLAUDE.md 单元测试规范：
1. 从 `tests.unit.conftest` 导入 `MockState`、`make_mock_session` 及相关 handler factory
2. 定义 `mock_db_session` fixture，配置 `MockState()` + mock handler
3. 为 `get_stats` 写测试：total=0、total>0、by_provider 多个的场景
4. 为 `list_stale` 写测试：空结果、单页、多页、page=2 偏移正确的场景
5. 为 `bulk_refresh` 写测试：0 条、若干条返回正确的 dispatched_count
6. 每个测试用 `EnrichmentAnalyticsService(mock_db_session)` 实例化

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([/* handlers */])

@pytest.fixture
def service(mock_db_session):
    from services.enrichment_analytics_service import EnrichmentAnalyticsService
    return EnrichmentAnalyticsService(mock_db_session)

class TestGetStats:
    async def test_total_zero(self, service, tenant_id):
        result = await service.get_stats(tenant_id)
        assert result["total_customers"] == 0
        assert result["coverage_pct"] == 0.0

    async def test_coverage_calc(self, service, tenant_id):
        result = await service.get_stats(tenant_id)
        expected_pct = round(result["enriched_count"] / result["total_customers"] * 100, 2) if result["total_customers"] else 0.0
        assert result["coverage_pct"] == expected_pct

class TestListStale:
    async def test_empty(self, service, tenant_id):
        items, total = await service.list_stale(tenant_id, 1, 20)
        assert items == []
        assert total == 0

    async def test_pagination_offset(self, service, tenant_id):
        items, total = await service.list_stale(tenant_id, 2, 10)
        assert len(items) <= 10

class TestBulkRefresh:
    async def test_dispatched_count(self, service, tenant_id):
        result = await service.bulk_refresh(tenant_id)
        assert "dispatched_count" in result
        assert isinstance(result["dispatched_count"], int)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics_service.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/enrichment_analytics_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_enrichment_analytics_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/ -m "not integration" -v` → 无新增失败（如有其他 unit 测试）
- [ ] `alembic upgrade head` → exit 0（如涉及任何 migration）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `CustomerEnrichment` 模型字段名与预期不符（如 `enriched_at` 实际为 `updated_at`） | 低 | 中 | 调整 SQL 查询中的列名引用；路由端点不受影响，仅统计结果偏差 |
| `func.make_interval` 在某些 PostgreSQL 版本不可用 | 低 | 中 | 降级为 `func.now() - text('interval \'30 days\'')`（需 `from sqlalchemy import text`） |
| `bulk_refresh` placeholder 被误当真实调度上线 | 低 | 高 | `_dispatch_enrich_job` 保持为空函数；在实现真实调度前，`bulk_refresh` 仅记录日志；后续 issue #N 替换实现 |
| 单元测试 mock 配置遗漏多租户过滤 | 中 | 中 | 在 mock handler 中强制检查 `tenant_id` 参数，未传入或类型错误时 raise ValidationException |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/enrichment_analytics_service.py tests/unit/test_enrichment_analytics_service.py
git commit -m "feat(analytics): implement EnrichmentAnalyticsService with get_stats/list_stale/bulk_refresh"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#754): implement EnrichmentAnalyticsService" --body "Closes #754"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — Service 模式参考（构造函数、tenant_id 过滤、返回域对象）
- 第三方文档：[SQLAlchemy 2.x async aggregate functions](https://docs.sqlalchemy.org/en/20/core/functions.html) — `func.count`、`func.make_interval` 用法
- 父 issue / 关联：#513（父 epic）、#753（依赖：富化路由 + 3 端点）、#755（后继：单元测试）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
