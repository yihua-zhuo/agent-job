# [sales] · Add ActivityService unit tests

| 元数据 | 值 |
|---|---|
| Issue | #486 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.5 工作日 |
| 依赖 | [0487-add-missing-activityservice-integration-tests](./0487-add-missing-activityservice-integration-tests.md), [0485-add-missing-activityservice-methods](./0485-add-missing-activityservice-methods.md) |
| 启用后赋能 | [0487-add-missing-activityservice-integration-tests](./0487-add-missing-activityservice-integration-tests.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The `ActivityService` class in `src/services/activity_service.py` implements 9 methods (`create_activity`, `get_activity`, `update_activity`, `delete_activity`, `list_activities`, `get_customer_activities`, `get_opportunity_activities`, `search_activities`, `get_activity_summary`) but has zero unit test coverage. Without unit tests, regressions in multi-tenancy filtering, error-raising behavior, or return-type contracts go undetected. `tests/unit/test_activity_service.py` does not exist yet.

### 1.2 做完后

- **用户视角**：`无用户可见变化 — 纯底层测试补充`
- **开发者视角**：`pytest tests/unit/test_activity_service.py -v` runs ~20+ test cases covering success and error paths for every `ActivityService` method. Any future change that breaks a contract (e.g. wrong return type, missing `tenant_id` filter) is caught by CI before merge.

### 1.3 不做什么（剔除）

- [ ] Do not add integration tests — those live in `tests/integration/test_activity_service_integration.py`
- [ ] Do not refactor the `ActivityService` implementation itself (this board is purely test-addition)
- [ ] Do not mock at the HTTP router level; only test the service class

### 1.4 关键 KPI

- [指标 1：`pytest tests/unit/test_activity_service.py -v` → ≥ 18 passed]
- [指标 2：Every `ActivityService` method has ≥ 1 success-case test and ≥ 1 error-case test]
- [指标 3：`ruff check src/services/activity_service.py tests/unit/test_activity_service.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/activity_service.py`](../../src/services/activity_service.py) L{1}-L{200}

```python
# TBD - 待验证：src/services/activity_service.py — 预期包含
# class ActivityService with methods:
#   __init__(session: AsyncSession)  # no default
#   async create_activity(tenant_id, data) -> ActivityModel  # raises ValidationException on bad type
#   async get_activity(activity_id, tenant_id) -> ActivityModel  # raises NotFoundException
#   async update_activity(activity_id, tenant_id, data) -> ActivityModel
#   async delete_activity(activity_id, tenant_id) -> bool
#   async list_activities(tenant_id, page, page_size) -> tuple[list[ActivityModel], int]
#   async get_customer_activities(customer_id, tenant_id) -> list[ActivityModel]
#   async get_opportunity_activities(opportunity_id, tenant_id) -> list[ActivityModel]
#   async search_activities(tenant_id, query, filters) -> list[ActivityModel]
#   async get_activity_summary(tenant_id) -> dict
```

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_activity_service.py` — 新建；目前不存在
- 要建：
  - `tests/unit/test_activity_service.py` — 覆盖全部 9 个 service 方法

### 2.3 缺什么

- [ ] `tests/unit/test_activity_service.py` — the test file itself is entirely absent
- [ ] `mock_db_session` fixture — must be built from `MockState` + `make_mock_session` + `activity_sql_handler` (or equivalent per-table handler from `tests/unit/conftest.py`)
- [ ] Per-method success + error test cases for all 9 methods listed in §1.1
- [ ] Activity model mock (returns `.to_dict()` when serialized by router, service returns ORM object)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_activity_service.py` | 单元测试，覆盖全部 9 个 ActivityService 方法的 success + error 路径 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/activity_service.py` | 无改动（本板块仅加测试） |

### 3.3 新增能力

- **Service method**：`ActivityService` 全部 9 个方法已有测试覆盖
- **Test coverage**：≥ 18 test cases: create (success + 422 invalid type), get (success + 404), update, delete, list (paginated), get_customer_activities, get_opportunity_activities, search_activities, get_activity_summary — each with success + at least one error path

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock framework: `MockState` + `make_mock_session` from `tests/unit/conftest.py`**, not `unittest.mock.patch` — matches the established pattern in this repo; avoids global autouse patching and keeps tests fast (no DB I/O).
- **One fixture per test method** instead of a shared class-scoped fixture — each test owns its own `mock_db_session` so tests are fully isolated and order-independent.

### 4.2 版本约束

无新依赖引人。

### 4.3 兼容性约束

- 每个 mock handler 必须传递 `tenant_id` 到 WHERE 子句（multi-tenancy contract）
- Service method tests must verify the return type is an ORM/model object (not a dict)
- Error cases use `pytest.raises(AppException subclass)` to assert the exact exception type (`NotFoundException`, `ValidationException`, etc.)
- Do NOT assert on exception message strings — fragile; assert on exception type only

### 4.4 已知坑

1. **`MockRow` / `MockResult` must return an object with `.to_dict()`** for tests that serialize the result in a router context → 规避：mock `ActivityModel` instances with a plain object having a `.to_dict()` method returning a dict, not a SQLAlchemy `Row`.
2. **Async test methods must be `async def` + `await` the service call** → 规避：mark test function `async def` and `await` each `svc.method(...)` call; forgetting `await` silently passes without running the coroutine.
3. **`mock_db_session` fixture must not be autouse** → 规避：explicitly pass it as a parameter to each test function; `autouse=True` would pollute other tests in the same file.

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 ActivityService 接口与现有 handler 模式

调查 `src/services/activity_service.py` 确认 9 个方法的签名、返回类型、异常类型。同时检查 `tests/unit/conftest.py` 中是否有 `activity_sql_handler` 或需要新建 handler。

操作：
- a) 阅读 `src/services/activity_service.py` 全文件，记录方法签名、tenant_id 过滤位置、raise 语句
- b) 阅读 `tests/unit/conftest.py` 中的 `make_mock_session`、`MockState`、现有 handler 工厂（`make_customer_handler` 等）作为参考模式
- c) 确认是否有现成的 activity SQL handler；若无，在 conftest.py 中参照 `make_customer_handler` 的结构新建一个 `make_activity_handler(state)` — 必须是 stateful（auto-increment ID），返回 `MockRow` / `MockResult`

**完成判定**：`grep -n "def.*activity" src/services/activity_service.py` → ≥ 9 method lines found

---

### Step 2: 创建 tests/unit/test_activity_service.py 骨架

新建文件，从 `tests/unit/conftest.py` 导入所需 fixtures，定义 `mock_db_session` fixture 使用 `make_activity_handler(state)`。

操作：
- a) 在 `tests/unit/test_activity_service.py` 顶部写入：

```python
import pytest
from tests.unit.conftest import (
    make_mock_session,
    MockState,
    make_activity_handler,   # 可能需要新建，见 Step 1
)

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_activity_handler(state)])

@pytest.fixture
def activity_service(mock_db_session):
    from services.activity_service import ActivityService
    return ActivityService(mock_db_session)
```

- b) 添加一个占位 `async def test_smoke(mock_db_session, activity_service): assert True` 通过 pytest 验证 fixture chain 无报错

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → `1 passed`

---

### Step 3: 测试 create_activity 成功路径

操作：
- a) 在 `mock_db_session` 的 handler state 中预置一个 valid activity 记录（id=1, tenant_id=1）
- b) 调用 `activity_service.create_activity(tenant_id=1, data={...})`
- c) `assert isinstance(result, ActivityModel)` — service 返回 ORM 对象，不是 dict

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py::test_create_activity_success -v` → `1 passed`

---

### Step 4: 测试 create_activity 错误路径（无效 type → 422）

操作：
- a) 调用 `activity_service.create_activity(tenant_id=1, data={"type": "invalid_type"})`
- b) `with pytest.raises(ValidationException): ...` 捕获
- c) 注意：不测试 HTTP 状态码 422，那是 router 层的事；service 层抛出 `ValidationException`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py::test_create_activity_invalid_type -v` → `1 passed`

---

### Step 5: 测试 get_activity 成功 + 404

操作：
- a) 预置 activity(id=1, tenant_id=1) 在 mock state 中
- b) `result = await svc.get_activity(1, tenant_id=1)` → assert isinstance(result, ActivityModel)
- c) `with pytest.raises(NotFoundException): await svc.get_activity(999, tenant_id=1)`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -k "get_activity" -v` → `2 passed`

---

### Step 6: 测试 update_activity 和 delete_activity

操作：
- a) `update_activity`: 预置 activity，找得到，调用 update，assert return 是 ActivityModel；找不到 → `NotFoundException`
- b) `delete_activity`: 预置 activity，调用 delete，assert return 是 bool True；非本人 tenant_id → `ForbiddenException` 或 `NotFoundException`（按实现）
- c) 每条路径加一个 error case

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -k "update_activity or delete_activity" -v` → `≥ 4 passed`

---

### Step 7: 测试 list_activities（分页）+ get_customer_activities + get_opportunity_activities

操作：
- a) 预置 3 条 activity 记录（tenant_id=1）
- b) `items, total = await svc.list_activities(tenant_id=1, page=1, page_size=10)` → assert len(items) == 3, total == 3
- c) 空列表 case：`with pytest.raises(NotFoundException):` 或 assert items == []（按实现决定）
- d) `get_customer_activities(customer_id=1, tenant_id=1)`: 预置 activity，assert list return；不匹配 tenant_id → empty
- e) 同上 for `get_opportunity_activities`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -k "list_activities or get_customer_activities or get_opportunity_activities" -v` → `≥ 5 passed`

---

### Step 8: 测试 search_activities + get_activity_summary

操作：
- a) `search_activities(tenant_id=1, query="deal", filters={})`: 预置 activity with matching title/description，assert return list non-empty；无结果 → return []
- b) `get_activity_summary(tenant_id=1)`: assert return is dict with keys e.g. `total`, `by_type`；empty DB → all zeros

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -k "search_activities or get_activity_summary" -v` → `2 passed`

---

## 6. 验收

- [ ] `ruff check src/services/activity_service.py tests/unit/test_activity_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → ≥ 18 passed
- [ ] 每个 ActivityService 方法至少有 1 个 success-case test 和 1 个 error-case test（通过 `-k` filter 验证方法数量）
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → no collection errors in `test_activity_service.py`
- [ ] `ruff format tests/unit/test_activity_service.py` → 0 diff

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `make_activity_handler` 需要从零实现但 conftest.py 不允许新增 handler 模式 | 低 | 中 | 参照 `make_customer_handler` 的结构完整复制；唯一区别是表名和字段名 |
| ActivityService 方法签名与预期不符导致测试编译失败 | 中 | 中 | 读取实际签名后调整测试参数；不在本步骤重构实现代码 |
| 测试数量不足（< 18 passed）导致 CI 失败 | 低 | 低 | 补充缺失方法的对偶测试（success + error 各 1 条） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_activity_service.py
git commit -m "test(activity): add unit tests for ActivityService (#486)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: add ActivityService unit tests (#486)" --body "Closes #486"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py)
- 同类参考实现：[`tests/unit/conftest.py`](../../tests/unit/conftest.py) — MockState / make_mock_session 模式
- 父 issue / 关联：#452（父），#485（依赖），#487（后续赋能）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
