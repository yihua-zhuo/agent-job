# 自动化 · 为 WorkflowService 添加单元测试

| 元数据 | 值 |
|---|---|
| Issue | #654 |
| 分类 | 50-automation |
| 优先级 | 推荐 |
| 工作量 | 0.5 工作日 |
| 依赖 | [0653-add-workflow-service](../0653-add-workflow-service.md) |
| 启用后赋能 | 0657-add-workflow-router, 0658-add-workflow-integration-tests |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`WorkflowService` 已实现（create_workflow / get_workflow / execute_workflow / delete_workflow 等），但没有对应的单元测试覆盖。当前 `tests/unit/` 中没有任何 `test_workflow.py`，意味着新增功能或重构时没有回归保护。必须为该 service 建立完整的 mock-based 单元测试。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试改进。
- **开发者视角**：`tests/unit/test_workflow.py` 提供 `WorkflowService` 所有核心方法的测试覆盖。后续改 `workflow_service.py` 时有回归网。

### 1.3 不做什么（剔除）

- [ ] 不实现真实数据库（integration test 属于另一板块）
- [ ] 不测试 router 层（router 测试属于单独的 router 测试文件）
- [ ] 不覆盖 Alembic migration（无 schema 变更）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_workflow.py -v` → ≥ 6 passed（含 create/get/update/delete/execute/NotFound 各路径）
- `ruff check src/services/workflow_service.py tests/unit/test_workflow.py` → 0 errors
- `ruff check tests/unit/domain_handlers/workflow.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/workflow_service.py`](../../../src/services/workflow_service.py) L1-L227

```python
# src/services/workflow_service.py
class WorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow(self, name, trigger_type, created_by, tenant_id=0, **kwargs):
        # INSERT workflows, flush, refresh, return ORM object

    async def get_workflow(self, workflow_id, tenant_id=0):
        # SELECT WHERE id=? AND tenant_id=? → NotFoundException if None

    async def execute_workflow(self, workflow_id, context, tenant_id=0):
        # INSERT workflow_executions, evaluate conditions, execute actions
```

模型文件：[`src/db/models/workflow.py`](../../../src/db/models/workflow.py) L1-L76 — `WorkflowModel` + `WorkflowExecutionModel`，各有 `to_dict()`

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/conftest.py` — 无需修改（make_mock_session / MockState / MockRow / MockResult 均已就绪）
- 要建：
  - `tests/unit/domain_handlers/workflow.py` — workflow SQL handler（INSERT/SELECT/UPDATE/DELETE/COUNT）
  - `tests/unit/test_workflow.py` — 单元测试文件

### 2.3 缺什么

- [ ] `tests/unit/domain_handlers/workflow.py` — 尚无 workflow 域的 mock SQL handler
- [ ] `tests/unit/test_workflow.py` — 尚无 `WorkflowService` 的单元测试
- [ ] 无 NotFoundException 路径测试（get_workflow / delete_workflow 对不存在 ID）
- [ ] 无 execute_workflow 的 conditions 评估路径测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/domain_handlers/workflow.py` | workflow 表的 mock SQL handler：INSERT/SELECT/UPDATE/DELETE/COUNT |
| `tests/unit/test_workflow.py` | `WorkflowService` 全方法单元测试（mock session） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/conftest.py` | 无需改动（make_mock_session 已自动发现 domain_handlers/ 下新增模块） |

### 3.3 新增能力

- **Mock SQL handler**：`make_workflow_handler(state: MockState) -> Callable`，处理 `workflows` 表所有 SQL 模式
- **单元测试**：覆盖 `create_workflow`、`get_workflow`、`update_workflow`、`activate_workflow`、`pause_workflow`、`delete_workflow`、`execute_workflow`、`NotFoundException` 路径

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用现有 mock 框架**（MockState + make_mock_session）而不引入 pytest-mock / respx — 保持测试风格一致，见 CLAUDE.md §Unit Test SQL Mocks

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- Session 通过 `Depends(get_db)` 注入，测试中用 `make_mock_session([make_workflow_handler(state)])` 替换
- Service 错误抛 `NotFoundException`，测试用 `pytest.raises(NotFoundException)` 捕获
- `tenant_id` 必须参与所有查询的 WHERE 条件

### 4.4 已知坑

1. **handler 未注册时 SQL 无响应** → 规避：确保 `make_workflow_handler(state)` 在 `make_mock_session([...])` 列表中
2. **`execute_workflow` 对不存在的 workflow_id 抛出 NotFoundException** → 规避：测试该路径时直接 mock session 抛出 NotFoundException，或先插入再执行
3. **MockState 无 workflow 字段** → 规避：在 handler 内部用 `if not hasattr(state, "workflows"): state.workflows = {}` 惰性初始化，与其他 domain handler 一致

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `tests/unit/domain_handlers/workflow.py`

新建文件，参照 `automation.py` / `customers.py` 实现 `make_workflow_handler(state)`。

操作：
在 `tests/unit/domain_handlers/workflow.py` 写入以下内容（行号从 1 开始）：

```python
"""Workflow SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def make_workflow_handler(state: MockState):
    """Handle workflow SQL (INSERT, SELECT, UPDATE, DELETE, COUNT)."""
    if not hasattr(state, "workflows"):
        state.workflows = {}
    if not hasattr(state, "workflows_next_id"):
        state.workflows_next_id = 1

    def handler(sql_text, params):
        tenant_id = params.get("tenant_id", 0)

        if "insert into workflows" in sql_text:
            wid = state.workflows_next_id
            state.workflows_next_id += 1
            record = {
                "id": wid,
                "tenant_id": tenant_id,
                "name": params.get("name", "Workflow"),
                "description": params.get("description"),
                "trigger_type": params.get("trigger_type", "manual"),
                "trigger_config": params.get("trigger_config", {}),
                "actions": params.get("actions", []),
                "conditions": params.get("conditions", []),
                "status": params.get("status", "draft"),
                "created_by": params.get("created_by", 0),
            }
            state.workflows[wid] = record
            return MockResult([MockRow(record.copy())], rowcount=1)

        if (
            "select" in sql_text
            and "from workflows" in sql_text
            and "where id" in sql_text
            and "count" not in sql_text
        ):
            wid = params.get("id")
            if wid in state.workflows:
                row = state.workflows[wid]
                if row.get("tenant_id") == tenant_id:
                    return MockResult([MockRow(row.copy())])
            return MockResult([])

        if (
            "select" in sql_text
            and "from workflows" in sql_text
            and "count" not in sql_text
            and "order_by" not in sql_text
        ):
            rows = [
                MockRow(r.copy())
                for r in state.workflows.values()
                if r.get("tenant_id") == tenant_id
            ]
            return MockResult(rows if rows else [])

        if "select" in sql_text and "from workflows" in sql_text and "count" in sql_text:
            count_val = sum(
                1 for r in state.workflows.values() if r.get("tenant_id") == tenant_id
            )
            if count_val == 0:
                count_val = 0
            return MockResult([[count_val]])

        if "update" in sql_text and "workflows" in sql_text:
            wid = params.get("id")
            if wid not in state.workflows:
                return MockResult([], rowcount=0)
            rec = state.workflows[wid]
            if rec.get("tenant_id") != tenant_id:
                return MockResult([], rowcount=0)
            for k, v in params.items():
                if k not in ("id", "tenant_id"):
                    rec[k] = v
            return MockResult([MockRow(rec.copy())], rowcount=1)

        if "delete" in sql_text and "workflows" in sql_text:
            wid = params.get("id")
            if wid in state.workflows:
                del state.workflows[wid]
                return MockResult([MockRow({"id": wid})], rowcount=1)
            return MockResult([], rowcount=0)

        return None

    return handler


def get_handlers(state: MockState):
    return [make_workflow_handler(state)]


__all__ = ["get_handlers", "make_workflow_handler"]
```

**完成判定**：`ruff check tests/unit/domain_handlers/workflow.py` → 0 errors

### Step 2: 创建 `tests/unit/test_workflow.py`

操作：
在 `tests/unit/test_workflow.py` 写入以下测试类结构（基于 `make_workflow_handler` + `WorkflowService`）：

```python
"""Unit tests for WorkflowService."""

from __future__ import annotations

import pytest

from src.services.workflow_service import WorkflowService
from pkg.errors.app_exceptions import NotFoundException
from tests.unit.conftest import make_mock_session, MockState
from tests.unit.domain_handlers.workflow import make_workflow_handler


@pytest.fixture
def state():
    return MockState()


@pytest.fixture
def mock_db_session(state):
    return make_mock_session([make_workflow_handler(state)], state=state)


@pytest.fixture
def workflow_service(mock_db_session):
    return WorkflowService(mock_db_session)


class TestCreateWorkflow:
    async def test_creates_workflow_with_fields(self, workflow_service, tenant_id):
        wf = await workflow_service.create_workflow(
            name="Test WF",
            trigger_type="manual",
            created_by=1,
            tenant_id=tenant_id,
            description="A test workflow",
        )
        assert wf.name == "Test WF"
        assert wf.trigger_type == "manual"
        assert wf.status == "draft"
        assert wf.tenant_id == tenant_id


class TestGetWorkflow:
    async def test_returns_workflow(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "draft",
            "trigger_config": {}, "actions": [], "conditions": [],
            "description": None, "created_by": 1,
        }
        wf = await workflow_service.get_workflow(1, tenant_id)
        assert wf["name"] == "WF1"

    async def test_raises_not_found_for_unknown_id(self, workflow_service, tenant_id):
        with pytest.raises(NotFoundException):
            await workflow_service.get_workflow(9999, tenant_id)


class TestActivateWorkflow:
    async def test_sets_status_to_active(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "draft",
            "trigger_config": {}, "actions": [], "conditions": [],
            "description": None, "created_by": 1,
        }
        wf = await workflow_service.activate_workflow(1, tenant_id)
        assert wf["status"] == "active"


class TestPauseWorkflow:
    async def test_sets_status_to_paused(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "active",
            "trigger_config": {}, "actions": [], "conditions": [],
            "description": None, "created_by": 1,
        }
        wf = await workflow_service.pause_workflow(1, tenant_id)
        assert wf["status"] == "paused"


class TestDeleteWorkflow:
    async def test_deletes_existing_workflow(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "draft",
            "trigger_config": {}, "actions": [], "conditions": [],
            "description": None, "created_by": 1,
        }
        deleted_id = await workflow_service.delete_workflow(1, tenant_id)
        assert deleted_id == 1
        assert 1 not in state.workflows

    async def test_raises_not_found_for_unknown_id(self, workflow_service, tenant_id):
        with pytest.raises(NotFoundException):
            await workflow_service.delete_workflow(9999, tenant_id)


class TestExecuteWorkflow:
    async def test_executes_with_success_status(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "active",
            "trigger_config": {}, "actions": [{"type": "notification.send", "to": "admin"}],
            "conditions": [],
            "description": None, "created_by": 1,
        }
        exec_result = await workflow_service.execute_workflow(1, {"user_id": 1}, tenant_id)
        assert exec_result["status"] == "success"

    async def test_fails_when_conditions_not_met(self, workflow_service, state, tenant_id):
        state.workflows[1] = {
            "id": 1, "tenant_id": tenant_id, "name": "WF1",
            "trigger_type": "manual", "status": "active",
            "trigger_config": {},
            "actions": [],
            "conditions": [{"field": "score", "operator": ">", "value": 100}],
            "description": None, "created_by": 1,
        }
        exec_result = await workflow_service.execute_workflow(1, {"score": 5}, tenant_id)
        assert exec_result["status"] == "failed"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow.py -v` → ≥ 6 passed

### Step 3: lint 全量验证

操作：
在 `src/services/workflow_service.py` `tests/unit/test_workflow.py` `tests/unit/domain_handlers/workflow.py` 上运行 ruff。

```bash
ruff check tests/unit/test_workflow.py tests/unit/domain_handlers/workflow.py
```

**完成判定**：`ruff check tests/unit/test_workflow.py tests/unit/domain_handlers/workflow.py` → 0 errors exit 0

---

## 6. 验收

- [ ] `ruff check tests/unit/test_workflow.py tests/unit/domain_handlers/workflow.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow.py -v` → ≥ 6 passed
- [ ] `ruff check src/services/workflow_service.py` → 0 errors（无回归）
- [ ] 测试覆盖 create_workflow、get_workflow（正常 + NotFound）、activate_workflow、pause_workflow、delete_workflow（正常 + NotFound）、execute_workflow（成功 + conditions 失败）共 ≥ 6 个用例

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| make_workflow_handler SQL 匹配逻辑遗漏导致测试全 pass 但 real DB 不通 | 低 | 中 | 追加 integration test 板块 #658 覆盖真实 DB 路径 |
| 新 handler 与其他 domain handler 冲突（如 SQL 关键字重叠） | 低 | 低 | conftest.py 按模块名排序注册；冲突时 handler 返回 None 由其他 handler 处理 |
| execute_workflow 中 mock 未覆盖 INSERT workflow_executions 表 | 中 | 低 | 在 workflow handler 中增加对 `insert into workflow_executions` 的空响应处理（状态记录外置） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_workflow.py tests/unit/domain_handlers/workflow.py
git commit -m "test(workflow): add unit tests for WorkflowService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#654): add unit tests for WorkflowService" --body "Closes #654"

# 2. 更新进度
# PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py)
- 同类参考实现：[`tests/unit/domain_handlers/automation.py`](../../../tests/unit/domain_handlers/automation.py)
- 父 issue：#37
- 依赖 issue：#653

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
