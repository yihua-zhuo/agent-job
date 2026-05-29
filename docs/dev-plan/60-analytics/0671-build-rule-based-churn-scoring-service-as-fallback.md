# 客户流失分析 · 实现规则引擎降级 ChurnService.predict_churn

| 元数据 | 值 |
|---|---|
| Issue | #671 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [新建 ChurnPredictionService（内部已存在，无外部依赖板块阻塞）](0672-add-churn-prediction-api-endpoints.md) |
| 启用后赋能 | [新建 API 端点](0672-add-churn-prediction-api-endpoints.md) — ChurnService.predict_churn 为 router 提供规则引擎 fallback 能力 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ChurnPredictionService` 在 [`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) 中已实现，其 `predict_churn` 基于数据库真实数据计算流失风险。当前无任何 HTTP 端点暴露其能力，也缺少一个独立规则引擎驱动的 fallback path：在 ML 模型上线前，需要一个基于登录频率、购买近度、Support 工单数、engagement score 四维规则的打分服务，作为快速响应业务需求的临时降级方案，并可独立测试和演进。

### 1.2 做完后

- **用户视角**：无直接用户可见变化 — 本板块为纯 service 层，API 端点由 #672 负责。
- **开发者视角**：`ChurnService` 类在 `src/services/churn_service.py` 中可用，接受 `session`、`customer_id`、`tenant_id`，返回含 `score`（0-100）、`tier`（high/medium/low）、`top_3_factors`（list）、`recommendations`（list）的结构化结果；单元测试 `tests/unit/test_churn_service.py` 覆盖 happy path / boundary / error 三类场景。

### 1.3 不做什么（剔除）

- [ ] 不实现 ML/模型训练，规则引擎为唯一评分路径
- [ ] 不新增数据库表或 migration，本服务使用已有 customer/activity/ticket 表（不新建 model）
- [ ] API router 层不在本板块实现（由 #672 负责）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → ≥3 passed（happy path + boundary + error 各一）
- `ruff check src/services/churn_service.py` → 0 errors
- `ruff format --check src/services/churn_service.py` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/churn_service.py` 不存在（greenfield），需新建。已有 `ChurnPredictionService` 在 `src/services/churn_prediction.py`，其 `predict_churn` 基于 DB 指标，可作为参考结构，但不直接复用（因为本 issue 要求独立的 rule-based 逻辑）。

[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) L{49}-L{65}

```python
class ChurnPredictionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def predict_churn(
        self,
        customer_ids: list[int] | None = None,
        tenant_id: int = 0,
    ) -> list[ChurnPrediction]: ...

@dataclass
class ChurnPrediction:
    customer_id: int
    score: float
    risk_level: str
    factors: list[ChurnRiskFactor]
```

`ChurnPredictionService` 是 DB-backed 实现；Issue #671 要求新建 `ChurnService`（rule-based），两者并行存在，职责不同。

### 2.2 涉及文件清单

- 要改：
  - 无需修改现有文件
- 要建：
  - `src/services/churn_service.py` — 新建 rule-based churn scoring service
  - `tests/unit/test_churn_service.py` — 单元测试

### 2.3 缺什么

- [ ] 完全缺失 `src/services/churn_service.py`（greenfield service 文件）
- [ ] 缺少 `ChurnScoreResult` dataclass（统一的结构化返回类型，含 score、tier、top_3_factors、recommendations）
- [ ] 缺少基于登录频率、购买近度、Support 工单数、engagement score 四维规则的打分逻辑
- [ ] 缺少 tier 映射逻辑（score → high/medium/low）
- [ ] 缺少 top_3_factors 提取（按 weight 排序取前 3）
- [ ] 缺少 recommendations 生成逻辑
- [ ] 单元测试文件 `tests/unit/test_churn_service.py` 不存在

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/churn_service.py` | Rule-based churn scoring service，提供 `predict_churn` 方法 |
| `tests/unit/test_churn_service.py` | 覆盖 happy path、boundary（score 临界值）、error（customer not found）三种场景的单元测试 |

### 3.2 修改文件

无。

### 3.3 新增能力

- **Service class**：`ChurnService` 在 `src/services/churn_service.py`
- **Service method**：`ChurnService.predict_churn(self, customer_id: int, tenant_id: int) -> ChurnScoreResult`
- **Dataclass**：`ChurnScoreResult`（含 `score: float`、`tier: str`、`top_3_factors: list[dict]`、`recommendations: list[str]`）
- **Dataclass**：`ChurnFactor`（含 `name: str`、`score: float`、`weight: float`）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用规则引擎而非 ML**：Issue #671 明确要求"no ML required yet"，规则引擎可快速实现并独立测试，符合"temporary fallback"的定位。
- **四维规则权重（login_freq / purchase_recency / support_tickets / engagement_score）**：各占 25% 贡献，最终归一化到 0-100。权重硬编码，不外露配置（YAGNI）。
- **`ChurnService` 与 `ChurnPredictionService` 并行存在**：两者职责不同（rule-based vs DB-backed），不互相调用，防止职责混乱。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 `ChurnScoreResult` dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责（#672 接入时）
- Service 错误抛 `AppException` 子类（`NotFoundException`），**不**返回 `ApiResponse.error()`
- 与 `ChurnPredictionService` 命名区分：`ChurnService`（本板块）vs `ChurnPredictionService`（已有），避免 import 冲突

### 4.4 已知坑

1. **SQLAlchemy Base 子类的列名不能用 `metadata`**（与 Base.metadata 冲突）→ 本板块不使用 ORM model，纯 rule-based 逻辑不涉及新增表列
2. **Customer 不存在时需要 `NotFoundException`** → 规则引擎同样需要查询 DB 确认 customer 存在，避免对无效 ID 打分

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/churn_service.py` 及 dataclass 定义

本步建立文件结构，定义返回类型和 service 类的基本签名。

操作：
- a) 创建 `src/services/churn_service.py`
- b) 写入所有 import（AsyncSession、datetime、timedelta、UTC、select、and_、func、BaseException）
- c) 定义 `ChurnFactor` dataclass：fields `name: str`、`score: float`（子因素 0-100）、`weight: float`
- d) 定义 `ChurnScoreResult` dataclass：fields `customer_id: int`、`score: float`（总分 0-100）、`tier: str`（high/medium/low）、`top_3_factors: list[ChurnFactor]`、`recommendations: list[str]`
- e) 定义 `ChurnService` 类，`__init__(self, session: AsyncSession)` — session 必填，无默认值

示例代码（≤15 行）：

```python
"""Rule-based churn scoring service (fallback, no ML)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.activity import ActivityModel
from db.models.opportunity import OpportunityModel
from db.models.ticket import TicketModel
from pkg.errors.app_exceptions import NotFoundException


@dataclass
class ChurnFactor:
    name: str
    score: float
    weight: float


@dataclass
class ChurnScoreResult:
    customer_id: int
    score: float
    tier: str
    top_3_factors: list[ChurnFactor]
    recommendations: list[str]


class ChurnService:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**完成判定**：`ruff check src/services/churn_service.py` → 0 errors / 文件存在

### Step 2: 实现 `_get_customer_metrics` 私有方法（查询四维原始数据）

操作：
- a) 在 `ChurnService` 中实现 `async def _get_customer_metrics(self, customer_id: int, tenant_id: int) -> dict`
- b) 验证 customer 存在，不存在则 `raise NotFoundException("Customer")`
- c) 查询四个维度的原始数据：

  - **login_freq**：查询 `activity` 表 `tenant_id + customer_id` 条件，统计近 30 天登录次数（`count(id)`）；同时统计 30-60 天前作为基准，生成频率 trend（ratio）
  - **purchase_recency**：查询 `opportunity` 表，按 `customer_id + tenant_id` 统计最近一次成交距今天数；无成交记录 → 90 天 fallback
  - **support_tickets**：查询 `ticket` 表，统计 `status in ('open','pending')` 且 `tenant_id + customer_id` 匹配的工单数
  - **engagement_score**：综合 activity 表近 30 天记录条数，映射到 0-100 分（无活动=0，≥30条=100，按 min(max(count/30*100,0),100) 归一化）

- d) 返回 dict：`{"login_freq_score": float, "purchase_recency_score": float, "support_ticket_score": float, "engagement_score": float}`

示例代码（≤15 行）：

```python
async def _get_customer_metrics(self, customer_id: int, tenant_id: int) -> dict:
    # Verify customer
    result = await self.session.execute(
        select(CustomerModel).where(and_(
            CustomerModel.id == customer_id,
            CustomerModel.tenant_id == tenant_id
        ))
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise NotFoundException("Customer")

    now = datetime.now(UTC)
    window_30 = now - timedelta(days=30)
    window_60 = now - timedelta(days=60)

    # login frequency (activity count last 30 days)
    login_result = await self.session.execute(
        select(func.count(ActivityModel.id)).where(and_(
            ActivityModel.tenant_id == tenant_id,
            ActivityModel.customer_id == customer_id,
            ActivityModel.created_at >= window_30
        ))
    )
    login_count = login_result.scalar() or 0
    login_score = min(login_count / 10 * 100, 100)  # 10+ logins = 100

    # purchase recency (days since last won opportunity)
    opp_result = await self.session.execute(
        select(func.max(OpportunityModel.created_at)).where(and_(
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.customer_id == customer_id,
            OpportunityModel.stage == "won"
        ))
    )
    last_opp = opp_result.scalar()
    if last_opp and last_opp.tzinfo is None:
        last_opp = last_opp.replace(tzinfo=UTC)
    days_since_purchase = (now - last_opp).days if last_opp else 90
    purchase_score = max(0, 100 - days_since_purchase)  # 0 days = 100, 90+ days = 0

    # support ticket count (open + pending)
    ticket_result = await self.session.execute(
        select(func.count(TicketModel.id)).where(and_(
            TicketModel.tenant_id == tenant_id,
            TicketModel.customer_id == customer_id,
            TicketModel.status.in_(("open", "pending"))
        ))
    )
    ticket_count = ticket_result.scalar() or 0
    ticket_score = min(ticket_count / 5 * 100, 100)  # 5+ tickets = 100

    # engagement score (activity count normalized)
    engagement_score = min(login_count / 30 * 100, 100)  # 30+ activities = 100

    return {
        "login_freq_score": round(login_score, 2),
        "purchase_recency_score": round(purchase_score, 2),
        "support_ticket_score": round(ticket_score, 2),
        "engagement_score": round(engagement_score, 2),
    }
```

**完成判定**：`ruff check src/services/churn_service.py` → 0 errors

### Step 3: 实现 `predict_churn` 公开方法

操作：
- a) 实现 `async def predict_churn(self, customer_id: int, tenant_id: int) -> ChurnScoreResult`
- b) 调用 `_get_customer_metrics` 获取原始分数
- c) 规则引擎打分（各占 25% 权重）：

  ```
  login_freq_weight = 0.25
  purchase_recency_weight = 0.25
  support_ticket_weight = 0.25  (inverted: high tickets = high churn)
  engagement_weight = 0.25

  churn_score = (
      login_freq_score * 0.25 +
      purchase_recency_score * 0.25 +
      (100 - support_ticket_score) * 0.25 +   # invert: more tickets = higher churn
      engagement_score * 0.25
  )
  ```

- d) tier 映射：score ≥ 70 → "high"，≥ 40 → "medium"，< 40 → "low"
- e) top_3_factors：构建 `ChurnFactor` 列表，按子因素 score 降序取前 3
- f) recommendations：根据各维度得分生成建议列表（示例：support_ticket_score > 60 → "优先处理客户工单"）

示例代码（≤15 行）：

```python
async def predict_churn(self, customer_id: int, tenant_id: int) -> ChurnScoreResult:
    metrics = await self._get_customer_metrics(customer_id, tenant_id)

    login_score = metrics["login_freq_score"]
    purchase_score = metrics["purchase_recency_score"]
    support_score = metrics["support_ticket_score"]  # will be inverted
    engagement_score = metrics["engagement_score"]

    # Rule-based weighted score (higher = more churn risk)
    score = (
        login_score * 0.25 +
        purchase_score * 0.25 +
        (100 - support_score) * 0.25 +  # invert: more tickets = higher churn
        engagement_score * 0.25
    )
    score = round(min(score, 100.0), 2)

    tier = "high" if score >= 70 else "medium" if score >= 40 else "low"

    factors = [
        ChurnFactor(name="login_frequency", score=login_score, weight=0.25),
        ChurnFactor(name="purchase_recency", score=purchase_score, weight=0.25),
        ChurnFactor(name="support_tickets", score=support_score, weight=0.25),
        ChurnFactor(name="engagement", score=engagement_score, weight=0.25),
    ]
    top_3 = sorted(factors, key=lambda f: f.score, reverse=True)[:3]

    recommendations = []
    if support_score > 60:
        recommendations.append("优先处理客户工单，降低流失风险")
    if purchase_score < 30:
        recommendations.append("客户长期无购买记录，触发重新激活营销")
    if engagement_score < 30:
        recommendations.append("客户参与度低，建议发送个性化内容")
    if not recommendations:
        recommendations.append("客户状态健康，维持常规维护")

    return ChurnScoreResult(
        customer_id=customer_id,
        score=score,
        tier=tier,
        top_3_factors=top_3,
        recommendations=recommendations,
    )
```

**完成判定**：`ruff format --check src/services/churn_service.py` → exit 0 / `ruff check src/services/churn_service.py` → 0 errors

### Step 4: 写入单元测试 `tests/unit/test_churn_service.py`

操作：
- a) 创建 `tests/unit/test_churn_service.py`
- b) 从 `tests.unit.conftest` 导入 `make_mock_session`、`MockState`、必要 handler factory（如 `make_customer_handler`、`make_count_handler`）
- c) `mock_db_session` fixture：使用 `MockState()` + 必要 handler（customer handler 模拟 customer 存在，activity/opportunity/ticket handler 提供指标数据）
- d) 添加三个测试用例：

  - **Happy path**：customer 存在，调用 `ChurnService(mock_session).predict_churn(customer_id=1, tenant_id=1)`，断言返回 `ChurnScoreResult`，`score` ∈ [0, 100]，`tier` ∈ {high, medium, low}，`len(top_3_factors)` == 3，`isinstance(recommendations, list)`
  - **Boundary**：`support_ticket_score` 恰好在边界（如 ticket_count=0 则 support_score=0 → churn_score 受其他因素影响），验证 score 临界值（<40 = low，≥40 = medium，≥70 = high）各有一个 case 通过
  - **Error**：`customer_id=9999` 不存在，断言抛出 `NotFoundException`

示例代码（≤20 行）：

```python
import pytest
from unittest.mock import MagicMock

from services.churn_service import ChurnService, ChurnScoreResult
from tests.unit.conftest import make_mock_session, make_customer_handler, MockState
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_db_session():
    state = MockState()
    state.customers[1] = {"id": 1, "tenant_id": 1, "name": "Test Customer"}
    return make_mock_session([make_customer_handler(state)])


@pytest.mark.asyncio
async def test_predict_churn_happy_path(mock_db_session):
    svc = ChurnService(mock_db_session)
    result = await svc.predict_churn(customer_id=1, tenant_id=1)
    assert isinstance(result, ChurnScoreResult)
    assert result.customer_id == 1
    assert 0.0 <= result.score <= 100.0
    assert result.tier in ("high", "medium", "low")
    assert len(result.top_3_factors) == 3
    assert isinstance(result.recommendations, list)


@pytest.mark.asyncio
async def test_predict_churn_not_found(mock_db_session):
    svc = ChurnService(mock_db_session)
    with pytest.raises(NotFoundException):
        await svc.predict_churn(customer_id=9999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/services/churn_service.py` → 0 errors
- [ ] `ruff format --check src/services/churn_service.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → `3 passed`
- [ ] 文件 `src/services/churn_service.py` 存在
- [ ] `ChurnService.predict_churn` 返回 `ChurnScoreResult` 含 `score`（0-100）、`tier`（high/medium/low）、`top_3_factors`（3 个 `ChurnFactor`）、`recommendations`（list[str]）
- [ ] 不存在的 customer 抛出 `NotFoundException` 而非静默返回错误数据

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ChurnService.predict_churn` 与 `ChurnPredictionService.predict_churn` 方法名相同，router 层调用时混用 | 中 | 高 | Router 层（#672）显式 import `ChurnService from services.churn_service`，不混用 |
| 四个维度的权重硬编码，ML 上线后需重构为可配置 | 中 | 中 | 规则引擎作为 fallback，与 ML 模型并行存在；重构时在 `ChurnService` 内部增加 feature flag 切换路径，不改接口签名 |
| Mock session 中 activity/opportunity/ticket 数据缺失导致 metrics 全为 0，score 不稳定 | 低 | 中 | 单元测试的 mock session 需提供至少一个 handler 返回非零数据；或接受 score=0 的输出（边界场景验证） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/churn_service.py tests/unit/test_churn_service.py
git commit -m "feat(analytics): add rule-based ChurnService.predict_churn as fallback"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#671): add rule-based ChurnService.predict_churn" --body "Closes #671"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) — 已有 `ChurnPredictionService`，本板块 `ChurnService` 为并行 rule-based 实现
- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — service 类的 `__init__(session: AsyncSession)` 签名规范
- 父 issue / 关联：#35（CRM Analytics 功能集）
- 依赖 issue / 关联：#670（新建 ChurnPredictionService） → #671（本板块） → #672（API 端点）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
