# 60-analytics · Add recommendation cache invalidation on stage change

| 元数据 | 值 |
|---|---|
| Issue | #669 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0670-add-churnprediction-orm-model-and-migration](../60-analytics/0670-add-churnprediction-orm-model-and-migration.md)（RecommendationService 所在模块） |
| 启用后赋能 | [0671-build-rule-based-churn-scoring-service-as-fallback](../60-analytics/0671-build-rule-based-churn-scoring-service-as-fallback.md), [0672-add-churn-prediction-api-endpoints](../60-analytics/0672-add-churn-prediction-api-endpoints.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`SalesRecommendationService` 目前持有 `_customer_cache: dict[int, dict]` 但从未实际使用——每次调用推荐方法都实时重新计算。`SalesService.change_stage`（L281-L294）和 `ActivityService.create_activity`（L41-L68）在记录阶段变更或活动时均未触发缓存失效，导致：同一机会的推荐结果在阶段变更后仍然返回过期数据；推荐接口每次请求都完整重算，性能差且浪费 DB 查询资源。Issue #669 要求在这两个写操作入口调用 `invalidate_cache`，并为 `SalesRecommendationService` 实现真正可用的 TTL 缓存。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层缓存逻辑和失效触发。
- **开发者视角**：新增 `SalesRecommendationService.invalidate_cache(opportunity_id, tenant_id)` 方法，可按 opportunity 维度清除缓存；`SalesService.change_stage` 和 `ActivityService.create_activity` 在写入成功后自动调用该方法；缓存采用内存 TTL（1 小时），无需引入 Redis 依赖。

### 1.3 不做什么（剔除）

- [ ] 不实现 Redis 缓存（采用 in-memory dict + TTL，不引入新基础设施依赖）
- [ ] 不实现推荐结果的持久化存储（仅内存缓存，重启进程自然失效）
- [ ] 不在 `SalesRecommendationService` 中新增推荐算法（仅挂缓存层）

### 1.4 关键 KPI

- `ruff check src/services/sales_recommendation.py src/services/sales_service.py src/services/activity_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → ≥ 3 passed（含缓存失效验证）— **TBD - 待验证：对应测试文件尚不存在，需新建**
- `PYTHONPATH=src pytest tests/unit/test_sales.py -v` → 全 passed（stage-change 相关用例）— **TBD - 待验证：对应测试文件尚不存在，需新建或使用 test_sales_router.py**
- `PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → 全 passed（activity 创建触发失效验证）

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) L62-L64（空缓存字段）：

```python
62:    def __init__(self):
63:        """初始化服务"""
64:        self._customer_cache: dict[int, dict] = {}
```

[`src/services/sales_service.py`](../../../src/services/sales_service.py) L281-L294（stage 变更无后效）：

```python
281:  async def change_stage(self, tenant_id: int = 0, opp_id: int = 0, stage: str = "") -> OpportunityModel:
282:      opportunity = await self._fetch_opportunity(tenant_id, opp_id)
283:      if opportunity.pipeline_id is not None:
284:          allowed_stages = await self._get_pipeline_stages(opportunity.pipeline_id, tenant_id)
285:          if stage not in allowed_stages:
286:              raise ValidationException("Stage is not defined in the opportunity pipeline")
287:      await self.session.execute(
288:          update(OpportunityModel)
289:          .where(and_(OpportunityModel.id == opp_id, OpportunityModel.tenant_id == tenant_id))
290:          .values(stage=stage, updated_at=datetime.now(UTC))
291:      )
292:      await self.session.flush()
293:      refreshed = await self._fetch_opportunity(tenant_id, opp_id)
294:      return refreshed
```

[`src/services/activity_service.py`](../../../src/services/activity_service.py) L41-L68（activity 创建无后效）：

```python
41:  async def create_activity(
42:      self,
43:      customer_id: int,
44:      activity_type: str,
45:      content: str,
46:      created_by: int,
47:      tenant_id: int = 0,
48:      **kwargs,
49:  ) -> Activity:
50:      try:
51:          activity_type_enum = ActivityType(activity_type)
52:      except ValueError:
53:          raise ValidationException(f"无效的活动类型: {activity_type}")
54:      now = datetime.now(UTC)
55:      row = ActivityModel(
56:          tenant_id=tenant_id,
57:          customer_id=customer_id,
58:          opportunity_id=kwargs.get("opportunity_id"),
59:          type=activity_type_enum.value,
60:          content=content,
61:          created_by=created_by,
62:          created_at=now,
63:      )
64:      self.session.add(row)
65:      await self.session.flush()
66:      await self.session.refresh(row)
67:      return _to_activity(row)
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) — 实现 `invalidate_cache` 方法和 TTL 缓存逻辑
  - [`src/services/sales_service.py`](../../../src/services/sales_service.py) — `change_stage` 方法末尾调用 `SalesRecommendationService.invalidate_cache`
  - [`src/services/activity_service.py`](../../../src/services/activity_service.py) — `create_activity` 方法末尾调用 `SalesRecommendationService.invalidate_cache`（当 `opportunity_id` 存在时）
  - **TBD - 待验证：tests/unit/test_sales_recommendation.py** — 新增缓存失效单元测试（文件尚不存在，需新建）
  - **TBD - 待验证：tests/unit/test_sales.py** — `change_stage` 单元测试覆盖缓存失效调用（文件尚不存在，可参考 test_sales_router.py）
  - [`tests/unit/test_activity_service.py`](../../../tests/unit/test_activity_service.py) — activity 创建触发失效的单元测试
- 要建：
  - `tests/unit/test_sales_recommendation.py`（若文件不存在）— 缓存失效 + TTL 验证

### 2.3 缺什么

- [ ] `SalesRecommendationService` 无 `invalidate_cache` 方法，缓存永远不失效
- [ ] `SalesService.change_stage` 不触发任何缓存失效，阶段变更后推荐结果仍为旧数据
- [ ] `ActivityService.create_activity` 不触发任何缓存失效（新活动插入后推荐结果不同步）
- [ ] 无 TTL 机制，现有 `_customer_cache` 字典永不自动过期

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_sales_recommendation.py` | 单元测试：验证 `invalidate_cache` 按 opportunity_id + tenant_id 清除缓存；验证 TTL 1 小时自动过期 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py) | 新增 `_recommendation_cache: dict[str, tuple[float, Any]]`（key = `f"{tenant_id}:{opportunity_id}"`，value = `(expires_at, result)`）；新增 `invalidate_cache(opportunity_id, tenant_id)` 方法；各推荐方法优先从缓存读取 |
| [`src/services/sales_service.py`](../../../src/services/sales_service.py) | `change_stage` 方法末尾注入 `SalesRecommendationService(session).invalidate_cache(opp_id, tenant_id)` |
| [`src/services/activity_service.py`](../../../src/services/activity_service.py) | `create_activity` 方法末尾当 `opportunity_id is not None` 时调用 `SalesRecommendationService().invalidate_cache(opportunity_id, tenant_id)` |
| **TBD - 待验证：tests/unit/test_sales_recommendation.py** | 新增 `test_invalidate_cache_clears_entry`、`test_invalidate_cache_tenant_isolation`、`test_cache_ttl_1_hour` 测试用例 |
| **TBD - 待验证：tests/unit/test_sales.py** | `change_stage` 测试断言 mock session 中 `invalidate_cache` 被调用一次 |
| [`tests/unit/test_activity_service.py`](../../../tests/unit/test_activity_service.py) | activity 测试断言创建含 `opportunity_id` 的 activity 时 `invalidate_cache` 被调用一次 |

### 3.3 新增能力

- **Service method**：`SalesRecommendationService.invalidate_cache(self, opportunity_id: int, tenant_id: int) -> None`
- **Service method**：`SalesRecommendationService._get_cached(self, key: str) -> Any | None`（内部，TTL 检查）
- **Service method**：`SalesRecommendationService._set_cached(self, key: str, value: Any) -> None`（内部，TTL 写缓存）
- **缓存结构**：key = `f"{tenant_id}:{opportunity_id}"`，TTL = 3600 秒（1 小时）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 in-memory dict + TTL，不选 Redis**：本项目未引入 Redis，无额外基础设施依赖；内存缓存在单实例场景下完全满足需求；多实例部署时各实例独立失效（可接受，早期阶段不强求跨实例一致）
- **选 opportunity_id + tenant_id 复合 key，不选单一 tenant_id**：推荐结果应按机会隔离失效，避免变更 A 机会阶段时清除 B 机会的缓存
- **选 lazy cache（读时填充），不选 write-through**：现有推荐方法已可独立工作，仅叠加缓存层；写入时不主动预热缓存，减少不必要的计算

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：缓存 key 必须包含 `tenant_id`，不同租户数据完全隔离
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `SalesRecommendationService` 由 router/service 调用方持有实例，不持有 `AsyncSession`；`invalidate_cache` 为无状态清除操作
- `ActivityService` 和 `SalesService` 已有 `session`；调用 `SalesRecommendationService` 时直接实例化（`SalesRecommendationService()`），不做单例注册

### 4.4 已知坑

1. **Python dict 在多线程/异步并发写入时可能竞争** → 规避：Python asyncio 协程运行于单线程，无真实并发写竞争；未来如升级多进程部署可改用 `asyncio.Lock`
2. **`_customer_cache` 与新 `_recommendation_cache` 并存导致混淆** → 规避：本 PR 只扩展 `_recommendation_cache`，清理废弃的 `_customer_cache` 不在本阶段范围（已在 `__init__` 中，但不影响逻辑）
3. **TTL 过期后缓存条目累积** → 规避：写缓存时用 `maxsize` LRU 约束（`functools.lru_cache` 或手动 `OrderedDict`）；或接受简单 dict 由 GC 回收

---

## 5. 实现步骤（按顺序）

### Step 1: 在 `SalesRecommendationService` 中实现 TTL 缓存基础设施

在 `src/services/sales_recommendation.py` 的 `__init__` 方法后新增缓存相关内部方法：

- `_CACHE_TTL: int = 3600`（类常量，秒）
- `_recommendation_cache: dict[str, tuple[float, Any]]`（替换原有的空 `_customer_cache`）
- `_get_cached(key: str) -> Any | None`：检查 key 是否存在且未过期，返回值或 None
- `_set_cached(key: str, value: Any) -> None`：以当前时间戳 + TTL 存入 dict
- `invalidate_cache(opportunity_id: int, tenant_id: int) -> None`：删除 `f"{tenant_id}:{opportunity_id}"` 对应条目

示例代码：

```python
import time

class SalesRecommendationService:
    _CACHE_TTL: int = 3600  # seconds

    def __init__(self):
        self._recommendation_cache: dict[str, tuple[float, Any]] = {}

    def _cache_key(self, tenant_id: int, opportunity_id: int) -> str:
        return f"{tenant_id}:{opportunity_id}"

    def _get_cached(self, key: str) -> Any | None:
        entry = self._recommendation_cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._recommendation_cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: Any) -> None:
        self._recommendation_cache[key] = (time.monotonic() + self._CACHE_TTL, value)

    def invalidate_cache(self, opportunity_id: int, tenant_id: int) -> None:
        key = self._cache_key(tenant_id, opportunity_id)
        self._recommendation_cache.pop(key, None)
```

**完成判定**：`ruff check src/services/sales_recommendation.py` → 0 errors

### Step 2: 修改推荐方法使用缓存

在 `get_next_best_action`、`recommend_cross_sell`、`recommend_up_sell`、`predict_conversion_probability` 各方法中，以 `tenant_id` + 调用链中的 `opportunity_id`（若无可用 customer_id）为 key，优先调用 `_get_cached`，未命中时计算并调用 `_set_cached`。

若推荐方法目前不接受 `tenant_id`，在方法签名中补齐（调用方已有此参数）。

```python
async def predict_conversion_probability(
    self, tenant_id: int, opportunity_id: int, customer_id: int
) -> float:
    key = self._cache_key(tenant_id, opportunity_id)
    cached = self._get_cached(key)
    if cached is not None:
        return cached
    # ... existing computation ...
    result = computed_value
    self._set_cached(key, result)
    return result
```

**完成判定**：`PYTHONPATH=src python -c "from services.sales_recommendation import SalesRecommendationService; s = SalesRecommendationService(); s.invalidate_cache(1, 1); print('ok')"` → `ok`

### Step 3: 在 `SalesService.change_stage` 中调用 `invalidate_cache`

在 `src/services/sales_service.py` 文件顶部添加 import：

```python
from services.sales_recommendation import SalesRecommendationService
```

在 `change_stage` 方法 return 语句之前插入：

```python
    # Invalidate recommendation cache after stage change
    rec_svc = SalesRecommendationService()
    rec_svc.invalidate_cache(opp_id, tenant_id)
```

**完成判定**：`ruff check src/services/sales_service.py` → 0 errors

### Step 4: 在 `ActivityService.create_activity` 中调用 `invalidate_cache`

在 `src/services/activity_service.py` 文件顶部添加 import：

```python
from services.sales_recommendation import SalesRecommendationService
```

在 `create_activity` 方法的 `return _to_activity(row)` 之前插入：

```python
    # Invalidate recommendation cache if this activity belongs to an opportunity
    opportunity_id = kwargs.get("opportunity_id")
    if opportunity_id is not None:
        rec_svc = SalesRecommendationService()
        rec_svc.invalidate_cache(opportunity_id, tenant_id)
```

**完成判定**：`ruff check src/services/activity_service.py` → 0 errors

### Step 5: 编写 `test_sales_recommendation.py` 缓存测试

**TBD - 待验证：tests/unit/test_sales_recommendation.py**（文件尚不存在，需新建；参考其他 unit test 的 fixture 写法）新增三个测试用例：

```python
import pytest
import time
from unittest.mock import AsyncMock, patch
from services.sales_recommendation import SalesRecommendationService


class TestCacheInvalidation:
    def test_invalidate_cache_clears_entry(self):
        svc = SalesRecommendationService()
        key = svc._cache_key(tenant_id=1, opportunity_id=100)
        svc._set_cached(key, {"score": 0.9})
        assert svc._get_cached(key) is not None
        svc.invalidate_cache(opportunity_id=100, tenant_id=1)
        assert svc._get_cached(key) is None

    def test_invalidate_cache_tenant_isolation(self):
        svc = SalesRecommendationService()
        key_t1 = svc._cache_key(tenant_id=1, opportunity_id=100)
        key_t2 = svc._cache_key(tenant_id=2, opportunity_id=100)
        svc._set_cached(key_t1, {"score": 0.8})
        svc._set_cached(key_t2, {"score": 0.9})
        svc.invalidate_cache(opportunity_id=100, tenant_id=1)
        assert svc._get_cached(key_t1) is None
        assert svc._get_cached(key_t2) is not None  # t2 unaffected

    def test_cache_ttl_1_hour(self):
        svc = SalesRecommendationService()
        key = svc._cache_key(tenant_id=1, opportunity_id=200)
        svc._CACHE_TTL = 1  # override to 1 second for test
        svc._set_cached(key, {"score": 0.7})
        assert svc._get_cached(key) is not None
        time.sleep(1.1)
        assert svc._get_cached(key) is None
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → `3 passed`

### Step 6: 更新 `test_sales.py` 中 stage-change 测试断言

**TBD - 待验证：tests/unit/test_sales.py**（文件尚不存在，stage-change 相关用例需新建或合并至 test_sales_router.py）在 `test_change_stage` 测试中，用 `patch("services.sales_recommendation.SalesRecommendationService.invalidate_cache")` 验证调用：

```python
from unittest.mock import patch

async def test_change_stage_invalidates_recommendation_cache(
    self, mock_db_session, sample_opportunity_data
):
    state = MockState()
    opp = state.add("opportunities", sample_opportunity_data)
    session = make_mock_session([make_opportunity_handler(state)])
    svc = SalesService(session)
    with patch.object(SalesRecommendationService, "invalidate_cache") as mock_inv:
        await svc.change_stage(tenant_id=1, opp_id=opp["id"], stage="qualified")
        mock_inv.assert_called_once_with(opp["id"], 1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_sales.py -v` → 全 passed

### Step 7: 更新 `test_activity_service.py` 断言缓存失效调用

在 `tests/unit/test_activity_service.py` 的 activity 创建测试中，当 `opportunity_id` 不为空时，断言 `invalidate_cache` 被调用：

```python
async def test_create_activity_triggers_cache_invalidation(
    self, mock_db_session, sample_activity_data
):
    svc = ActivityService(mock_db_session)
    with patch.object(SalesRecommendationService, "invalidate_cache") as mock_inv:
        result = await svc.create_activity(
            customer_id=1, activity_type="call", content="跟进",
            created_by=1, tenant_id=1, opportunity_id=10
        )
        mock_inv.assert_called_once_with(10, 1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/services/sales_recommendation.py src/services/sales_service.py src/services/activity_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → `3 passed` — **TBD - 待验证：测试文件需新建**
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales.py -v` → 全 passed — **TBD - 待验证：测试文件需新建或合并至 test_sales_router.py**
- [ ] `PYTHONPATH=src pytest tests/unit/test_activity_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src python -c "from services.sales_recommendation import SalesRecommendationService; s = SalesRecommendationService(); s.invalidate_cache(1, 1); s._set_cached('1:1', 0.5); print(s._get_cached('1:1'))"` → `0.5`
- [ ] `PYTHONPATH=src python -c "from services.sales_recommendation import SalesRecommendationService; s = SalesRecommendationService(); s._set_cached('1:1', 0.5); s.invalidate_cache(1, 1); print(s._get_cached('1:1'))"` → `None`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `SalesService` / `ActivityService` 循环导入 `SalesRecommendationService`（Python import 顺序问题） | 低 | 中 | 将 import 移至方法内部（`from services.sales_recommendation import SalesRecommendationService` 在函数体内），避免模块级循环导入 |
| 多实例部署时内存缓存不共享（各自独立失效） | 中 | 低 | 早期阶段可接受；后续若需要跨实例一致可升级为 Redis（届时 `invalidate_cache` 仅需替换实现） |
| `invalidate_cache` 抛出异常导致原事务回滚（若写在 flush 之前） | 低 | 高 | 必须写在 `flush()` 之后调用，确保原 DB 事务不受影响 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/sales_recommendation.py src/services/sales_service.py src/services/activity_service.py tests/unit/test_sales_recommendation.py tests/unit/test_sales.py tests/unit/test_activity_service.py
git commit -m "feat(analytics): add TTL cache and stage/activity invalidation to SalesRecommendationService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): cache invalidation on stage change and activity insert (#669)" --body "Closes #669"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/sales_recommendation.py`](../../../src/services/sales_recommendation.py)（现有 `SalesRecommendationService`，`_customer_cache` 字段为历史遗留）
- 父 issue / 关联：#36（父 issue）
- 关联 issue：#668（依赖项，RecommendationService 基础）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
