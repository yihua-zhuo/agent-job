# Sales · Add recommendation service with caching

| 元数据 | 值 |
|---|---|
| Issue | #598 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [#597](../20-sales/0597-add-recommendation-orm-model-and-risk-schema.md) |
| 启用后赋能 | TBD - 待验证：关联的 automation 板块编号 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前的商机推荐数据（成交概率、相似商机、下一步行动）每次 API 调用都重新计算，频繁访问时造成多余的开销。商机阶段变更时旧推荐数据不会被清除，导致决策依据滞后。#597 已引入推荐结果存储 ORM models，本板块需要为推荐结果访问构建统一的缓存抽象，避免重复查询数据库或重复计算。

### 1.2 做完后

- **用户视角**：`GET /sales/opportunities/{id}/recommendations` 在缓存新鲜（<1h）时直接返回缓存数据，响应更快。无用户可见的功能变化。
- **开发者视角**：`RecommendationService` 提供 `get_recommendations(opportunity_id, tenant_id)` 和 `invalidate_cache(opportunity_id, tenant_id)`，服务可注入到 router 或 automation engine 中调用。缓存 TTL = 3600s，清除策略由调用方在 stage 变更时触发。

### 1.3 不做什么（剔除）

- [ ] 不引入 Redis 或其他外部缓存基础设施 — 仅使用进程内 dict（module-level singleton）
- [ ] 不新建 ORM model —依赖 #597 已有的 `Recommendation` / `RiskSignal` models
- [ ] 不改变 `get_recommendations` 的返回数据结构 — 与现有 router兼容
- [ ] 不实现 TTL 配置化（config file / env var）—硬编码 3600s，后续可扩展

### 1.4 关键 KPI

- `ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 5 passed（cache miss hit, cache hit fresh, cache stale bypass, invalidate, not found）
- `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → 全 passed（回归验证）
- `alembic upgrade head && alembic downgrade -1` → exit 0（如 #597 migration 存在）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) L{43}-L{63}

```python:src/services/sales_recommendation.py
class SalesRecommendationService:
    """销售推荐服务"""

    def __init__(self):
        """初始化服务"""
        self._customer_cache: dict[int, dict] = {}

    def get_next_best_action(self, tenant_id: int, customer_id: int) -> SalesActionRecommendation:
        ...
    def recommend_cross_sell(self, tenant_id: int, customer_id: int) -> list[ProductRecommendation]:
        ...
    def recommend_up_sell(self, tenant_id: int, customer_id: int) -> list[ProductRecommendation]:
        ...
    def get_similar_customers(self, tenant_id: int, customer_id: int, limit: int = 5) -> list[SimilarCustomer]:
        ...
    def predict_conversion_probability(self, opportunity_id: int) -> float:
        ...
```

现有的 `SalesRecommendationService` 是 `__init__(self)`（无 session），按 customer_id 工作，不按 opportunity_id 工作，且不提供 `get_recommendations(opportunity_id, tenant_id)` 接口。

### 2.2 涉及文件清单

- 要改：
  - [`src/services/__init__.py`](../../../src/services/__init__.py) —导出新 `RecommendationService`
- 要建：
  - `src/services/recommendation_service.py` — 缓存封装 service
  - `tests/unit/test_recommendation_service.py` — 缓存行为单元测试

### 2.3 缺什么

- [ ] `RecommendationService` —封装 `get_recommendations` + `invalidate_cache`，内部委托 `SalesRecommendationService`
- [ ] 模块级 dict缓存（key = `(opportunity_id, tenant_id)`，value = `(timestamp, result)`）
- [ ] 缓存新鲜度判定（TTL = 3600s）
- [ ] `NotFoundException`抛出当 opportunity 不存在
- [ ] 单元测试覆盖 cache hit / miss / stale bypass / invalidate / not found

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/recommendation_service.py` | 推荐缓存 service，含 `get_recommendations` / `invalidate_cache`，delegate 到 `SalesRecommendationService` |
| `tests/unit/test_recommendation_service.py` | 缓存行为单元测试（5 passed: cache miss, hit fresh, stale bypass, invalidate, not found） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/__init__.py`](../../../src/services/__init__.py) | 新增 `RecommendationService` 到模块导出 |

### 3.3 新增能力

- **Service**：`RecommendationService(session)` — 构造时注入 `AsyncSession`；委托 `SalesRecommendationService` 计算，内部维护 dict缓存
- **Cache TTL**：3600 秒（1 小时），超过则视为 stale
- **Cache key**：`str(opportunity_id) + ":" + str(tenant_id)`
- **Public API**：
  - `get_recommendations(opportunity_id: int, tenant_id: int) -> dict` — cache hit/fresh 时返回缓存；否则计算并写入缓存；opportunity 不存在时 raise `NotFoundException("Opportunity")`
  - `invalidate_cache(opportunity_id: int, tenant_id: int) -> None` — 从缓存中删除对应 key，无视是否存在均不抛异常

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 dict 而非 Redis**：当前需求是进程内单实例缓存，TTL 短（1h），不需要跨实例共享。dict 实现最简，符合"先用最简方案"原则。
- **module-level `_cache: dict`** 而非 `__init__` 实例属性：路由每次请求创建新 `RecommendationService` 实例（通过 `Depends`），若缓存在实例属性则每次请求均 miss。module-level singleton 保证跨请求复用。
- **Singleton cache 而非 service 实例缓存**：与 `SalesRecommendationService` 的 `_customer_cache` 设计保持一致。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：缓存按 `(opportunity_id, tenant_id)` 两维 key 隔离，不同 tenant不会覆盖彼此缓存
- Service构造 `__init__(self, session: AsyncSession)` — 类型 `AsyncSession`，无默认值（见 CLAUDE.md §Service Pattern）
- `get_recommendations` 内部需要通过 `SalesService` 查询 opportunity存在性，涉及 `tenant_id` 过滤
- Service错误抛 `AppException` 子类（`NotFoundException`），不返回 `ApiResponse.error()`

### 4.4 已知坑

1. **module-level dict 缓存不受测试隔离** →规避：每个测试内部调用 `recommendation_service._cache.clear()` 或在 `MockState` 中独立构造；CI进程重启即清空
2. **时间戳比较依赖 `time.time()` 单调性** →规避：测试用 `monkeypatch.setattr(time, "time", lambda: fixed_ts)` 固定时间，避免 sleep 等待
3. **`SalesRecommendationService.__init__` 无 session，方法签名各异** →规避：直接在 `get_recommendations` 内实例化，不传 session；后续如需 DB 则通过参数传入

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/recommendation_service.py`

操作：
- a) 创建 `src/services/recommendation_service.py`
- b) 实现 module-level `_cache: dict[str, tuple[float, dict]]` 缓存（key = `"{opportunity_id}:{tenant_id}"`）
- c) `RecommendationService.__init__(self, session: AsyncSession)` — 保存 session，实例化 `SalesRecommendationService()`
- d) `get_recommendations(opportunity_id, tenant_id)` — 查缓存如 fresco 返回；否则委托计算并缓存；不存在则 raise `NotFoundException("Opportunity")`
- e) `invalidate_cache(opportunity_id, tenant_id)` — 从 `_cache` 删除 key（key 不存在不抛异常）

```python:src/services/recommendation_service.py
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException
from services.sales_recommendation import SalesRecommendationService

_CACHE_TTL = 3600.0  # seconds

# Module-level singleton cache — survives across service instances within a process.
_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(opportunity_id: int, tenant_id: int) -> str:
    return f"{opportunity_id}:{tenant_id}"


class RecommendationService:
    __slots__ = ("session", "_sales_svc")

    def __init__(self, session: AsyncSession):
        self.session = session
        self._sales_svc = SalesRecommendationService()

    async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:
        key = _cache_key(opportunity_id, tenant_id)
        now = time.time()
        if key in _cache:
            ts, data = _cache[key]
            if now - ts < _CACHE_TTL:
                return data        # opportunity must exist
        result = await self.session.execute(
            select(OpportunityModel).where(
                OpportunityModel.id == opportunity_id,
                OpportunityModel.tenant_id == tenant_id,
            )
        )
        opp = result.scalar_one_or_none()
        if opp is None:
            raise NotFoundException("Opportunity")
        data = {
            "opportunity_id": opportunity_id,
            "conversion_probability": self._sales_svc.predict_conversion_probability(opportunity_id),
            "next_action": self._sales_svc.get_next_best_action(tenant_id, opp.customer_id),
            "similar_deals": [],  # populated in follow-up issue        }
        _cache[key] = (now, data)
        return data

    @staticmethod
    def invalidate_cache(opportunity_id: int, tenant_id: int) -> None:
        _cache.pop(_cache_key(opportunity_id, tenant_id), None)
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors

### Step 2: 创建 `tests/unit/test_recommendation_service.py`

操作：
- a) 创建 `tests/unit/test_recommendation_service.py`，使用 `make_mock_session` + `opportunity_handler` + `make_customer_handler`
- b) fixture `recommendation_service(mock_db_session)` → `RecommendationService(mock_db_session)`
- c) 测试 case1（缓存 miss）：mock 当前时间 T0，调用 `get_recommendations` 后 `_cache`，下一次调用返回 cache hit
- d) 测试 case 2（缓存 stale）：固定时间为 T0，写入缓存，再固定时间为 T0 +3601（stale），验证重新计算
- e) 测试 case 3（invalidate）：写入缓存后调用 `invalidate_cache`，验证 cache 已清空
- f) 测试 case 4（not found）：opportunity 不存在时 raise `NotFoundException`

示例代码：

```python:tests/unit/test_recommendation_service.py
"""Unit tests for src/services/recommendation_service.py."""
import time
import pytestfrom unittest.mock import AsyncMock

from services.recommendation_service import (
    RecommendationService,
    _CACHE_TTL,
    _cache,
    _cache_key,
)
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_db_session():
    state = MockState()
    session = make_mock_session([
        make_opportunity_handler(state),
        make_customer_handler(state),
    ])
    return session


@pytest.fixture
def svc(mock_db_session, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    _cache.clear()
    return RecommendationService(mock_db_session)


async def test_cache_miss_populates_cache(svc, mock_db_session, monkeypatch):
    result1 = await svc.get_recommendations(1, tenant_id=1)
    key = _cache_key(1, 1)
    assert key in _cache
    ts1, data1 = _cache[key]
    assert data1 == result1想象


async def test_cache_hit_returns_same_object(svc, mock_db_session, monkeypatch):
    result1 = await svc.get_recommendations(1, tenant_id=1)
    result2 = await svc.get_recommendations(1, tenant_id=1)
    assert result1 == result2


async def test_stale_cache_is_bypassed(svc, mock_db_session, monkeypatch):
    await svc.get_recommendations(1, tenant_id=1)
    monkeypatch.setattr(time, "time", lambda: 1000.0 + _CACHE_TTL + 1)
    result = await svc.get_recommendations(1, tenant_id=1)
    assert result["opportunity_id"] == 1


async def test_invalidate_removes_cache_entry(svc):
    await svc.get_recommendations(1, tenant_id=1)
    assert _cache_key(1, 1) in _cache
    RecommendationService.invalidate_cache(1, 1)
    assert _cache_key(1, 1) not in _cache


async def test_not_found_raises(svc, mock_db_session):
    class EmptyResult:
        def scalar_one_or_none(self):
            return None
    mock_db_session.execute = AsyncMock(return_value=EmptyResult())
    with pytest.raises(NotFoundException):
        await svc.get_recommendations(9999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 5 passed

### Step 3:导出 `RecommendationService` 到 `src/services/__init__.py`

操作：
- a) 在 `src/services/__init__.py` 中新增 `from services.recommendation_service import RecommendationService`

**完成判定**：`PYTHONPATH=src ruff check src/services/__init__.py` → 0 errors

### Step 4: Lint 全量验证

操作：
- 在 `src/services/recommendation_service.py` 和 `tests/unit/test_recommendation_service.py` 上运行 `ruff check`

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/recommendation_service tests/unit/test_recommendation_service.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 全 pass- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 5 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_router.py -v` → 全 passed（回归）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（依赖 #597 migration 可用）
- [ ] `PYTHONPATH=src mypy src/services/recommendation_service.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| module-level dict 缓存在 uvicorn 重载时未清空，导致 stale 数据被复用 | 低 | 中 | uvicorn --reload 重启进程即清空；生产环境重部署即可；代码注释已说明 |
| 多进程（gunicorn -w N）下缓存不共享，各自独立，缓存命中率低于预期 | 中 | 低 | 当前设计为进程内缓存；文档注明后续换 Redis；不影响正确性 |
| #597 migration 未合并，OpportunityModel 未就绪导致 import失败 | 低 | 中 | 本板块依赖 #597，合并不冲突时先合 #597；PR描述已注明顺序 |

---

## 8. 完成后必做

```bash
git add src/services/recommendation_service.py src/services/__init__.py tests/unit/test_recommendation_service.py
git commit -m "feat(sales): add RecommendationService with in-memory TTL cache (closes #598)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): add RecommendationService with in-memory TTL cache (closes #598)" --body "Closes #598## Summary
- Add \`RecommendationService\` in \`src/services/recommendation_service.py\` wrapping cache + delegate to \`SalesRecommendationService\`
- \`get_recommendations(opportunity_id, tenant_id)\` — cache hit (<1h TTL) or compute + cache
- \`invalidate_cache(opportunity_id, tenant_id)\` — clears cache entry (called on stage change)
- Raise \`NotFoundException\` when opportunity does not exist
- Unit tests: 5 passed covering cache hit/miss/stale/invalidate/not-found

## Test plan
- [x] ruff check —0 errors
- [x] pytest tests/unit/test_recommendation_service.py -v — 5 passed
- [x] pytest tests/unit/test_sales_router.py -v — full pass (regression)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) — 现有 `SalesRecommendationService`，本板块 delegate 对象
- 同类参考实现：[`src/services/pipeline_service.py`](../../../src/services/pipeline_service.py) — `SalesService` 模式，`__init__(self, session: AsyncSession)` 构造
- 父 issue / 关联：#46（Epic），#597（依赖 — Recommendation ORM），#687（消费方 — automation rule engine 调用 `invalidate_cache`）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
