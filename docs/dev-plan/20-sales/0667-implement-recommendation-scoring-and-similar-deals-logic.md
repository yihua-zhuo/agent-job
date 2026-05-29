# 20-sales · Add deal confidence scoring and similar-deals lookup

| 元数据 | 值 |
|---|---|
| Issue | #667 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 1.5 工作日 |
| 依赖 | [0666-add-recommendation-models-and-service-get-methods](0666-add-recommendation-models-and-service-get-methods.md) |
| 启用后赋能 | [0668-add-get-sales-opportunities-id-recommendations-endpoint](0668-add-get-sales-opportunities-id-recommendations-endpoint.md), [0669-add-recommendation-cache-invalidation-on-stage-change-and-ne](0669-add-recommendation-cache-invalidation-on-stage-change-and-ne.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`SalesRecommendationService` currently returns fixed mock data for opportunity-level recommendations. It has no real database backing and no logic to score an individual deal's confidence or surface comparable historical deals. Issue #667 is required before the `GET /sales/opportunities/{id}/recommendations` router endpoint (issue #668) can return meaningful, data-driven signals instead of stub responses.

### 1.2 做完后

- **用户视角**：无用户可见 UI change — this is a pure service-layer change that powers the downstream API endpoint in issue #668.
- **开发者视角**：`SalesRecommendationService` gains three new async methods — `compute_confidence_score`, `find_similar_deals`, and `get_recommendations` — returning domain dicts. Services in other modules can call these without coupling to the router layer.

### 1.3 不做什么（剔除）

- [ ] API endpoint `GET /sales/opportunities/{id}/recommendations` — that is issue #668.
- [ ] Cache invalidation on stage change — that is issue #669.
- [ ] New ORM model or migration — the `opportunities` table already contains all required fields; no schema change is needed.

### 1.4 关键 KPI

- `PYTHONPATH=src ruff check src/services/sales_recommendation.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → ≥ 3 passed (one per new method)
- `PYTHONPATH=src python -c "from services.sales_recommendation import SalesRecommendationService; import asyncio; s=SalesRecommendationService(session=None); print('import ok')"` → exit 0 (service loads with new signature)

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/sales_recommendation.py`](../../src/services/sales_recommendation.py) L{1}-L{60}

```python
43: class SalesRecommendationService:
44:     """销售推荐服务"""
62:     def __init__(self):
63:         """初始化服务"""
64:         self._customer_cache: dict[int, dict] = {}
66:     def _get_mock_customer_data(self, tenant_id: int, customer_id: int) -> dict:
249:     def predict_conversion_probability(self, opportunity_id: int) -> float:
```

`SalesRecommendationService` currently has no async methods and no database-backed opportunity queries. All per-customer data comes from `_get_mock_customer_data` (in-memory hash seeding). `predict_conversion_probability` exists but is also mock-based and takes no `tenant_id`. The service takes no `session` argument today.

### 2.2 涉及文件清单

- 要改：
  - [`src/services/sales_recommendation.py`](../../src/services/sales_recommendation.py) — add 3 async methods; update `__init__` to accept `AsyncSession`
- 要建：
  - `tests/unit/test_sales_recommendation.py` — unit tests for the 3 new methods (extend existing test file if present, else create)

### 2.3 缺什么

- [ ] No `AsyncSession`-backed opportunity queries — all data is mock/in-memory
- [ ] No `compute_confidence_score` method — confidence (0-100) combining deal age, update recency, and probability field
- [ ] No `find_similar_deals` method — query closed-won/lost deals by similar `amount` range, return top 3-5 with stage progression and `time_to_close`
- [ ] No `get_recommendations` aggregation method — combines signals into `next_action`, `confidence`, `reasons`, `similar_deals`
- [ ] Service constructor requires update to accept `AsyncSession` (required for DB queries)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_sales_recommendation.py` | 单元测试覆盖 `compute_confidence_score`、`find_similar_deals`、`get_recommendations` 三个新方法 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/sales_recommendation.py`](../../src/services/sales_recommendation.py) | `__init__` 新增 `session: AsyncSession` 参数；新增 `compute_confidence_score`、`find_similar_deals`、`get_recommendations` 三个 async 方法 |

### 3.3 新增能力

- **Service method**：`SalesRecommendationService.compute_confidence_score(self, opportunity_id: int, tenant_id: int) -> dict`
- **Service method**：`SalesRecommendationService.find_similar_deals(self, opportunity_id: int, tenant_id: int, limit: int = 5) -> list[dict]`
- **Service method**：`SalesRecommendationService.get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict`
- **Constructor change**：`__init__(self, session: AsyncSession)` — session is required (no `None` default per CLAUDE.md conventions)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Query `opportunities` table by `amount` range (±30%) for similar deals** — `OpportunityModel` has no `industry` column, so industry-based matching is not feasible. Amount range is the most reliable proxy available in the existing schema.
- **Return domain dicts (not ORM objects or dataclasses) from new methods** — consistent with the existing `SalesRecommendationService` pattern (`get_similar_customers` returns a list of `SimilarCustomer` dataclasses; new methods return plain dicts for direct router serialization).
- **Add `AsyncSession` to `__init__`** — required to issue real DB queries; existing no-arg constructor is replaced so callers must be updated. This is a breaking constructor change.

### 4.2 版本约束

（无新增依赖）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 错误抛 `AppException` 子类 — `NotFoundException("Opportunity")` 当商机不存在时，不返回 dict 或 None
- Service 返回 domain dicts，router 负责 `.to_dict()` 序列化
- `__init__` 的 `session` 参数类型为 `AsyncSession`，无默认值（与 CLAUDE.md §Service Pattern 一致）

### 4.4 已知坑

1. **`predict_conversion_probability` currently takes `opportunity_id` without `tenant_id`** — this existing method will be updated to match the new signature convention in a separate cleanup pass; do not rely on it in the new methods.
2. **Opportunity has no `last_contact_date` column** — use `updated_at` as the proxy for "last activity" in `compute_confidence_score`; document this assumption in the method docstring.

---

## 5. 实现步骤（按顺序）

### Step 1: Update `SalesRecommendationService.__init__` to accept `AsyncSession`

Add `session: AsyncSession` parameter (no default) to the constructor. Store as `self.session`. This enables DB queries in all new methods.

```python
from sqlalchemy.ext.asyncio import AsyncSession

class SalesRecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._customer_cache: dict[int, dict] = {}
```

**完成判定**：`PYTHONPATH=src ruff check src/services/sales_recommendation.py` → 0 errors

---

### Step 2: Add `compute_confidence_score` async method

Query the `opportunities` table for the given `opportunity_id` filtered by `tenant_id`. Raise `NotFoundException("Opportunity")` if not found. Compute confidence as a weighted score combining:
- **deal_age_score** (0-40): based on days since `created_at` — older open deals are higher urgency
- **recency_score** (0-40): based on days since `updated_at` — stale records score lower
- **probability_score** (0-20): raw `probability` field / 5 (maps 0-100 → 0-20)

Risk severity labels: `high` (score < 35), `medium` (35-65), `low` (> 65).

```python
async def compute_confidence_score(self, opportunity_id: int, tenant_id: int) -> dict:
    from datetime import datetime, timezone
    from sqlalchemy import select, text
    from db.models.opportunity import OpportunityModel

    stmt = select(OpportunityModel).where(
        OpportunityModel.id == opportunity_id,
        OpportunityModel.tenant_id == tenant_id
    )
    result = await self.session.execute(stmt)
    opp = result.scalar_one_or_none()
    if opp is None:
        raise NotFoundException("Opportunity")

    now = datetime.now(timezone.utc)
    age_days = (now - opp.created_at.replace(tzinfo=timezone.utc)).days
    stale_days = (now - opp.updated_at.replace(tzinfo=timezone.utc)).days

    deal_age_score = min(age_days / 60 * 40, 40)  # max at 60 days
    recency_score = max(0, 40 - stale_days * 2)    # loses 2 pts/day after last update
    probability_score = min(opp.probability / 5, 20)

    confidence = round(deal_age_score + recency_score + probability_score, 1)
    if confidence < 35:
        risk = "high"
    elif confidence < 65:
        risk = "medium"
    else:
        risk = "low"

    return {"opportunity_id": opportunity_id, "confidence": confidence, "risk_severity": risk}
```

**完成判定**：`PYTHONPATH=src python -c "from services.sales_recommendation import SalesRecommendationService; print('ok')"` → exit 0

---

### Step 3: Add `find_similar_deals` async method

Query all non-open opportunities (`stage` NOT IN `['lead', 'qualification', 'proposal', 'negotiation']`) within the same `tenant_id`, with `amount` within ±30% of the target's amount, excluding the opportunity itself. Return `limit` results (default 5) ordered by amount similarity.

Each result dict includes: `opportunity_id`, `name`, `stage`, `amount`, `days_to_close` (abs diff between `updated_at` and `created_at`), and a `stage_progression` key (list of stages inferred from creation order — not tracked in current schema, so return `["created", opp.stage]` as a stub).

```python
async def find_similar_deals(self, opportunity_id: int, tenant_id: int, limit: int = 5) -> list[dict]:
    from sqlalchemy import select, and_, or_
    from db.models.opportunity import OpportunityModel

    target_result = await self.session.execute(
        select(OpportunityModel).where(
            OpportunityModel.id == opportunity_id,
            OpportunityModel.tenant_id == tenant_id
        )
    )
    target = target_result.scalar_one_or_none()
    if target is None:
        raise NotFoundException("Opportunity")

    CLOSED_STAGES = ["closed_won", "closed_lost"]
    amount_min = target.amount * Decimal("0.7")
    amount_max = target.amount * Decimal("1.3")

    stmt = select(OpportunityModel).where(
        and_(
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.stage.in_(CLOSED_STAGES),
            OpportunityModel.id != opportunity_id,
            OpportunityModel.amount >= amount_min,
            OpportunityModel.amount <= amount_max,
        )
    ).order_by(
        sqlalchemy.func.abs(OpportunityModel.amount - target.amount)
    ).limit(limit)

    result = await self.session.execute(stmt)
    similar = result.scalars().all()

    from datetime import timedelta
    return [
        {
            "opportunity_id": o.id,
            "name": o.name,
            "stage": o.stage,
            "amount": str(o.amount),
            "days_to_close": (o.updated_at - o.created_at).days,
            "stage_progression": ["created", o.stage],
        }
        for o in similar
    ]
```

**完成判定**：`PYTHONPATH=src ruff check src/services/sales_recommendation.py` → 0 errors

---

### Step 4: Add `get_recommendations` async method

Combine `compute_confidence_score` and `find_similar_deals` results. Derive `next_action` and `reasons` from confidence and risk severity:
- `risk_severity == "high"` → action `"immediate_follow_up"`, reason `"Deal urgency high — last contact stale"`
- `risk_severity == "medium"` → action `"scheduled_call"`, reason `"Moderate risk — monitor closely"`
- `risk_severity == "low"` → action `"maintain_engagement"`, reason `"Deal progressing well"`

Also push `similar_deals` from `find_similar_deals` into the result. Return one dict with keys: `opportunity_id`, `next_action`, `confidence`, `risk_severity`, `reasons` (list), `similar_deals` (list).

```python
async def get_recommendations(self, opportunity_id: int, tenant_id: int) -> dict:
    confidence_data = await self.compute_confidence_score(opportunity_id, tenant_id)
    similar = await self.find_similar_deals(opportunity_id, tenant_id, limit=5)

    risk = confidence_data["risk_severity"]
    if risk == "high":
        next_action = "immediate_follow_up"
        reasons = ["Deal urgency high — last contact stale", "Recommend direct outreach within 24h"]
    elif risk == "medium":
        next_action = "scheduled_call"
        reasons = ["Moderate risk — monitor closely", "Schedule check-in within this week"]
    else:
        next_action = "maintain_engagement"
        reasons = ["Deal progressing well", "Continue current engagement cadence"]

    if similar:
        reasons.append(f"Found {len(similar)} similar closed deals for benchmarking")

    return {
        "opportunity_id": opportunity_id,
        "next_action": next_action,
        "confidence": confidence_data["confidence"],
        "risk_severity": risk,
        "reasons": reasons,
        "similar_deals": similar,
    }
```

**完成判定**：`PYTHONPATH=src ruff check src/services/sales_recommendation.py` → 0 errors

---

### Step 5: Write unit tests for all three new methods

In `tests/unit/test_sales_recommendation.py`, add tests using `make_mock_session` with an opportunity handler. Mock the SQLAlchemy result to return a synthetic `OpportunityModel` for each test.

Test cases:
1. `test_compute_confidence_score_returns_dict_with_confidence_and_risk` — happy path
2. `test_compute_confidence_score_raises_not_found_on_missing_opportunity`
3. `test_find_similar_deals_returns_list_of_dicts`
4. `test_find_similar_deals_raises_not_found_on_missing_opportunity`
5. `test_get_recommendations_returns_full_recommendation_dict`
6. `test_get_recommendations_action_matches_risk_severity` (parametrized for high/medium/low)

```python
# Mock handler for opportunities (add to tests/unit/conftest.py if not present)
def make_opportunity_handler(state):
    async def handle(session, op):
        if op.type == "SELECT":
            return state.opportunities.get(op.filters.get("id"))
        return None
    return handle
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → ≥ 6 passed

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/sales_recommendation.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/services/sales_recommendation.py` → pass
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_recommendation.py -v` → ≥ 6 passed
- [ ] `SalesRecommendationService.__init__` signature accepts exactly `self, session: AsyncSession` — no default
- [ ] `compute_confidence_score`, `find_similar_deals`, `get_recommendations` are all `async def` methods
- [ ] All SQL queries in new methods include `WHERE tenant_id = :tenant_id`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Constructor signature change breaks existing callers of `SalesRecommendationService()` (no-arg) | 中 | 中 | Issue #668 router update will pass `session` via DI; temporarily use `make_mock_session(None)` in tests |
| `updated_at` used as proxy for "last contact" may overstate staleness when only system updates (not human contact) occur | 低 | 低 | Document as known limitation; confidence score is a guide, not ground truth — not a blocker for #668 |
| Amount range ±30% for similar deals may return too few results on edge-case amounts (very large or very small) | 低 | 低 | Add `amount_min` floor (`Decimal("1")`) and cap result set to ensure at least 1 similar deal when possible |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/sales_recommendation.py tests/unit/test_sales_recommendation.py
git commit -m "feat(20-sales): add compute_confidence_score, find_similar_deals, get_recommendations to SalesRecommendationService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#667): scoring and similar-deals logic for SalesRecommendationService" --body "Closes #667"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/sales_recommendation.py`](../../src/services/sales_recommendation.py) — existing `SalesRecommendationService` with similar dataclass + mock pattern; new methods follow the same service-layer conventions
- 同类参考实现：[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) — `calculate_churn_score` async method pattern with multi-factor weighted scoring (useful reference for confidence score weighting)
- 同类参考实现：[`src/db/models/opportunity.py`](../../src/db/models/opportunity.py) — `OpportunityModel` fields used in scoring (`created_at`, `updated_at`, `amount`, `probability`, `stage`)
- 父 issue / 关联：#36 (parent epic), #666 (dependency — service get-methods), #668 (downstream API endpoint), #669 (downstream cache invalidation)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
