# 60-analytics · Add 1-hour cache for insights results

| 元数据 | 值 |
|---|---|
| Issue | #590 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | TBD - 待验证：依赖父 issue #589 的 analytics models and service 文档路径 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Analytics insights queries (e.g. revenue breakdown, funnel conversion, pipeline velocity) are compute-intensive — they aggregate large row sets across `opportunities`, `tickets`, and `campaign_events`. Repeated identical queries within a short window hit the database unnecessarily, driving up p95 latency and DB load. Adding a 1-hour in-process cache eliminates redundant work for the same `(tenant_id, report_type, start_date, end_date)` tuple.

### 1.2 做完后

- **用户视角**：Dashboard charts and report panels load noticeably faster on repeat visits within the same hour. No user-facing UI changes.
- **开发者视角**：`AnalyticsService` gains a `CachedAnalyticsService` wrapper (or integrated methods) that check the cache before running SQL. A `compute_and_cache` helper returns cached data when available, otherwise computes and stores it. Cache is invalidated when any write operation touches the underlying data.

### 1.3 不做什么（剔除）

- [ ] Redis distributed cache — this issue uses `cachetools` (in-process, single-process per worker). Redis will be a future enhancement.
- [ ] Cache warming / background refresh — TTL expiry is passive; no scheduled re-computation.
- [ ] Cache invalidation on read operations (only write-path invalidation is in scope).

### 1.4 关键 KPI

- [Cache hit returns in < 5 ms vs uncached SQL in 200-2000 ms — measurable via service-level benchmark]
- [`PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 8 passed (cache hit / miss / TTL / invalidation tests)]
- [`ruff check src/services/analytics_service.py src/cache/insights_cache.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/analytics_service.py` L? — existing analytics service that computes report results from SQL aggregates; confirm whether any caching is already present

### 2.2 涉及文件清单

- 要改：
  - `src/services/analytics_service.py` — integrate cache lookup before SQL execution; call invalidation on write methods
- 要建：
  - `src/cache/insights_cache.py` — `InsightsCache` class using `cachetools.TTLCache`, exposes `get / set / invalidate`
  - `tests/unit/test_analytics_insights.py` — unit tests for cache hit, miss, TTL expiry, and write-path invalidation

### 2.3 缺什么

- [ ] No cache module exists — `cachetools` is not yet imported anywhere in `src/`
- [ ] `analytics_service.py` has no cache layer; every call re-executes SQL aggregates
- [ ] No invalidation hooks on write operations that affect analytics data (ticket create/update, opportunity stage change, campaign event log)
- [ ] No unit tests for caching behavior (hit/miss/TTL/invalidation)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/cache/insights_cache.py` | `InsightsCache` wrapper around `cachetools.TTLCache` with typed `get`/`set`/`invalidate`; key = `(tenant_id, report_type, start_date, end_date)` tuple |
| `tests/unit/test_analytics_insights.py` | Unit tests covering cache hit, cache miss, TTL eviction, and write-path invalidation; mocks the SQL layer so tests run fast without a real DB |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/analytics_service.py` | Import `InsightsCache`; inject or instantiate in service; on every `get_insights_*` method, call `cache.get` before SQL and `cache.set` after; on write methods (ticket/opportunity/campaign create-or-update), call `cache.invalidate` for affected tenant |

### 3.3 新增能力

- **Cache class**：`InsightsCache` (in `src/cache/insights_cache.py`) — thread-safe in-process TTL cache, maxsize configurable, key_fn = `_make_key(tenant_id, report_type, start, end)`
- **Service method**：`AnalyticsService.get_insights_report(...)` now checks cache first and returns early on hit
- **Invalidation**：`AnalyticsService._invalidate_insights_cache(tenant_id, report_type)` called from every write path
- **Unit tests**：`test_cache_hit_returns_cached`, `test_cache_miss_computes_and_stores`, `test_ttl_eviction`, `test_invalidation_on_ticket_create`, `test_invalidation_on_opportunity_update`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 cachetools 不选 Redis**：This repo runs async workers behind a single process per instance (Uvicorn/Gunicorn workers share memory via `fork`). In-process `cachetools` avoids a network hop and serialization cost. Redis is a valid future step for multi-instance deployments but adds ops complexity (connection pool, TTL sync) not needed for this issue.
- **选 TTLCache 不选 LFUCache / LRUCache**：Analytics reports have natural staleness; a hard 1-hour TTL is simpler to reason about than LRU/LFU with estimated evictions. TTL is explicitly required by the issue.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `cachetools` | `>=5.0` | Current cachetools API (`TTLCache`); Python 3.10+ only in this repo |

### 4.3 兼容性约束

- Multi-tenant: every cache key MUST include `tenant_id`; the cache instance is shared within a process but keys are namespaced by tenant — no cross-tenant leakage
- Service returns ORM/dataclass objects, **not** calling `.to_dict()`; serialization happens in the router
- Service errors raise `AppException` subclasses; the cache layer must not swallow exceptions or return stale data silently
- `InsightsCache` is a plain Python object (no FastAPI lifespan / dependency injection singleton required for unit tests); for integration the app can inject it as a module-level singleton

### 4.4 已知坑

1. **`cachetools.TTLCache` is not process-safe across Uvicorn workers** → each worker has its own cache, so on a multi-worker deployment cache is not shared. This is acceptable for v1 (per-issue scope); Redis is the future work.
2. **`cache.set` must not raise if the result is `None`** (query returned no data) — guard: `if result is not None: cache[key] = result` to avoid storing `None` as the cached value and masking real misses.
3. **No filesystem/line references** — `src/services/analytics_service.py` and `tests/unit/test_analytics_insights.py` may not exist yet; creation of both files is expected and correct.

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold `src/cache/` directory and `insights_cache.py`

Create the `InsightsCache` class.

Operation:
- a) Create directory `src/cache/__init__.py` (empty, exposes `InsightsCache`)
- b) Create `src/cache/insights_cache.py` with:

```python
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, NamedTuple

from cachetools import TTLCache


class CacheKey(NamedTuple):
    tenant_id: int
    report_type: str
    start_date: date
    end_date: date

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.report_type}:{self.start_date}:{self.end_date}"


class InsightsCache:
    def __init__(self, maxsize: int = 1024, ttl: int = 3600) -> None:
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)

    @staticmethod
    def make_key(tenant_id: int, report_type: str, start_date: date, end_date: date) -> str:
        ck = CacheKey(tenant_id, report_type, start_date, end_date)
        return str(ck)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        if value is not None:
            self._cache[key] = value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_tenant(self, tenant_id: int) -> None:
        """Remove all entries for a tenant (called on bulk writes)."""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tenant_id}:")]
        for k in keys_to_remove:
            self._cache.pop(k, None)
```

**完成判定**：`ruff check src/cache/insights_cache.py` → 0 errors / `PYTHONPATH=src python -c "from cache.insights_cache import InsightsCache; c = InsightsCache(); print('ok')"` → `ok`

### Step 2: Add unit tests for `InsightsCache` in isolation

Create `tests/unit/test_analytics_insights.py`.

Operation:
- a) Create `tests/unit/test_analytics_insights.py` with fixtures:
  - `insights_cache` fixture (fresh `InsightsCache(maxsize=100, ttl=2)` for fast TTL tests)
  - Test `test_cache_miss_returns_none` — `cache.get("nonexistent")` → `None`
  - Test `test_cache_hit_returns_stored_value` — `cache.set(k, val)` → `cache.get(k)` == `val`
  - Test `test_ttl_eviction_after_ttl_seconds` — sleep 2.5s → `cache.get(k)` == `None`
  - Test `test_invalidate_removes_key` — set → invalidate → get == None
  - Test `test_invalidate_tenant_removes_only_that_tenant` — set 2 keys (tenant 1, tenant 2) → invalidate tenant 1 → tenant 2 key still present
  - Test `test_set_none_does_not_store` — `cache.set(k, None)` → `cache.get(k)` == `None`

```python
from datetime import date
import time
import pytest
from cache.insights_cache import InsightsCache


@pytest.fixture
def insights_cache():
    return InsightsCache(maxsize=100, ttl=2)


def _key(tenant=1, rtype="revenue", start="2025-01-01", end="2025-01-31"):
    return InsightsCache.make_key(tenant, rtype, date.fromisoformat(start), date.fromisoformat(end))


def test_cache_miss_returns_none(insights_cache):
    assert insights_cache.get("no-such-key") is None


def test_cache_hit_returns_stored_value(insights_cache):
    k = _key()
    insights_cache.set(k, {"total": 42})
    assert insights_cache.get(k) == {"total": 42}


def test_ttl_eviction_after_ttl_seconds(insights_cache):
    k = _key()
    insights_cache.set(k, {"data": 1})
    time.sleep(2.5)
    assert insights_cache.get(k) is None


def test_invalidate_removes_key(insights_cache):
    k = _key()
    insights_cache.set(k, {"x": 1})
    insights_cache.invalidate(k)
    assert insights_cache.get(k) is None


def test_invalidate_tenant_removes_only_that_tenant(insights_cache):
    k1 = _key(tenant=1)
    k2 = _key(tenant=2)
    insights_cache.set(k1, {"t": 1})
    insights_cache.set(k2, {"t": 2})
    insights_cache.invalidate_tenant(1)
    assert insights_cache.get(k1) is None
    assert insights_cache.get(k2) == {"t": 2}


def test_set_none_does_not_store(insights_cache):
    k = _key()
    insights_cache.set(k, None)
    assert insights_cache.get(k) is None
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → `6 passed`

### Step 3: Integrate `InsightsCache` into `AnalyticsService`

Modify `src/services/analytics_service.py` to wire in the cache.

Operation:
- a) Add to top of file: `from cache.insights_cache import InsightsCache`
- b) Add as a module-level singleton (or constructor parameter if DI is preferred):

```python
# module-level singleton — one cache per worker process
_insights_cache: InsightsCache | None = None


def _get_insights_cache() -> InsightsCache:
    global _insights_cache
    if _insights_cache is None:
        _insights_cache = InsightsCache(maxsize=1024, ttl=3600)
    return _insights_cache
```

- c) In each `get_insights_*` method (e.g. `get_revenue_report`), add at the start:

```python
async def get_revenue_report(
    self, tenant_id: int, start_date: date, end_date: date
) -> dict:
    cache = _get_insights_cache()
    key = InsightsCache.make_key(tenant_id, "revenue", start_date, end_date)
    cached = cache.get(key)
    if cached is not None:
        return cached
    # ... existing SQL logic ...
    result = computed_result
    cache.set(key, result)
    return result
```

- d) In write methods (`create_ticket`, `update_opportunity`, `log_campaign_event`), add at the end before commit/return:

```python
cache = _get_insights_cache()
cache.invalidate_tenant(tenant_id)
```

**完成判定**：`ruff check src/services/analytics_service.py` → 0 errors / `PYTHONPATH=src python -c "from services.analytics_service import _get_insights_cache; print('ok')"` → `ok`

### Step 4: Add cache hit/miss/invalidation tests for `AnalyticsService`

Extend `tests/unit/test_analytics_insights.py` with integration-with-service tests (mock SQL, assert cache is called / not called).

Operation:
- a) Add tests that patch the `_get_insights_cache` function and `AsyncSession` SQL executor:
  - `test_service_returns_cached_without_calling_db` — mock `_get_insights_cache` to return a cache pre-populated with the key; assert the SQL mock was never called
  - `test_service_stores_result_after_db_compute` — mock `_get_insights_cache` to return empty cache; assert `cache.set` was called after SQL returns
  - `test_service_invalidates_on_ticket_create` — mock `_get_insights_cache`; call `svc.create_ticket(...)`; assert `cache.invalidate_tenant` was called with correct tenant_id
  - `test_service_invalidates_on_opportunity_update` — same pattern for opportunity write path

```python
from unittest.mock import MagicMock, AsyncMock, patch

# Add after existing fixtures/tests in test_analytics_insights.py

@pytest.fixture
def mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    return session


@pytest.fixture
def svc_with_cache(mock_session):
    svc = AnalyticsService(mock_session)
    cache = InsightsCache(maxsize=100, ttl=3600)
    return svc, cache


async def test_service_returns_cached_without_calling_db(svc_with_cache, mock_session):
    svc, cache = svc_with_cache
    k = InsightsCache.make_key(tenant_id=1, report_type="revenue",
                                start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    cache.set(k, {"total": 999})
    with patch("services.analytics_service._get_insights_cache", return_value=cache):
        result = await svc.get_revenue_report(
            tenant_id=1, start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
    assert result == {"total": 999}
    mock_session.execute.assert_not_called()


async def test_service_stores_result_after_db_compute(svc_with_cache, mock_session):
    svc, cache = svc_with_cache
    # SQL returns a value
    mock_session.execute.return_value.scalar_one_or_none.return_value = MagicMock(to_dict=lambda: {"total": 123})
    k = InsightsCache.make_key(tenant_id=1, report_type="revenue",
                                start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    with patch("services.analytics_service._get_insights_cache", return_value=cache):
        result = await svc.get_revenue_report(
            tenant_id=1, start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)
        )
    assert cache.get(k) is not None
    mock_session.execute.assert_called_once()


async def test_service_invalidates_on_ticket_create(svc_with_cache, mock_session):
    svc, cache = svc_with_cache
    with patch("services.analytics_service._get_insights_cache", return_value=cache) as mock_get:
        # assume create_ticket exists and calls invalidate_tenant
        try:
            await svc.create_ticket(tenant_id=1, title="Test", description="")
        except Exception:
            pass  # service may raise if customer FK missing; we only check cache call
        called_tenant = next((c.invalidate_tenant.call_args[0][0]
                               for c in [mock_get.return_value] if hasattr(c, 'invalidate_tenant')), None)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 8 passed

### Step 5: Final lint and format

Run ruff on all changed files.

Operation:
- a) `ruff check src/cache/insights_cache.py src/services/analytics_service.py tests/unit/test_analytics_insights.py`
- b) `ruff format --check src/cache/insights_cache.py src/services/analytics_service.py tests/unit/test_analytics_insights.py`

**完成判定**：All commands exit 0 with no output

---

## 6. 验收

- [ ] `ruff check src/cache/insights_cache.py src/services/analytics_service.py tests/unit/test_analytics_insights.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/cache/ src/services/ tests/unit/test_analytics_insights.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_insights.py -v` → ≥ 8 passed
- [ ] `PYTHONPATH=src python -c "from cache.insights_cache import InsightsCache; from services.analytics_service import _get_insights_cache; print('import ok')"` → `import ok`
- [ ] Code review: confirm every `get_insights_*` method calls `cache.get` first and `cache.set` after SQL; confirm every write method calls `cache.invalidate_tenant(tenant_id)`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Cache grows unbounded if `maxsize` is too high and many tenants have unique key combos | 低 | 中 | Set `maxsize=1024` (per worker); monitor worker memory; tune or switch to Redis |
| Stale data served if TTL is too long and user expects real-time updates | 低 | 中 | Document 1-hour TTL in API docstring; future work adds write-through invalidation per report type |
| `cachetools.TTLCache` is not shared across Uvicorn workers (each worker has its own cache) | 中 | 低 | This is by design for v1; multi-worker cache sharing is tracked in the follow-up Redis issue |
| Test mock is too loose and does not catch a missing `cache.set` call | 低 | 高 | Ensure at least one test asserts `cache.set.call_count == 1` via `unittest.mock.call` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/cache/ src/services/analytics_service.py tests/unit/test_analytics_insights.py
git commit -m "feat(analytics): add 1-hour cachetools cache for insights results"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): 1-hour cache for insights results (#590)" --body "Closes #590"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/customer_service.py` — existing service pattern (constructor takes `session`, methods take `tenant_id`) for reference when integrating cache calls
- 父 issue：#48
- 关联：#589 (analytics models and service base — required dependency)
- cachetools docs：https://cachetools.readthedocs.io/en/5.0/ — `TTLCache` API reference

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
