# 60-analytics · 新增客户流失风险 API 端点

| 元数据 | 值 |
|---|---|
| Issue | #574 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：#573 依赖路径 — 确认0573-add-churn-prediction-service 文档已生成且路径为 `docs/dev-plan/0573-add-churn-prediction-service/README.md` |
| 启用后赋能 | TBD - 待验证：#580 依赖路径 — 确认 0580-churn-risk-dashboard-widget 文档已生成且路径为 `docs/dev-plan/0580-churn-risk-dashboard-widget/README.md` |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

#573 已实现 `ChurnPredictionService`，提供核心预测能力。本 issue 在其上封装两个 REST 端点，使前端和集成方可以通过 HTTP 调用流失风险服务，无需直接引用 service 层逻辑。缺少 API 层会限制 churn-prediction-service 的可复用性。

### 1.2 做完后

- **用户视角**：管理员访问 `/customers/{id}/churn-risk` 可立即获取指定客户的最新流失概率；使用 `/customers/churn-predict-batch` 可批量查询多个客户的流失风险，无需逐个请求。
- **开发者视角**：新增 `ChurnRiskRouter`（或挂载到现有 `CustomerRouter`），提供两个 versioned-ready endpoints；可在其他 service 中复用 `ChurnPredictionService`，无需重复调用 DB。

### 1.3 不做什么（剔除）

- [ ] 不实现新的预测算法或模型 — 预测逻辑由 #573 的 `ChurnPredictionService` 提供
- [ ] 不修改已有的 customer schema 或增加新字段 — 仅在 router 层封装
- [ ] 不实现前端 UI 或可视化组件 — 纯 API 层（由 #580 处理）
- [ ] 不实现缓存策略（如 Redis 缓存预测结果）— 基础版不含

### 1.4 关键 KPI

- `ruff check src/api/routers/churn_risk.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v` → 4 passed（GET + POST 各两用例：正常 + 异常）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 #573 涉及 migration）

---

## 2. 当前现状（起点）

### 2.1 现有实现

依赖方（由 #573 提供）：

TBD - 待验证：`src/services/churn_prediction_service.py` —需确认 `ChurnPredictionService` 已存在且包含 `predict(customer_id, tenant_id)` 和 `predict_batch(customer_ids, tenant_id)` 方法

TBD - 待验证：`src/db/models/churn_prediction.py` — 需确认 `ChurnPrediction` ORM model 存在，含字段 `customer_id`, `tenant_id`, `risk_score`, `predicted_at`

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/churn_risk.py` — 新建 router 文件，注册 GET 和 POST 两个端点
  - `src/main.py` — 将新 router 挂载到 app（如尚未引用）
  - `tests/unit/test_churn_risk_router.py` — 新建测试文件，测试两个端点
- 要建：
  - `src/api/routers/churn_risk.py` — churn risk 端点 router
  - `tests/unit/test_churn_risk_router.py` — router 单元测试

### 2.3 缺什么

- [ ] 无 `/customers/{id}/churn-risk` 端点 — 前端无法通过 HTTP 获取单个客户流失风险
- [ ] 无 `/customers/churn-predict-batch` 端点 — 批量查询需前端循环调用，效率低
- [ ] 无 `ChurnRiskRouter` 的测试覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/churn_risk.py` | ChurnPredictionService 的 REST 封装，提供两个 API 端点 |
| `tests/unit/test_churn_risk_router.py` | 对两个端点的单元测试（正常 + 异常场景） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | 将 `ChurnRiskRouter`（或 `CustomerRouter` 中的子路由）挂载到 FastAPI app |

### 3.3 新增能力

- **API endpoint**：`GET /customers/{id}/churn-risk` → `{"success": true, "data": {"customer_id": ..., "risk_score": ..., "predicted_at": ...}}`
- **API endpoint**：`POST /customers/churn-predict-batch` body: `{"customer_ids": [...]}` → `{"success": true, "data": {"predictions": [{"customer_id": ..., "risk_score": ..., "predicted_at": ...}, ...]}}`
- **Router**：`ChurnRiskRouter` 在 `src/api/routers/churn_risk.py`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **将 router 单独新建（`churn_risk.py`）而非混入 `customer.py`**：流失风险本质上是 analytics 域而非 customer 域，单独 router 便于后续 analytics 模块扩展（如评分历史、趋势图 endpoint）。与 #580 的 dashboard widget 也更易对齐。
- **批量端点用 `POST` 而非 `GET`**：客户 ID 列表在 request body 中传递，GET query string 长度受限且不易传 JSON 数组。

### 4.2 版本约束

<!-- 无新依赖引入，删除本段 -->

### 4.3 兼容性约束

- Session 注入必须使用 `session: AsyncSession = Depends(get_db)`，禁止 `async with get_db()`
- AuthContext 使用 `ctx: AuthContext = Depends(require_auth)`，每个查询必须 `WHERE tenant_id = :tenant_id`
- Service 层返回 ORM 对象，router 层调用 `.to_dict()` 序列化，禁止在 service 内调用 `.to_dict()`
- 响应格式：`{"success": true, "data": ...}`，错误由 `main.py` 全局 `AppException` handler 处理
- 批量接口 body schema 需使用 Pydantic 模型验证，拒绝空列表或非数组输入

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不可用 `metadata`**（与 `Base.metadata` 冲突）→ `ChurnPrediction` model 如需 JSON 字段，用 `risk_factors` /. `model_version` 等命名
2. **Alembic autogen 误将 JSONB 写为 JSON** → 如 #573 涉及 migration，检查生成的 migration 文件中 `JSON` 是否应为 `JSONB`，`DateTime` 是否应加 `timezone=True`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ChurnRiskRouter 并注册 GET /customers/{id}/churn-risk

在 `src/api/routers/churn_risk.py` 新建 router，使用 #573 的 `ChurnPredictionService` 的 `predict` 方法：

```python
# src/api/routers/churn_risk.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies import require_auth, AuthContext
from services.churn_prediction_service import ChurnPredictionService

router = APIRouter(prefix="/customers", tags=["ChurnRisk"])

@router.get("/{customer_id}/churn-risk")
async def get_churn_risk(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ChurnPredictionService(session)
    prediction = await svc.predict(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": prediction.to_dict()}
```

在 `src/main.py` 的 `include_routers` 部分添加：
```python
from api.routers.churn_risk import router as churn_risk_router
app.include_router(churn_risk_router)
```

**完成判定**：`ruff check src/api/routers/churn_risk.py` → 0 errors

---

### Step 2: 注册 POST /customers/churn-predict-batch

在 `churn_risk.py` 中追加 batch 端点：

```python
from pydantic import BaseModel

class BatchPredictRequest(BaseModel):
    customer_ids: list[int]

class BatchPredictResponse(BaseModel):
    predictions: list[dict]

@router.post("/churn-predict-batch")
async def predict_batch(
    body: BatchPredictRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    if not body.customer_ids:
        from pkg.errors.app_exceptions import ValidationException
        raise ValidationException("customer_ids cannot be empty")
    svc = ChurnPredictionService(session)
    results = await svc.predict_batch(body.customer_ids, tenant_id=ctx.tenant_id)
    return {"success": True, "data": {"predictions": [r.to_dict() for r in results]}}
```

**完成判定**：`ruff check src/api/routers/churn_risk.py src/main.py` → 0 errors

---

### Step 3: 编写单元测试 tests/unit/test_churn_risk_router.py

测试两个端点的正常路径和异常路径（customer 不存在、batch 空列表）：

```python
# tests/unit/test_churn_risk_router.py
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import app
from dependencies import require_auth

# Override auth dependency for tests
async def mock_auth():
    from internal.middleware.fastapi_auth import AuthContext
    return AuthContext(user_id=1, tenant_id=1)

app.dependency_overrides[require_auth] = mock_auth

class TestGetChurnRisk:
    def test_returns_prediction(self, mock_db_session):
        # mock ChurnPredictionService.predict returning a prediction object
        ...

    def test_not_found(self, mock_db_session):
        # ChurnPredictionService raises NotFoundException → HTTP 404
        ...

class TestBatchPredict:
    def test_returns_predictions(self, mock_db_session):
        # mock predict_batch returning list of prediction objects
        ...

    def test_empty_list_rejected(self, mock_db_session):
        # POST with {"customer_ids": []} → HTTP 422
        ...
```

每个端点至少 2 个测试用例（正常 + 异常）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v` → 4 passed

---

### Step 4: 更新 src/main.py 挂载 router（若尚未完成 Step 1）

在 `src/main.py` 的 `include_routers` 部分追加 churn_risk_router 的 include 调用。

**完成判定**：`ruff check src/main.py` → 0 errors

---

### Step 5: 全量 lint + 单元测试

运行完整检查：

```bash
ruff check src/api/routers/churn_risk.py src/main.py
PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v
```

**完成判定**：所有命令 exit 0，pytest 显示 ≥ 4 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/churn_risk.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors（如有改动）
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_risk_router.py -v` → ≥ 4 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 #573 涉及新 migration）
- [ ] 端到端（可选，如本地运行）：`curl -X GET http://localhost:8000/customers/1/churn-risk -H "Authorization: Bearer <token>"` 返回 `{"success": true, "data": {...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #573 的 `ChurnPredictionService.predict` 接口签名与预期不符 | 低 | 中 | router 层适配 service 实际签名，本 issue 可在 #573 合并后补测 |
| Pydantic body validation 在 fastapi 0.100+ 版本行为变更 | 低 | 低 | 固定 fastapi 版本范围；router 层已有显式 `ValidationException` 处理空列表 |
| 批量端点 customer_ids 列表过大（>1000）导致 DB 连接超时 | 中 | 低 | 在 BatchPredictRequest 中加 `max_length=500` 约束，超出返回 422 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/churn_risk.py src/main.py tests/unit/test_churn_risk_router.py
git commit -m "feat(analytics): add churn risk API endpoints (#574)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add churn risk API endpoints (#574)" --body "Closes #574"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/customer.py` — 现有 customer 端点的 router 模式（session 注入、AuthContext、to_dict 序列化结构）
- 第三方文档：[FastAPI Router](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- 父 issue / 关联：#51, #573, #580

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---

**Changes made** (lines 9 and 10 only):
- Line 9: replaced broken link `[0573-add-churn-prediction-service](../0573-add-churn-prediction-service/README.md)` with plain `TBD - 待验证：` text matching the format used in section 2.1- Line 10: replaced broken link `[0580-churn-risk-dashboard-widget](../0580-churn-risk-dashboard-widget/README.md)` with plain `TBD - 待验证：` text
