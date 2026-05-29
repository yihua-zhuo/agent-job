# 20-sales · Add Kanban filter controls and pipeline analytics panel

| 元数据 | 值 |
|---|---|
| Issue | #556 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 2 工作日 |
| 依赖 | [0555-add-kanban-board-endpoint](../20-sales/0555-add-kanban-board-endpoint.md) |
| 启用后赋能 | [0682-add-deal-comparison-orm-model-and-migration](./0682-add-deal-comparison-orm-model-and-migration.md) — deal comparison needs filtered opportunity counts |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The Kanban board endpoint (built in #555) currently returns all opportunities unfiltered. Sales managers need to slice the board by owner, date range, and deal value to focus on specific cohorts. Separately, the pipeline analytics panel — conversion rates, avg time-in-stage, win/loss ratio, and forecast-vs-actual — cannot be computed without new service methods that aggregate stage-level data from the `opportunities` table. Both features are standard in any CRM Kanban experience and are expected by end users.

### 1.2 做完后

- **用户视角**：A filter bar (owner dropdown, date range picker, value range slider) appears above the Kanban board. The board refreshes with filtered results. An analytics panel below the board shows conversion rates between adjacent stages, average time spent in each stage, win/loss ratio, and a forecast-vs-actual bar chart.
- **开发者视角**：`OpportunityAnalyticsService.list_opportunities` accepts `owner_id`, `date_from`, `date_to`, `amount_min`, `amount_max` filters and returns paginated `OpportunityModel` objects. `OpportunityAnalyticsService.get_pipeline_stats` returns per-stage counts, conversion rates, avg time-in-stage, and closed_won / closed_lost totals. Both methods are callable from the existing sales router.

### 1.3 不做什么（剔除）

- [ ] Frontend UI components (filter bar, analytics panel) — those belong in a dedicated frontend board.
- [ ] Forecast-vs-actual historical data aggregation — the current `opportunities` table lacks a historical snapshot table; the chart will be stubbed with a note that it requires a `opportunity_snapshots` table (future board).
- [ ] Alerting or SLA on stage durations — those belong in the analytics / SLA boards.

### 1.4 关键 KPI

- `ruff check src/services/opportunity_analytics_service.py src/api/routers/sales.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_opportunity_analytics_service.py -v` → ≥ 6 passed
- `PYTHONPATH=src pytest tests/integration/test_opportunity_analytics_integration.py -v` → 全 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `GET /sales/opportunities?owner_id=1&date_from=2025-01-01&date_to=2025-12-31&amount_min=1000&amount_max=500000` returns JSON with `items` array filtered accordingly

---

## 2. 当前现状（起点）

### 2.1 现有实现

The Kanban endpoint is wired in [`src/api/routers/sales.py`](../../src/api/routers/sales.py). The `GET /sales/kanban` handler calls `PipelineService` to fetch stages, then queries `OpportunityModel` grouped by stage — but applies no filters beyond `tenant_id`.

The `OpportunityModel` in [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) L17-L30 has `created_at` but no `stage_changed_at` — avg time-in-stage cannot be accurately computed for historical stages until a timestamp tracking last stage transition is added.

```17:30:src/db/models/opportunity.py
    stage: Mapped[str] = mapped_column(String(50), default="lead", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/sales.py`](../../src/api/routers/sales.py) — add filter query params to `GET /sales/kanban`; add `GET /sales/analytics/pipeline` endpoint
  - [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) — add `stage_changed_at: Mapped[datetime]` column
- 要建：
  - `src/services/opportunity_analytics_service.py` — new service with filtered list + pipeline stats methods
  - `alembic/versions/<id>_add_stage_changed_at_to_opportunities.py` — migration for new column
  - `tests/unit/test_opportunity_analytics_service.py` — unit tests using MockState/MockRow
  - `tests/integration/test_opportunity_analytics_integration.py` — integration tests against real DB

### 2.3 缺什么

- [ ] `OpportunityModel` has no `stage_changed_at` — avg time-in-stage is inaccurate for historical transitions.
- [ ] No `OpportunityAnalyticsService` — no service layer to apply filters or aggregate pipeline statistics.
- [ ] `GET /sales/kanban` does not accept `owner_id`, `date_from`, `date_to`, `amount_min`, `amount_max` params.
- [ ] No `GET /sales/analytics/pipeline` endpoint — analytics panel has no backend to call.
- [ ] `opportunities` table lacks a snapshot table for forecast-vs-actual historical comparison — the chart is stubbed until that schema exists.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/opportunity_analytics_service.py` | Service with `list_opportunities(tenant_id, filters)` and `get_pipeline_stats(tenant_id)` methods |
| `alembic/versions/<id>_add_stage_changed_at_to_opportunities.py` | Migration: adds `stage_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` with index to `opportunities` |
| `tests/unit/test_opportunity_analytics_service.py` | Unit tests: filter logic, pipeline stats computation, MockRow tenant isolation |
| `tests/integration/test_opportunity_analytics_integration.py` | Integration tests: real DB, seed opportunities across stages, assert stats correctness |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/sales.py`](../../src/api/routers/sales.py) | Extend `GET /sales/kanban` with `owner_id`, `date_from`, `date_to`, `amount_min`, `amount_max` query params; add `GET /sales/analytics/pipeline` handler |
| [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) | Add `stage_changed_at: Mapped[datetime]` column with `server_default=func.now()` and index |

### 3.3 新增能力

- **Service method**：`OpportunityAnalyticsService.list_opportunities(session, tenant_id, owner_id, date_from, date_to, amount_min, amount_max) -> tuple[list[OpportunityModel], int]`
- **Service method**：`OpportunityAnalyticsService.get_pipeline_stats(session, tenant_id) -> dict` — returns `{"stages": [{"name": "lead", "count": N, "avg_time_hours": H, "conversion_rate": 0.0}, ...], "win_loss_ratio": 0.0, "closed_won": N, "closed_lost": M}`
- **API endpoint**：`GET /sales/kanban?owner_id=1&date_from=2025-01-01&date_to=2025-12-31&amount_min=1000&amount_max=500000` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`GET /sales/analytics/pipeline` → `{"success": true, "data": {"stages": [...], "win_loss_ratio": 0.42, "closed_won": 12, "closed_lost": 8}}`
- **ORM model**：extend `OpportunityModel` with `stage_changed_at: Mapped[datetime]` column
- **Migration**：`alembic upgrade head` adds `stage_changed_at` column and index to `opportunities` table

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Analytics computed in SQL, not in Python** — computing per-stage counts, avg time, and conversion rates in SQL (via `func.count`, `func.avg`, `func.extract`) is far more efficient than loading all rows into Python. Use `GROUP BY stage` sub-queries joined in the service method.
- **stage_changed_at updated via trigger-like update-on-write** — the `stage_changed_at` column is set to `NOW()` on every `UPDATE` of the `stage` column. Implement this as an `before_flush` hook in the service layer (not a DB trigger) to keep the logic testable and portable.
- **Forecast-vs-actual stubbed** — without a historical snapshot table (`opportunity_snapshots`), the forecast chart cannot be accurate. A JSON `{"stub": true, "requires": "opportunity_snapshots table"}` is returned with a comment that a future board will wire in the snapshot table.

### 4.2 版本约束

TBD - 待补充：检查是否有新增依赖（如 `pandas`/`numpy` 用于统计计算）。若无，删除此段。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `OpportunityModel` 列名 `stage_changed_at` avoids collision with `Base.metadata`; `created_at` remains unchanged
- Router injects session via `session: AsyncSession = Depends(get_db)` — never `async with get_db()`
- Import paths: `from db.models.opportunity import OpportunityModel` (not `from src.db.models...`)

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()` for JSONB columns, and drops `timezone=True` on DateTime columns** → After running `--autogenerate`, manually review the migration file: ensure `DateTime(timezone=True)` is present for `stage_changed_at`, and use `server_default=func.now()` rather than a Python-side default.
2. **`OpportunityModel` cannot have a column named `metadata`** (conflicts with `Base.metadata` SQLAlchemy MetaData object) → the new column is named `stage_changed_at`, not `metadata`, so this does not apply — noted for future authors.
3. **PYTHONPATH must be `src`** → always run commands as `PYTHONPATH=src pytest ...` / `PYTHONPATH=src ruff check ...`

---

## 5. 实现步骤（按顺序）

### Step 1: Add stage_changed_at column to OpportunityModel

Add `stage_changed_at` to `OpportunityModel` in [`src/db/models/opportunity.py`](../../src/db/models/opportunity.py). Set `server_default=func.now()` so existing rows get a value. Add an index on `(tenant_id, stage_changed_at)` for range queries.

```python
# 在 updated_at 定义后添加
stage_changed_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), nullable=False
)
```

**完成判定**：`ruff check src/db/models/opportunity.py` → 0 errors

### Step 2: Generate Alembic migration for stage_changed_at column

Spin up a clean disposable database (`alembic_dev`) as documented in CLAUDE.md §Alembic Migrations. Run `alembic revision --autogenerate -m "add_stage_changed_at_to_opportunities"`. Manually verify the generated migration uses `DateTime(timezone=True)` and has the index.

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: Create OpportunityAnalyticsService

Create `src/services/opportunity_analytics_service.py` with two public methods:

- `list_opportunities(session, tenant_id, owner_id=None, date_from=None, date_to=None, amount_min=None, amount_max=None, page=1, page_size=50) -> tuple[list[OpportunityModel], int]`
  — builds SQLAlchemy `select()` with `WHERE tenant_id = :tenant_id` and filter conditions; returns paginated results.
- `get_pipeline_stats(session, tenant_id) -> dict`
  — `SELECT stage, COUNT(*), AVG(EXTRACT(EPOCH FROM (stage_changed_at - created_at))/3600) FROM opportunities WHERE tenant_id = :tenant_id GROUP BY stage` → computes conversion_rate per adjacent stage pair and win/loss ratio from `closed_won` / `closed_lost` counts.

The service constructor: `def __init__(self, session: AsyncSession): self.session = session` — no default, no None.

**完成判定**：`ruff check src/services/opportunity_analytics_service.py` → 0 errors

### Step 4: Write unit tests for OpportunityAnalyticsService

Create `tests/unit/test_opportunity_analytics_service.py`. Use `make_mock_session` with a `opportunity_handler` (or a new `make_opportunity_handler` in `conftest.py` if one doesn't exist). Test:
- Filter by `owner_id`: mock returns 3 rows, assert count = 3.
- Filter by `date_from`/`date_to`: mock returns 2 rows, assert count = 2.
- Filter by `amount_min`/`amount_max`: mock returns 1 row, assert count = 1.
- `get_pipeline_stats`: mock rows with stages `lead`, `qualified`, `closed_won`; assert conversion_rate for lead→qualified and win_loss_ratio.
- Tenant isolation: second tenant's rows not returned when first tenant_id is passed.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_analytics_service.py -v` → ≥ 6 passed

### Step 5: Update sales router with filter params and analytics endpoint

In [`src/api/routers/sales.py`](../../src/api/routers/sales.py):

a) Extend `GET /sales/kanban` handler to accept:
  - `owner_id: int | None = None`
  - `date_from: datetime | None = None`
  - `date_to: datetime | None = None`
  - `amount_min: Decimal | None = None`
  - `amount_max: Decimal | None = None`
  Pass all filters to `OpportunityAnalyticsService.list_opportunities`.

b) Add new handler `GET /sales/analytics/pipeline`:
  ```python
  @router.get("/analytics/pipeline")
  async def get_pipeline_analytics(
      ctx: AuthContext = Depends(require_auth),
      session: AsyncSession = Depends(get_db),
  ):
      svc = OpportunityAnalyticsService(session)
      stats = await svc.get_pipeline_stats(tenant_id=ctx.tenant_id)
      return {"success": True, "data": stats}
  ```
  Note on forecast-vs-actual stub: return `{"stages": [...], "win_loss_ratio": N, "forecast_vs_actual": {"stub": true}}`.

**完成判定**：`ruff check src/api/routers/sales.py` → 0 errors

### Step 6: Write integration tests

Create `tests/integration/test_opportunity_analytics_integration.py`. Use fixtures `db_schema`, `tenant_id`, `async_session`. Seed 10 opportunities across 4 stages with varying `owner_id`, `amount`, `created_at`. Assert:
- `GET /sales/kanban?owner_id=X` returns only X's opportunities.
- `GET /sales/kanban?amount_min=5000` filters correctly.
- `GET /sales/analytics/pipeline` returns correct stage counts and conversion rates.
- `alembic` migrations apply cleanly (covered by Step 2).

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_opportunity_analytics_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/opportunity_analytics_service.py src/api/routers/sales.py src/db/models/opportunity.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_analytics_service.py -v` → ≥ 6 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_opportunity_analytics_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：`curl "http://localhost:8000/sales/kanban?owner_id=1&amount_min=1000"` → `{"success": true, "data": {"items": [...], "total": N}}` (200 OK)
- [ ] 端到端：`curl "http://localhost:8000/sales/analytics/pipeline"` → `{"success": true, "data": {"stages": [...], "win_loss_ratio": N, "closed_won": N, "closed_lost": M}}` (200 OK)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic migration drops data or locks table on large `opportunities` table | 低 | 高 | Revert with `alembic downgrade -1`; if lock is a concern, use `ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS stage_changed_at` in a separate migration step |
| `stage_changed_at` backfill from `updated_at` for existing rows is expensive on large tables | 中 | 中 | Migration uses `server_default=func.now()` for new rows; for existing rows, add a data migration step: `UPDATE opportunities SET stage_changed_at = updated_at WHERE stage_changed_at IS NULL` — run during low-traffic window |
| Forecast-vs-actual chart requires `opportunity_snapshots` table not yet built | 中 | 低 | The `/analytics/pipeline` endpoint returns `forecast_vs_actual: {"stub": true, "requires": "opportunity_snapshots table"}` — downstream frontend board is not blocked, it shows a placeholder |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/opportunity_analytics_service.py \
       src/db/models/opportunity.py \
       src/api/routers/sales.py \
       alembic/versions/<id>_add_stage_changed_at_to_opportunities.py \
       tests/unit/test_opportunity_analytics_service.py \
       tests/integration/test_opportunity_analytics_integration.py
git commit -m "feat(sales): add Kanban filter controls and pipeline analytics panel (closes #556)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): Kanban filters and pipeline analytics (#556)" --body "Closes #556"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/pipeline_service.py`](../../src/services/pipeline_service.py) L1-L248 — existing pipeline stage service; follow the same service constructor pattern
- 第三方文档：[FastAPI query params](https://fastapi.tiangolo.com/tutorial/query-params/), [SQLAlchemy aggregate functions](https://docs.sqlalchemy.org/en/20/core/functions.html)
- 父 issue / 关联：#54 (parent), #555 (Kanban board endpoint — dependency)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
