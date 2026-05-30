# 工作流 API 路由 · 为 WorkflowService 添加 REST 接口

| 元数据 | 值 |
|---|---|
| Issue | #465 |
| 分类 | 10-automation |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0449-workflow-service](../0449-workflow-service/0449-add-workflow-service.md), [0464-workflow-db-model](../0464-workflow-db-model/0464-add-workflow-db-model.md) |
| 启用后赋能 | [0466-workflow-cli-commands](../0466-workflow-cli-commands/0466-add-workflow-cli-commands.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #449 要求构建完整的工作流（Workflow）子系统，#464 已完成数据模型，#465 则是将 WorkflowService 的业务逻辑通过 HTTP API 对外暴露。没有 router，业务逻辑无法被前端、CLI 或其他服务调用——这是交付链路的最后一环。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯后端 API 扩展，为前端/CLI 提供调用入口。
- **开发者视角**：`POST /api/v1/workflows`、`GET /api/v1/workflows`、`GET /api/v1/workflows/{id}` 等 REST 端点可用；SDK/CLI 依赖可基于此 router 构建命令。

### 1.3 不做什么（剔除）

- [ ] 不在 router 层引入新的业务逻辑（service 层已在 #464 定义，router 只做序列化/反序列化）
- [ ] 不实现 Webhook / 事件驱动触发（属于 #449 后续子 issue）
- [ ] 不实现工作流执行引擎（#449 另有子 issue 负责）

### 1.4 关键 KPI

- `ruff check src/api/routers/workflow.py src/main.py` → 0 errors
- `PYTHONPATH=src pytest tests/integration/test_workflow_api.py -v` → 全 passed（预计 ≥ 5 条用例）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（router 注册不引入 migration 问题）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/workflow_service.py` L? — WorkflowService 方法签名及返回值类型（由 #464 生成，需在开始前确认）

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — 注册 workflow router
- 要建：
  - `src/api/routers/workflow.py` — Workflow REST 路由
  - `tests/integration/test_workflow_api.py` — API 集成测试

### 2.3 缺什么

- [ ] `src/api/routers/workflow.py` 不存在，无 REST 入口
- [ ] `src/main.py` 未注册 `/api/v1/workflows` 前缀
- [ ] 无针对 router 层的集成测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/workflow.py` | Workflow CRUD REST 端点 |
| `tests/integration/test_workflow_api.py` | API 集成测试（db_schema + async_session） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | 导入 WorkflowRouter 并以 `/api/v1/workflows` 注册 |

### 3.3 新增能力

- **API router**：`/api/v1/workflows` 前缀，完整 CRUD 端点（取决于 WorkflowService 定义的方法）
- **端点示例**：
  - `POST /api/v1/workflows` → 创建工作流
  - `GET /api/v1/workflows` → 列表查询（分页）
  - `GET /api/v1/workflows/{workflow_id}` → 获取单个
  - `PUT /api/v1/workflows/{workflow_id}` → 更新
  - `DELETE /api/v1/workflows/{workflow_id}` → 删除
- **测试覆盖**：每条端点的成功/失败路径（NotFound、Validation）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **沿用 ApiResponse 包装 vs 直接返回 Pydantic 模型**：选前者 — 与仓库现有 router（`customer.py`、`sales.py` 等）保持一致，保证统一响应格式。
- **使用 `Depends(get_db)` vs `async with get_db()`**：选前者 — 遵循 CLAUDE.md router 规范，由 FastAPI 生命周期管理 session 生命周期。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个端点通过 `AuthContext` 获取 `tenant_id`，service 调用时必须传入。
- Service 返回 ORM 对象，router 调用 `.to_dict()` 序列化，不在 service 层处理。
- 错误由全局 `AppException` 处理器统一拦截（`NotFoundException` → 404，`ValidationException` → 422），router 不写 try/catch。
- router 文件使用 `from db.connection import get_db`，import 路径不含 `src.` 前缀（`PYTHONPATH=src` 已设定）。

### 4.4 已知坑

1. **SQLAlchemy Base 列名禁止用 `metadata`** → 如 WorkflowService 返回的 model 含 `metadata` 字段，改用 `event_metadata` / `payload`；如已有 model 使用了 `metadata` 列名，需先修 model（与本 issue 并行或前置）。
2. **Alembic autogen 不涉及** → 本 issue 不写 migration，无需关注 JSON→JSONB / DateTime timezone 问题。
3. **import 路径写 `from src.xxx`** → 违反 `PYTHONPATH=src` 约定，ruff 会报 `TCH` 错误；必须写 `from db.models...` / `from services...` 形式。

---

## 5. 实现步骤（按顺序）

### Step 1: 阅读现有 router 模式与 WorkflowService 接口

确认 `src/services/workflow_service.py` 中的 public 方法列表（`create_`、`get_`、`list_`、`update_`、`delete_` 等），记录每个方法的参数签名和返回类型，作为 router 端点定义的依据。

**完成判定**：`PYTHONPATH=src python -c "from services.workflow_service import WorkflowService; print(dir(WorkflowService))"` exit 0

---

### Step 2: 创建 `src/api/routers/workflow.py`

参照现有 router（如 `customer.py`）的结构，编写以下内容：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.workflow_service import WorkflowService
# ApiResponse import 路径待确认，以下为示意
from models.response import ApiResponse

router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.post("/", response_model=ApiResponse)
async def create_workflow(
    body: CreateWorkflowSchema,  # 待从 WorkflowService 的 create 方法签名推导
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = WorkflowService(session)
    result = await svc.create_workflow(tenant_id=ctx.tenant_id, **body.model_dump())
    return ApiResponse(success=True, data=result.to_dict())
```

对每个 service 方法重复上述模式。`AuthContext` 必须注入以获取 `tenant_id`。

**完成判定**：`ruff check src/api/routers/workflow.py` exit 0

---

### Step 3: 在 `src/main.py` 注册 router

找到 `src/main.py` 中其他 router 的注册位置（如 `app.include_router(customer_router, prefix="/api/v1")`），在其后插入：

```python
from api.routers.workflow import router as workflow_router

app.include_router(workflow_router, prefix="/api/v1")
```

**完成判定**：`PYTHONPATH=src python -c "from main import app; print([r.path for r in app.routes])"` 包含 `/api/v1/workflows`

---

### Step 4: 编写集成测试 `tests/integration/test_workflow_api.py`

使用 `db_schema`、`tenant_id`、`async_session` fixtures。每条端点覆盖：

```python
import pytest

@pytest.mark.integration
class TestWorkflowAPI:
    async def test_create_workflow(self, db_schema, tenant_id, async_session):
        client = TestClient(...)
        resp = client.post("/api/v1/workflows/", json={...}, headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "id" in resp.json()["data"]

    async def test_get_workflow_not_found(self, db_schema, tenant_id, async_session):
        resp = client.get("/api/v1/workflows/99999", headers=auth_header)
        assert resp.status_code == 404
```

确保 `_seed_workflow`（如存在）或直接通过 service seed 测试数据。

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_workflow_api.py -v` 全 passed

---

### Step 5: 全量 lint + 单元回归

```bash
ruff check src/api/routers/workflow.py src/main.py
ruff format --check src/api/routers/workflow.py
PYTHONPATH=src pytest tests/unit/ -v  # 确保现有单元测试不因 router 注册被破坏
```

**完成判定**：以上每条命令 exit 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/workflow.py src/main.py` → 0 errors
- [ ] `ruff format --check src/api/routers/workflow.py` → exit 0
- [ ] `PYTHONPATH=src python -c "from api.routers.workflow import router; print(router.path_prefix)"` → `/workflows`
- [ ] `PYTHONPATH=src python -c "from main import app; assert any('/workflows' in r.path for r in app.routes)"` → exit 0
- [ ] `PYTHONPATH=src pytest tests/integration/test_workflow_api.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → 现有单元测试不被破坏

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| WorkflowService 方法签名与 router 实现不匹配（参数类型不一致） | 中 | 中 | router 层用 `**body.model_dump()` 转发，灵活适配；如 service 接口变更，router 同步更新 |
| router 注册导致 main.py 启动时循环 import | 低 | 高 | 将 `WorkflowRouter` 的 import 改为延迟导入（`from api.routers import workflow` 移至函数内），或提取到独立 `api/__init__.py` 聚合 |
| 集成测试 fixture 缺少 `_seed_workflow` 导致 setup 失败 | 中 | 中 | 在 `tests/integration/conftest.py` 中新增 `_seed_workflow` helper，与其他 seed 函数模式一致 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/workflow.py src/main.py tests/integration/test_workflow_api.py
git commit -m "feat(workflow): add REST API router for WorkflowService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(api): add Workflow REST router (closes #465)" --body "Closes #465"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/customer.py` — 现有 router 模式参考
- 父 issue / 关联：#449（Workflow 子系统总览），#464（Workflow 数据模型）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
