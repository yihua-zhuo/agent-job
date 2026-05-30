# [Automation] · 新增 Workflow API Router 6端点

| 元数据 | 值 |
|---|---|
| Issue | #653 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [Automation板块汇总](../README.md#50-automation) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #37 定义了自动化规则系统的完整蓝图，其中 #652 已实现 WorkflowService 业务逻辑层。本板块是将该业务逻辑暴露为 HTTP API 的最后一公里——没有 router，调用方无法通过 REST 调用任何 workflow 操作。workflow.py 目前不存在，WorkflowService 已就绪，缺少的是适配层。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层 API 绑定，仅供内部服务/前端通过 HTTP 调用 workflow 操作。
- **开发者视角**：本板块完成后，`POST /workflows` / `GET /workflows` / `GET /workflows/{id}` 等 6 个端点在 `src/main.py` 注册完毕，可通过 `curl` 或 SDK 调用 WorkflowService 的所有方法，无需直接实例化 service。

### 1.3 不做什么（剔除）

- [ ] 不实现 WorkflowService 业务逻辑本身（已在 #652 完成）
- [ ] 不设计新的数据库 schema 或 migration（由 #652 的依赖板块覆盖）
- [ ] 不添加认证/权限细粒度控制（权限粒度由 `require_auth` 统一处理，用户级权限在后续 issue 中实现）
- [ ] 不实现 webhook /事件触发 /异步调度等运行时 trigger 逻辑
- [ ] 不使用 `async with get_db() as session:` — 必须用 `Depends(get_db)`

### 1.4 关键 KPI

- [ ] `ruff check src/api/routers/workflow.py` →0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_router.py -v` → ≥6 passed（6 个端点各至少 1 个 case）
- [ ] `grep -c "def " src/api/routers/symptom.py` → 确认 router 文件中定义了 6 个路径函数，且每个调用 `WorkflowService` 并返回 `{success: True, data: ...}` 结构
- [ ] `grep "/workflows" src/main.py` →至少 1 次 match（router 注册语句）

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块：`src/api/routers/workflow.py` 不存在。

关联 service现状（来自 #652）：
`src/services/workflow_service.py` — `WorkflowService` 类已实现，方法列表待通过 `grep -n "async def" src/services/workflow_service.py` 确认，预期包含 create / get / update / delete / list / trigger 等方法，覆盖 issue #653要求的 6 个端点。

关联 router 注册现状（来自 #652）：
`src/main.py` — `app` 对象已存在，`APIRouter` 实例通过 `app.include_router(...)` 方式注册各子 router，具体行号待查证（搜索 `include_router`）。

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — 新增 `app.include_router(workflow_router, prefix="/workflows")` 注册语句
- 要建：
  - `src/api/routers/workflow.py` —6 个 endpoint 的 router，inject session + AuthContext，call WorkflowService，序列化为 `.to_dict()`
  - `tests/unit/test_workflow_router.py` — 6 个 endpoint 的单元测试，用 MockState + mock session（mock WorkflowService 而非真实 DB）

### 2.3 缺什么

- [ ] `src/api/routers/workflow.py` 不存在 — 无法通过 HTTP 访问任何 workflow 操作
- [ ] `src/main.py` 未注册 workflow router — 即使文件存在也不会被路由
- [ ] 无 `test_workflow_router.py` — 没有可验证 6 端点行为的自动化测试
- [ ] 6 个 endpoint 的路由函数签名未定义（session 注入方式、`AuthContext` 取值方式、response 格式需与现有 router保持一致）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/workflow.py` | Workflow HTTP router：6 个 REST端点，call WorkflowService，序列化返回 |
| `tests/unit/test_workflow_router.py` | 单元测试：覆盖6 个端点各 1+ 条 case，使用 mock session |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | 新增 `workflow_router` import 及 `include_router` 注册（prefix `/workflows`） |

### 3.3 新增能力

- **API router**：`src/api/routers/workflow.py` —6 个 endpoint（预期结构如下，以实际 WorkflowService 方法为准）
  - `POST /workflows` → 创建 workflow rule
  - `GET /workflows` → 列表查询（分页）
  - `GET /workflows/{workflow_id}` → 获取单个 rule
  - `PUT /workflows/{workflow_id}` → 更新 rule
  - `DELETE /workflows/{workflow_id}` → 删除 rule
  - `POST /workflows/{workflow_id}/trigger` → 手动触发执行
- **Router 注册**：`src/main.py` 增加 `app.include_router(workflow_router, prefix="/workflows")`
- **测试覆盖**：`tests/unit/test_workflow_router.py` 实现各端点 mock 测试，exit 0

---

## 4. 设计 Decisions and Known Pitfalls

### 4.1 关键选型

- **选 `WorkflowService` 直接调用而非 wrapper**：WorkflowService 由 #652 提供，本板块仅做 thin adapter。Router 层不应承载业务逻辑，判断逻辑全在 service — 这与本仓库 `CustomerService` / `OpportunityService` 等现有 router 的模式一致。
- **选 `Depends(get_db)` 而非 `async with get_db()`**：按 CLAUDE.md 规范，router 层 session 必须通过 FastAPI 注入，不许手动 with-block 管理。
- **选 `.to_dict()` 在 router 而非 service 层**：本仓库规范要求 service 返回 ORM 对象，router负责序列化。本板块严格遵循，不在 router内部调用 ORM 构建 dict。

### 4.2 版本约束

无新依赖引入。本板块使用的所有包均已在 `pyproject.toml`声明：
- `fastapi` / `sqlalchemy[asyncio]` / `pydantic` 等已有
- 无需新增第三方包

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（由 WorkflowService 保证，本 router 通过 `ctx.tenant_id` 传入）
- Session注入：`session: AsyncSession = Depends(get_db)` — 不使用 `async with get_db() as session:`
- Response 格式：`{"success": True, "data":<result>.to_dict()}` — 与所有现有 router格式一致
- Service错误：`WorkflowService`抛出的 `AppException` 子类由 `src/main.py` 全局 handler捕获，router 不捕获
- Auth：`ctx: AuthContext = Depends(require_auth)` — 所有端点均需认证

### 4.4 已知坑

1. **Alembic autogenerate 常见偏差** → 本板块涉及 migration 时注意：`sa.JSON()` 应改为 `sa.JSONB()`，`DateTime` 应检查是否需要 `timezone=True`
2. **`metadata` 列名冲突** → SQLAlchemy `Base.metadata` 与用户自定义列 `metadata`冲突。本板块 router 不涉及 ORM 定义，但需注意若 `WorkflowService` 或 model 中使用了 `metadata` 列名，改用 `event_metadata` / `payload` 等替名
3. **单元测试 mock session 必须自包含** → 每个测试文件定义自己的 `mock_db_session` fixture，不使用全局 autouse patching（见 CLAUDE.md §6）

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/api/routers/workflow.py`骨架
参照 `src/api/routers/` 下现有 router 文件（如 `ticket_router.py` 或 `customer_router.py`）的格式，新建 `workflow.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["Workflow"])

#6 个 endpoint 函数，待填充正确的方法名和 Pydantic Payload 模型
```

从 `WorkflowService` 的方法签名推断 endpoint 映射：`grep -n "async def" src/services/workflow_service.py` 获取真实方法名后，填入各 router 函数。

操作：
- a) 新建 `src/api/routers/workflow.py`
- b) 每个 endpoint 函数签名：`async def <name>(... ctx: AuthContext = Depends(require_auth), session: AsyncSession = Depends(get_db))`
- c) 调用 `WorkflowService(session).<method>(...)`，传入 `tenant_id=ctx.tenant_id`
- d) 返回 `{"success": True, "data": result.to_dict()}` 或分页格式 `{"success": True, "data": {"items": [...], "total": N}}`

**完成判定**：`wc -l src/api/routers/workflow.py` → 文件存在且非空 / `ruff check src/api/routers/workflow.py` exit 0

---

### Step 2: 注册 router 到 `src/main.py`

操作：
- a) 在 `src/main.py` 顶部 import 区添加：`from api.routers.workflow import router as workflow_router`
- b) 找到 `app = FastAPI(...)` 所在的 router include区域，添加 `app.include_router(workflow_router, prefix="/workflows")`
- c) 确认 `prefix="/workflows"` 不与其他已注册 router冲突

```python
# 在 src/main.py 大约第 N 行附近
from api.routers.workflow import router as workflow_router
# ...
app.include_router(customer_router, prefix="/customers")
app.include_router(ticket_router, prefix="/tickets")
# 新增：
app.include_router(workflow_router, prefix="/workflows")
```

**完成判定**：`grep "/workflows" src/main.py` → 至少1 行 match / `ruff check src/main.py` exit 0

---

### Step 3: 创建 `tests/unit/test_workflow_router.py`

操作：
- a) 新建 `tests/unit/test_workflow_router.py`
- b) 参考现有测试文件（如 `test_customer_router.py`）的 fixture 结构：
  - `mock_db_session` fixture：只 mock WorkflowService 相关 handler
  - 每个 endpoint 一个 `pytest.mark.asyncio` 测试函数
  - MockState 提供 `tenant_id`
- c) 每个 test 用 `client.<method>("url", json=...)` 或直接调用 router 函数，验证返回 `{"success": True, "data": ...}`

```python
#框架（具体实现依赖 WorkflowService 方法名）
@pytest.mark.asyncio
async def test_create_workflow(mock_db_session, tenant_context):
    svc = WorkflowService(mock_db_session)
    # mock handler已在 mock_db_session 中设置
    # ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_router.py -v` → ≥ 6 passed / `ruff check tests/unit/test_workflow_router.py` exit 0

---

### Step 4: 运行全量检查并修复
操作：
- a) `ruff check src/api/routers/workflow.py src/main.py` → 0 errors
- b) `ruff format --check src/api/routers/workflow.py src/main.py tests/unit/test_workflow_router.py`
- c) 如有格式问题：`ruff format src/api/routers/workflow.py src/main.py tests/unit/test_workflow_router.py`
- d) `PYTHONPATH=src pytest tests/unit/test_workflow_router.py -v` 确认全 passed

**完成判定**：`ruff check src/api/routers/workflow.py src/main.py` exit 0 且 `pytest tests/unit/test_workflow_router.py` ≥ 6 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/workflow.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_router.py -v` → ≥ 6 passed（注：根据实际端点数量调整）
- [ ] `ruff format --check src/api/routers/workflow.py src/main.py` → exit 0
- [ ] `grep "/workflows" src/main.py` → ≥ 1 match（router 注册行）
- [ ] `grep -c "return {" src/api/routers/workflow.py` → ≥ 6（每个端点至少1 个 return 语句，格式 `{"success": True, "data": ...}`）
- [ ] `grep "WorkflowService" src/api/routers/workflow.py` → ≥ 1 match（确认调用了 service 层）

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| WorkflowService 方法名与预期不符，导致 router 函数签名报错 | 中 | 中 | Step 1 先 `grep -n "async def" src/services/workflow_service.py` 获取真实方法名再写 router；如已写完可 `git stash` → 修正 |
| 与已有 router prefix冲突（`/workflows` vs 其他） | 低 | 高 | `grep -rn "prefix=" src/api/routers/`排查所有 prefix，冲突则调整为本 issue 指定的 `/workflows` |
| test_workflow_router.py mock 不完整，测试在 CI失败 | 中 | 低 | 按 CLAUDE.md §6 规范重写 mock handler；不影响运行中服务，只阻塞 PR merge |
| main.py include_router 位置错误导致路由失效 | 低 | 高 | 确认 include 语句在 `app = FastAPI()` 初始化之后、`run()` 之前任意位置均可；`pytest tests/unit/` 全 passed 即证明注册成功 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/workflow.py src/main.py tests/unit/test_workflow_router.py
git commit -m "feat(workflow): add Workflow API router endpoints- POST/GET/PUT/DELETE /workflows/{id} and POST /workflows/{id}/trigger
- Registers router in src/main.py under /workflows prefix
-6 unit tests for all endpoints

Closes #653"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add Workflow API router (#653)" --body "Closes #653"

# 2. 更新进度
# - docs/dev-plan/50-automation/0653-add-workflow-api-router-endpoints.md §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现（existing router pattern）：[`src/api/routers/ticket_router.py`](../../../src/api/routers/ticket_router.py) — `require_auth` + `Depends(get_db)` + `WorkflowService` 调用模式参照
- 同类参考实现（service layer）：[`src/services/workflow_service.py`](../../../src/services/workflow_service.py) — 由 #652 提供，本板块调用其方法
- 父 issue / 关联：#37（Automation Rules System 顶层）、#652（WorkflowService 实现）
- 依赖 issue：#652

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
