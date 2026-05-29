# 50-automation · 构建 WorkflowService CRUD + execute 方法

| 元数据 | 值 |
|---|---|
| Issue | #463 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0465-add-workflow-api-router](0465-add-workflow-api-router.md), [0516-add-workflow-orm-models-and-migration](0516-add-workflow-orm-models-and-migration.md) |
| 启用后赋能 | [0517-implement-dag-execution-engine-core](0517-implement-dag-execution-engine-core.md), [0518-implement-trigger-and-condition-node-types](0518-implement-trigger-and-condition-node-types.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`src/services/workflow_service.py` 已完整实现（`create_workflow` / `get_workflow` / `update_workflow` / `activate_workflow` / `pause_workflow` / `delete_workflow` / `list_workflows` / `execute_workflow` / `get_execution_history` 共 9 个方法），但缺少对应的单元测试覆盖。依据 CLAUDE.md §"Unit Test SQL Mocks"规范，每一个新 service 文件必须配有 `tests/unit/test_<name>.py`，本 issue 即为补全这一环节。没有单元测试的 service 在后续重构时无法做回归保护，也违反了项目规范。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯后端测试补全。
- **开发者视角**：`tests/unit/test_workflow_service.py` 存在，覆盖全部 9 个 public 方法 + 关键边界 case；后续 PR 可直接 `pytest tests/unit/test_workflow_service.py` 验证 WorkflowService 不被破坏；`conftest.py` 中新增 `workflow_handler`（按需复用）。

### 1.3 不做什么（剔除）

- [ ] 不修改 `src/services/workflow_service.py` 源码（已有完整实现，本 issue 仅测不改）
- [ ] 不写集成测试（`tests/integration/test_workflow_service.py` 属于后续 router 联动板块）
- [ ] 不实现 `evaluate_conditions` / `execute_actions` 的深度执行路径（这两个是 `_execute_actions` / `_evaluate_conditions` 的公开代理，核心逻辑在后两者，由 `execute_workflow` 覆盖）

### 1.4 关键 KPI

- `ruff check src/services/workflow_service.py` → 0 errors
- `PYTHONPATH=src mypy src/services/workflow_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 9 passed

---

## 2. 当前现状（起点）

### 2.1 现有实现

[`src/services/workflow_service.py`](../../src/services/workflow_service.py) L1-L227 — 已实现全部 9 个 public 方法 + 2 个 private helper，ORM 模型为 `WorkflowModel` 与 `WorkflowExecutionModel`（`src/db/models/workflow.py`）。

[`src/db/models/workflow.py`](../../src/db/models/workflow.py) L12-L76 — 两个模型均含 `tenant_id`、`id`、`to_dict()` 方法。

```python
# workflow_service.py L19-51 — constructor + create_workflow
class WorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow(
        self,
        name: str,
        trigger_type,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> WorkflowModel:
        now = datetime.now(UTC)
        workflow = WorkflowModel(
            tenant_id=tenant_id,
            name=name,
            description=kwargs.get("description"),
            trigger_type=_enum_val(trigger_type) or "manual",
            trigger_config=kwargs.get("trigger_config", {}),
            actions=kwargs.get("actions", []),
            conditions=kwargs.get("conditions", []),
            status="draft",
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(workflow)
        await self.session.flush()
        await self.session.refresh(workflow)
        return workflow
```

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/conftest.py` — 新增 `workflow_handler`（按需，与 `pipeline_handler` 并列）
  - `tests/unit/test_workflow_service.py` — 新建，全部测试用例
- 要建：
  - `tests/unit/test_workflow_service.py` — 约 150-200 行，含 mock DB fixture

### 2.3 缺什么

- [ ] `workflow_handler` 在 `conftest.py` 中不存在，无法组合 `mock_db_session`
- [ ] `tests/unit/test_workflow_service.py` 不存在，全部 9 个 public 方法均无测试
- [ ] `get_execution_history` 返回 `list[WorkflowExecutionModel]` 的 mock 结构未定义
- [ ] `execute_workflow` 内部调用 `_evaluate_conditions` / `_execute_actions`，需 mock 两者以独立测试 `execute_workflow` 路径

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_workflow_service.py` | WorkflowService 完整单元测试（mock DB，≥ 9 条用例） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../tests/unit/conftest.py) | 新增 `workflow_handler` 函数（注册到 `DOMAIN_HANDLERS` 映射，供 `make_mock_session` 调用） |
| [`src/services/__init__.py`](../../src/services/__init__.py) | 确认 `WorkflowService` 已导出（如有 `__all__`，追加） |

### 3.3 新增能力

- **Test fixture**：`mock_db_session`（含 `workflow_handler`）在 `test_workflow_service.py` 中定义
- **Test fixture**：`workflow_service(mock_db_session)` → `WorkflowService(mock_db_session)`
- **Test fixture**：`empty_workflow_session`（无任何 workflow 记录，用于 not-found 场景）
- **Unit tests**：9+ 条用例，覆盖全部 public 方法 + 边界（not-found、empty-list、execute success/fail/conditions-not-met）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **在 `conftest.py` 中新增 `workflow_handler`** 而非在测试文件中内联 — 与 `pipeline_handler`、`opportunity_handler` 等已有模式保持一致；多测试文件复用时只需在 fixture 中引用即可。
- **在 `mock_db_session` 中组合 `workflow_handler` + `make_count_handler(state)`** — `list_workflows` 内部有 count 查询，需要 count handler；复用已有的 `make_count_handler` 避免重复造轮子。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 每个 SQL 查询必须 `WHERE tenant_id = :tenant_id` — mock handler 中的 `workflow_handler` 也需透传 `tenant_id` 参数（见 `pipeline_handler` 模式）。
- Service 返回 ORM 对象，不调用 `.to_dict()` — 测试中用 `assert isinstance(result, WorkflowModel)` 验证。
- Service 错误抛 `AppException` 子类 — 用 `pytest.raises(NotFoundException)` 验证。
- import 路径：`from services.workflow_service import WorkflowService`，非 `from src.services...`。
- `WorkflowModel` 的 `id` 为 `autoincrement=True` 的 int；mock handler 的返回行需包含 `id` 字段。

### 4.4 已知坑

1. **mock handler 对 `len(rows) == 0` 的判断必须精确** — `workflow_handler` 的 SQL 匹配需区分 SELECT（有结果为空）和 DELETE（rowcount=0）；参考 `pipeline_handler` 对 `pipelines` / `pipeline_stages` 表名的多分支判断。
2. **`execute_workflow` 内部调用 `self._evaluate_conditions` / `self._execute_actions`** — 这两个方法不经过 DB，无法 mock；测试时用真实条件（`conditions=[]` 或 `context` 不触发条件）绕过，或直接用 `WorkflowModel` 实例 stub 对象。
3. **`list_workflows` 需要 count handler** — `make_count_handler(state)` 会为所有 count 查询返回 0；如需验证 count=1 的返回，测试内部可手动 `state.counts["workflows"] = 1` 或构造带 count 的 mock session。

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 conftest.py 中的 handler 注册结构

查阅 `tests/unit/conftest.py` 的 `DOMAIN_HANDLERS` 字典（或 `make_mock_session` 的 `handlers` 参数），确认 handler 签名规范（`(sql_text: str, params: dict) -> MockResult | None`），并找到其他 handler（如 `pipeline_handler`）的完整实现作为模板。

**完成判定**：`grep -n "def pipeline_handler" tests/unit/conftest.py` 返回匹配行

---

### Step 2: 在 `conftest.py` 中新增 `workflow_handler`

在 `tests/unit/conftest.py` 底部添加（参考 `pipeline_handler` 签名）：

```python
def workflow_handler(sql_text: str, params: dict) -> MockResult | None:
    """Mock handler for workflows + workflow_executions tables."""
    state_key = None
    if "workflows" in sql_text and ("SELECT" in sql_text or "FROM" in sql_text):
        state_key = "workflows"
    elif "workflows" in sql_text and "DELETE" in sql_text:
        state_key = "workflows"
    elif "workflow_executions" in sql_text:
        state_key = "workflow_executions"
    else:
        return None

    from tests.unit.conftest import MockRow, MockResult, MockState
    # Delegates to the global MockState registry used by make_mock_session
    state = getattr(MockState, "_instance", None)
    if state is None:
        return MockResult([])
    items = getattr(state, state_key, [])
    rows = [MockRow(item) for item in items]
    return MockResult(rows)
```

**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors；`grep -n "def workflow_handler" tests/unit/conftest.py` 返回匹配行

---

### Step 3: 创建 `tests/unit/test_workflow_service.py` 文件结构

在 `tests/unit/test_workflow_service.py` 顶部写入 import + fixtures：

```python
"""Unit tests for WorkflowService."""
import pytest
from services.workflow_service import WorkflowService
from pkg.errors.app_exceptions import NotFoundException, ValidationException
from tests.unit.conftest import (
    make_mock_session,
    workflow_handler,
    make_count_handler,
    MockState,
    MockRow,
    MockResult,
)

@pytest.fixture
def mock_db_session():
    state = MockState()
    # Pre-seed a workflow row so SELECT queries return it
    state.workflows = [{
        "id": 1,
        "tenant_id": 1,
        "name": "Test Workflow",
        "description": None,
        "trigger_type": "manual",
        "trigger_config": {},
        "actions": [],
        "conditions": [],
        "status": "draft",
        "created_by": 10,
        "created_at": None,
        "updated_at": None,
    }]
    return make_mock_session([workflow_handler, make_count_handler(state)])


@pytest.fixture
def empty_db_session():
    """Session with no workflow rows — for not-found tests."""
    state = MockState()
    state.workflows = []
    return make_mock_session([workflow_handler, make_count_handler(state)])


@pytest.fixture
def workflow_service(mock_db_session):
    return WorkflowService(mock_db_session)


@pytest.fixture
def empty_workflow_service(empty_db_session):
    return WorkflowService(empty_db_session)
```

**完成判定**：`ruff check tests/unit/test_workflow_service.py` → 0 errors

---

### Step 4: 实现全部 9 个 public 方法的测试用例

在 `TestWorkflowService` 类中按以下顺序实现每条用例：

**Case 1 — `test_create_workflow`**：
- 调用 `workflow_service.create_workflow(name="New WF", trigger_type="manual", created_by=10, tenant_id=1)`
- `assert isinstance(result, WorkflowModel)`
- `assert result.name == "New WF"`
- `assert result.status == "draft"`
- `assert result.tenant_id == 1`

**Case 2 — `test_get_workflow`**：
- 调用 `workflow_service.get_workflow(1, tenant_id=1)` — 使用 mock 预置行
- `assert result.id == 1`
- `assert result.name == "Test Workflow"`

**Case 3 — `test_get_workflow_not_found`**：
- 调用 `empty_workflow_service.get_workflow(999, tenant_id=1)`
- `with pytest.raises(NotFoundException): ...`

**Case 4 — `test_update_workflow`**：
- 调用 `workflow_service.update_workflow(1, tenant_id=1, name="Updated Name")`
- `assert result.name == "Updated Name"`
- `assert result.updated_at is not None`

**Case 5 — `test_delete_workflow`**：
- mock session 的 `workflow_handler` 对 DELETE 返回 `MockResult([], rowcount=1)`
- 在 fixture 的 `state.workflows` 中预置行后，`delete_workflow` 调用应返回 `workflow_id`（int）
- `assert result == 1`

**Case 6 — `test_activate_workflow`**：
- 调用 `workflow_service.activate_workflow(1, tenant_id=1)`
- `assert result.status == "active"`

**Case 7 — `test_pause_workflow`**：
- 调用 `workflow_service.pause_workflow(1, tenant_id=1)`
- `assert result.status == "paused"`

**Case 8 — `test_list_workflows_paginated`**：
- `state.workflows` 预置 3 条记录，`make_count_handler(state)` 返回 count=3
- 调用 `workflow_service.list_workflows(tenant_id=1, page=1, page_size=20)`
- `assert len(items) == 3`
- `assert total == 3`

**Case 9 — `test_execute_workflow_success`**：
- `mock_db_session` 的 `state.workflows[0]` 预置 `conditions=[]`（条件为空，直接满足）
- 调用 `workflow_service.execute_workflow(workflow_id=1, context={"user_id": 10}, tenant_id=1)`
- `assert result.status == "success"`
- `assert result.result is not None`
- `assert result.workflow_id == 1`

**Case 10 — `test_execute_workflow_conditions_not_met`**：
- `mock_db_session` 的 `state.workflows[0]` 预置 `conditions=[{"field": "x", "operator": "==", "value": 1}]` 且 `context={"x": 2}`（条件不匹配）
- 调用 `workflow_service.execute_workflow`
- `assert result.status == "failed"`
- `assert "Conditions not met" in str(result.result)`

**Case 11 — `test_get_execution_history`**：
- 预置 `state.workflow_executions = [{"id": 1, "workflow_id": 1, "trigger_type": "manual", "triggered_by": 10, "started_at": None, "completed_at": None, "status": "success", "result": {}}]`
- 调用 `workflow_service.get_execution_history(workflow_id=1, tenant_id=1)`
- `assert len(result) == 1`
- `assert result[0].workflow_id == 1`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 9 passed

---

### Step 5: 全量 lint + type check

```bash
ruff check src/services/workflow_service.py tests/unit/test_workflow_service.py tests/unit/conftest.py
ruff format --check src/services/workflow_service.py tests/unit/test_workflow_service.py
PYTHONPATH=src mypy src/services/workflow_service.py
```

**完成判定**：三条命令均 exit 0

---

## 6. 验收

- [ ] `ruff check src/services/workflow_service.py tests/unit/test_workflow_service.py tests/unit/conftest.py` → 0 errors
- [ ] `ruff format --check src/services/workflow_service.py tests/unit/test_workflow_service.py` → exit 0
- [ ] `PYTHONPATH=src mypy src/services/workflow_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → ≥ 9 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → 现有单元测试不被破坏

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `workflow_handler` SQL 匹配不完整，特定查询返回 None 导致 `AttributeError` | 中 | 中 | 参考 `pipeline_handler` 增加更多分支（`SELECT`、`INSERT`、`UPDATE`、`DELETE`），或直接用正则匹配表名 |
| `execute_workflow` 内部 `_evaluate_conditions` 路径覆盖不足，条件通过 mock 绕过的 case 与生产不符 | 低 | 中 | 增加一条 `test_execute_workflow_with_valid_condition` 用例，context 明确匹配 conditions 中的条件 |
| `MockState.workflows` 的初始化时机与 `make_mock_session` 内部状态不一致 | 低 | 中 | 将 state 传入 `make_mock_session` 时显式 `state.workflows = [...]`，避免依赖全局 `MockState._instance` |
| 新增 `workflow_handler` 影响其他已有测试（`pipeline_handler` 等不依赖 workflows 表） | 极低 | 低 | `workflow_handler` 仅在显式传入 `make_mock_session([workflow_handler, ...])` 时激活，不影响其他测试 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_workflow_service.py tests/unit/conftest.py
git commit -m "feat(automation): add WorkflowService unit tests with mock DB session

Closes #463"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add WorkflowService unit tests (closes #463)" --body "Closes #463

## Summary
- Add tests/unit/test_workflow_service.py with 9+ test cases covering all public methods
- Add workflow_handler to tests/unit/conftest.py for mock DB session composition
- Cover happy path, NotFound, Validation, execute success/fail, execution history

## Test plan
- [ ] ruff check tests/unit/test_workflow_service.py tests/unit/conftest.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v → ≥ 9 passed
- [ ] PYTHONPATH=src pytest tests/unit/ -m \"not integration\" -v → existing tests not broken"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_pipeline_service.py`](../../tests/unit/test_pipeline_service.py) — 相同 mock DB 模式（`MockState` + `make_mock_session` + domain handler）
- 同类参考实现：[`tests/unit/test_customer_service.py`](../../tests/unit/test_customer_service.py) — service 测试中 `pytest.raises(NotFoundException)` 的标准写法
- 父 issue / 关联：#449（Workflow 子系统总览）
- 依赖 issue：#462（上游 service 基础实现）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
