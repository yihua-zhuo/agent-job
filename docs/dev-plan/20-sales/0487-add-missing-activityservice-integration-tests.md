# Sales · Add missing ActivityService integration tests

| 元数据 | 值 |
|---|---|
| Issue | #487 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [板 #486](), [板 #452]() |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The `ActivityService` currently has unit tests but is missing integration test coverage against a real PostgreSQL database. Unit tests with mocked SQL sessions cannot catch real query bugs, FK constraint violations, or async session misuse. Adding integration tests ensures the service behaves correctly when wired into the full FastAPI + SQLAlchemy 2.x async stack.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯测试覆盖率提升。

- **开发者视角**：CI gates on `pytest tests/integration/test_services_integration.py` passing, eliminating the risk that `ActivityService` method changes silently break the integration path. Developers gain regression safety when modifying `ActivityService` methods.

### 1.3 不做什么（剔除）

- [ ] Do not add unit tests for `ActivityService` — those already exist in `tests/unit/`.
- [ ] Do not add router-level HTTP tests (those belong in `tests/unit/test_<router>.py`).
- [ ] Do not modify `ActivityService` business logic — this board adds tests only.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_services_integration.py -k Activity -v` → all 5 tests pass
- `ruff check tests/integration/test_services_integration.py` → 0 errors
- `git diff tests/integration/test_services_integration.py --stat` shows ≥ 150 net new lines

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`tests/integration/test_services_integration.py` — 现有 `TestActivityIntegration` 类仅包含 skeleton（或不存在）；需确认文件是否存在并列出当前内容。

### 2.2 涉及文件清单

- 要改：
  - [`tests/integration/test_services_integration.py`](../../tests/integration/test_services_integration.py) — 向 `TestActivityIntegration` 添加 5 个新测试方法
- 要建：
  - `tests/integration/test_activity_integration.py` — 独立文件（如选择拆出而非改现有文件）

### 2.3 缺什么

- [ ] `test_get_opportunity_activities` — seeds customer + opportunity + 2 activities, asserts `len(result) == 2`
- [ ] `test_search_activities` — keyword search + type filter, asserts returned items match
- [ ] `test_get_activity_summary` — `by_type` breakdown + `recent_activities` field assertions
- [ ] `test_get_recent_activities` — seeds 3+ activities, asserts chronological order
- [ ] `test_get_activity_by_type` — seeds mixed types, asserts type filter isolation
- [ ] Integration fixtures (`db_schema`, `tenant_id`, `async_session`) wired to each new test

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_activity_integration.py` | 独立集成测试文件（若不复用现有 `test_services_integration.py`） |
| `tests/integration/test_opportunity_activity_integration.py` | TBD - 待确认：是否有此文件存在并复用 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/integration/test_services_integration.py`](../../tests/integration/test_services_integration.py) | 新增 5 个测试方法到 `TestActivityIntegration` 类 |

### 3.3 新增能力

- **Integration test**：`test_get_opportunity_activities(async_session, db_schema, tenant_id)` — seeds 1 customer + 1 opportunity + 2 activities, asserts `count == 2`
- **Integration test**：`test_search_activities(async_session, db_schema, tenant_id)` — keyword + type filter, asserts matching rows returned
- **Integration test**：`test_get_activity_summary(async_session, db_schema, tenant_id)` — asserts `by_type` dict and `recent_activities` list from real DB
- **Integration test**：`test_get_recent_activities(async_session, db_schema, tenant_id)` — asserts chronological ordering of returned activities
- **Integration test**：`test_get_activity_by_type(async_session, db_schema, tenant_id)` — asserts exact type filter isolation

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 `test_services_integration.py` 而非新建文件** — keeps all service-level integration tests in one place, consistent with existing project layout.
- **Use `db_schema` fixture (TRUNCATE CASCADE) over raw DB setup** — ensures each test starts from a clean state; `db_schema` auto-creates/drops tables per test function per `tests/integration/conftest.py`.
- **Seed via service layer (e.g. `CustomerService`) rather than raw SQL INSERT** — mirrors how the app actually creates data and exercises FK constraints.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest-asyncio` | `≥ 0.23` | Required for `async_session` fixture with `await` |
| `pytest` | `≥ 8.0` | Required for `db_schema` autouse fixture |

### 4.3 兼容性约束

- All integration tests must be marked `@pytest.mark.integration` and excluded from `pytest tests/unit/` runs.
- Tests must use `async_session` (function-scoped) — do not share a session across tests; `db_schema` truncates tables between tests.
- Seed data must include `tenant_id` on every multi-tenant table row; queries filtered by `tenant_id` in service methods must return consistent results.
- Assert exact field values from real DB rows — do not assert ORM identity (e.g. `id == 1`), assert field content instead.

### 4.4 已知坑

1. **`db_schema` truncates tables between tests but does not reset sequences** → `id` values from prior tests may persist into later tests → Avoid asserting exact integer IDs; assert field content instead.
2. **`async_session` is function-scoped but `db_schema` runs once per test function** → Ensure each test method seeds its own data before calling service methods.
3. **Integration tests require `DATABASE_URL` env var set to a live Postgres** → `docker compose -f configs/docker-compose.test.yml up -d test-db` must be run before `pytest tests/integration/`; document this in §6.

---

## 5. 实现步骤（按顺序）

### Step 1: Verify existing test file and ActivityService implementation

确认 `tests/integration/test_services_integration.py` 存在且 `TestActivityIntegration` 类可找到。确认 `ActivityService` 已实现 `get_opportunity_activities`、`search_activities`、`get_activity_summary`、`get_recent_activities`、`get_activity_by_type` 方法签名。

操作：
- a) Read `tests/integration/test_services_integration.py` to find `TestActivityIntegration` class
- b) Read `src/services/activity_service.py` (或对应文件) to confirm method signatures

**完成判定**：`PYTHONPATH=src python -c "from services.activity_service import ActivityService; print('import ok')"` → exit 0

### Step 2: Seed helper functions in tests/integration/conftest.py

If `_seed_customer`, `_seed_opportunity`, `_seed_activity` helpers do not exist in `conftest.py`, add them. These helpers must insert into real DB with correct `tenant_id`.

操作：
- a) Read `tests/integration/conftest.py`
- b) Add `_seed_customer`, `_seed_opportunity`, `_seed_activity` helpers if missing

示例代码（如有）：

```python
async def _seed_activity(session: AsyncSession, tenant_id: int, **kwargs) -> ActivityModel:
    row = ActivityModel(tenant_id=tenant_id, **kwargs)
    session.add(row)
    await session.flush()
    return row
```

**完成判定**：`PYTHONPATH=src python -c "from tests.integration.conftest import _seed_activity; print('seed helper ok')"` → exit 0

### Step 3: Add test_get_opportunity_activities

Seeds 1 customer + 1 opportunity + 2 `ActivityModel` rows (with `opportunity_id` FK), calls `ActivityService(session).get_opportunity_activities(opportunity_id, tenant_id)`, asserts `len(result) == 2`.

操作：
- a) Add `async def test_get_opportunity_activities` to `TestActivityIntegration`
- b) Call `_seed_customer`, `_seed_opportunity`, `_seed_activity` (×2) via helpers
- c) Call service method and assert count

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_services_integration.py::TestActivityIntegration::test_get_opportunity_activities -v` → 1 passed

### Step 4: Add test_search_activities

Seeds 3 activities with different `type` and `description` field values, calls `ActivityService(session).search_activities(query=..., activity_type=..., tenant_id=...)`, asserts returned items match filter criteria.

操作：
- a) Add `async def test_search_activities` to `TestActivityIntegration`
- b) Seed activities with distinct `type` values and searchable `description`
- c) Call service with keyword and type filter and assert exact matches

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_services_integration.py::TestActivityIntegration::test_search_activities -v` → 1 passed

### Step 5: Add test_get_activity_summary

Seeds 4+ activities of mixed types, calls `ActivityService(session).get_activity_summary(tenant_id)`, asserts `by_type` is a dict and `recent_activities` is a list with correct type counts.

操作：
- a) Add `async def test_get_activity_summary` to `TestActivityIntegration`
- b) Seed at least 4 activities with 2+ distinct types
- c) Call service and assert `by_type` dict keys/values and `recent_activities` ordering

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_services_integration.py::TestActivityIntegration::test_get_activity_summary -v` → 1 passed

### Step 6: Add test_get_recent_activities and test_get_activity_by_type

Seeds 3+ activities, calls `get_recent_activities`, asserts returned list is in descending chronological order. Then seeds mixed-type activities, calls `get_activity_by_type`, asserts only matching type returned.

操作：
- a) Add `async def test_get_recent_activities` — assert `result[0].created_at >= result[1].created_at`
- b) Add `async def test_get_activity_by_type` — assert all returned items have matching `activity_type`

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_services_integration.py::TestActivityIntegration -k "recent or by_type" -v` → 2 passed

### Step 7: Lint and verify all 5 new tests

Run ruff and full integration test suite to confirm all tests pass.

操作：
- a) `ruff check tests/integration/test_services_integration.py`
- b) `PYTHONPATH=src pytest tests/integration/test_services_integration.py -k Activity -v`

**完成判定**：`ruff check tests/integration/test_services_integration.py` exit 0 AND all 5 new tests pass

---

## 6. 验收

- [ ] `ruff check tests/integration/test_services_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_services_integration.py -k Activity -v` → 5 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` (no integration) → all unit tests still pass
- [ ] `git diff tests/integration/test_services_integration.py --stat` shows ≥ 150 net new lines added
- [ ] `docker compose -f configs/docker-compose.test.yml up -d test-db && PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" pytest tests/integration/test_services_integration.py::TestActivityIntegration -v` → all 5 passed (clean env run)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ActivityService` method signatures differ from what tests assume | 低 | 中 | Update test calls to match actual signatures; do not modify service |
| DB schema for `ActivityModel` differs from what seeds expect (missing columns) | 低 | 中 | Check `src/db/models/` for actual `ActivityModel` column names before seeding |
| `docker compose` not available in CI | 低 | 高 | CI uses `services:` block in GitHub Actions; this board documents docker requirement only for local dev |
| Tests pass in isolation but fail when run as a suite (shared state) | 低 | 高 | Each test seeds all its own data; `db_schema` truncates between tests |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/integration/test_services_integration.py
git add tests/integration/conftest.py  # if seed helpers added
git commit -m "test(integration): add ActivityService integration tests for #487"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(integration): add missing ActivityService integration tests" --body "Closes #487"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/integration/test_marketing_integration.py`](../../tests/integration/test_marketing_integration.py) — existing service integration test pattern in same directory
- 同类参考实现：[`tests/integration/test_opportunity_activity_integration.py`](../../tests/integration/test_opportunity_activity_integration.py) — existing opportunity-activity integration tests (verify if already exists)
- 父 issue：#452
- 关联：#486

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
