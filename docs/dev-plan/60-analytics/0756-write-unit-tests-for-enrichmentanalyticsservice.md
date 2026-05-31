# EnrichmentAnalyticsService · Write unit tests for EnrichmentAnalyticsService

| 元数据 | 值 |
|---|---|
| Issue | #756 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：父 issue #755 EnrichmentAnalyticsService 实现 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`EnrichmentAnalyticsService` 已通过 #755 实现，但其单元测试尚未覆盖。缺少测试意味着任何对 service逻辑的修改都无法被及时发现，容易引入回归。当前代码库要求每个 service 必须有对应的单元测试（见 CLAUDE.md §「添加新功能 → 新单元测试」），这是质量门的必要组成部分。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层测试工作
- **开发者视角**：`tests/unit/test_enrichment_analytics.py` 包含 6 个 test cases，覆盖 `get_stats`、`list_stale`、`bulk_refresh` 三个核心方法。后续修改 service 逻辑时 CI 自动验证回归

### 1.3 不做什么（剔除）

- [ ] 不实现新的 service 方法（仅补充测试）
- [ ] 不修改 `EnrichmentAnalyticsService` 源码
- [ ] 不编写集成测试（集成测试在 `tests/integration/` 下，后续由另一 issue覆盖）
- [ ] 不覆盖 `#755` 中未实现的接口

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → `6 passed`
- `ruff check src/services/enrichment_analytics_service.py tests/unit/test_enrichment_analytics.py` → 0 errors
- `ruff check tests/unit/conftest.py` →0 errors（如需新增 `make_enrichment_handler`）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/enrichment_analytics_service.py` L? —需确认 `EnrichmentAnalyticsService` 的 `__init__`签名、`get_stats`、`list_stale`、`bulk_refresh` 方法签名及返回类型

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/conftest.py` — 若 `make_enrichment_handler` 不存在，需新增
  - `tests/unit/test_enrichment_analytics.py` — 新建，6 个 test cases
- 要建：
  - `tests/unit/test_enrichment_analytics.py` — 单元测试文件

### 2.3 缺什么

- [ ] `tests/unit/conftest.py` 中无 `make_enrichment_handler`（需先确认 #755 是否已添加）
- [ ] `tests/unit/test_enrichment_analytics.py` 不存在，无任何 test case
- [ ] `EnrichmentAnalyticsService` 的三个核心方法（`get_stats`、`list_stale`、`bulk_refresh`）均无单元测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_enrichment_analytics.py` | EnrichmentAnalyticsService 单元测试，6 个 test cases |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/conftest.py` | 新增 `make_enrichment_handler(state)` 和对应 SQL mock handler（如 #755 尚未添加） |

### 3.3 新增能力

- **Test case**：`test_get_stats_returns_correct_coverage` — total=100, enriched=30 → coverage_pct=30.0
- **Test case**：`test_get_stats_by_provider_grouping` — 两个 provider → by_provider dict包含两者
- **Test case**：`test_list_stale_returns_paginated_results` — 5 stale, page=1, page_size=2 → 2 items, total=5
- **Test case**：`test_list_stale_respects_stale_after_days_param` — 验证 stale_after_days 参数过滤
- **Test case**：`test_bulk_refresh_dispatches_all_stale_records` — 3 stale → dispatched_count=3
- **Test case**：`test_stats_returns_zero_for_empty_tenant` — 空 tenant 返回全零 stats

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 mock_db_session 而非真实 DB**：单元测试必须无 DB依赖，遵循 CLAUDE.md §「Unit Test SQL Mocks」规则
- **每个 test file 定义自己的 mock_db_session fixture**：不复用其他文件的 fixture，确保测试自包含

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：mock handler 的 SELECT 查询必须 `WHERE tenant_id = :tenant_id`
- Service错误抛 `AppException` 子类；测试用 `pytest.raises()`验证错误路径
- 测试文件中 `mock_db_session` fixture 仅注入本 service需要的 handler，不注入无关 domain handler

### 4.4 已知坑

1. **conftest.py 中无 `make_enrichment_handler`** → 规避：先检查 `conftest.py` 是否已定义；若未定义，需在 `conftest.py` 中参照 `make_customer_handler` 等模式新增 handler
2. **SQLAlchemy 列名避免 `metadata`** →规避：若 enrichment 表有 `metadata` 列，mock handler映射时用 `event_metadata` 或 `payload` 作为 Python 属性名，避免与 `Base.metadata` 冲突
3. **PYTHONPATH=src** →规避：所有 pytest 命令前加 `PYTHONPATH=src`，确保 import路径正确

---

## 5. 实现步骤（按顺序）

### Step 1:确认 conftest.py 中 make_enrichment_handler 是否已存在

在 `tests/unit/conftest.py` 中搜索 `make_enrichment_handler` 函数定义。若不存在，参照 `make_customer_handler` 的工厂模式新增：

```python
def make_enrichment_handler(state: MockState) -> dict[str, Callable]:
    """Handler for enrichment_analytics table mock."""
    def handle(session, stmt):
        # SELECT: WHERE tenant_id + optional stale_after_days filter
        # COUNT: total count
        # UPDATE: mark as refreshed
        ...
    return {
        "select": handle,
        "count": handle,
        "update": handle,
    }
```

同时在 `MockState` 中注册 `enrichment_analytics` 表：

```python
class MockState:
    def __init__(self):
        self.customers = []
        self.users = []
        self.enrichment_analytics = []  # 新增
```

**完成判定**：`ruff check tests/unit/conftest.py` →0 errors

---

### Step 2: 创建 tests/unit/test_enrichment_analytics.py，定义 mock_db_session fixture

```python
import pytest
from tests.unit.conftest import make_mock_session, make_enrichment_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_enrichment_handler(state)])

@pytest.fixture
def enrichment_service(mock_db_session):
    from services.enrichment_analytics_service import EnrichmentAnalyticsService
    return EnrichmentAnalyticsService(mock_db_session)
```

**完成判定**：`ruff check tests/unit/test_enrichment_analytics.py` → 0 errors

---

### Step 3: 实现 test_get_stats_returns_correct_coverage

在 `MockState.enrichment_analytics` 中插入 100 条记录（其中 30 条 `enriched_at` 非 NULL），调用 `svc.get_stats(tenant_id=1)`，断言 `coverage_pct == 30.0`：

```python
async def test_get_stats_returns_correct_coverage(enrichment_service, mock_db_session):
    state = mock_db_session._state
    tenant_id = 1
    #30 条已 enrichment
    for _ in range(30):
        state.enrichment_analytics.append({
            "id": len(state.enrichment_analytics) + 1,
            "tenant_id": tenant_id,
            "enriched_at": "2026-01-01T00:00:00Z",
        })
    # 70 条未 enrichment
    for _ in range(70):
        state.enrichment_analytics.append({
            "id": len(state.enrichment_analytics) + 1,
            "tenant_id": tenant_id,
            "enriched_at": None,
        })

    stats = await enrichment_service.get_stats(tenant_id=tenant_id)
    assert stats.total == 100
    assert stats.enriched == 30
    assert stats.coverage_pct == 30.0
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_get_stats_returns_correct_coverage -v` → `1 passed`

---

### Step 4: 实现 test_get_stats_by_provider_grouping

插入两个不同 provider 的记录，验证 `by_provider` dict 包含两者：

```python
async def test_get_stats_by_provider_grouping(enrichment_service, mock_db_session):
    state = mock_db_session._state
    tenant_id = 1
    providers = ["provider_a", "provider_b"]
    for provider in providers:
        for _ in range(5):
            state.enrichment_analytics.append({
                "id": len(state.enrichment_analytics) + 1,
                "tenant_id": tenant_id,
                "provider": provider,
                "enriched_at": "2026-01-01T00:00:00Z",
            })

    stats = await enrichment_service.get_stats(tenant_id=tenant_id)
    assert "provider_a" in stats.by_provider
    assert "provider_b" in stats.by_provider
    assert stats.by_provider["provider_a"] == 5
    assert stats.by_provider["provider_b"] == 5
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_get_stats_by_provider_grouping -v` → `1 passed`

---

### Step 5: 实现 test_list_stale_returns_paginated_results

插入 5 条 stale 记录，调用 `list_stale(page=1, page_size=2)`，断言返回 2 条、total=5：

```python
async def test_list_stale_returns_paginated_results(enrichment_service, mock_db_session):
    state = mock_db_session._state
    tenant_id = 1
    for i in range(5):
        state.enrichment_analytics.append({
            "id": i + 1,
            "tenant_id": tenant_id,
            "enriched_at": None,
            "updated_at": "2020-01-01T00:00:00Z",  # stale
        })

    items, total = await enrichment_service.list_stale(
        tenant_id=tenant_id, page=1, page_size=2
    )
    assert len(items) == 2
    assert total == 5
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_list_stale_returns_paginated_results -v` → `1 passed`

---

### Step 6: 实现 test_list_stale_respects_stale_after_days_param

插入两条不同更新时间的记录，调用 `list_stale(stale_after_days=30)`，断言只返回超过30 天的记录：

```python
async def test_list_stale_respects_stale_after_days_param(enrichment_service, mock_db_session):
    state = mock_db_session._state
    tenant_id = 1
    #60 天前 → stale
    state.enrichment_analytics.append({
        "id": 1,
        "tenant_id": tenant_id,
        "enriched_at": None,
        "updated_at": "2026-03-01T00:00:00Z",
    })
    # 10 天前 → 不 stale
    state.enrichment_analytics.append({
        "id": 2,
        "tenant_id": tenant_id,
        "enriched_at": None,
        "updated_at": "2026-05-21T00:00:00Z",
    })

    items, total = await enrichment_service.list_stale(
        tenant_id=tenant_id, page=1, page_size=10, stale_after_days=30
    )
    assert total == 1
    assert items[0].id == 1
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_list_stale_respects_stale_after_days_param -v` → `1 passed`

---

### Step 7: 实现 test_bulk_refresh_dispatches_all_stale_records 和 test_stats_returns_zero_for_empty_tenant

`test_bulk_refresh_dispatches_all_stale_records`：

```python
async def test_bulk_refresh_dispatches_all_stale_records(enrichment_service, mock_db_session):
    state = mock_db_session._state
    tenant_id = 1
    for i in range(3):
        state.enrichment_analytics.append({
            "id": i + 1,
            "tenant_id": tenant_id,
            "enriched_at": None,
            "updated_at": "2020-01-01T00:00:00Z",
        })

    result = await enrichment_service.bulk_refresh(tenant_id=tenant_id)
    assert result.dispatched_count == 3
```

`test_stats_returns_zero_for_empty_tenant`：

```python
async def test_stats_returns_zero_for_empty_tenant(enrichment_service, mock_db_session):
    stats = await enrichment_service.get_stats(tenant_id=9999)
    assert stats.total == 0
    assert stats.enriched == 0
    assert stats.coverage_pct == 0.0
    assert stats.by_provider == {}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_bulk_refresh_dispatches_all_stale_records tests/unit/test_enrichment_analytics.py::test_stats_returns_zero_for_empty_tenant -v` → `2 passed`

---

### Step 8: 全量验证运行完整测试文件并 lint 检查：

```bash
PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v
ruff check tests/unit/test_enrichment_analytics.py
ruff check tests/unit/conftest.py
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → `6 passed`，`ruff check` 两文件均 exit 0

---

## 6. 验收

- [ ] `ruff check tests/unit/test_enrichment_analytics.py` → 0 errors
- [ ] `ruff check tests/unit/conftest.py` → 0 errors（如有修改）
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py -v` → `6 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_get_stats_returns_correct_coverage -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_get_stats_by_provider_grouping -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_list_stale_returns_paginated_results -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_list_stale_respects_stale_after_days_param -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_bulk_refresh_dispatches_all_stale_records -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_analytics.py::test_stats_returns_zero_for_empty_tenant -v` → `1 passed`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `make_enrichment_handler` 与 #755 的接口不匹配导致 mock 返回空结果 | 中 | 中 | 参照 #755 合并后的实际 `EnrichmentAnalyticsService` 方法签名调整 handler；若 #755 尚未合并，先等待 |
| conftest.py 中已存在同名 handler 但行为不一致 | 低 | 中 | 复用现有 handler，仅在本文件 fixture 中调整注入数据 |
| 6 个 test cases 中有边界 case 未覆盖（如 coverage_pct=0 时除零） | 低 | 低 | 在 `test_stats_returns_zero_for_empty_tenant` 中覆盖；如有新发现补充 test case |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_enrichment_analytics.py tests/unit/conftest.py
git commit -m "test(enrichment): add unit tests for EnrichmentAnalyticsService (6 cases)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#756): unit tests for EnrichmentAnalyticsService" --body "Closes #756"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — 参照其 mock_db_session fixture 结构和 test case 编写模式
-父 issue /关联：#513, #755
