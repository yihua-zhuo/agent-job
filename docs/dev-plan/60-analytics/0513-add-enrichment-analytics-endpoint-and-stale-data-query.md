# Analytics · Add enrichment stats and stale-data query endpoints

| 元数据 | 值 |
|---|---|
| Issue | #513 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #513 is a subtask of #74 (CRM enrichment pipeline). The enrichment system stores per-customer enrichment data but currently exposes no analytics view — operators cannot see coverage ratios, per-provider breakdowns, or which records are stale. Without these endpoints, stale-data驱动的运营完全依赖 manual SQL queries.

### 1.2 做完后

- **用户视角**：管理员可以通过 `GET /api/v1/enrichment/stats` 立即了解全量客户 enrichment 覆盖率，包括按 provider 分组的分布；通过 `GET /api/v1/enrichment/stale?page=1&page_size=20` 分页查看超过 30 天未更新的客户列表；通过 `POST /api/v1/enrichment/bulk-refresh` 一键触发全量 stale 记录重新 enrichment — 无需手动筛选或写 SQL。
- **开发者视角**：获得 `EnrichmentAnalyticsService`（含 `get_stats`、`list_stale`、`bulk_refresh` 方法）和 `enrichment` router（含 `GET /stats`、`GET /stale`、`POST /bulk-refresh`）。新增 `CustomerEnrichment` ORM model 可被其他 service 复用。

### 1.3 不做什么（剔除）

- [ ] 前端 UI 或 dashboard 改动（issue 明确 "No frontend changes"）
- [ ] Actual third-party enrichment API calls in `bulk-refresh` — the endpoint triggers the re-enrich job but the job itself is handled by the pipeline started in #512; this endpoint is a dispatch-only signal
- [ ] Push notification or Slack alerting on stale records

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → ≥ 6 passed]
- [指标 2：`ruff check src/services/enrichment_analytics_service.py src/api/routers/enrichment.py` → 0 errors]
- [指标 3：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0]
- [指标 4：`GET /api/v1/enrichment/stats` returns valid JSON with all required keys (`total_customers`, `enriched_count`, `coverage_pct`, `by_provider`, `stale_count`)]
- [指标 5：`GET /api/v1/enrichment/stale?page=1&page_size=5` returns paginated array of customer objects]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/` 下是否存在 `customer_service.py` 或 `enrichment_service.py` — 现有 enrichment 数据可能由 CustomerService 或单独的 EnrichmentService 管理。需要确认：
- 是否有 `CustomerEnrichment` 或类似 ORM model
- 是否有 `enrichment` 相关 router 路径前缀
- `customers` 表是否有 `enriched_at` / `enrichment_provider` / `enrichment_data` 字段

### 2.2 涉及文件清单

- 要改：
  - `src/services/customer_service.py` — 可能需要新增 enrichment 查询辅助方法（如有现有 enrichment service 则不动）
  - `tests/unit/test_customer_service.py` — 可能需补充 enrichment 相关 mock（如有现有测试则扩展）
- 要建：
  - `src/services/enrichment_analytics_service.py` — 核心 analytics service
  - `src/api/routers/enrichment.py` — 新 router，3 个 endpoint
  - `src/db/models/enrichment.py` — `CustomerEnrichment` ORM model（含 `tenant_id` 索引、`enriched_at` TIMESTAMPTZ、`provider` VARCHAR、`enrichment_data` JSONB、`stale_after_days` configurable 默认 30）
  - `alembic/versions/<id>_add_customer_enrichment_table.py` — migration
  - `tests/unit/test_enrichment_analytics.py` — 单元测试（mock DB）

### 2.3 缺什么

- [ ] 没有 `CustomerEnrichment` ORM model — 无法跨 service 共享 enrichment 数据结构
- [ ] 没有 `GET /api/v1/enrichment/stats` endpoint — 覆盖率数据无法通过 API 获取
- [ ] 没有 `GET /api/v1/enrichment/stale` endpoint — stale 记录列表无法查询
- [ ] 没有 `POST /api/v1/enrichment/bulk-refresh` endpoint — 无法通过 API 触发批量重新 enrichment
- [ ] `bulk-refresh` 是 dispatch-only（触发 pipeline，不做同步 enrichment call）— 需要与 #512 pipeline 协调接口

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/enrichment_analytics_service.py` | Analytics service：get_stats、list_stale、bulk_refresh 方法 |
| `src/api/routers/enrichment.py` | Router：3 个 enrichment endpoint |
| `src/db/models/enrichment.py` | `CustomerEnrichment` ORM model（含 `tenant_id` 索引、`enriched_at` TIMESTAMPTZ、`provider` VARCHAR、`enrichment_data` JSONB） |
| `alembic/versions/<id>_add_customer_enrichment_table.py` | 创建 `customer_enrichment` 表的 migration |
| `tests/unit/test_enrichment_analytics.py` | 6+ 个单元测试（mock DB） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/main.py` | 注册 `enrichment` router 到 `/api/v1/enrichment` 前缀 |
| `src/db/models/__init__.py` 或 `src/db/models/customer.py` | 导入 `CustomerEnrichment` model 以确保 alembic 可见 |

### 3.3 新增能力

- **ORM model**：`CustomerEnrichment` in `src/db/models/enrichment.py` — stores per-customer enrichment state (provider, timestamp, raw data JSONB)
- **Service**：`EnrichmentAnalyticsService(session: AsyncSession)` with:
  - `get_stats(tenant_id: int) -> dict` — returns `{total_customers, enriched_count, coverage_pct, by_provider: dict, stale_count}`
  - `list_stale(tenant_id: int, page: int, page_size: int, stale_after_days: int = 30) -> tuple[list[CustomerEnrichment], int]`
  - `bulk_refresh(tenant_id: int) -> dict` — dispatches re-enrich for all stale records, returns `{dispatched_count}`
- **API endpoints**：
  - `GET /api/v1/enrichment/stats` → `{"success": true, "data": {...}}`
  - `GET /api/v1/enrichment/stale?page=1&page_size=20&stale_after_days=30` → `{"success": true, "data": {"items": [...], "total": N}}`
  - `POST /api/v1/enrichment/bulk-refresh` → `{"success": true, "data": {"dispatched_count": N}}`
- **Migration**：`alembic upgrade head` 创建 `customer_enrichment` 表（含 `tenant_id` 索引、`enriched_at` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 separate `CustomerEnrichment` table 而非在 `Customer` model 上加列**：enrichment 数据是半结构化 JSONB，与主 customer 实体分离更干净，也避免单行膨胀。JSONB 可用 GIN 索引支持 payload 内字段查询。
- **bulk-refresh dispatch-only 而非同步 call**：同步调用会引入超时风险和外部 API 依赖；改为向 enrichment pipeline（从 #512 继承）发一条 dispatch message，由后台 worker 处理。
- **stale threshold 用可配置参数（默认 30 天）**：30 天是合理默认值，但不同客户群可能需要不同阈值。通过 query param `stale_after_days` 暴露给 API 调用方。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| SQLAlchemy | 2.x async | 见 CLAUDE.md |
| alembic | latest | 见 CLAUDE.md |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `CustomerEnrichment` 列名不用 `metadata`（与 `Base.metadata` 冲突）→ 用 `enrichment_data`
- Async session 注入用 `session: AsyncSession = Depends(get_db)`，不用 `async with get_db()`
- Import 路径：`from db.models...`、`from services...`，不用 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogen 会把 JSONB 写成 `sa.JSON()`** → 手动改回 `sa.JSONB()` in migration
2. **Alembic autogen 会把 TIMESTAMPTZ 写成 `DateTime` without `timezone=True`** → 手动加上 `timezone=True` for `enriched_at` column
3. **JSONB 列的 GIN 索引 migration 需要用 `sa.Index('ix_customer_enrichment_tenant_enriched', ...)` with `postgresql_using='gin'`** → 不要让 autogen 生成默认 B-tree 索引
4. **Service `__init__` 必须 `session: AsyncSession`（无 default）** → `bulk_refresh` 等方法需要 `tenant_id` param，不能让 `session` 有 default

---

## 5. 实现步骤（按顺序）

### Step 1: Define CustomerEnrichment ORM model

在 `src/db/models/enrichment.py` 创建新 model 文件：

```python
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class CustomerEnrichment(Base):
    __tablename__ = "customer_enrichment"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=True)
    enriched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enrichment_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    __table_args__ = (
        Index("ix_customer_enrichment_tenant_enriched", "tenant_id", "enriched_at"),
        Index("ix_customer_enrichment_tenant_customer", "tenant_id", "customer_id", unique=True),
    )
```

在 `src/db/models/__init__.py` 或 `src/db/models/customer.py` 底部添加导入以确保 alembic 可见。

**完成判定**：`ruff check src/db/models/enrichment.py` → 0 errors

---

### Step 2: Generate alembic migration

启动干净 DB：
```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
```

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "add customer_enrichment table"
```

手动修正生成的 migration：
- `enrichment_data` 列：`sa.JSON()` → `sa.JSONB()`
- `enriched_at` 列：加 `timezone=True`
- 删除自动生成的 default B-tree 索引，改为手动加 GIN 索引行（`Index("ix_customer_enrichment_data_gin", "enrichment_data", postgresql_using="gin")`）

验证：
```bash
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0

---

### Step 3: Implement EnrichmentAnalyticsService

在 `src/services/enrichment_analytics_service.py` 创建 service：

```python
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.enrichment import CustomerEnrichment
from db.models.customer import Customer  # for total count
from pkg.errors.app_exceptions import NotFoundException


class EnrichmentAnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_stats(self, tenant_id: int) -> dict:
        # total customers
        total_result = await self.session.execute(
            select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)
        )
        total_customers = total_result.scalar_one()

        # enriched count
        enriched_result = await self.session.execute(
            select(func.count(CustomerEnrichment.id))
            .where(CustomerEnrichment.tenant_id == tenant_id)
        )
        enriched_count = enriched_result.scalar_one()

        coverage_pct = round(enriched_count / total_customers * 100, 2) if total_customers > 0 else 0.0

        # by_provider breakdown
        provider_result = await self.session.execute(
            select(
                CustomerEnrichment.provider,
                func.count(CustomerEnrichment.id)
            )
            .where(CustomerEnrichment.tenant_id == tenant_id)
            .group_by(CustomerEnrichment.provider)
        )
        by_provider = {row[0] or "unknown": row[1] for row in provider_result.all()}

        # stale count (>30 days)
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)
        stale_result = await self.session.execute(
            select(func.count(CustomerEnrichment.id))
            .where(
                CustomerEnrichment.tenant_id == tenant_id,
                CustomerEnrichment.enriched_at < stale_threshold
            )
        )
        stale_count = stale_result.scalar_one()

        return {
            "total_customers": total_customers,
            "enriched_count": enriched_count,
            "coverage_pct": coverage_pct,
            "by_provider": by_provider,
            "stale_count": stale_count
        }

    async def list_stale(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        stale_after_days: int = 30
    ) -> tuple[list[CustomerEnrichment], int]:
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=stale_after_days)

        count_result = await self.session.execute(
            select(func.count(CustomerEnrichment.id))
            .where(
                CustomerEnrichment.tenant_id == tenant_id,
                CustomerEnrichment.enriched_at < stale_threshold
            )
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CustomerEnrichment)
            .where(
                CustomerEnrichment.tenant_id == tenant_id,
                CustomerEnrichment.enriched_at < stale_threshold
            )
            .order_by(CustomerEnrichment.enriched_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        items = result.scalars().all()
        return list(items), total

    async def bulk_refresh(self, tenant_id: int) -> dict:
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)
        result = await self.session.execute(
            select(CustomerEnrichment.customer_id)
            .where(
                CustomerEnrichment.tenant_id == tenant_id,
                CustomerEnrichment.enriched_at < stale_threshold
            )
        )
        stale_customer_ids = [row[0] for row in result.all()]
        # Dispatch re-enrich job (interface to #512 pipeline)
        for cid in stale_customer_ids:
            await self._dispatch_enrich_job(cid, tenant_id)
        return {"dispatched_count": len(stale_customer_ids)}

    async def _dispatch_enrich_job(self, customer_id: int, tenant_id: int) -> None:
        # Placeholder: actual dispatch via message queue (Redis/pg-queue) from #512
        pass
```

**完成判定**：`ruff check src/services/enrichment_analytics_service.py` → 0 errors

---

### Step 4: Register enrichment router

在 `src/main.py` 添加：

```python
from api.routers.enrichment import router as enrichment_router

app.include_router(enrichment_router, prefix="/api/v1/enrichment", tags=["Enrichment"])
```

在 `src/api/routers/enrichment.py` 创建 router：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.enrichment_analytics_service import EnrichmentAnalyticsService

router = APIRouter()

@router.get("/stats")
async def get_enrichment_stats(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    stats = await svc.get_stats(tenant_id=ctx.tenant_id)
    return {"success": True, "data": stats}


@router.get("/stale")
async def list_stale_enrichments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stale_after_days: int = Query(30, ge=1, le=365),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    items, total = await svc.list_stale(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        stale_after_days=stale_after_days
    )
    return {
        "success": True,
        "data": {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.post("/bulk-refresh")
async def bulk_refresh_enrichments(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = EnrichmentAnalyticsService(session)
    result = await svc.bulk_refresh(tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}
```

**完成判定**：`ruff check src/api/routers/enrichment.py` → 0 errors

---

### Step 5: Write unit tests

在 `tests/unit/test_enrichment_analytics.py` 编写测试（使用 `tests/unit/conftest.py` 的 mock 工具）：

- `test_get_stats_returns_correct_coverage` — mock customer count=100, enriched=30 → coverage_pct=30.0
- `test_get_stats_by_provider_grouping` — two providers → by_provider dict has both
- `test_list_stale_returns_paginated_results` — 5 stale records, page=1, page_size=2 → 2 items, total=5
- `test_list_stale_respects_stale_after_days_param` — threshold respects param value
- `test_bulk_refresh_dispatches_all_stale_records` — 3 stale → dispatched_count=3
- `test_stats_returns_zero_for_empty_tenant` — no customers → total=0, coverage=0.0

每个测试文件定义自己的 `mock_db_session` fixture：

```python
from tests.unit.conftest import make_mock_session, make_customer_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_customer_handler(state),
        make_enrichment_handler(state)  # add to conftest.py if not exists
    ])
```

如果 `make_enrichment_handler` 不存在，在 `tests/unit/conftest.py` 添加对应 handler（参考 CLAUDE.md §Unit Test SQL Mocks）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → 6 passed

---

### Step 6: Verify end-to-end with local server

启动本地 dev server（确保 `DATABASE_URL` 和 `PYTHONPATH=src` 已设置），然后：

```bash
# Stats endpoint
curl -s http://localhost:8000/api/v1/enrichment/stats \
  -H "Authorization: Bearer <token>" | python -m json.tool

# Expected: {"success": true, "data": {"total_customers": ..., "enriched_count": ..., "coverage_pct": ..., "by_provider": {}, "stale_count": ...}}

# Stale list
curl -s "http://localhost:8000/api/v1/enrichment/stale?page=1&page_size=5" \
  -H "Authorization: Bearer <token>" | python -m json.tool

# Expected: {"success": true, "data": {"items": [...], "total": ..., "page": 1, "page_size": 5}}

# Bulk refresh
curl -s -X POST http://localhost:8000/api/v1/enrichment/bulk-refresh \
  -H "Authorization: Bearer <token>" | python -m json.tool

# Expected: {"success": true, "data": {"dispatched_count": N}}
```

**完成判定**：三个 curl 均返回 `{"success": true, "data": {...}}`，无 422/500

---

## 6. 验收

- [ ] `ruff check src/services/enrichment_analytics_service.py src/api/routers/enrichment.py src/db/models/enrichment.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → 6 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0（如有 migration 变更）
- [ ] `GET /api/v1/enrichment/stats` 返回 valid JSON，含所有 required keys（`total_customers`, `enriched_count`, `coverage_pct`, `by_provider`, `stale_count`）
- [ ] `GET /api/v1/enrichment/stale?page=1&page_size=5` 返回 `{"items": [], "total": N, "page": 1, "page_size": 5}`
- [ ] `POST /api/v1/enrichment/bulk-refresh` 返回 `{"dispatched_count": N}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `bulk-refresh` dispatch 与 #512 pipeline 接口不匹配（#512 尚未完成） | 中 | 中 | `bulk_refresh` 目前返回 `dispatched_count` 但实际 dispatch 是 no-op placeholder；先完成 #512 后再实现真正的 dispatch logic；不阻塞 stats/stale endpoints |
| alembic migration 与已有 `customers` 表的 `enrichment_data` 列冲突（如原 schema 已有字段但命名不同） | 低 | 高 | 运行 `alembic history` + `alembic current` 确认当前 migration 状态；如有冲突，写补偿 migration 而非修改已有迁移 |
| JSONB GIN 索引拖慢写入性能（enrichment_data 频繁更新时） | 低 | 中 | 先不加 GIN 索引，用 B-tree 索引 on `enriched_at` 即可；按需加 GIN |
| 多租户 filter 遗漏导致数据泄露 | 低 | 高 | 每个 SQL query 审查确认含 `WHERE tenant_id = :tenant_id`；新增 `CustomerEnrichment` model 尤其需要检查 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/enrichment_analytics_service.py src/api/routers/enrichment.py src/db/models/enrichment.py tests/unit/test_enrichment_analytics.py alembic/versions/<id>_add_customer_enrichment_table.py
git commit -m "feat(analytics): add enrichment stats, stale query, and bulk-refresh endpoints

Closes #513"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add enrichment stats, stale query, and bulk-refresh endpoints" --body "Closes #513

## Summary
- Add GET /api/v1/enrichment/stats (coverage %, by_provider, stale_count)
- Add GET /api/v1/enrichment/stale (paginated, configurable stale_after_days)
- Add POST /api/v1/enrichment/bulk-refresh (dispatch re-enrich for stale records)
- Add CustomerEnrichment ORM model + alembic migration

## Test plan
- [ ] ruff check src/services/enrichment_analytics_service.py src/api/routers/enrichment.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v → 6 passed
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/customer_service.py` — 参考 service pattern（`__init__(session: AsyncSession)`, `tenant_id` filter, return ORM objects）
- 父 issue：#74
- 依赖 issue：#512
- ORM model 参考：`src/db/models/customer.py` — 参考 Base subclass、列定义、`to_dict()` pattern（router 层使用，service 层不调用）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
