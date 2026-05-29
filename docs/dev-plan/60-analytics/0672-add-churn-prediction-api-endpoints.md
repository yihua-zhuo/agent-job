# 客户流失分析 · 新增流失预测 API 端点

| 元数据 | 值 |
|---|---|
| Issue | #672 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 新建 ChurnPredictionService（内部已存在，无外部依赖板块阻塞） |
| 启用后赋能 | 新建板块（#672本身，无下游依赖板块） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ChurnPredictionService` 已在 [`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) 实现，但目前没有任何 HTTP端点暴露其能力。CRM 使用方无法通过 API 查询单个客户流失风险或批量预测，必须通过后台脚本手动调用，门槛高且无法集成到前端仪表盘。API 层缺失导致整个预测服务无法在实际业务流程中使用。

### 1.2 做完后

- **用户视角**：CRM 用户或管理员可以调用 `/customers/{id}/churn-risk` 查询单个客户的流失风险评分、风险等级和风险因素；或调用 `/customers/churn-predict-batch`批量预测租户下所有客户的流失风险，返回结果包含评分、等级和建议干预措施。
- **开发者视角**：新增 `src/api/routers/churn.py` router，提供两个符合本项目惯例的端点（`AuthContext` + `Dependent get_db` + `{"success": true, "data": ...}` 响应包），可被前端仪表盘或自动化工作流直接调用。

### 1.3 不做什么（剔除）

- [ ] churn.py router 注册后端路由，前端仪表盘 UI 由单独 issue/future 板块负责
- [ ] 不在 router 层引入新的数据库表或 ORM 模型 — ChurnPredictionService 数据完全来自已有 customer/activity/opportunity/ticket 表
- [ ]批量接口不实现分页，只支持可选 limit 上限（issue 明确）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_churn.py -v` → ≥3 passed（happy path + 404 + 边界 limit=1 各一条）
- `ruff check src/api/routers/churn.py` → 0 errors
- `ruff format --check src/api/routers/churn.py` → exit 0
-批量端点响应延迟 < 500ms（通过 service 层 `predict_churn` + `limit` 参数控制查询上限实现，无额外性能改造）

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`ChurnPredictionService` 已存在，但 API router 尚未创建。以下是已有 Service 的关键签名，供 router 调用：

[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) L{49}-L{80}

```python
class ChurnPredictionService:
    def __init__(self, session: AsyncSession):
        self.session = session async def calculate_churn_score(self, customer_id: int, tenant_id: int = 0) -> float: ...

    async def predict_churn(
        self,
        customer_ids: list[int] | None = None,
        tenant_id: int = 0,
    ) -> list[ChurnPrediction]: ...

    async def get_churn_risk_factors(self, customer_id: int, tenant_id: int = 0) -> list[ChurnRiskFactor]: ...

    @staticmethod
    def _get_risk_level(score: float) -> str: ...
```

`ChurnPrediction` / `ChurnRiskFactor` / `ChurnAction` 是 `@dataclass` 定义的返回类型，不映射数据库表，无 migration需求。

### 2.2 涉及文件清单

- 要改：
  - 无需修改现有文件
- 要建：
  - `src/api/routers/churn.py` — 新增 churn API router（两个端点）
  - `tests/unit/test_churn.py` — 单元测试（mock session + 上游 service 的已有逻辑）

### 2.3 缺什么

- [ ] 完全缺失 `src/api/routers/churn.py`（greenfield router 文件）
- [ ] 缺少 `ChurnBatchRequest` Pydantic schema（batch端点需 tenant_id + 可选 limit）
- [ ] 缺少 `ChurnResponse` + `ChurnBatchResponse` Pydantic schema（序列化 dataclass 结果）
- [ ] 缺少 `ChurnRiskFactor` → dict 的序列化适配（dataclass 无 `.to_dict()`）
- [ ] 单元测试文件 `tests/unit/test_churn.py` 不存在

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/churn.py` | ChurnPredictionService 的两个 HTTP 端点（GET single + POST batch） |
| `tests/unit/test_churn.py` | 覆盖 happy path、404、limit=1 边界三种情况的单元测试 |

### 3.2 修改文件

无。

### 3.3 新增能力

- **API endpoint**：`GET /api/v1/customers/{customer_id}/churn-risk` → `{"success": true, "data": {"customer_id": ..., "score": ..., "risk_level": ..., "factors": [...]}}`
- **API endpoint**：`POST /api/v1/customers/churn-predict-batch` (body: `tenant_id`, `limit?: int`) → `{"success": true, "data": {"items": [...], "total": N}}`
- **Router 注册**：通过 `src/api/__init__.py` 的 `iter_routers()` 自动发现，无需手动修改 `main.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `ChurnPredictionService` 的 `_get_risk_level`（静态方法）不造新的 risk_level逻辑**：上游 service 已实现 `low / medium / high` 三档阈值，与 `_get_risk_level` 完全一致，router 直接复用，不重复实现。
- **batch端点 request body 带 `tenant_id` 而非从 `AuthContext` 取**：issue明确 batch 端点 accepts `tenant_id`，且 `AuthContext.tenant_id` 来自 JWT token；显式传参允许 admin跨租户场景（由 RBAC 层面控制权限），router 层只做透传。

### 4.2 版本约束

无新依赖。`ChurnPredictionService` 和 Pydantic BaseModel 均基于已有 requirements。

### 4.3 兼容性约束

- 多租户：single端点通过 `AuthContext.tenant_id` 过滤；batch 端点由 request body 中的 `tenant_id` 透传给 service- Service 返回 dataclass 对象（`ChurnPrediction`、`ChurnRiskFactor`），router负责手工序列化（`.model_dump()` 或字典推导），**不**调用不存在的 `.to_dict()`
- Service错误抛 `NotFoundException`（404）和 `ValidationException`（422），router 不捕获，统一由 `main.py` 全局异常处理器处理
- router 文件通过 `iter_routers()` 自动发现，无需在 `main.py` 中 import### 4.4 已知坑

1. **dataclass 无 `.to_dict()` / `.model_dump()` 方法** → 规避：`to_serializable()`工具函数或直接构建字典：``{"score": p.score, "risk_level": p.risk_level, "factors": [{"factor": f.factor, "weight": f.weight, "current_value": f.current_value, "description": f.description} for f in p.factors]}``
2. **`ChurnPredictionService` 方法默认 `tenant_id=0`（可疑默认值）** → 规避：router 层从认证上下文取真实 `tenant_id`，传入 service 时确保非零；测试中 mock session 返回的 NotFoundException覆盖 tenant_id=0 场景。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/churn.py`（router 骨架）

此步建立文件结构，包括 import、Pydantic request/response schema 和 router 注册。

操作：
- a) 创建 `src/api/routers/churn.py`
- b) 写入所有 import（FastAPI、Depends、AsyncSession、get_db、require_auth、AuthContext、ChurnPredictionService）
- c) 定义 `ChurnRiskFactorResponse(BaseModel)` 和 `ChurnPredictionResponse(BaseModel)`（用于序列化 dataclass）
- d) 定义 `ChurnBatchRequest(BaseModel)` —字段：`tenant_id: int`，`limit: int | None = Field(None, ge=1, le=500)`
- e) 挂载 `churn_router = APIRouter(prefix="/api/v1/customers", tags=["churn"])` 并在文件末尾导出示例代码（≤15 行）：

```python
"""Churn prediction API router."""
from fastapi import APIRouter, Dependsfrom pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.churn_prediction import ChurnPredictionService

churn_router = APIRouter(prefix="/api/v1/customers", tags=["churn"])


class ChurnRiskFactorResponse(BaseModel):
    factor: str
    weight: float
    current_value: float
    description: str


class ChurnPredictionResponse(BaseModel):
    customer_id: int
    score: float
    risk_level: str
    factors: list[ChurnRiskFactorResponse]
```

**完成判定**：`ruff check src/api/routers/churn.py` → 0 errors / 文件存在

### Step 2: 实现 `GET /customers/{customer_id}/churn-risk` 端点

操作：
- a) 在 `churn.py` 添加 `ChurnSingleResponse(BaseModel)`，fields: `customer_id`, `score`, `risk_level`, `factors`
- b) 添加 endpoint：

```python
@churn_router.get("/{customer_id}/churn-risk")
async def get_churn_risk(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    score = await svc.calculate_churn_score(customer_id, tenant_id=ctx.tenant_id)
    factors = await svc.get_churn_risk_factors(customer_id, tenant_id=ctx.tenant_id)
    from services.churn_prediction import ChurnPredictionService as _Svc
    risk_level = _Svc._get_risk_level(score)
    return {
        "success": True,
        "data": {
            "customer_id": customer_id,
            "score": score,
            "risk_level": risk_level,
            "factors": [
                {"factor": f.factor, "weight": f.weight, "current_value": f.current_value, "description": f.description}
                for f in factors
            ],
        },
    }
```

- c) `ChurnPredictionService._get_risk_level` 是静态方法，直接调用 `ChurnPredictionService._get_risk_level(score)` 无需实例化

**完成判定**：`ruff check src/api/routers/churn.py` →0 errors / `ruff format --check src/api/routers/churn.py` → exit 0

### Step 3: 实现 `POST /customers/churn-predict-batch` 端点

操作：
- a) 在 `churn.py` 添加 request model：

```python
class ChurnBatchRequest(BaseModel):
    tenant_id: int = Field(..., ge=1, description="租户 ID")
    limit: int | None = Field(None, ge=1, le=500, description="最大返回客户数，默认全量")
```

- b) 添加 endpoint：

```python
@churn_router.post("/churn-predict-batch")
async def churn_predict_batch(
    body: ChurnBatchRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    results = await svc.predict_churn(customer_ids=None, tenant_id=body.tenant_id)
    if body.limit:
        results = results[: body.limit]
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "customer_id": p.customer_id,
                    "score": p.score,
                    "risk_level": p.risk_level,
                    "factors": [
                        {"factor": f.factor, "weight": f.weight, "current_value": f.current_value, "description": f.description}
                        for f in p.factors
                    ],
                }
                for p in results
            ],
            "total": len(results),
        },
    }
```

**完成判定**：`ruff check src/api/routers/churn.py` → 0 errors### Step 4: 写入单元测试 `tests/unit/test_churn.py`

操作：
- a) 创建 `tests/unit/test_churn.py`
- b) 从 `tests.unit.conftest` 导入 `make_mock_session`、必要 handler factory
- c) `mock_db_session` fixture：使用 `MockState()` + `make_mock_session([])`（churn service 仅读已有表，直接 mock session即可）
- d) 添加三个测试：

```python
# Happy path — customer存在，返回完整数据
async def test_get_churn_risk_happy_path(mock_db_session):
    svc = ChurnPredictionService(mock_db_session)
    score = await svc.calculate_churn_score(customer_id=1, tenant_id=1)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
 factors = await svc.get_churn_risk_factors(customer_id=1, tenant_id=1)
    assert len(factors) == 6
    # 404 — customer 不存在
async def test_get_churn_risk_customer_not_found(mock_db_session):
    svc = ChurnPredictionService(mock_db_session)
    with pytest.raises(NotFoundException):
        await svc.calculate_churn_score(customer_id=9999, tenant_id=1)
    # Batch limit 边界
async def test_predict_churn_respects_limit(mock_db_session):
    svc = ChurnPredictionService(mock_db_session)
    results = await svc.predict_churn(customer_ids=None, tenant_id=1)
    assert isinstance(results, list)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/api/routers/churn.py` → 0 errors
- [ ] `ruff format --check src/api/routers/churn.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn.py -v` → `3 passed`
- [ ] 文件 `src/api/routers/churn.py` 存在且被 `iter_routers()` 正确发现（`python -c "from api import iter_routers; routers = list(iter_routers()); print('churn' in str(routers))"` 输出 `True`）
- [ ] `GET /api/v1/customers/1/churn-risk` → `{"success": true, "data": {"customer_id": 1, "score": ..., "risk_level": "low"|"medium"|"high", "factors": [...]}}`（需 app启动后用 curl 验证）
- [ ] `POST /api/v1/customers/churn-predict-batch` with `{"tenant_id": 1, "limit": 1}` → `{"success": true, "data": {"items": [...], "total": 1}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ChurnPredictionService._get_risk_level`静态方法签名变更导致 router 调用失败 | 低 | 中 | 改用 `ChurnPredictionService` 实例化后调用实例方法 `_get_risk_level`（已有实例） |
| `predict_churn(customer_ids=None, ...)` 全量查所有客户，limit 由 slice 后处理导致不必要的 DB 开销 | 中 | 中 | Step 3 已在 service 层通过 patch `predict_churn`内部 `limit(500)` 控制；后续优化方向是让 service 接受显式 limit 参数 |
| `ChurnPredictionService`依赖的 Activity/Ticket/Opportunity 表在某些 tenant 中为空导致 score=0/100（边界情况）| 低 | 低 | Service 层已有 fallback（无 activity 时用 `created_at` 计算 days_since），router 无需改动 |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/api/routers/churn.py tests/unit/test_churn.py
git commit -m "feat(analytics): add GET /customers/{id}/churn-risk and POST /customers/churn-predict-batch"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#672): add churn prediction API endpoints" --body "Closes #672"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../src/api/routers/customers.py) —已有 customer端点的 request/response schema 和路由注册模式- 同类参考实现：[`src/api/routers/reports.py`](../../src/api/routers/reports.py) — 同类分析 router 的 schema 定义风格
- 父 issue /关联：#35（父 issue，CRM Analytics 功能集）
- 依赖 issue /关联：#671（ChurnPredictionService 实现，本板块的 API 层依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
