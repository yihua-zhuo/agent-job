# 客户流失分析 · ChurnPredictionService 评分逻辑实现

| 元数据 | 值 |
|---|---|
| Issue | #573 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0671-build-rule-based-churn-scoring-service-as-fallback](0671-build-rule-based-churn-scoring-service-as-fallback.md), [0670-add-churnprediction-orm-model-and-migration](0670-add-churnprediction-orm-model-and-migration.md) |
| 启用后赋能 | [0672-add-churn-prediction-api-endpoints](0672-add-churn-prediction-api-endpoints.md), [0673-add-churn-risk-to-customer-response-schema](0673-add-churn-risk-to-customer-response-schema.md), [0674-wire-early-warning-alert-on-score-threshold](0674-wire-early-warning-alert-on-score-threshold.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ChurnPredictionService`（[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) L{49}-L{312}）已实现 DB-backed 流失预测，包含 `calculate_churn_score` 和 `predict_churn` 等方法。但该服务依赖 `ChurnPredictionModel` 数据库表存储结果，在 ML 模型未上线阶段需要一个独立于 DB 表的纯内存 scoring逻辑：`calculate_score` 方法接受四维客户属性（login_frequency、purchase_recency、support_ticket_count、engagement_score），实时计算 0-100 流失分，直接返回域对象，无需依赖 `churn_predictions` 表。#572 已建立 rule-based `ChurnService`，#573 需要在此基础上补充完整评分返回结构（score + tier + top_3_factors + recommended_actions）。

### 1.2 做完后

- **用户视角**：无直接用户可见变化 — 纯 service 层，API 端点由 #672 负责。
- **开发者视角**：新增 `ChurnPredictionService.calculate_score(customer_id, tenant_id) -> ChurnPrediction` 方法，输入客户 ID +租户 ID，实时计算流失评分（0-100）、推断 tier（high/medium/low）、提取 top_3_risk_factors、生成推荐操作列表；不写 DB，直接返回 dataclass；单元测试 `tests/unit/test_churn_prediction_service.py` 覆盖 happy path + boundary + error 三类场景。

### 1.3 不做什么（剔除）

- [ ] 不新增数据库表或 ORM model，本服务纯计算逻辑，不写 `churn_predictions` 表
- [ ] 不实现 ML/模型训练，计算基于四维规则引擎（硬编码权重）
- [ ] API router 层不在本板块实现（由 #672 负责）
- [ ] 不复用 `ChurnPredictionService` 的 DB-backed 方法（两者职责不同，#573 专注 `calculate_score` 独立评分路径）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → ≥3 passed（happy path + boundary score thresholds + customer not found error 各一）
- `ruff check src/services/churn_prediction_service.py` → 0 errors
- `ruff format --check src/services/churn_prediction_service.py` → exit 0
- `PYTHONPATH=src python -c "from services.churn_prediction_service import ChurnPredictionService, ChurnPrediction; print('ok')"` → `ok`

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) L{49}-L{80}

```python
class ChurnPredictionService:
    """客户流失预测服务 — backed by real DB."""

    RISK_FACTORS = [
        "days_since_last_activity",
        "decrease_in_activity",
        "decrease_in_revenue",
        "support_tickets_increase",
        "payment_delays",
        "negative_feedback",
    ]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate_churn_score(self, customer_id: int, tenant_id: int = 0) -> float:
        """计算流失风险分数 (0-100)"""
        data = await self._get_customer_metrics(customer_id, tenant_id)
        scores = self._compute_scores(data)
        total_score = sum(scores[factor] * self.FACTOR_WEIGHTS[factor] for factor in self.RISK_FACTORS)
        return round(total_score, 2)

    async def predict_churn(
        self,
        customer_ids: list[int] | None = None,
        tenant_id: int = 0,
    ) -> list[ChurnPrediction]: ...

    @staticmethod
    def _compute_scores(data: dict) -> dict[str, float]: ...

    @staticmethod
    def _get_risk_level(score: float) -> str:
        if score >= 70: return "high"
        if score >= 40: return "medium"
        return "low"
```

现有的 `ChurnPredictionService` 计算分数依赖已有的 `calculate_churn_score`；Issue #573 要求新建 `src/services/churn_prediction_service.py`（文件名带 `_service` 后缀），提供独立的 `calculate_score`入口方法，使用四维加权公式，返回含 `ChurnPrediction` + `ChurnRiskFactor` + `recommended_actions` 的完整域对象。

### 2.2 涉及文件清单

- 要改：
  - 无（不修改现有文件）
- 要建：
  - `src/services/churn_prediction_service.py` — 新建 rule-based ChurnPredictionService（含 `calculate_score` 方法）
  - `tests/unit/test_churn_prediction_service.py` — 覆盖 happy path、boundary（score thresholds）、error（customer not found）三种场景的单元测试

### 2.3 缺什么

- [ ] 缺少 `src/services/churn_prediction_service.py`（greenfield，文件名带 `_service`，与已有 `churn_prediction.py` 区分）
- [ ] 缺少 `calculate_score(customer_id, tenant_id) -> ChurnPrediction` 方法：从 customer/activity/opportunity/ticket 表取原始数据，按四维加权公式计算 0-100 score- [ ] 缺少四维 rule engine 打分逻辑（login_frequency / purchase_recency / support_ticket_count / engagement_score 各占 25%，归一化到 0-100）
- [ ] 缺少 `tier` 映射逻辑（score ≥ 70 → high，≥ 40 → medium，< 40 → low）
- [ ] 缺少 `top_3_risk_factors` 提取（按 weight排序取前3，返回 `list[ChurnRiskFactor]`）
- [ ] 缺少 `recommended_actions` 生成逻辑（根据各维度得分生成干预建议列表）
- [ ] 缺少 `NotFoundException` 处理（customer 不存在时抛出）
- [ ] 单元测试文件 `tests/unit/test_churn_prediction_service.py` 不存在

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/churn_prediction_service.py` | Rule-based ChurnPredictionService，提供 `calculate_score` 方法，使用四维加权公式计算流失分 |
| `tests/unit/test_churn_prediction_service.py` | 单元测试：覆盖 happy path（customer 存在，返回有效 score/tier/top_3_factors/recommendations）、boundary（score 临界值 low→medium→high）、error（customer not found 抛 NotFoundException） |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| 无 | 不修改现有文件 |

### 3.3 新增能力

- **Service class**：`ChurnPredictionService` in `src/services/churn_prediction_service.py`
- **Service method**：`calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction` — 实时计算流失评分，返回域对象
- **Dataclass**：`ChurnPrediction`（含 `customer_id: int`、`score: float`（0-100）、`tier: str`（high/medium/low）、`top_3_risk_factors: list[ChurnRiskFactor]`、`recommended_actions: list[str]`）
- **Dataclass**：`ChurnRiskFactor`（含 `name: str`、`weight: float`、`score: float`、`description: str`）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **新建 `churn_prediction_service.py`（带 `_service` 后缀）而非修改 `churn_prediction.py`**：文件名为 `churn_prediction_service.py` 与 `churn_prediction.py` 区分，前者专注单一 `calculate_score` 入口，后者是 DB-backed 全套预测；两条路径并行，不互相调用，防止职责混乱。
- **四维规则权重各25%（login_frequency / purchase_recency / support_ticket_count / engagement_score）**：Issue #573 明确四维属性；权重硬编码不外露（YAGNI），后续可迁移到配置中。
- **support_ticket_count 取反（高工单数 → 高流失）**：公式为 `(100 - support_score) * 0.25`，工单越多流失风险越高。
- **返回域对象而非 dict**：Service 返回 `ChurnPrediction` dataclass，router（#672）负责序列化。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| 无新依赖 | — | 仅使用已有 SQLAlchemy、AsyncSession、AppException |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service `__init__` 接受 `session: AsyncSession`，无默认值
- Service 返回 `ChurnPrediction` dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `NotFoundException`，**不**返回 `ApiResponse.error()`
- PYTHONPATH=src，import写 `from db.models...` 而不是 `from src.db.models...`

### 4.4 已知坑

1. **SQLAlchemy Base 子类的列名不能用 `metadata`**（与 Base.metadata 冲突）→ 本板块是纯 service 不涉及 ORM model，但若后续扩展需新增 model 时避免用 `metadata` 列名
2. **Alembic autogen 会把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 本板块无 migration，但同系 analytics板块（如 #670/674）已遭遇此坑，注意迁移审查3. **Async session 不要用 `async with get_db()`**（router 中）→ 本板块在 service 层接收已注入的 session，不自行管理连接生命周期
4. **Python datetime.now() 无 tzinfo 时差值比较会出错** → `now = datetime.now(UTC)` 始终使用 aware datetimes；比较时用 UTC 一致化
5. **`ChurnPredictionService`（本板块）与 `ChurnPredictionService`（已有 `churn_prediction.py`）命名相同** → 本板块文件名为 `churn_prediction_service.py`，router 层 import 时需用完整模块路径区分

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/churn_prediction_service.py` 及 dataclass 定义

本步建立文件结构，定义返回类型和 service 类的基本签名。

操作：
- a) 创建 `src/services/churn_prediction_service.py`
- b) 写入所有 import（dataclass、datetime、UTC、timedelta、Annotated、and_、select、func、AsyncSession、Base）
- c) 定义 `ChurnRiskFactor` dataclass：fields `name: str`、`weight: float`、`score: float`（子因素 0-100 分）、`description: str`
- d) 定义 `ChurnPrediction` dataclass：fields `customer_id: int`、`score: float`（总分 0-100）、`tier: str`（high/medium/low）、`top_3_risk_factors: list[ChurnRiskFactor]`、`recommended_actions: list[str]`
- e) 定义 `ChurnPredictionService` 类，`__init__(self, session: AsyncSession)` — session必填，无默认值

示例代码：

```python
"""Rule-based churn score calculation service (no ML, no DB writes)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.activity import ActivityModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from db.models.ticket import TicketModel
from pkg.errors.app_exceptions import NotFoundException


@dataclass
class ChurnRiskFactor:
    name: str
    weight: float
    score: float
    description: str


@dataclass
class ChurnPrediction:
    customer_id: int
    score: float
    tier: str
    top_3_risk_factors: list[ChurnRiskFactor]
    recommended_actions: list[str]


class ChurnPredictionService:
    """Rule-based churn scoring using four weighted dimensions."""

    # Weights: each dimension contributes 25% to total score
    WEIGHTS = {
        "login_frequency": 0.25,
        "purchase_recency": 0.25,
        "support_ticket_count": 0.25,
        "engagement_score": 0.25,
    }

    def __init__(self, session: AsyncSession):
        self.session = session
```

**完成判定**：`ruff check src/services/churn_prediction_service.py` → 0 errors / 文件存在

---

### Step 2: 实现 `_fetch_raw_metrics` 私有方法（查询四维原始数据）

操作：
- a) 在 `ChurnPredictionService` 中实现 `async def _fetch_raw_metrics(self, customer_id: int, tenant_id: int) -> dict`
- b) 第一步先验证 customer存在：`SELECT FROM customer WHERE id=? AND tenant_id=?`，不存在则 `raise NotFoundException("Customer")`
- c) 查询四个维度的原始数据：

  - **login_frequency**：查询 `activity` 表 `tenant_id + customer_id` 条件，统计近 30 天 `count(id)`；无活动则 fallback0
  - **purchase_recency**：查询 `opportunity` 表，`customer_id + tenant_id` 条件且 `stage == 'won'`，取 `max(created_at)` 距今天数；无成交记录则 fallback 90 天
  - **support_ticket_count**：查询 `ticket` 表，`status in ('open', 'pending')` 且 `tenant_id + customer_id` 匹配的工单条数
  - **engagement_score**：综合 activity 表近 30 天 `count(id)` / 30 * 100 归一化到 0-100；无活动则0

- d) 返回 dict：`{"login_frequency": int, "purchase_recency_days": int, "support_ticket_count": int, "engagement_score": float}`（原始值，非归一化）

示例代码：

```python
async def _fetch_raw_metrics(self, customer_id: int, tenant_id: int) -> dict:
    # Verify customer exists
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

    # login_frequency (activity count last 30 days)
    login_result = await self.session.execute(
        select(func.count(ActivityModel.id)).where(and_(
            ActivityModel.tenant_id == tenant_id,
            ActivityModel.customer_id == customer_id,
            ActivityModel.created_at >= window_30
        ))
    )
    login_count = login_result.scalar() or 0

    # purchase_recency_days (days since last won opportunity)
    opp_result = await self.session.execute(
        select(func.max(OpportunityModel.created_at)).where(and_(
            OpportunityModel.tenant_id == tenant_id,
            OpportunityModel.customer_id == customer_id,
            OpportunityModel.stage == "won"
        ))
    )
    last_opp = opp_result.scalar()
    if last_opp:
        if last_opp.tzinfo is None:
            last_opp = last_opp.replace(tzinfo=UTC)
        days_since_purchase = (now - last_opp).days
    else:
        days_since_purchase = 90  # fallback

    # support_ticket_count (open + pending)
    ticket_result = await self.session.execute(
        select(func.count(TicketModel.id)).where(and_(
            TicketModel.tenant_id == tenant_id,
            TicketModel.customer_id == customer_id,
            TicketModel.status.in_(("open", "pending"))
        ))
    )
    ticket_count = ticket_result.scalar() or 0

    # engagement_score (activity count / 30, capped at 100)
    engagement_score_raw = login_count

    return {
        "login_frequency": login_count,
        "purchase_recency_days": days_since_purchase,
        "support_ticket_count": ticket_count,
        "engagement_score_raw": engagement_score_raw,
    }
```

**完成判定**：`ruff check src/services/churn_prediction_service.py src/services/churn_prediction_service.py` →0 errors

---

### Step 3: 实现 `_normalize_and_score` 和 `_compute_tier` 私有方法

操作：
- a) 实现 `_normalize_score(name: str, raw_value: float) -> float`：将各维度原始值映射到 0-100 子分数：
  - `login_frequency`：`min(raw / 10 * 100, 100)` —10+ logins = 100 分
  - `purchase_recency_days`：`max(0, 100 - days)` —0 天前 = 100，90+ 天 = 0
  - `support_ticket_count`：`min(raw / 5 * 100, 100)` — 5+ tickets = 100 分（注意：support 在公式中是"低分=高流失"，此处分数高低代表健康度）
  - `engagement_score`：`min(raw / 30 * 100, 100)` — 30+ activities = 100 分
- b) 实现 `_compute_tier(score: float) -> str`：score ≥ 70 → "high"，score ≥ 40 → "medium"，score < 40 → "low"
- c) 实现 `_build_top_3_factors(name_to_score: dict[str, float]) -> list[ChurnRiskFactor]`：按子分数降序取前 3，构建 `ChurnRiskFactor` 列表

示例代码（≤20 行）：

```python
def _normalize_score(self, name: str, raw: float) -> float:
    if name == "login_frequency":
        return min(raw / 10 * 100, 100.0)
    elif name == "purchase_recency":
        return max(0.0, 100.0 - raw)
    elif name == "support_ticket_count":
        return min(raw / 5 * 100, 100.0)
    elif name == "engagement_score":
        return min(raw / 30 * 100, 100.0)
    return 0.0

@staticmethod
def _compute_tier(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
```

**完成判定**：`ruff check src/services/churn_prediction_service.py` → 0 errors

---

### Step 4: 实现 `calculate_score` 公开方法

操作：
- a) 实现 `async def calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction`
- b) 调用 `_fetch_raw_metrics` 获取原始值
- c) 对每个维度调用 `_normalize_score` 得到 0-100 子分数
- d) 加权求和得到总分（support_ticket_count 在公式中取反：`100 - support_score` 后乘权重）
- e) 调用 `_compute_tier` 得到 tier
- f) 调用 `_build_top_3_factors` 获取 top 3 风险因素
- g) 生成 `recommended_actions`（基于各维度得分的建议列表）
- h) 返回 `ChurnPrediction` 域对象（不调用 `.to_dict()`）

示例代码（≤20 行）：

```python
async def calculate_score(self, customer_id: int, tenant_id: int) -> ChurnPrediction:
    metrics = await self._fetch_raw_metrics(customer_id, tenant_id)

    login_score = self._normalize_score("login_frequency", metrics["login_frequency"])
    purchase_score = self._normalize_score("purchase_recency", metrics["purchase_recency_days"])
    support_raw = metrics["support_ticket_count"]
    support_score = self._normalize_score("support_ticket_count", support_raw)
    engagement_score = self._normalize_score("engagement_score", metrics["engagement_score_raw"])

    # Weighted churn score (inverted support: more tickets = higher churn)
    score = (
        login_score * 0.25 +
        purchase_score * 0.25 +
        (100.0 - support_score) * 0.25 +
        engagement_score * 0.25
    )
    score = round(min(score, 100.0), 2)

    tier = self._compute_tier(score)

    name_to_score = {
        "login_frequency": login_score,
        "purchase_recency": purchase_score,
        "support_ticket_count": support_score,
        "engagement_score": engagement_score,
    }
    top_3 = self._build_top_3_factors(name_to_score)

    recommendations = []
    if support_raw > 2:
        recommendations.append("优先处理客户工单，降低流失风险")
    if metrics["purchase_recency_days"] > 60:
        recommendations.append("客户长期无购买记录，触发重新激活营销")
    if metrics["login_frequency"] < 3:
        recommendations.append("客户登录频率低，建议发送个性化内容激活")
    if not recommendations:
        recommendations.append("客户状态健康，维持常规维护")

    return ChurnPrediction(
        customer_id=customer_id,
        score=score,
        tier=tier,
        top_3_risk_factors=top_3,
        recommended_actions=recommendations,
    )
```

**完成判定**：`ruff check src/services/churn_prediction_service.py` → 0 errors / `ruff format --check src/services/churn_prediction_service.py` → exit 0

---

### Step 5: 写入单元测试 `tests/unit/test_churn_prediction_service.py`

操作：
- a) 创建 `tests/unit/test_churn_prediction_service.py`
- b) 从 `tests.unit.conftest` 导入 `make_mock_session`、`MockState`、必要 handler factory- c) `mock_db_session` fixture：使用 `MockState()` + `make_mock_session([make_customer_handler(state), make_count_handler(state)])`（customer handler 必须返回非空 customer 用于验证，count handler 用于 activity/opportunity/ticket计数）
- d) 添加三个测试用例：

  - **Happy path**：`ChurnPredictionService(mock_session).calculate_score(customer_id=1, tenant_id=1)`，断言返回 `ChurnPrediction`，`0.0 <= score <= 100.0`，`tier in ("high", "medium", "low")`，`len(top_3_risk_factors) == 3`，`isinstance(recommended_actions, list)`
  - **Boundary / tier thresholds**：使用 mock 构造不同 login_count purchase_days ticket_count engagement 值，验证 score< 40 即 tier "low"，40 ≤ score < 70 即 "medium"，≥70 即 "high"（三个子测试，各覆盖一档临界）
  - **Error**：`customer_id=9999` 不存在，断言抛出 `NotFoundException`

示例代码（≤30 行）：

```python
import pytest

from services.churn_prediction_service import ChurnPredictionService, ChurnPrediction
from tests.unit.conftest import make_mock_session, make_customer_handler, make_count_handler, MockState
from pkg.errors.app_exceptions import NotFoundException


@pytest.fixture
def mock_db_session():
    state = MockState()
    state.customers[1] = {"id": 1, "tenant_id": 1, "name": "Test Customer"}
    return make_mock_session([
        make_customer_handler(state),
        make_count_handler(state),
    ])


@pytest.mark.asyncio
async def test_calculate_score_happy_path(mock_db_session):
    svc = ChurnPredictionService(mock_db_session)
    result = await svc.calculate_score(customer_id=1, tenant_id=1)
    assert isinstance(result, ChurnPrediction)
    assert result.customer_id == 1
    assert 0.0 <= result.score <= 100.0
    assert result.tier in ("high", "medium", "low")
    assert len(result.top_3_risk_factors) == 3
    assert isinstance(result.recommended_actions, list)


@pytest.mark.asyncio
async def test_calculate_score_customer_not_found(mock_db_session):
    svc = ChurnPredictionService(mock_db_session)
    with pytest.raises(NotFoundException):
        await svc.calculate_score(customer_id=9999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → `3 passed` / `ruff check tests/unit/test_churn_prediction_service.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/churn_prediction_service.py` → 0 errors
- [ ] `ruff format --check src/services/churn_prediction_service.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_prediction_service.py -v` → `3 passed`（happy path + boundary 三档 + customer not found error）
- [ ] 文件 `src/services/churn_prediction_service.py`存在
- [ ] `ChurnPredictionService.calculate_score` 返回 `ChurnPrediction` 含 `score`（0-100）、`tier`（high/medium/low）、`top_3_risk_factors`（3 个 `ChurnRiskFactor`）、`recommended_actions`（`list[str]`）
- [ ] `PYTHONPATH=src python -c "from services.churn_prediction_service import ChurnPredictionService, ChurnPrediction; print('ok')"` → `ok`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ChurnPredictionService`（本板块）与已有 `churn_prediction.py` 中的 `ChurnPredictionService` 命名相同，router 层（#672）import 时冲突 | 中 | 高 | Router 层（#672）显式 `from services.churn_prediction_service import ChurnPredictionService`，用模块路径区分；不在同一 Python 模块中 co-import |
| 四维权重硬编码，业务方后续需要调整权重比例 | 中 | 中 | 本板块专注 MVP 实现；权重可配置化作为独立后续 issue，不在本板块 scope 内 |
| Mock session 中 activity/opportunity/ticket 数据缺失导致 metrics 全为 0，score不可预期 | 低 | 中 | 单元测试中 mock session需至少提供 `make_count_handler` 返回非零 activity计数；测试覆盖 score=0 的 low tier边界场景 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/churn_prediction_service.py tests/unit/test_churn_prediction_service.py
git commit -m "feat(analytics): add ChurnPredictionService.calculate_score with four-dimension weighted scoring"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#573): implement ChurnPredictionService scoring logic" --body "Closes #573"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) — 已有 `ChurnPredictionService`（DB-backed），本板块 `calculate_score` 为并行 rule-based 入口
- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — service类的 `__init__(session: AsyncSession)`签名规范
- 父 issue / 关联：#51（CRM Analytics 功能集）
- 依赖板块：[0671](0671-build-rule-based-churn-scoring-service-as-fallback.md)（rule-based scoring service 结构参考）、[0670](0670-add-churnprediction-orm-model-and-migration.md)（ORM model 参考）
- 启用后赋能：[0672](0672-add-churn-prediction-api-endpoints.md)（API router 依赖本板块 service）、[0673](0673-add-churn-risk-to-customer-response-schema.md)、[0674](0674-wire-early-warning-alert-on-score-threshold.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
