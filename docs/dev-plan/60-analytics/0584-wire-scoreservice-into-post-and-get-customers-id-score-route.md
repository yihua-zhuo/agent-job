# Analytics · Wire ScoreService into customer score endpoints

| 元数据 | 值 |
|---|---|
| Issue | #584 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：ScoreService 实现文档（#583） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ScoreService` 在 #583 中已实现，但目前没有任何 HTTP API 端点暴露其能力。CRM 无法通过 REST 接口对客户进行评分或查询已有评分，导致整个评分服务无法在实际业务流程、前端仪表盘或自动化工作流中被调用。

### 1.2 做完后

- **用户视角**：`POST /customers/{id}/score` 触发评分计算，返回 `score`, `risk_level`, `factors` 等字段；`GET /customers/{id}/score` 查询当前评分，不存在则返回 404。
- **开发者视角**：两个新端点以标准 router 模式（`AuthContext` + `Depends(get_db)` + `{"success": true, "data": ...}`）暴露 `ScoreService` 能力，可被前端仪表盘或自动化工作流直接调用。

### 1.3 不做什么（剔除）

- [ ] 不在 router 层引入新的数据库表或 ORM model — 评分数据完全来自已有 customer/activity/opportunity/ticket 表（由 #583 ScoreService 处理）
- [ ] 不实现 AI 增强评分路径 — 纯静态评分，由 `ScoreService.calculate_score` 同步完成（AI 增强属于 #585 后续工作）
- [ ] 不在 router 层处理 try/catch — `AppException` 由全局 handler 统一处理

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_customers.py -v` → 全部 passed（新增用例覆盖 score 两个端点）
- `ruff check src/api/routers/customers.py` → 0 errors
- `ruff format --check src/api/routers/customers.py` → exit 0
- `python -c "from api.routers.customers import router; print('ok')"` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`ScoreService` 已在 #583 实现，但 customers router 尚未有 score 相关端点。以下是 #583 Service 的关键签名，供 router 调用：

ScoreService（定义在 `src/services/score_service.py`，由 #583 提供）：

```python
class ScoreService:
    def __init__(self, session: AsyncSession): ...

    async def calculate_score(
        self, customer_id: int, tenant_id: int
    ) -> ScoreResponse: ...

    async def get_score(
        self, customer_id: int, tenant_id: int
    ) -> ScoreResponse | None: ...
```

`ScoreResponse` 是 Pydantic dataclass，包含 `score: float`, `risk_level: str`, `factors: list[str]`, `calculated_at: datetime | None` 字段。

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 新增 `POST /customers/{customer_id}/score` 和 `GET /customers/{customer_id}/score` 两个端点
- 要建：
  - `tests/unit/test_customers.py` — 扩展现有单元测试，覆盖两个新端点（正常、404、auth 拒绝路径）

### 2.3 缺什么

- [ ] customers.py 缺少 `POST /customers/{id}/score` 端点（调用 `ScoreService.calculate_score`）
- [ ] customers.py 缺少 `GET /customers/{id}/score` 端点（调用 `ScoreService.get_score`，无记录返回 404）
- [ ] 缺少对 `ScoreService` 的 import 和 session 注入
- [ ] 缺少单元测试覆盖两个新端点（happy path + 404 + auth missing）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_customers.py` | 扩展现有单元测试，新增 score 端点覆盖（POST 触发计算、GET 查询、GET 404） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) | 新增 `POST /customers/{customer_id}/score` 和 `GET /customers/{customer_id}/score` 两个端点；import `ScoreService`；注入 `session` 和 `AuthContext` |

### 3.3 新增能力

- **API endpoint**：`POST /customers/{customer_id}/score` → body: `{}`（空 body）→ response: `{"success": true, "data": {"score": 0.85, "risk_level": "low", "factors": [...], "calculated_at": "..."}}`
- **API endpoint**：`GET /customers/{customer_id}/score` → response: `{"success": true, "data": {...}}` 或 404（如从未评分）
- **Service method**：`ScoreService.calculate_score(customer_id, tenant_id)` / `ScoreService.get_score(customer_id, tenant_id)`（由 #583 提供）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **遵循现有 customers.py Router Pattern** 不选自建新模式：与同一文件中其他端点（`GET /customers/{id}`, `PUT /customers/{id}` 等）保持一致的参数注入方式（`AuthContext = Depends(require_auth)` + `session: AsyncSession = Depends(get_db)`），降低审查摩擦。

### 4.2 版本约束

无新依赖引入（`ScoreService` 已在 #583 中定义并通过 `PYTHONPATH=src` 可直接 import）。

### 4.3 兼容性约束

- AuthContext：通过 `ctx: AuthContext = Depends(require_auth)` 注入，提取 `tenant_id = ctx.tenant_id` 向下传递
- 多租户：`tenant_id` 由 AuthContext 提取，传递给 ScoreService 的每个方法调用
- Session 注入：`session: AsyncSession = Depends(get_db)`，禁止使用 `async with get_db()`
- 序列化：Router 调用 `result.to_dict()` 并用 `{"success": True, "data": ...}` 包装，不在 Service 层调用 `.to_dict()`
- 错误处理：Router 不写 `try/except`，由 `main.py` 全局 `AppException` handler 捕获 `NotFoundException` 并返回 404 JSON

### 4.4 已知坑

1. **Alembic autogen 会把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 本板块不涉及 migration（评分数据来自已有表），但如 #583 ScoreService 内部有 schema 变更需生成 migration，需手动将 `sa.JSON()` 改回 `sa.JSONB()` 并补上 `timezone=True`
2. **SQLAlchemy Base 子类列名不能用 `metadata`** → 本板块只涉及 router，不修改 ORM model；如 #583 ScoreService 内部定义的新 model 有此问题，需反馈给 #583 作者

---

## 5. 实现步骤（按顺序）

### Step 1: 在 customers.py 中添加 score 端点 import

在 [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) 顶部添加 `ScoreService` import。

操作：
a) 找到文件顶部现有 import 块
b) 添加 `from services.score_service import ScoreService`

```python
from services.score_service import ScoreService
```

**完成判定**：`python -c "from api.routers.customers import router; print('ok')"` exit 0

---

### Step 2: 新增 POST /customers/{customer_id}/score 端点

在 customers.py 末尾或合适位置添加端点定义。

操作：
a) 定义 endpoint：

```python
@router.post("/{customer_id}/score", status_code=status.HTTP_201_CREATED)
async def post_score(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ScoreService(session)
    result = await svc.calculate_score(customer_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result.to_dict()}
```

b) 确保 `from fastapi import status` 已 import（如无则添加）

**完成判定**：`ruff check src/api/routers/customers.py` exit 0

---

### Step 3: 新增 GET /customers/{customer_id}/score 端点

在 customers.py 添加 GET 端点，`get_score` 返回 `None` 时抛 `NotFoundException`（由全局 handler 转 404）。

操作：
a) 定义 endpoint：

```python
@router.get("/{customer_id}/score")
async def get_score(
    customer_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ScoreService(session)
    result = await svc.get_score(customer_id, tenant_id=ctx.tenant_id)
    if result is None:
        raise NotFoundException("Score")
    return {"success": True, "data": result.to_dict()}
```

b) 确保 `from pkg.errors.app_exceptions import NotFoundException` 已 import（如无则添加）

**完成判定**：`ruff check src/api/routers/customers.py` exit 0

---

### Step 4: 扩展 tests/unit/test_customers.py 单元测试

扩展现有 customers 单元测试，新增 score 端点覆盖。

操作：
a) 在 `test_customers.py` 中找到 `mock_db_session` fixture 的定义（如需新增 handler 支持 score SQL 模式，在 `tests/unit/conftest.py` 添加 `make_score_handler`）
b) 新增测试用例：
   - `test_post_score_returns_201_with_data` — mock session 返回 ScoreResponse，验证 status 201 和 response 结构
   - `test_get_score_returns_200_with_data` — mock session 返回 ScoreResponse，验证 200
   - `test_get_score_returns_404_when_not_found` — mock session 返回 None，验证 404 response
   - `test_score_endpoints_require_auth` — 不提供 AuthContext，验证 401

```python
async def test_post_score_returns_201_with_data(mock_db_session, client):
    response = client.post(
        "/customers/1/score",
        json={},
        headers={"Authorization": "Bearer testtoken"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "score" in data
    assert "risk_level" in data

async def test_get_score_returns_404_when_not_found(mock_db_session, client):
    response = client.get(
        "/customers/9999/score",
        headers={"Authorization": "Bearer testtoken"},
    )
    assert response.status_code == 404
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customers.py -v` → 全部 passed

---

### Step 5: ruff check + format

操作：
a) `ruff check src/api/routers/customers.py tests/unit/test_customers.py`
b) `ruff format src/api/routers/customers.py tests/unit/test_customers.py`
c) 确认两个命令 exit 0，无 error 级输出

**完成判定**：`ruff check src/api/routers/customers.py tests/unit/test_customers.py` exit 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/customers.py tests/unit/test_customers.py` → 0 errors
- [ ] `ruff format --check src/api/routers/customers.py tests/unit/test_customers.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_customers.py -v` → 全部 passed（新增 ≥ 3 个 score 端点用例）
- [ ] `python -c "from api.routers.customers import router; print('ok')"` → exit 0
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 #583 涉及 migration）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #583 ScoreService 尚未就绪导致 router 无法联调 | 中 | 中 | Router 文件可提前完成并通过静态检查（import + 端点定义）；与 #583 作者对齐 `ScoreResponse` dataclass 字段名后联合调试 |
| ScoreService.calculate_score 内部依赖尚未创建的表（如 score_history）导致运行时错误 | 低 | 中 | 确认 #583 涉及的 migration 已生成并可 apply；本地 `alembic upgrade head` 验证无报错 |
| customers.py 中新增端点与现有端点路由冲突（e.g. `/{id}/score` vs `/{id}` 路径匹配顺序） | 低 | 低 | FastAPI 按定义顺序匹配，score 端点放在 `/{id}` 之后则不影响；如出现意外匹配检查 `/{id}/score` 定义的准确参数名 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/customers.py tests/unit/test_customers.py
git commit -m "feat(customers): add POST and GET /customers/{id}/score router endpoints"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#584): wire ScoreService into POST and GET /customers/{id}/score" --body "Closes #584"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — 本文件，在其中添加 score 端点
- 同类参考实现：TBD - 待验证：churn router 参考实现
- 父 issue / 关联：#49（父 epic）、#583（依赖：ScoreService 实现先完成）
- 第三方文档：[FastAPI Router](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
