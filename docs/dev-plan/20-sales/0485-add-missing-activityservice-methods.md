# ActivityService · Add missing get_recent_activities and get_activity_by_type

| 元数据 | 值 |
|---|---|
| Issue | #485 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0486-add-activityservice-unit-tests](0486-add-activityservice-unit-tests.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/services/activity_service.py` currently lacks two referenced methods — `get_recent_activities` and `get_activity_by_type` — that are required by downstream consumers. Without them, callers have no supported API to fetch ordered activity feeds or filter by `ActivityType`. The router `src/api/routers/activities.py` also lacks corresponding endpoints, so the new service methods remain unreachable over HTTP.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 service/router 补全。
- **开发者视角**：`ActivityService.get_recent_activities(tenant_id, limit)` returns the N most-recent activity rows ordered by `created_at DESC`. `ActivityService.get_activity_by_type(tenant_id, activity_type, page, page_size)` returns a paginated slice filtered by `ActivityType` enum. Two new router endpoints expose these over HTTP.

### 1.3 不做什么（剔除）

- [ ] No new ORM model or migration — the `activities` table already exists.
- [ ] No authentication middleware changes — reuse `require_auth` / `AuthContext` as-is.
- [ ] No `get_activity_by_id` or update/delete CRUD — out of scope.

### 1.4 关键 KPI

- [`PYTHONPATH=src pytest tests/unit/test_activity_service.py -v`](../../tests/unit/test_activity_service.py) → ≥2 passed (one per new method)
- [`ruff check src/services/activity_service.py src/api/routers/activities.py`](../../src/services/activity_service.py) → 0 errors
- Both methods include `tenant_id` in every SQL WHERE clause (checked via grep in review)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/activity_service.py` —现有 ActivityService 类结构（含现有方法签名） L?

TBD - 待验证：`src/api/routers/activities.py` — 现有 router endpoints 列表 L?

TBD - 待验证：`src/db/models/` 中 activity相关的 ORM model 文件名

### 2.2 涉及文件清单

- 要改：
  - [`src/services/activity_service.py`](../../src/services/activity_service.py) — 新增 `get_recent_activities` 和 `get_activity_by_type` 两个 method
  - [`src/api/routers/activities.py`](../../src/api/routers/activities.py) — 新增两个对应 router endpoints
- 要建：
  - `tests/unit/test_activity_service.py` — 覆盖两个新方法的 unit test（含 mock_db_session fixture）
  - `tests/integration/test_activity_service_integration.py` — 覆盖两个新方法的 integration test

### 2.3 缺什么

- [ ] `ActivityService.get_recent_activities(tenant_id, limit)` method — limit-based query, ordered by `created_at DESC`, filtered by `tenant_id`
- [ ] `ActivityService.get_activity_by_type(tenant_id, activity_type, page, page_size)` method — filter by `ActivityType` enum, paginated, filtered by `tenant_id`
- [ ] `GET /activities/recent?limit=N` router endpoint exposing `get_recent_activities`
- [ ] `GET /activities/by-type/{activity_type}?page=N&page_size=N` router endpoint exposing `get_activity_by_type`
- [ ] Unit tests for both new service methods
- [ ] Integration tests for both new service methods

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_activity_service.py` | Unit tests for `get_recent_activities` and `get_activity_by_type` |
| `tests/integration/test_activity_service_integration.py` | Integration tests using real Postgres for both new methods |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/activity_service.py`](../../src/services/activity_service.py) | 新增 `get_recent_activities` 和 `get_activity_by_type` 两个 async 方法 |
| [`src/api/routers/activities.py`](../../src/api/routers/activities.py) | 新增 `GET /activities/recent` 和 `GET /activities/by-type/{activity_type}` 两个 endpoints |

### 3.3 新增能力

- **Service method**：`ActivityService.get_recent_activities(self, tenant_id: int, limit: int = 10) -> list[ActivityModel]` — ordered `created_at DESC`, `tenant_id` filtered, raises `ValidationException` if `limit <= 0`
- **Service method**：`ActivityService.get_activity_by_type(self, tenant_id: int, activity_type: ActivityType, page: int = 1, page_size: int = 20) -> tuple[list[ActivityModel], int]` — filtered + paginated, `tenant_id` filtered, raises `ValidationException` if `page< 1` or `page_size` out of range
- **API endpoint**：`GET /activities/recent?limit=10` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`GET /activities/by-type/{activity_type}?page=1&page_size=20` → `{"success": true, "data": {"items": [...], "total": N}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Paginate `get_activity_by_type` but not `get_recent_activities`**：`get_recent_activities` is a lightweight "last N" helper (like a notification tray); `get_activity_by_type` is a proper list that can grow unbounded, so it returns `(items, total)` for pagination.
- **Filter by enum member, not string**：The `ActivityType` Pydantic enum is passed as a path/query parameter — router validates it via FastAPI's built-in enum parsing, avoiding string-cast bugs.

### 4.2 版本约束

<!-- 无新依赖引入，整段保持空白 -->

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service `__init__` takes `session: AsyncSession` — no default value, no `= None`
- Service raises `AppException` subclasses; router does NOT wrap in try/catch
- Router serializes via `.to_dict()` — service returns ORM objects only

### 4.4 已知坑

1. **SQLAlchemy `text()` required for raw ORDER BY / LIMIT** →规避：使用 SQLAlchemy `select(...).order_by(desc(...)).limit(...)` chaining; no raw `text()` needed for these simple queries.
2. **ActivityType enum in path parameter** →规避：router uses `activity_type: ActivityType = Path(...)` so FastAPI handles validation + 422 on unknown value.
3. **Unit test mock session** →规避：reuse `tests/unit/conftest.py` pattern — define local `mock_db_session` fixture per test file with `make_activity_handler(state)` if available, or extend existing handlers.

---

## 5. 实现步骤（按顺序）

### Step 1: Add service methods to ActivityService

在 `src/services/activity_service.py` 中新增两个 async 方法。

**`get_recent_activities`：**

```python
async def get_recent_activities(
    self, tenant_id: int, limit: int = 10
) -> list[ActivityModel]:
    if limit <= 0:
        raise ValidationException("limit must be a positive integer")
    stmt = (
        select(ActivityModel)
        .where(ActivityModel.tenant_id == tenant_id)
        .order_by(desc(ActivityModel.created_at))
        .limit(limit)
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())
```

**`get_activity_by_type`：**

```python
async def get_activity_by_type(
    self,
    tenant_id: int,
    activity_type: ActivityType,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ActivityModel], int]:
    if page < 1:
        raise ValidationException("page must be >= 1")
    if not (1 <= page_size <= 100):
        raise ValidationException("page_size must be between 1 and 100")
    offset = (page - 1) * page_size
    base_where = [
        ActivityModel.tenant_id == tenant_id,
        ActivityModel.activity_type == activity_type,
    ]
    count_stmt = select(func.count(ActivityModel.id)).where(*base_where)
    count_res = await self.session.execute(count_stmt)
    total = count_res.scalar_one()
    list_stmt = (
        select(ActivityModel)
        .where(*base_where)
        .order_by(desc(ActivityModel.created_at))
        .offset(offset)
        .limit(page_size)
    )
    list_res = await self.session.execute(list_stmt)
    return list(list_res.scalars().all()), total
```

在文件顶部确保已有 `from sqlalchemy import func, select, desc` 及 `from pkg.errors.app_exceptions import ValidationException`。

**完成判定**：`ruff check src/services/activity_service.py` →0 errors

### Step 2: Add router endpoints in activities.py

在 `src/api/routers/activities.py` 新增两个 endpoint 方法。 route handler 使用 `Depends(get_db)` 和 `Depends(require_auth)`，不自行管理 session。

在文件顶部确保已有 `from models.activity import ActivityType`（或对应的 enum导入路径——TBD - 待验证：ActivityType enum实际路径）。

```python
@router.get("/recent", response_model=ApiResponse[dict])
async def get_recent_activities(
    limit: int = 10,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ActivityService(session)
    activities = await svc.get_recent_activities(tenant_id=ctx.tenant_id, limit=limit)
    return {"success": True, "data": {"items": [a.to_dict() for a in activities], "total": len(activities)}}

@router.get("/by-type/{activity_type}", response_model=ApiResponse[dict])
async def get_activities_by_type(
    activity_type: ActivityType,
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ActivityService(session)
    activities, total = await svc.get_activity_by_type(
        tenant_id=ctx.tenant_id,
        activity_type=activity_type,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "data": {
            "items": [a.to_dict() for a in activities],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
```

**完成判定**：`ruff check src/api/routers/activities.py` → 0 errors

### Step 3: Write unit tests in tests/unit/test_activity_service.py

新建 `tests/unit/test_activity_service.py`，按 CLAUDE.md § Adding New Features 的模式定义 `mock_db_session` fixture。

测试用例（每个方法至少覆盖 success + error path）：

```python
# get_recent_activitiesasync def test_get_recent_activities_returns_ordered(mock_db_session):
    svc = ActivityService(mock_db_session)
    # seed3 activities, newest first
    result = await svc.get_recent_activities(tenant_id=1, limit=2)
    assert len(result) == 2
 assert result[0].created_at >= result[1].created_at

async def test_get_recent_activities_rejects_non_positive_limit(mock_db_session):
    svc = ActivityService(mock_db_session)
    with pytest.raises(ValidationException):
        await svc.get_recent_activities(tenant_id=1, limit=0)

# get_activity_by_type
async def test_get_activity_by_type_paginates(mock_db_session):
    svc = ActivityService(mock_db_session)
    items, total = await svc.get_activity_by_type(tenant_id=1, activity_type=ActivityType.CALL, page=1, page_size=5)
    assert total >= 0
    assert len(items) <=5

async def test_get_activity_by_type_rejects_invalid_page(mock_db_session):
    svc = ActivityService(mock_db_session)
    with pytest.raises(ValidationException):
        await svc.get_activity_by_type(tenant_id=1, activity_type=ActivityType.CALL, page=0)
```

如 `make_activity_handler` 不存在，在 `tests/unit/conftest.py` 中新增一个（参考 `make_customer_handler` 的模式）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → ≥ 4 passed

### Step 4: Write integration tests

新建 `tests/integration/test_activity_service_integration.py`，使用 `db_schema`、`tenant_id`、`async_session` fixtures。

```python
@pytest.mark.integration
class TestActivityServiceIntegration:
    async def test_get_recent_activities(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        # assume _seed_activity helper exists, or use raw insert
        result = await svc.get_recent_activities(tenant_id=tenant_id, limit=5)
        assert isinstance(result, list)

    async def test_get_activity_by_type(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        items, total = await svc.get_activity_by_type(tenant_id=tenant_id, activity_type=ActivityType.CALL, page=1, page_size=10)
        assert isinstance(items, list)
        assert isinstance(total, int)

    async def test_get_activity_by_type_tenant_isolation(self, db_schema, tenant_id, async_session):
        svc = ActivityService(async_session)
        other_tenant = tenant_id + 999        items, total = await svc.get_activity_by_type(tenant_id=other_tenant, activity_type=ActivityType.CALL, page=1, page_size=10)
        assert total == 0
        assert items == []
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_activity_service_integration.py -v` → ≥3 passed

---

## 6. 验收

- [ ] `ruff check src/services/activity_service.py src/api/routers/activities.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → ≥ 4 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_activity_service_integration.py -v` → ≥ 3 passed
- [ ] `grep -r "tenant_id" src/services/activity_service.py | grep -c "ActivityModel.*tenant_id\|tenant_id.*=="` → ≥ 4（每条 SQL都有 tenant_id 过滤）
- [ ] `PYTHONPATH=src mypy src/services/activity_service.py src/api/routers/activities.py` → 0 errors（类型检查通过）

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ActivityType` enum path/import位置与本板块假设不符，导致 import 失败 | 低 | 中 | 调整 import路径后重跑 ruff check；改动局限在 import 行 |
| 新方法 SQL产生 N+1 查询或缺索引导致性能差（activity 表数据量大） | 低 | 中 | 添加 `tenant_id + created_at DESC`索引（需新建 alembic migration，后续板块处理） |
| 现有单元测试 mock 与新方法签名不兼容，破坏 CI | 低 | 高 | 仅修改 `test_activity_service.py`；其他 test 文件不受影响 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/activity_service.py src/api/routers/activities.py
git add tests/unit/test_activity_service.py tests/integration/test_activity_service_integration.py
git commit -m "feat(sales): add get_recent_activities and get_activity_by_type to ActivityService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#485): add missing ActivityService methods" --body "Closes #485"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — `get_recent_*` + `get_by_type`模式参考
- 同类参考实现：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) — paginated list pattern (`tuple[list, int]` return)
- 父 issue /关联：#452
