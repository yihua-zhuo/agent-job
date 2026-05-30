# Scoreservice · Calculate customer health score via static rules

| 元数据 | 值 |
|---|---|
| Issue | #583 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：#582 |
| 启用后赋能 | TBD - 待验证：#584, TBD - 待验证：#585 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM currently stores customer attributes (company_size, industry, engagement_level, budget, etc.) but has no mechanism to derive a unified health or value score from them. Without a quantitative score, sales and success teams cannot consistently prioritize outreach, personalize engagement, or benchmark accounts. This is a prerequisite for analytics dashboards, automated workflows, and any downstream feature that needs to rank or segment customers.

### 1.2 做完后

- **用户视角**：Each customer record will display a computed score (0–100) and tier badge (A/B/C/D). Sales reps see a ranked list of accounts; CS sees at-risk customers in tier D. Recommendations such as "Schedule a QBR" or "Expand to mid-market" surface on the customer detail view.
- **开发者视角**：`ScoreService` becomes the canonical scoring entry point. `calculate_score(customer_id, tenant_id)` runs the static rule engine and returns `(score: int, tier: str, top_factors: list[str], recommendations: list[str])`. `get_score(customer_id, tenant_id)` retrieves or computes and caches the latest score for a customer. Both methods raise `NotFoundException` if the customer is absent.

### 1.3 不做什么（剔除）

- [ ] AI / LLM-powered scoring — this board covers static rule-based evaluation only.
- [ ] Automatic re-calculation triggered by customer data changes — covered by #585.
- [ ] Persisting score history / audit log — out of scope for now.
- [ ] UI components displaying the score — out of scope (handled by a downstream front-end board).

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 5 passed
- [ ] `ruff check src/services/score_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_score_service_integration.py -v` → 全 passed（如 integration test is created）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（if migration is needed）

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

TBD - 待验证：`src/db/models/customer.py` — 现有 CustomerModel 的字段清单（company_size, industry, engagement_level, budget 等是否存在）；[`src/services/customer_service.py`](../../../src/services/customer_service.py) — get_customer / fetch logic

### 2.2 涉及文件清单

- 要改：
  - `TBD - 待验证：`src/services/customer_service.py` — 如需添加 cache helpers
  - `TBD - 待验证：`src/api/routers/customers.py` — 如需暴露 score endpoint（实际由 #584 处理）
- 要建：
  - [`src/services/score_service.py`](../../../src/services/score_service.py) — ScoreService with calculate_score + get_score
  - [`src/models/score.py`](../../../src/models/score.py) — Pydantic schemas: ScoreResult, ScoreTier enum
  - [`tests/unit/test_score_service.py`](../../../tests/unit/test_score_service.py) — Unit tests (MockRow / MockResult / MockState)
  - `TBD - 待验证：`tests/integration/test_score_service_integration.py` — Integration tests

### 2.3 缺什么

- [ ] `ScoreService` class — no scoring engine exists
- [ ] `ScoreResult` Pydantic schema — no structured response type for score output
- [ ] `get_score` retrieval / cache pattern — no mechanism to reuse a previously computed score
- [ ] Deterministic scoring weights for customer fields — no agreed-upon rule set
- [ ] Tier classification (A/B/C/D) — no tier mapping from numeric score
- [ ] Top factors extraction — no logic to surface which fields contributed most
- [ ] Recommendation generation — no rule → recommendation mapping

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| [`src/services/score_service.py`](../../../src/services/score_service.py) | ScoreService: calculate_score + get_score; static rule engine |
| [`src/models/score.py`](../../../src/models/score.py) | Pydantic schemas: ScoreResult, ScoreTier enum |
| [`tests/unit/test_score_service.py`](../../../tests/unit/test_score_service.py) | Unit tests with MockState / MockRow / MockResult |
| `TBD - 待验证：`tests/integration/test_score_service_integration.py` | Integration tests against real Postgres |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `TBD - 待验证：`src/services/customer_service.py | Add optional score cache helpers if get_score needs persistence |
| `TBD - 待验证：`src/models/__init__.py | Re-export ScoreResult, ScoreTier |

### 3.3 新增能力

- **Service**：`ScoreService.calculate_score(self, customer_id: int, tenant_id: int) -> tuple[int, str, list[str], list[str]]` — runs static rules, returns (score, tier, top_factors, recommendations)
- **Service**：`ScoreService.get_score(self, customer_id: int, tenant_id: int) -> tuple[int, str, list[str], list[str]]` — retrieves or computes score
- **ORM model**：N/A (no new table in this board; ScoreResult is a Pydantic dataclass)
- **Pydantic schema**：`ScoreResult` (score: int, tier: str, top_factors: list[str], recommendations: list[str]); `ScoreTier` enum (A/B/C/D)
- **Exception**：`NotFoundException("Customer")` when customer_id not found for tenant

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Static if/elif rule engine 不选 LLM** — deterministic, unit-testable, no external dependency, fast. Required by issue scope.
- **Tier boundaries: A ≥ 80, B 60–79, C 40–59, D < 40** — industry-standard quartile split; easy to adjust via constants.
- **Score range 0–100** — normalized scale; each field contributes a sub-weight, summed and clamped.
- **top_factors = top 2–3 fields by absolute contribution** — keeps the result actionable without overwhelming the user.
- **Recommendations generated from a field → text map** — simple dict lookup, no ML needed; extendable.

### 4.2 版本约束

无新依赖引人。全部使用已有 `sqlalchemy`, `pydantic`, `pytest`。

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id`
- Service `__init__` takes `session: AsyncSession` with NO default
- Service returns raw tuple / dataclass objects; **no** `.to_dict()` call in service
- Service errors raise `AppException` subclasses (`NotFoundException`); **no** `ApiResponse.error()` return
- Router (handled in #584) is responsible for serialization via `.to_dict()`
- All imports use `from db.models...`, `from services...`, `from pkg.errors...` — never `from src.db.models...`

### 4.4 已知坑

1. **SQLAlchemy Base column named `metadata`** → Not applicable in this board (no new ORM model).
2. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()` and drops `timezone=True` on DateTime** → Not applicable (no migration in this board; verify in #585 if migration is added).
3. **PYTHONPATH must be `src`** → All test commands run as `PYTHONPATH=src pytest ...`.
4. **Unit tests must not hit real DB** → Use `MockState`, `MockRow`, `MockResult` from `tests/unit/conftest.py`. Each test file defines its own `mock_db_session` fixture.

---

## 5. 实现步骤（按顺序）

### Step 1: Define ScoreResult Pydantic schema and ScoreTier enum

Create `src/models/score.py`. Define `ScoreTier` enum (A/B/C/D) and `ScoreResult` Pydantic model with fields: `score: int`, `tier: ScoreTier`, `top_factors: list[str]`, `recommendations: list[str]`. Add `__all__` export list.

操作：
- a) Write `src/models/score.py` with enum and schema
- b) Add re-export in `src/models/__init__.py`

```python
from enum import StrEnum
from pydantic import BaseModel, Field


class ScoreTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ScoreResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    tier: ScoreTier
    top_factors: list[str]
    recommendations: list[str]
```

**完成判定**：`ruff check src/models/score.py` → 0 errors

---

### Step 2: Implement ScoreService with calculate_score and get_score

Create `src/services/score_service.py`. Implement `ScoreService`:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.customer import CustomerModel  # TBD - 待验证字段名
from pkg.errors.app_exceptions import NotFoundException

# Field weights (sum to 100 or normalized)
FIELD_WEIGHTS = {
    "company_size": 25,
    "engagement_level": 25,
    "budget": 25,
    "industry": 15,
    "last_activity_days": 10,
}

TIER_BOUNDARIES = [(80, ScoreTier.A), (60, ScoreTier.B), (40, ScoreTier.C)]
TIER_D = ScoreTier.D

FIELD_RECOMMENDATIONS = {
    "company_size": "Consider enterprise expansion play",
    "engagement_level": "Increase touchpoints with targeted campaigns",
    "budget": "Propose premium upsell package",
    "industry": "Tailor vertical-specific case studies",
    "last_activity_days": "Schedule re-engagement call",
}


class ScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_score(self, customer_id: int, tenant_id: int):
        result = await self.session.execute(
            select(CustomerModel).where(
                CustomerModel.id == customer_id,
                CustomerModel.tenant_id == tenant_id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundException("Customer")

        total = 0
        contributions = {}
        # company_size: 1-10 → 0-100 scale
        size_score = min(100, int((customer.company_size or 0) * 10))
        contributions["company_size"] = size_score
        total += size_score * FIELD_WEIGHTS["company_size"] // 100

        # engagement_level: enum/str → mapped score
        engagement_map = {"high": 100, "medium": 65, "low": 30, None: 0}
        eng_score = engagement_map.get(customer.engagement_level, 0)
        contributions["engagement_level"] = eng_score
        total += eng_score * FIELD_WEIGHTS["engagement_level"] // 100

        # budget: 0=None, 1=low, 2=mid, 3=high → 0/33/66/100
        budget_map = {3: 100, 2: 66, 1: 33, 0: 0, None: 0}
        bud_score = budget_map.get(customer.budget, 0)
        contributions["budget"] = bud_score
        total += bud_score * FIELD_WEIGHTS["budget"] // 100

        # industry: known vertical → +15 or +5 (diverse list)
        known_industries = ["technology", "finance", "healthcare", "retail"]
        ind_score = 100 if customer.industry in known_industries else 50
        contributions["industry"] = ind_score
        total += ind_score * FIELD_WEIGHTS["industry"] // 100

        # last_activity_days: <=7 → 100, 8-30 → 60, 31-90 → 30, >90 → 0
        days = getattr(customer, "last_activity_days", None) or 999
        if days <= 7:
            act_score = 100
        elif days <= 30:
            act_score = 60
        elif days <= 90:
            act_score = 30
        else:
            act_score = 0
        contributions["last_activity_days"] = act_score
        total += act_score * FIELD_WEIGHTS["last_activity_days"] // 100

        # Clamp to 0-100
        score = max(0, min(100, total))

        # Tier
        tier = TIERS_D
        for threshold, t in TIER_BOUNDARIES:
            if score >= threshold:
                tier = t
                break

        # Top 2-3 factors by absolute contribution
        sorted_contrib = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        top_factors = [k for k, v in sorted_contrib[:3] if v > 0]

        # Recommendations: one per contributing field above threshold
        recommendations = [
            FIELD_RECOMMENDATIONS[f]
            for f in top_factors
            if f in FIELD_RECOMMENDATIONS
        ]

        return score, tier.value, top_factors, recommendations

    async def get_score(self, customer_id: int, tenant_id: int):
        return await self.calculate_score(customer_id, tenant_id)
```

操作：
- a) Write `src/services/score_service.py` with the full service above
- b) Verify CustomerModel field names match (`company_size`, `engagement_level`, `budget`, `industry`, `last_activity_days`) — if not confirmed, use `TBD - 待验证` placeholders and adjust in code review

**完成判定**：`ruff check src/services/score_service.py` → 0 errors

---

### Step 3: Write unit tests for ScoreService

Create `tests/unit/test_score_service.py`. Define `mock_db_session` fixture using `MockState`, `MockRow`, `MockResult`, and handler helpers from `conftest.py`. Test the following cases:

- `test_calculate_score_tier_a` — customer with high engagement, large size, high budget → score ≥ 80, tier A
- `test_calculate_score_tier_d` — customer with low engagement, no budget, stale activity → score < 40, tier D
- `test_calculate_score_middle_tier` — customer in B/C range
- `test_calculate_score_not_found` → raises `NotFoundException`
- `test_get_score_delegates_to_calculate` — get_score returns same result as calculate_score
- `test_top_factors_excludes_zero_contribution` — fields scoring 0 do not appear in top_factors
- `test_recommendations_match_top_factors` — each top_factor generates a recommendation

操作：
- a) Write `tests/unit/test_score_service.py`
- b) Run `PYTHONPATH=src pytest tests/unit/test_score_service.py -v`

```python
import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select
from services.score_service import ScoreService
from pkg.errors.app_exceptions import NotFoundException
from tests.unit.conftest import MockState, MockRow, make_mock_session


@pytest.fixture
def mock_db_session():
    state = MockState()
    def execute_handler(query):
        # Return a mock customer for customer_id=1
        return MockResult(rows=[
            MockRow(id=1, tenant_id=10, company_size=8, engagement_level="high",
                   budget=3, industry="technology", last_activity_days=5)
        ])
    return make_mock_session(execute_handler=execute_handler)


@pytest.fixture
def score_service(mock_db_session):
    return ScoreService(mock_db_session)


@pytest.mark.asyncio
async def test_calculate_score_tier_a(score_service):
    score, tier, factors, recs = await score_service.calculate_score(1, 10)
    assert score >= 80
    assert tier == "A"
    assert len(factors) <= 3
    assert len(recs) <= 3


@pytest.mark.asyncio
async def test_calculate_score_not_found(score_service):
    with pytest.raises(NotFoundException):
        await score_service.calculate_score(999, 10)


@pytest.mark.asyncio
async def test_get_score_delegates(score_service):
    r1 = await score_service.get_score(1, 10)
    r2 = await score_service.calculate_score(1, 10)
    assert r1 == r2
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 5 passed

---

### Step 4: Run full verification

操作：
- a) `ruff check src/services/score_service.py src/models/score.py` → 0 errors
- b) `ruff format --check src/services/score_service.py src/models/score.py` → pass
- c) `PYTHONPATH=src mypy src/services/score_service.py` → 0 errors (if mypy config present)
- d) `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 5 passed

**完成判定**：All commands above exit 0 with expected pass count.

---

## 6. 验收

- [ ] `ruff check src/services/score_service.py src/models/score.py` → 0 errors
- [ ] `ruff format --check src/services/score_service.py src/models/score.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src mypy src/services/score_service.py` → 0 errors (if mypy is configured)
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（only if a migration was added in a follow-up step; otherwise skip）
- [ ] ScoreService returns correct tier (A/B/C/D) and top_factors length ≤ 3 for all test cases

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| CustomerModel field names differ from assumed schema (company_size, engagement_level, budget, industry) | 中 | 高 — tests fail, service crashes | Add defensive `getattr(customer, "field", default)` and adjust FIELD_WEIGHTS dict keys after verifying schema; no downstream board is blocked until ScoreService is merged |
| Scoring weights produce unexpected tier distribution | 中 | 中 — tier boundaries are arbitrary | Expose weights as module-level constants; adjust thresholds in §4.1; unit tests validate expected tier per fixture |
| ScoreService.get_score added to a downstream board's router before ScoreService is merged | 低 | 高 — import error in downstream router | Gate router changes behind the ScoreService merge; downstream board #584 can merge after this one |
| NotFoundException import path wrong | 低 | 中 — import error | Confirm `from pkg.errors.app_exceptions import NotFoundException` is correct path; adjust if verified |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/score_service.py src/models/score.py tests/unit/test_score_service.py
git commit -m "feat(scoring): implement ScoreService with static rule engine"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#583): implement ScoreService with static non-AI scoring logic" --body "Closes #583"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — existing service pattern to follow
- 第三方文档：[Pydantic docs](https://docs.pydantic.dev/) — ScoreResult schema
- 父 issue / 关联：#49 (parent epic), TBD - 待验证：#582 (ScoreResult model — dependency), TBD - 待验证：#584 (score API router), TBD - 待验证：#585 (auto-recalculation trigger)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---

Changes made:
- **Lines 9–10** (依赖/启用后赋能): `0582-*.md`, `0584-*.md`, `0585-*.md` don't exist — replaced with `TBD - 待验证：#582` etc.
- **Lines 56, 57, 58, 79, 80, 81**: `../../src/...` → `../../../src/...` (board lives 3 levels deep under `docs/dev-plan/60-analytics/`, not 2). This matches the pattern already used on line 30 (`../../../src/services/customer_service.py`).
