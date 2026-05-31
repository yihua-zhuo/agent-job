# Sales · Implement risk-indicator detection in RecommendationService

| 元数据 | 值 |
|---|---|
| Issue | #666 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：确认 activity detection service 文档编号（0655 或 0665） |
| 启用后赋能 | [0667-implement-recommendation-scoring-and-similar-deals-logic](0667-implement-recommendation-scoring-and-similar-deals-logic.md), [0668-add-get-sales-opportunities-id-recommendations-endpoint](0668-add-get-sales-opportunities-id-recommendations-endpoint.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The current CRM system surfaces open opportunities to sales reps but provides no automated signals when a deal is going cold, overdue, disengaged, or mentions a competitor. Sales teams lose deals to silence — a deal that hasn't moved in 7 days, a past due date, or a competitor named in notes are all actionable signals that exist in the data but are never surfaced. The RecommendationService (separate from the existing mock-only `SalesRecommendationService`) needs a structured, rule-based risk-indicator layer before similarity/comparison logic can be built on top.

### 1.2 做完后

- **用户视角**：Sales reps and managers will have programmatic access to four risk signals per opportunity: stalled (no activity > 7 days), overdue (past expected_close_date), low engagement (no email activity), and competitor mentions (text match in activity notes). No UI is included in this board.
- **开发者视角**：`RecommendationService` provides four `detect_*` async methods, each returning a typed `RiskIndicator` dataclass with `indicator_type: str` and `severity: float`. Downstream services (scoring, ranking, router) can call these methods without duplicating SQL logic.

### 1.3 不做什么（剔除）

- [ ] Similarity / comparison logic between opportunities (deferred to #667)
- [ ] API router or HTTP endpoint (deferred to #668)
- [ ] Notification / alert triggers based on risk indicators
- [ ] Machine-learning model for risk scoring — rule-based only

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors]
- [指标 2：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → ≥ 12 passed (4 methods × 3 cases each)]
- [指标 3：`PYTHONPATH=src mypy src/services/recommendation_service.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `src/services/__init__.py` — 导出新增的 `RecommendationService`
- 要建：
  - `src/services/recommendation_service.py` — 核心检测逻辑
  - `tests/unit/test_recommendation_service.py` — 单元测试（mock DB）
  - `src/api/routers/recommendations.py` — API router（可选，列在 §3.2 供后续板块直接使用）

### 2.3 缺什么

- [ ] `RecommendationService` class with async `detect_*` methods — does not exist
- [ ] Typed return model for risk indicators (`RiskIndicator` dataclass) — missing
- [ ] SQL queries that join `opportunities` + `activities` filtered by `tenant_id` and `opportunity_id` — not yet written
- [ ] Unit tests covering stalled, overdue, low-engagement, and competitor-mention detection
- [ ] Activity `type` values are free-form `String(50)` — no enforced enum, so detection must use case-insensitive substring match

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/services/recommendation_service.py` | Risk-indicator detection service (4 detect_* methods) |
| `tests/unit/test_recommendation_service.py` | Unit tests for all 4 detect_* methods with mock DB |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/__init__.py` | 新增 `RecommendationService` 导出 |
| `src/api/routers/recommendations.py` | 新建 router（供 #668 直接使用；本板块仅 scaffold，验证完整路径注册在 main.py） |

### 3.3 新增能力

- **Service class**：`RecommendationService(session: AsyncSession)`
- **Service methods**：
  - `detect_stalled(self, opportunity_id: int, tenant_id: int, days_threshold: int = 7) -> list[RiskIndicator]`
  - `detect_overdue(self, opportunity_id: int, tenant_id: int) -> list[RiskIndicator]`
  - `detect_low_engagement(self, opportunity_id: int, tenant_id: int) -> list[RiskIndicator]`
  - `detect_competitor_mentions(self, opportunity_id: int, tenant_id: int) -> list[RiskIndicator]`
- **Dataclass**：`RiskIndicator(indicator_type: str, severity: float, detail: str | None = None)`
- **Router**：`GET /api/v1/recommendations/opportunities/{id}/risk-indicators` (returns `list[RiskIndicator]`)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `ActivityModel` 作为 activity 来源，不新建 `OpportunityActivityModel`**：`ActivityModel.opportunity_id` already links activities to opportunities. Creating a separate join table would duplicate the same relationship. Detection queries use `WHERE opportunity_id = :opportunity_id AND tenant_id = :tenant_id`.
- **选 severity 0.0–1.0 浮点数，不选枚举 tier（高/中/低）**：Floating-point severity allows downstream scoring services to weight and threshold indicators precisely. An enum would lose information.
- **选 dataclass `RiskIndicator` 作为返回类型，不返回 dict**：Typed dataclass enables static type checking and self-documenting method signatures. Routers call `.to_dict()` for serialization.
- **competitor 关键词使用硬编码列表，不从 DB/配置读取**：Keeps this board self-contained. Configurable keyword lists can be added in #667 when more sophisticated logic lands.

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service constructor accepts `session: AsyncSession` with no default value
- Service raises `AppException` subclasses on errors; does **not** return `ApiResponse.error()`
- Router calls `session.execute()` with `text()` for raw SQL when ORM query is insufficient (competitor text search)
- Activity `type` column is free-form `String(50)` — keyword detection must use `ILIKE`/`LOWER()` for case-insensitive match

### 4.4 已知坑

1. **Activity `type` values are unconstrained** → 规避：email engagement detection uses `ILIKE '%email%'` / `ILIKE '%open%'` / `ILIKE '%reply%'` — broad but safe substring match
2. **`expected_close_date` may be NULL** → 规避：`detect_overdue` only fires when `expected_close_date IS NOT NULL AND expected_close_date < now()`
3. **No activity at all for a brand-new opportunity should not count as "stalled"** → 规避：`detect_stalled` sets `days_threshold=7` default; if opportunity was created within the last 7 days it returns empty list regardless of activity date
4. **Severity calibration** → 规避：start with simple linear mappings (e.g., days overdue / 30 capped at 1.0) — refine in #667 when real usage data is available

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold `src/services/recommendation_service.py` — models and constructor

Create the file with imports, the `RiskIndicator` dataclass, and the `RecommendationService` class shell with the `__init__` storing the session. No DB calls yet.

```python
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class RiskIndicator:
    """Risk indicator returned by detect_* methods."""
    indicator_type: str       # e.g. "stalled", "overdue", "low_engagement", "competitor_mention"
    severity: float          # 0.0–1.0
    detail: str | None = None

class RecommendationService:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors

---

### Step 2: Implement `detect_stalled`

Query `activities` for the given `opportunity_id` ordered by `created_at DESC`, take the first row. If the latest activity is more than `days_threshold` calendar days ago (default 7), return one `RiskIndicator` with `indicator_type="stalled"` and severity proportional to staleness (days / 30, capped at 1.0). If there are no activities, use `opportunities.updated_at` as the fallback last-activity timestamp.

```python
    async def detect_stalled(
        self, opportunity_id: int, tenant_id: int, days_threshold: int = 7
    ) -> list[RiskIndicator]:
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import text

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)

        result = await self.session.execute(
            text("""
                SELECT created_at FROM activities
                WHERE opportunity_id = :opp_id AND tenant_id = :tid
                ORDER BY created_at DESC LIMIT 1
            """),
            {"opp_id": opportunity_id, "tid": tenant_id}
        )
        row = result.scalar_one_or_none()

        last_activity_at = row if row else None

        if last_activity_at is None:
            opp_result = await self.session.execute(
                text("SELECT updated_at FROM opportunities WHERE id = :id AND tenant_id = :tid"),
                {"id": opportunity_id, "tid": tenant_id}
            )
            opp_row = opp_result.scalar_one_or_none()
            if opp_row is None:
                return []
            last_activity_at = opp_row

        if last_activity_at.tzinfo is None:
            last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)

        if last_activity_at >= cutoff:
            return []

        days_stale = (datetime.now(timezone.utc) - last_activity_at).days
        severity = min(days_stale / 30.0, 1.0)
        return [RiskIndicator(
            indicator_type="stalled",
            severity=round(severity, 2),
            detail=f"No activity for {days_stale} days (threshold: {days_threshold})"
        )]
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors；单元测试中 `detect_stalled` 可被调用并返回 `list[RiskIndicator]`

---

### Step 3: Implement `detect_overdue`

Query `opportunities` for the given `opportunity_id` and `tenant_id`. If `expected_close_date` is not NULL and is before `now()`, return one `RiskIndicator` with `indicator_type="overdue"`. Severity = `days_overdue / 30.0`, capped at 1.0.

```python
    async def detect_overdue(self, opportunity_id: int, tenant_id: int) -> list[RiskIndicator]:
        from datetime import datetime, timezone
        from sqlalchemy import text

        result = await self.session.execute(
            text("SELECT expected_close_date FROM opportunities WHERE id = :id AND tenant_id = :tid"),
            {"id": opportunity_id, "tid": tenant_id}
        )
        row = result.scalar_one_or_none()
        if row is None:
            return []

        expected_close = row
        if expected_close.tzinfo is None:
            expected_close = expected_close.replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if expected_close >= now_utc:
            return []

        days_overdue = (now_utc - expected_close).days
        severity = min(days_overdue / 30.0, 1.0)
        return [RiskIndicator(
            indicator_type="overdue",
            severity=round(severity, 2),
            detail=f"Expected close date was {days_overdue} days ago"
        )]
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors

---

### Step 4: Implement `detect_low_engagement`

Query distinct activity `type` values for the given `opportunity_id` within the last 30 days. If none of the activity types contain `email`, `open`, `reply`, `send`, `touch` (case-insensitive), return one `RiskIndicator` with `indicator_type="low_engagement"`. Severity is always 0.5 (tuned in #667).

```python
    async def detect_low_engagement(
        self, opportunity_id: int, tenant_id: int, lookback_days: int = 30
    ) -> list[RiskIndicator]:
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import text

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        result = await self.session.execute(
            text("""
                SELECT DISTINCT LOWER(type) AS activity_type FROM activities
                WHERE opportunity_id = :opp_id
                  AND tenant_id = :tid
                  AND created_at >= :cutoff
            """),
            {"opp_id": opportunity_id, "tid": tenant_id, "cutoff": cutoff}
        )
        rows = result.fetchall()
        all_types = [r[0] for r in rows]

        email_keywords = ["email", "open", "reply", "send", "touch"]
        has_email = any(any(kw in t for kw in email_keywords) for t in all_types)

        if has_email or not all_types:
            return []

        return [RiskIndicator(
            indicator_type="low_engagement",
            severity=0.5,
            detail=f"No email engagement activity in the last {lookback_days} days"
        )]
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors

---

### Step 5: Implement `detect_competitor_mentions`

Query `activities` for the given `opportunity_id` with `ILIKE` match on `content` against a hardcoded competitor keyword list. Each match returns one `RiskIndicator` with `indicator_type="competitor_mention"`. Severity = 0.6 if a competitor is named (future: could be weighted by number of mentions, tuned in #667).

```python
COMPETITOR_KEYWORDS = [
    "salesforce", "hubspot", "dynamics", "zoho",
    "pipedrive", "freshsales", "oracle", "sap",
]
```

```python
    async def detect_competitor_mentions(
        self, opportunity_id: int, tenant_id: int
    ) -> list[RiskIndicator]:
        from sqlalchemy import text

        keyword_pattern = " OR ".join(
            f"LOWER(content) LIKE :kw_{i}" for i in range(len(COMPETITOR_KEYWORDS))
        )
        params = {f"kw_{i}": f"%{kw}%" for i, kw in enumerate(COMPETITOR_KEYWORDS)}
        params["opp_id"] = opportunity_id
        params["tid"] = tenant_id

        result = await self.session.execute(
            text(f"""
                SELECT id, content FROM activities
                WHERE opportunity_id = :opp_id
                  AND tenant_id = :tid
                  AND ({keyword_pattern})
            """),
            params
        )
        rows = result.fetchall()
        return [
            RiskIndicator(
                indicator_type="competitor_mention",
                severity=0.6,
                detail=f"Competitor keyword '{kw}' found in activity id={row[0]}"
            )
            for row in rows
            for kw in COMPETITOR_KEYWORDS
            if kw in (row[1] or "").lower()
        ]
```

**完成判定**：`PYTHONPATH=src ruff check src/services/recommendation_service.py` → 0 errors

---

### Step 6: Write unit tests `tests/unit/test_recommendation_service.py`

Define `mock_db_session` fixture using `MagicMock` + `AsyncMock` (no DB). Write 3 test cases per method:

**Happy path**: `detect_stalled` returns non-empty list when latest activity is 10 days ago; `detect_overdue` returns non-empty when `expected_close_date` is yesterday; `detect_low_engagement` returns non-empty when only `call` activities exist; `detect_competitor_mentions` returns non-empty when activity content contains "salesforce".

**Boundary**: `detect_stalled` returns empty list when activity is 3 days ago (below 7-day threshold); `detect_overdue` returns empty when `expected_close_date` is in the future; `detect_low_engagement` returns empty when `email` activity exists; `detect_competitor_mentions` returns empty when no competitor keywords present.

**Error**: `detect_stalled` / `detect_overdue` return empty list when `opportunity_id` does not exist (tenant_id matches but row absent); `detect_low_engagement` returns empty when no activities exist in lookback window; `detect_competitor_mentions` returns empty when `content` is NULL.

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
from services.recommendation_service import RecommendationService, RiskIndicator

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.execute = AsyncMock()
    return session

@pytest.mark.asyncio
async def test_detect_stalled_returns_indicator_when_no_activity(mock_db_session):
    stale_date = datetime.now(timezone.utc) - timedelta(days=10)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=stale_date)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_stalled(opportunity_id=1, tenant_id=1, days_threshold=7)
    assert len(result) == 1
    assert result[0].indicator_type == "stalled"
    assert 0.0 < result[0].severity <= 1.0

@pytest.mark.asyncio
async def test_detect_stalled_returns_empty_when_recent_activity(mock_db_session):
    recent_date = datetime.now(timezone.utc) - timedelta(days=3)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=recent_date)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_stalled(opportunity_id=1, tenant_id=1, days_threshold=7)
    assert result == []

@pytest.mark.asyncio
async def test_detect_stalled_returns_empty_when_opportunity_not_found(mock_db_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(side_effect=[None, None])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_stalled(opportunity_id=999, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_overdue_returns_indicator_when_past_due_date(mock_db_session):
    past_date = datetime.now(timezone.utc) - timedelta(days=5)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=past_date)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_overdue(opportunity_id=1, tenant_id=1)
    assert len(result) == 1
    assert result[0].indicator_type == "overdue"

@pytest.mark.asyncio
async def test_detect_overdue_returns_empty_when_future_date(mock_db_session):
    future_date = datetime.now(timezone.utc) + timedelta(days=10)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=future_date)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_overdue(opportunity_id=1, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_overdue_returns_empty_when_no_expected_date(mock_db_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = AsyncMock(return_value=None)
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_overdue(opportunity_id=1, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_low_engagement_returns_indicator_when_no_email_activity(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[("call",), ("meeting",)])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_low_engagement(opportunity_id=1, tenant_id=1)
    assert len(result) == 1
    assert result[0].indicator_type == "low_engagement"

@pytest.mark.asyncio
async def test_detect_low_engagement_returns_empty_when_email_present(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[("call",), ("email_sent",)])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_low_engagement(opportunity_id=1, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_low_engagement_returns_empty_when_no_activities(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_low_engagement(opportunity_id=1, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_competitor_mentions_returns_indicator_when_keyword_found(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[(1, "The client is evaluating us vs Salesforce")])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_competitor_mentions(opportunity_id=1, tenant_id=1)
    assert len(result) == 1
    assert result[0].indicator_type == "competitor_mention"
    assert result[0].severity == 0.6

@pytest.mark.asyncio
async def test_detect_competitor_mentions_returns_empty_when_no_match(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[(2, "Good progress on the demo")])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_competitor_mentions(opportunity_id=1, tenant_id=1)
    assert result == []

@pytest.mark.asyncio
async def test_detect_competitor_mentions_returns_empty_when_content_null(mock_db_session):
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[(3, None)])
    mock_db_session.execute = AsyncMock(return_value=mock_result)
    svc = RecommendationService(mock_db_session)
    result = await svc.detect_competitor_mentions(opportunity_id=1, tenant_id=1)
    assert result == []
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → `12 passed`

---

### Step 7: Scaffold `src/api/routers/recommendations.py` and register in `main.py`

Create `src/api/routers/recommendations.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.recommendation_service import RecommendationService

recommendations_router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

@recommendations_router.get("/opportunities/{opportunity_id}/risk-indicators")
async def get_risk_indicators(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = RecommendationService(session)
    stalled = await svc.detect_stalled(opportunity_id, ctx.tenant_id)
    overdue = await svc.detect_overdue(opportunity_id, ctx.tenant_id)
    low_eng = await svc.detect_low_engagement(opportunity_id, ctx.tenant_id)
    competitors = await svc.detect_competitor_mentions(opportunity_id, ctx.tenant_id)
    all_indicators = stalled + overdue + low_eng + competitors
    return {"success": True, "data": [i.__dict__ for i in all_indicators]}
```

Register in `src/main.py` by adding `from api.routers.recommendations import recommendations_router` and `app.include_router(recommendations_router)`.

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/recommendations.py src/main.py` → 0 errors；`PYTHONPATH=src python -c "from api.routers.recommendations import recommendations_router; print('ok')"` → `ok`

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/recommendation_service.py src/api/routers/recommendations.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/services/recommendation_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → `12 passed`
- [ ] `PYTHONPATH=src python -c "from services.recommendation_service import RecommendationService, RiskIndicator; print('import ok')"` → `import ok`
- [ ] `PYTHONPATH=src python -c "from api.routers.recommendations import recommendations_router; print('router ok')"` → `router ok`
- [ ] `PYTHONPATH=src ruff check src/main.py` → 0 errors (after registering router)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Activity `type` column values vary across tenants (no enforced vocabulary), causing `detect_low_engagement` to miss email activity | 中 | 中 | Adjust keyword list in `detect_low_engagement` after auditing real `activities.type` values; severity=0.5 is conservative — a miss is a false negative, not a false positive |
| `detect_competitor_mentions` hardcoded keyword list goes stale as market changes | 低 | 低 | Extract keywords to a module-level list constant; document that #667 should promote this to a DB-backed config table |
| `detect_stalled` fallback to `opportunities.updated_at` may be stale if updates don't touch the row | 低 | 中 | Document that any automated activity (e.g. automated reminder) should insert an `ActivityModel` row; fallback severity is capped at 1.0 so won't overflow |
| Downstream #667 depends on this service existing; if this board slips, #667 is blocked | 低 | 高 | Keep this board ≤ 2 working days; if blocked, #667 can mock `RecommendationService` locally until this merges |

---

## 8. 完成后必做

```bash
git add src/services/recommendation_service.py tests/unit/test_recommendation_service.py src/api/routers/recommendations.py src/services/__init__.py src/main.py
git commit -m "feat(recommendation): add risk-indicator detection service (#666)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(recommendation): risk-indicator detection service (#666)" --body "Closes #666"
```

---

## 9. 参考

- 同类参考实现：[`src/services/sales_service.py`](../../../src/services/sales_service.py) — service constructor pattern, session usage, multi-tenancy SQL filter
- 同类参考实现：[`src/db/models/activity.py`](../../../src/db/models/activity.py) — `ActivityModel` column layout used for engagement and competitor search
- 同类参考实现：[`src/db/models/opportunity.py`](../../../src/db/models/opportunity.py) — `OpportunityModel` column layout including `expected_close_date`
- 父 issue / 关联：#36
- 依赖 issue / 关联：#665

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
