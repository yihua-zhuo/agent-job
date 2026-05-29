# 自动化板块 · 为 CoordinatorAgent 添加集成测试

| 元数据 | 值 |
|---|---|
| Issue | #629 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.25 工作日 |
| 依赖 | 无（#628 为前瞻参考，非阻塞依赖） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`CoordinatorAgent` 当前仅有顶层逻辑（`parse_task` / `dispatch_to_agent` / `run_workflow`），没有任何测试覆盖。issue #628 实现/完善了 `run_workflow` 的任务分派与进度追踪逻辑，但在 src/ 之外没有对应的集成测试来验证其在真实数据库会话下的行为。集成测试是确保多组件（tenant isolation、session lifecycle、task dispatch）协同正确的唯一手段。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯测试层。
- **开发者视角**：`tests/integration/test_coordinator_agent_integration.py` 存在，覆盖 happy-path、boundary 和 error 三类场景；每次 `pytest tests/integration/test_coordinator_agent_integration.py -v` 通过即代表 CoordinatorAgent 在真实 DB 上下文中正确运行。

### 1.3 不做什么（剔除）

- [ ] 不修改 `docs/agents/coordinator/coordinator_agent.py` 的业务逻辑（仅写测试）。
- [ ] 不为 `coordinator_agent.py` 编写单元测试（issue scope 仅含 integration tests）。
- [ ] 不引入新的 fixture 或改动 `conftest.py`（使用现有 `db_schema`、`tenant_id`、`async_session`）。

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py -v` → `≥ 3 passed`（3 个测试用例）
- `ruff check tests/integration/test_coordinator_agent_integration.py` → 0 errors
- 测试文件中包含：1 个 happy-path、1 个 boundary（空任务列表）、1 个 error（agent script 不存在）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`docs/agents/coordinator/coordinator_agent.py`](../../docs/agents/coordinator/coordinator_agent.py) L{60}-L{72}

```python
60:    def run_workflow(self, tasks: List[Dict]) -> Dict:
61:        """Execute full workflow with parallel agent execution"""
62:        results = {"dispatched": [], "completed": [], "failed": []}
63:        
64:        # Phase 1: Dispatch all tasks
65:        for task in tasks:
66:            dispatch_result = self.dispatch_to_agent(task.get("assignee", "coordinator"), task)
67:            results["dispatched"].append(dispatch_result)
68:            
69:        # Phase 2: Aggregate results
70:        # Phase 3: Quality gates
71:        
72:        return results
```

### 2.2 涉及文件清单

- 要改：无
- 要建：
  - `tests/integration/test_coordinator_agent_integration.py` — 集成测试文件，覆盖 `CoordinatorAgent.run_workflow` 的任务分派与结果聚合

### 2.3 缺什么

- [ ] `tests/integration/test_coordinator_agent_integration.py` 不存在 — 无法验证 CoordinatorAgent 在真实 DB 会话下的行为
- [ ] 无测试覆盖 `run_workflow` 对空任务列表的处理（boundary case）
- [ ] 无测试覆盖 `dispatch_to_agent` 遇到不存在的 agent script 时的返回（error case）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_coordinator_agent_integration.py` | 为 CoordinatorAgent 编写的集成测试，使用真实 AsyncSession，验证任务分派与进度追踪 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | — |

### 3.3 新增能力

- **集成测试覆盖**：`CoordinatorAgent.run_workflow` happy-path、空列表 boundary、agent-not-found error 三种场景
- **验证手段**：`pytest tests/integration/test_coordinator_agent_integration.py -v` → 3 passed

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `tempfile.TemporaryDirectory` 而非硬编码路径**：`CoordinatorAgent` 构造函数需要 `workspace: Path`，测试时创建临时目录确保 agent script 查找逻辑的隔离性。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- `CoordinatorAgent` 不是 service 类，不走 `get_db_session`，但 `async_session` fixture 用于验证 DB 会话生命周期不报错（纯传入参数，非直接依赖）。
- 测试中不调用 `.to_dict()`（`run_workflow` 返回 Python dict，非 ORM 对象）。
- `run_workflow` 错误不抛 `AppException`，只返回 `{"status": "not_found"}` 等 dict — 测试直接断言 dict 内容。

### 4.4 已知坑

1. **`dispatch_to_agent` 调用 `subprocess.run`** → 测试环境若无 `agents/coordinator/coordinator_agent.py` 等脚本路径，`status` 为 `"not_found"`；这是预期的 error-case 行为，不是 bug，无需 mock。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 tests/integration/test_coordinator_agent_integration.py

在 `tests/integration/` 下新建文件，导入 `CoordinatorAgent`，设置 `sys.path` 以解析 `docs/agents` 目录。

操作：
- a) 创建 `tests/integration/test_coordinator_agent_integration.py`
- b) 在文件顶部添加 `sys.path` 逻辑，使其能 `from docs.agents.coordinator.coordinator_agent import CoordinatorAgent`

示例代码：

```python
import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import tempfile
import pytest
from docs.agents.coordinator.coordinator_agent import CoordinatorAgent
```

**完成判定**：`ruff check tests/integration/test_coordinator_agent_integration.py` → exit 0（文件存在且可解析 import）

### Step 2: 编写 happy-path 测试

用 `tempfile.TemporaryDirectory` 作为 `workspace`，写入一个假的 agent script `agents/test/test_agent.py`（返回 exit 0），构造含一个 task 的 `tasks` 列表，调用 `run_workflow`，断言 `results["dispatched"]` 非空且至少有一个 `status == "completed"`。

操作：
- a) 创建临时 workspace dir 并写入假 agent script
- b) 调用 `CoordinatorAgent(workspace).run_workflow([...])`
- c) 断言 `results["dispatched"][0]["status"] == "completed"`

示例代码：

```python
class TestCoordinatorAgent:
    @pytest.fixture
    def workspace(self, tmp_path):
        agent_dir = tmp_path / "agents" / "test"
        agent_dir.mkdir(parents=True)
        (agent_dir / "test_agent.py").write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
        return tmp_path

    @pytest.mark.asyncio
    async def test_run_workflow_dispatches_task_and_returns_completed(
        self, workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        tasks = [{"task_id": "t1", "assignee": "test", "type": "feature"}]
        results = agent.run_workflow(tasks)
        assert "dispatched" in results
        assert len(results["dispatched"]) == 1
        assert results["dispatched"][0]["status"] == "completed"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_dispatches_task_and_returns_completed -v` → `1 passed`

### Step 3: 编写 boundary 测试（空任务列表）

调用 `run_workflow([])`，断言 `results["dispatched"]` 为空列表，函数不抛异常。

```python
    @pytest.mark.asyncio
    async def test_run_workflow_with_empty_task_list_returns_empty_dispatched(
        self, workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        results = agent.run_workflow([])
        assert results["dispatched"] == []
        assert results["completed"] == []
        assert results["failed"] == []
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_with_empty_task_list_returns_empty_dispatched -v` → `1 passed`

### Step 4: 编写 error 测试（agent script 不存在）

调用 `run_workflow` 传入一个 `assignee` 为不存在的 agent，断言对应 `dispatched` 项的 `status == "not_found"`。

```python
    @pytest.mark.asyncio
    async def test_run_workflow_with_nonexistent_agent_returns_not_found(
        self, workspace, tenant_id, async_session
    ):
        agent = CoordinatorAgent(workspace=workspace)
        tasks = [{"task_id": "t2", "assignee": "nonexistent_agent", "type": "feature"}]
        results = agent.run_workflow(tasks)
        assert results["dispatched"][0]["status"] == "not_found"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py::TestCoordinatorAgent::test_run_workflow_with_nonexistent_agent_returns_not_found -v` → `1 passed`

---

## 6. 验收

- [ ] `ruff check tests/integration/test_coordinator_agent_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_coordinator_agent_integration.py -v` → 3 passed
- [ ] 测试文件路径 `tests/integration/test_coordinator_agent_integration.py` 存在且非空（≥ 50 行）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `CoordinatorAgent` 的 import 路径随重构改变导致测试无法解析 | 低 | 低 | 测试文件顶部 `sys.path` 逻辑可快速更新，不阻塞其他板块 |
| `subprocess.run` 在 CI 环境中行为差异导致 error-case 测试 flaky | 低 | 中 | error-case 只断言 `status == "not_found"`，不依赖具体 stderr/stdout；已隔离在临时目录中执行 |
| 新增测试文件与现有 `db_schema` fixture 不兼容（session scope 问题） | 极低 | 高 | 所有测试均使用 `async_session` fixture（函数级），与 `db_schema` 完全解耦；不会污染其他测试文件 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/integration/test_coordinator_agent_integration.py
git commit -m "test(integration): add CoordinatorAgent integration tests (#629)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#629): integration tests for CoordinatorAgent" --body "Closes #629"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/integration/test_auth_integration.py`](../../tests/integration/test_auth_integration.py) — 同为集成测试，使用 `async_session` fixture，结构可对照
- 同类参考实现：[`tests/integration/test_rules_integration.py`](../../tests/integration/test_rules_integration.py) — integration test 典型结构
- 父 issue / 关联：#41
- 前瞻参考（实现前可先阅读）：#628（CoordinatorAgent 主体实现）
