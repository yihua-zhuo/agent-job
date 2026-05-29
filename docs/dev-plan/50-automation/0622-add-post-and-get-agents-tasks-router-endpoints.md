# Automation · 添加 Agent Tasks 三个 REST API 端点

| 元数据 | 值 |
|---|---|
| Issue | #622 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0621-add-agent-task-service-and-model](../0621-add-agent-task-service-and-model) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前系统缺少 Agent Tasks 相关的 HTTP API端点。Router 层是新功能的对外入口，属于 #42 子任务中必须完成的工作。在 #621 完成 Service 层和 Model 层之后，本板块负责把 Service能力以 RESTful 形式暴露出来，使前端和管理员可以通过 API 创建和查询 Agent Tasks。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层 REST API 提供。
- **开发者视角**：
  - 可调用 `POST /agents/tasks` 创建一条 Agent Task，获取 `{task_id, subtasks, status}`
  - 可调用 `GET /agents/tasks` 列表查询，支持 `?status=` 和 `?date_from=&date_to=` 过滤
  - 可调用 `GET /agents/tasks/{task_id}` 根据 ID 查询单条任务

### 1.3 不做什么（剔除）

- [ ] 不在本板块创建 AgentTask ORM model（属于 #621依赖）
- [ ] 不在本板块实现任务状态变更端点（PUT /agents/tasks/{task_id} 属于后续工作）
- [ ] 不在 Router 层处理 try/catch（AppException 由全局 handler统一处理）
- [ ] 不在 Router 层调用 `.to_dict()`，由调用方 Router 按统一约定处理

### 1.4 关键 KPI

- `ruff check src/api/routers/agent_tasks.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_tasks.py -v` →全部 passed（≥ 5 个用例）
- `PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → 全部 passed- Router 文件存在且可正常导入：`python -c "from api.routers.agent_tasks import router; print('ok')"`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。Router 层依赖于 #621 提供的 Service 和 Model 层，#621 未完成时本板块无法端到端联调，但可独立完成文件创建和静态检查。

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 将 `agent_tasks` router 注册到 FastAPI app（如尚未注册）
- 要建：
  - `src/api/routers/agent_tasks.py` — Router 实现（POST /agents/tasks, GET /agents/tasks, GET /agents/tasks/{task_id}）
  - `tests/unit/test_agent_tasks.py` — mock session单元测试
  - `tests/integration/test_agent_tasks_integration.py` —真实 DB 集成测试

### 2.3 缺什么

- [ ] 缺少 `src/api/routers/agent_tasks.py` 路由文件，无 Agent Tasks HTTP端点
- [ ] 缺少 Router 在 main.py 中的注册（或 `api/routers/__init__.py` 的自动汇聚）
- [ ]缺少 `POST /agents/tasks` 端点（接收 `{description}` JSON body）
- [ ] 缺少 `GET /agents/tasks` 端点（带 `?status=` / `?date_from=` / `?date_to=` 查询参数）
- [ ] 缺少 `GET /agents/tasks/{task_id}` 端点（路径参数）
- [ ] 缺少对应单元测试和集成测试
- [ ] 缺少 AuthContext 和 AsyncSession injection 模式验证（需与同类 Router 对齐）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/agent_tasks.py` | Agent Tasks 路由：POST /agents/tasks 创建任务、GET /agents/tasks 列表查询、GET /agents/tasks/{task_id} 单条查询 |
| `tests/unit/test_agent_tasks.py` | 单元测试，使用 mock session 覆盖正常和异常路径 |
| `tests/integration/test_agent_tasks_integration.py` | 集成测试，使用真实 PostgreSQL 和 db_schema fixture |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/main.py` | import `agent_tasks` router 并 `app.include_router(router, prefix="/agents/tasks")` |

### 3.3 新增能力

- **API endpoint**：`POST /agents/tasks` — body: `{"description": "..."}` → response: `{"success": true, "data": {"task_id": ..., "subtasks": [...], "status": "pending"}}`
- **API endpoint**：`GET /agents/tasks` — query: `?status=pending&date_from=2026-01-01&date_to=2026-12-31` → response: `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`GET /agents/tasks/{task_id}` — path param → response: `{"success": true, "data": {...}}`
- **Router 文件**：`src/api/routers/agent_tasks.py`（遵循 CLAUDE.md §Router Pattern）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **遵循现有 Router Pattern** 不选自建新模式：与 `customers.py`、`tickets.py` 等现有路由保持一致（`AuthContext = Depends(require_auth)` + `session: AsyncSession = Depends(get_db)` + 全局 error handler），降低学习成本和审查摩擦。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- AuthContext：通过 `ctx: AuthContext = Depends(require_auth)` 注入，提取 `tenant_id = ctx.tenant_id` 向下传递- 多租户：每个 SQL 查询由 Service 层保证带上 `tenant_id`，Router 无需額外处理
- Session 注入：`session: AsyncSession = Depends(get_db)`，禁止使用 `async with get_db()`
- 序列化：Router 调用 `entity.to_dict()` 并用 `{"success": True, "data": ...}` 包装，不在 Service 层调用 `.to_dict()`
- 错误处理：Router 不写 `try/except`，统一由 `main.py` 全局 `AppException` handler 捕获并返回错误 JSON### 4.4 已知坑

1. **SQLAlchemy 列名不能用 `metadata`** → 如 AgentTask model存在 `metadata` 字段（与 `Base.metadata` 冲突），需使用 `event_metadata` / `payload` / `attrs` 等替代名称（本板块仅引用 Router，不修改 Model，但需留意并反馈给 #621）
2. **Alembic autogen 常见问题** → 本板块不涉及 migration（Model 由 #621负责），但如 #621 生成的 migration 有误，Router 无法正常工作；如遇 `sa.JSON()` 而非 `sa.JSONB()`，建议 #621 作者手动修正

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 src/api/routers/agent_tasks.py 路由文件创建 `src/api/routers/agent_tasks.py`，实现三个端点。

操作：
a) 在文件顶部按标准模式 import 所需模块：
   ```python from fastapi import APIRouter, Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   from db.connection import get_db
   from internal.middleware.fastapi_auth import AuthContext, require_auth
   from services.agent_tasks import AgentTasksService  # 依赖 #621
   ```
b) 定义 `router = APIRouter(prefix="/agents/tasks", tags=["Agent Tasks"])`
c) 实现 `POST /`端点：接收 `{"description": str}` body，调用 `svc.create_task(description, tenant_id=ctx.tenant_id)`，返回 `{success: True, data: {...}}`
d) 实现 `GET /` 端点：接收 `status: str | None = None`、`date_from: date | None = None`、`date_to: date | None = None` query params，调用 `svc.list_tasks(tenant_id, status, date_from, date_to)`，返回分页结构
e) 实现 `GET /{task_id}` 端点：接收 `task_id: int`，调用 `svc.get_task(task_id, tenant_id=ctx.tenant_id)`，返回或抛404

**完成判定**：`python -c "from api.routers.agent_tasks import router; print('import ok')"` exit 0

---

### Step 2: 注册 Router 到 main.py

将新路由注册到 FastAPI app 实例。

操作：
a) 打开 `src/main.py`（如 Router尚未通过 `api/routers/__init__.py` 自动注册）
b) 添加 import（或确认 `api/routers.agent_tasks` 中已有覆盖）
c) 添加 `app.include_router(agent_tasks_router, prefix="/agents/tasks")`

示例代码片段：

```python
from api.routers import agent_tasks as agent_tasks_router

app.include_router(agent_tasks_router.router)
```

**完成判定**：`python -c "from main import app; print([r.path for r in app.routes])" | grep agents` 包含 `/agents/tasks`路径

---

### Step 3: 创建 tests/unit/test_agent_tasks.py 单元测试

使用 mock session（不连接真实 DB）覆盖 Router逻辑。

操作：
a) 参考 `tests/unit/test_customers.py` `mock_db_session` fixture 模式
b) 如 #621 AgentTasksService尚未就绪，先用 `MockState` + 占位 handler独立测试参数验证路径（status enum、date range 边界）
c) 覆盖场景：POST 正常创建、GET 列表（带/不带 filter）、GET 单条（存在/不存在）

```python
#简化结构import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_agent_tasks_handler(state)])

@pytest.fixture
def client(mock_db_session):
    from api.routers.agent_tasks import router
    from main import app
    app.include_router(router)
    # override get_db dependency...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_tasks.py -v` → `N passed`

---

### Step 4: 创建 tests/integration/test_agent_tasks_integration.py 集成测试

使用真实 PostgreSQL（docker compose）验证 Router → Service → DB 全链路。

操作：
a) 参考 `tests/integration/test_customers_integration.py` fixture模式
b) 使用 `db_schema`, `tenant_id`, `async_session` fixtures
c) 用 `_seed_agent_task` helper 准备测试数据（若 #621 未提供则在 TestClass 内 local 定义）
d) 测试 POST201、GET 200、GET 404、状态过滤、分页

```python
@pytest.mark.integration
class TestAgentTasksIntegration:
    async def test_post_creates_task(self, db_schema, tenant_id, async_session):
        svc = AgentTasksService(async_session)
        task = await svc.create_task("build report", tenant_id=tenant_id)
        assert task.task_id is not None    async def test_get_404(self, db_schema, tenant_id, async_session):
        svc = AgentTasksService(async_session)
        with pytest.raises(NotFoundException):
            await svc.get_task(9999, tenant_id=tenant_id)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → 全 passed

---

### Step 5: ruff check + mypy

操作：
a) `ruff check src/api/routers/agent_tasks.py tests/unit/test_agent_tasks.py`
b) 确认无 error（warning 可选择性处理，但不许 error 级）
c) 如 mypy 相关配置存在：`mypy src/api/routers/agent_tasks.py` exit 0

**完成判定**：`ruff check src/api/routers/agent_tasks.py` exit 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/agent_tasks.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_tasks.py -v` → 全部 passed（≥5 个用例）
- [ ] `PYTHONPATH=src pytest tests/integration/test_agent_tasks_integration.py -v` → 全部 passed
- [ ] `python -c "from api.routers.agent_tasks import router; print('import ok')"` → exit 0
- [ ] `python -c "from main import app; print('/agents/tasks' in [r.path for r in app.routes])"` → True

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #621 Service 层未就绪导致 Router 无法联调 | 中 | 中 | Router 文件可提前完成并通过静态检查；与 #621 作者对齐接口定义后联合调试 |
| #621 Model 列名误用 `metadata` 导致 import失败 | 低 | 高 | 在 #621 评审时提醒检查列名；如已发生则通知 #621 作者修复或在 board §4.4 记录 |
| Router 注册路径冲突（prefix "/agents/tasks" 已被占用） | 低 | 中 | 检查 main.py 中无重复注册；如有冲突在 board §4 记录并通知 #621 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/agent_tasks.py tests/unit/test_agent_tasks.py tests/integration/test_agent_tasks_integration.py src/main.py
git commit -m "feat(agents): add POST and GET /agents/tasks router endpoints"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#622): add POST and GET /agents/tasks router endpoints" --body "Closes #622"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../src/api/routers/customers.py) — Router Pattern 范本（POST/GET list/GET {id} 三件套）
- 父 issue / 关联：#42（父 epic）、#621（依赖：Service + Model 层先完成）
- 第三方文档：[FastAPI Router](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — Router 注册模式

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
