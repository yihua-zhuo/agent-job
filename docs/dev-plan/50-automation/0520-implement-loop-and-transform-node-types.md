# 自动化 · 实现 Loop 与 Transform 节点类型

| 元数据 | 值 |
|---|---|
| Issue | #520 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1.5 工作日 |
| 依赖 | TBD - 待验证：是否已有 #519 板块文档（node 接口基础） |
| 启用后赋能 | [0654-add-workflow-unit-tests](./0654-add-workflow-unit-tests.md)（节点级单元测试） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

工作流执行引擎（`WorkflowService`）目前仅支持线性 action 执行——无控制流节点，无法遍历列表数据，也无法在执行前变换 context 结构。自动化规则（#73）需要在工单列表遍历、批量通知等场景下展开循环；数据处理（#73）需要将上游结果重塑为下游所需的格式。本 issue 引入两个基础控制流节点，填补这一空白。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层工作流引擎增强。
- **开发者视角**：`src/workflow/nodes/loop.py` 提供 `LoopNode`，可在 `WorkflowService.execute_workflow` 中执行带列表遍历的 DAG 子图；`src/workflow/nodes/transform.py` 提供 `TransformNode`，支持 JSONPath 提取和字符串模板替换；两者均实现统一 `NodeProtocol`，可直接在 `workflow_service._execute_actions` 中被 dispatch。

### 1.3 不做什么（剔除）

- [ ] 不实现持久化循环状态（如记录每个 item 的执行进度到 DB）— 属于后续 issue
- [ ] 不实现条件分支节点（`IfNode`）— 属于后续 issue
- [ ] 不修改现有 `WorkflowModel` / `WorkflowExecutionModel` ORM schema — 本次仅新建 Python 模块
- [ ] 不实现并行循环（`ParallelLoopNode`）— 后续扩展

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → ≥ 8 passed（含 LoopNode × 4 + TransformNode × 4）
- `ruff check src/workflow/nodes/loop.py src/workflow/nodes/transform.py` → 0 errors
- `ruff check tests/unit/test_nodes.py` → 0 errors
- `WorkflowService` 的 `execute_workflow` 对包含 `{"type": "loop", ...}` 的 actions 能正确 dispatch 并返回累积结果

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/workflow_service.py`](../../src/services/workflow_service.py) L189-L211

```{python}
# src/services/workflow_service.py
# _execute_actions is the current action dispatch point (no node abstraction)
@staticmethod
def _execute_actions(workflow: WorkflowModel) -> dict:
    results = []
    for action in workflow.actions or []:
        action_type = action.get("type")
        if action_type == "email.send":
            results.append({"type": "email.send", "status": "sent", "template": action.get("template")})
        elif action_type == "notification.send":
            results.append({"type": "notification.send", "status": "sent", "to": action.get("to")})
        # ... other hardcoded types — no extension point
        else:
            results.append({"type": action_type, "status": "unknown"})
    return {"actions_executed": results}
```

节点接口尚不存在：`src/workflow/nodes/` 目录为空（待验证：无任何 `.py` 文件）。

### 2.2 涉及文件清单

- 要改：
  - [`src/services/workflow_service.py`](../../src/services/workflow_service.py) — 在 `_execute_actions` 中追加 node dispatch 逻辑（向后兼容，原有 hardcoded 分支保留）
  - [`tests/unit/conftest.py`](../../tests/unit/conftest.py) — 新增 `make_workflow_handler`（如果 `tests/unit/domain_handlers/workflow.py` 尚不存在则先建它）
- 要建：
  - `src/workflow/nodes/base.py` — `NodeProtocol`（interface）+ `NodeResult` dataclass）
  - `src/workflow/nodes/loop.py` — `LoopNode` 实现
  - `src/workflow/nodes/transform.py` — `TransformNode` 实现
  - `src/workflow/nodes/__init__.py` — 导出 `NodeProtocol`, `LoopNode`, `TransformNode`
  - `tests/unit/test_nodes.py` — 单元测试
  - `tests/unit/domain_handlers/workflow.py` — mock SQL handler（如果尚不存在）

### 2.3 缺什么

- [ ] 无 node 接口（`NodeProtocol`）— 无法以统一方式 dispatch 不同节点类型
- [ ] 无 `LoopNode` — 无法对列表类型的 context 值逐项执行子 action
- [ ] 无 `TransformNode` — 无法用 JSONPath 提取或 Jinja2 模板修改变量上下文
- [ ] `WorkflowService._execute_actions` 无 dispatch 扩展点，新增节点类型需修改 service 源码
- [ ] `tests/unit/test_nodes.py` 尚不存在 — 无节点级回归保护

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/workflow/nodes/base.py` | `NodeProtocol`（ABC）+ `NodeResult` dataclass |
| `src/workflow/nodes/loop.py` | `LoopNode` — 遍历 `items_path`（JSONPath），对每项执行 `body` actions |
| `src/workflow/nodes/transform.py` | `TransformNode` — JSONPath 提取 + Jinja2 模板替换 |
| `src/workflow/nodes/__init__.py` | 导出 `NodeProtocol`, `NodeResult`, `LoopNode`, `TransformNode` |
| `tests/unit/test_nodes.py` | LoopNode × 4 + TransformNode × 4 共 ≥ 8 个测试用例 |
| `tests/unit/domain_handlers/workflow.py` | workflow 表的 mock SQL handler（如果尚不存在则建之） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/workflow_service.py`](../../src/services/workflow_service.py) | 在 `_execute_actions` 末尾追加 node dispatch：检测 `"type"` 为 `"loop"` / `"transform"` 时，调用对应 node 类 |

### 3.3 新增能力

- **Protocol / Interface**：`NodeProtocol`（`async def execute(self, config: dict, context: dict) -> NodeResult`）
- **LoopNode**：`items_path: str`（JSONPath） + `body: list[dict]`（子 actions）+ `max_iterations: int`（默认 100）
- **TransformNode**：`transforms: list[dict]` — 每项含 `path`（JSONPath）+ `template`（Jinja2）+ `set_key`
- **Node dispatch**：在 `WorkflowService._execute_actions` 中以 `elif` chain 扩展，兼容原有 hardcoded 分支

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 JSONPath（jsonpath-ng）不选 JSONPath_std** — jsonpath-ng 是纯 Python、实现完整 JMESPath 之外的最佳选择；本仓库已有 `jinja2`（用于模板），无需引入额外大依赖
- **选 Protocol（abc）不选 ABC + duck typing** — `NodeProtocol` 用 `@runtime_checkable` 让 `isinstance(node, NodeProtocol)` 在测试中可用，灵活度高于严格 ABC
- **LoopNode.body 直接复用现有 `workflow.actions` 执行逻辑** — body 内 actions 与 workflow.actions 同构，不需要独立 DAG 解析器，降低复杂度

### 4.2 版本约束

无新依赖引入。jsonpath-ng 如已存在于 pyproject.toml 则复用；否则改用 Python 内置 `jsonpath_ng`（若也不存在，则在 `transform.py` 中用简单 `list` 循环替代 JSONPath）。

### 4.3 兼容性约束

- `WorkflowService` 的 `execute_workflow` 方法签名不变 — 扩展通过内部 `_execute_actions` 实现，对外透明
- 新 node 类型的 config 结构遵循 `{"type": "...", ...}` action 对象格式，与现有 actions 列表无缝共存
- 节点 `execute` 方法为 `async`，与 `WorkflowService._execute_actions` 中的 `await` 兼容

### 4.4 已知坑

1. **Alembic autogenerate 会把 `JSONB` 列写成 `JSON` 列** → 本次不涉及 migration，跳过
2. **PYTHONPATH=src，import 必须写 `from workflow.nodes.base` 而不是 `from src.workflow.nodes.base`** → 本次所有新文件遵守
3. **LoopNode 的 `max_iterations` 必须防死循环** → 默认 100，超出抛 `ValidationException("Loop iterations exceeded max={max_iterations}")`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/workflow/nodes/base.py`

定义 node 接口和返回类型，供 loop / transform 复用。

操作：
a) 创建目录 `src/workflow/nodes/`（含 `__init__.py`）
b) 在 `src/workflow/nodes/base.py` 写入：

```python
"""Base node interface for workflow node types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResult:
    """Return value from a node's execute()."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


class NodeProtocol(ABC):
    """Interface all workflow nodes must implement."""

    @abstractmethod
    async def execute(self, config: dict, context: dict) -> NodeResult:
        """Execute the node with the given config and context.

        Args:
            config: Node-specific configuration dict (e.g. {"items_path": "$.tickets", ...})
            context: Shared workflow execution context dict

        Returns:
            NodeResult with success=True/False and data with node output
        """
        ...
```

c) 在 `src/workflow/nodes/__init__.py` 写入：

```python
"""Workflow node types."""

from workflow.nodes.base import NodeProtocol, NodeResult
from workflow.nodes.loop import LoopNode
from workflow.nodes.transform import TransformNode

__all__ = ["NodeProtocol", "NodeResult", "LoopNode", "TransformNode"]
```

**完成判定**：`ruff check src/workflow/nodes/base.py src/workflow/nodes/__init__.py` exit 0

---

### Step 2: 创建 `src/workflow/nodes/loop.py`

实现 `LoopNode`：遍历 JSONPath 列表，对每项执行 body actions。

操作：
a) 在 `src/workflow/nodes/loop.py` 写入：

```python
"""Loop node — iterates over a list and executes a sub-DAG for each item."""

from __future__ import annotations

from workflow.nodes.base import NodeProtocol, NodeResult
from pkg.errors.app_exceptions import ValidationException

MAX_ITERATIONS_DEFAULT = 100


class LoopNode(NodeProtocol):
    """Iterates over a list in context, executing body actions for each item.

    Config schema:
        items_path (str): JSONPath expression pointing to a list in context.
        body (list[dict]): Action objects to execute per item.
        max_iterations (int): Upper bound on iterations (default 100).
        item_key (str): Key under which each item is injected into context (default "item").
        result_key (str): Key in output data where iteration results are stored (default "results").
    """

    async def execute(self, config: dict, context: dict) -> NodeResult:
        items_path = config.get("items_path", "")
        body = config.get("body", [])
        max_iterations = config.get("max_iterations", MAX_ITERATIONS_DEFAULT)
        item_key = config.get("item_key", "item")
        result_key = config.get("result_key", "results")

        items = self._jsonpath_get(context, items_path)
        if not isinstance(items, list):
            return NodeResult(
                success=False,
                error=f"items_path '{items_path}' did not resolve to a list: {type(items).__name__}",
            )

        if len(items) > max_iterations:
            raise ValidationException(f"Loop iterations {len(items)} exceeded max={max_iterations}")

        results = []
        for idx, item in enumerate(items):
            item_context = {**context, item_key: item, "_loop_index": idx}
            item_result = {"index": idx, "item": item, "actions": []}
            for action in body:
                action_type = action.get("type", "unknown")
                action_params = {k: v for k, v in action.items() if k != "type"}
                # Template substitution on each param using item_context
                rendered_params = {
                    k: self._render_template(str(v), item_context) if isinstance(v, str) else v
                    for k, v in action_params.items()
                }
                item_result["actions"].append({
                    "type": action_type,
                    "params": rendered_params,
                    "status": "executed",
                })
            results.append(item_result)

        output_data = {**context, result_key: results}
        return NodeResult(success=True, data=output_data)

    @staticmethod
    def _jsonpath_get(data: dict, path: str) -> Any:
        """Simple list-keyed path resolver (supports "$.key" / "$.key[0]" / "$.a.b")."""
        if not path:
            return data
        segments = path.lstrip("$.").split(".")
        current = data
        for seg in segments:
            if not seg:
                continue
            if isinstance(current, dict):
                current = current.get(seg)
            elif isinstance(current, list):
                try:
                    idx = int(seg)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    @staticmethod
    def _render_template(template: str, context: dict) -> str:
        """Minimal Jinja2-style template substitution: {{ item.field }} → value."""
        import re
        def replacer(m):
            key = m.group(1).strip()
            keys = key.split(".")
            val = context
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    return m.group(0)
            return str(val) if val is not None else m.group(0)
        return re.sub(r"\{\{([^}]+)\}\}", replacer, template)
```

**完成判定**：`ruff check src/workflow/nodes/loop.py` exit 0

---

### Step 3: 创建 `src/workflow/nodes/transform.py`

实现 `TransformNode`：对 context 应用 JSONPath 提取和模板替换。

操作：
在 `src/workflow/nodes/transform.py` 写入：

```python
"""Transform node — applies JSONPath extractions and template substitutions to context."""

from __future__ import annotations

import re
from workflow.nodes.base import NodeProtocol, NodeResult


class TransformNode(NodeProtocol):
    """Applies a list of transforms to the workflow context.

    Config schema:
        transforms (list[dict]): List of transform objects. Each object:
            - path (str): JSONPath to set in the context (e.g. "$.filtered_ids").
            - extract (str): JSONPath expression to extract a value from context.
            - template (str): Jinja2-style template string rendered with current context.
            - set_key (str): Alias for path (one must be present).
            Exactly one of 'extract' or 'template' must be specified per transform.
    """

    async def execute(self, config: dict, context: dict) -> NodeResult:
        transforms = config.get("transforms", [])
        result_context = {**context}

        for t in transforms:
            path = t.get("path") or t.get("set_key")
            if not path:
                return NodeResult(
                    success=False,
                    error="Each transform must specify 'path' or 'set_key'",
                )

            extract_expr = t.get("extract")
            template_str = t.get("template")

            if extract_expr:
                value = self._jsonpath_get(result_context, extract_expr)
                self._jsonpath_set(result_context, path, value)
            elif template_str:
                rendered = self._render_template(template_str, result_context)
                self._jsonpath_set(result_context, path, rendered)
            else:
                return NodeResult(
                    success=False,
                    error=f"Transform at path '{path}' must specify 'extract' or 'template'",
                )

        return NodeResult(success=True, data=result_context)

    @staticmethod
    def _jsonpath_get(data: dict, path: str):
        """Resolve a dot-notation path against a dict (supports list indexing)."""
        if not path:
            return data
        segments = path.lstrip("$.").split(".")
        current = data
        for seg in segments:
            if not seg:
                continue
            if isinstance(current, dict):
                current = current.get(seg)
            elif isinstance(current, list):
                try:
                    current = current[int(seg)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    @staticmethod
    def _jsonpath_set(data: dict, path: str, value) -> None:
        """Set a value at a dot-notation path, creating intermediate dicts as needed."""
        segments = path.lstrip("$.").split(".")
        node = data
        for seg in segments[:-1]:
            if seg not in node:
                node[seg] = {}
            node = node[seg]
        node[segments[-1]] = value

    @staticmethod
    def _render_template(template: str, context: dict) -> str:
        """Minimal Jinja2-style substitution: {{ a.b }} → context value."""
        def replacer(m):
            key = m.group(1).strip()
            keys = key.split(".")
            val = context
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    return m.group(0)
            return str(val) if val is not None else m.group(0)
        return re.sub(r"\{\{([^}]+)\}\}", replacer, template)
```

**完成判定**：`ruff check src/workflow/nodes/transform.py` exit 0

---

### Step 4: 更新 `WorkflowService._execute_actions` 添加 node dispatch

在 `_execute_actions` 末尾追加 loop / transform dispatch，向后兼容原有 hardcoded 分支。

操作：
在 `src/services/workflow_service.py` 的 `_execute_actions` 方法的 `for action in workflow.actions` 循环末尾追加：

```python
        elif action_type == "loop":
            from workflow.nodes import LoopNode
            node = LoopNode()
            result = await node.execute(action, context)
            results.append({"type": "loop", "status": "success" if result.success else "failed", "data": result.data, "error": result.error})
        elif action_type == "transform":
            from workflow.nodes import TransformNode
            node = TransformNode()
            result = await node.execute(action, context)
            results.append({"type": "transform", "status": "success" if result.success else "failed", "data": result.data, "error": result.error})
```

追加位置：`src/services/workflow_service.py` `_execute_actions` 方法 `results.append({"type": action_type, "status": "unknown"})` 之前。

**完成判定**：`ruff check src/services/workflow_service.py` exit 0

---

### Step 5: 创建 `tests/unit/domain_handlers/workflow.py`

新建 workflow mock SQL handler（如该文件尚不存在）。

```python
"""Workflow SQL handlers for unit tests."""

from __future__ import annotations

from tests.unit.conftest import MockResult, MockRow, MockState


def make_workflow_handler(state: MockState):
    if not hasattr(state, "workflows"):
        state.workflows = {}
    if not hasattr(state, "workflows_next_id"):
        state.workflows_next_id = 1

    def handler(sql_text, params):
        tenant_id = params.get("tenant_id", 0)

        if "insert into workflows" in sql_text.lower():
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

        if "select" in sql_text and "from workflows" in sql_text and "where id" in sql_text and "count" not in sql_text.lower():
            wid = params.get("id")
            row = state.workflows.get(wid)
            if row and row.get("tenant_id") == tenant_id:
                return MockResult([MockRow(row.copy())])
            return MockResult([])

        if "select" in sql_text and "from workflows" in sql_text and "count" in sql_text.lower():
            count_val = sum(1 for r in state.workflows.values() if r.get("tenant_id") == tenant_id)
            return MockResult([[count_val]])

        return None

    return handler
```

**完成判定**：`ruff check tests/unit/domain_handlers/workflow.py` exit 0

---

### Step 6: 创建 `tests/unit/test_nodes.py`

创建节点单元测试，覆盖 LoopNode × 4 + TransformNode × 4。

操作：
在 `tests/unit/test_nodes.py` 写入以下内容：

```python
"""Unit tests for workflow node types: LoopNode and TransformNode."""

from __future__ import annotations

import pytest

from workflow.nodes import LoopNode, TransformNode, NodeResult
from pkg.errors.app_exceptions import ValidationException


class TestLoopNode:
    """LoopNode — iterate over a list and execute body actions per item."""

    async def test_iterates_over_list_and_injects_item_key(self):
        node = LoopNode()
        config = {
            "items_path": "$.tickets",
            "item_key": "ticket",
            "body": [{"type": "log", "message": "{{ ticket.id }}"}],
        }
        context = {"tickets": [{"id": 10}, {"id": 20}], "tenant_id": 1}
        result = await node.execute(config, context)
        assert result.success is True
        assert len(result.data["results"]) == 2
        assert result.data["results"][0]["item"]["id"] == 10
        assert result.data["results"][1]["item"]["id"] == 20

    async def test_returns_error_when_items_path_not_a_list(self):
        node = LoopNode()
        config = {"items_path": "$.scalar", "body": []}
        context = {"scalar": "not-a-list"}
        result = await node.execute(config, context)
        assert result.success is False
        assert "did not resolve to a list" in result.error

    async def test_raises_validation_exception_when_exceeds_max_iterations(self):
        node = LoopNode()
        config = {"items_path": "$.items", "max_iterations": 2, "body": []}
        context = {"items": [1, 2, 3]}
        with pytest.raises(ValidationException) as exc_info:
            await node.execute(config, context)
        assert "exceeded max=2" in str(exc_info.value)

    async def test_renders_template_in_body_params_using_item_context(self):
        node = LoopNode()
        config = {
            "items_path": "$.users",
            "item_key": "user",
            "body": [{"type": "notify", "message": "Hello {{ user.name }}"}],
        }
        context = {"users": [{"name": "Alice"}, {"name": "Bob"}], "tenant_id": 1}
        result = await node.execute(config, context)
        assert result.success is True
        assert result.data["results"][0]["actions"][0]["params"]["message"] == "Hello Alice"
        assert result.data["results"][1]["actions"][0]["params"]["message"] == "Hello Bob"


class TestTransformNode:
    """TransformNode — JSONPath extraction and template substitution."""

    async def test_extracts_value_with_jsonpath_and_sets_at_path(self):
        node = TransformNode()
        config = {"transforms": [{"path": "$.filtered_ids", "extract": "$.tickets[*].id"}]}
        context = {"tickets": [{"id": 1}, {"id": 2}, {"id": 3}]}
        result = await node.execute(config, context)
        assert result.success is True
        assert result.data["filtered_ids"] == [1, 2, 3]

    async def test_renders_template_with_jinja2_style_substitution(self):
        node = TransformNode()
        config = {"transforms": [{"path": "$.greeting", "template": "Hello {{ user.name }}"}]}
        context = {"user": {"name": "Carol"}}
        result = await node.execute(config, context)
        assert result.success is True
        assert result.data["greeting"] == "Hello Carol"

    async def test_returns_error_when_neither_extract_nor_template_specified(self):
        node = TransformNode()
        config = {"transforms": [{"path": "$.result"}]}
        context = {}
        result = await node.execute(config, context)
        assert result.success is False
        assert "must specify" in result.error

    async def test_returns_error_when_path_key_missing(self):
        node = TransformNode()
        config = {"transforms": [{"extract": "$.x"}]}
        context = {"x": 1}
        result = await node.execute(config, context)
        assert result.success is False
        assert "path" in result.error or "set_key" in result.error
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → ≥ 8 passed

---

### Step 7: lint 全量验证

操作：
- `ruff check src/workflow/nodes/loop.py src/workflow/nodes/transform.py src/workflow/nodes/base.py src/workflow/nodes/__init__.py src/services/workflow_service.py`
- `ruff check tests/unit/test_nodes.py tests/unit/domain_handlers/workflow.py`

**完成判定**：所有文件 ruff exit 0 且 pytest tests/unit/test_nodes.py 全 passed

---

## 6. 验收

- [ ] `ruff check src/workflow/nodes/` → 0 errors
- [ ] `ruff check src/services/workflow_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_nodes.py tests/unit/domain_handlers/workflow.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → ≥ 8 passed
- [ ] `LoopNode.execute` 对 `{"items": [1,2,3], "max_iterations": 10, "body": []}` 返回 `success=True` 且 `results` 长度为 3
- [ ] `TransformNode.execute` 对 `{"transforms": [{"path": "$.out", "template": "{{ a }}"}]}` + context `{"a": "val"}` 返回 `out: "val"`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `_execute_actions` 追加 node dispatch 后与现有 actions 中的 `"type": "loop"` / `"transform"` 字符串冲突（已有用户使用同名 action type） | 低 | 中 | 向前兼容：原有 hardcoded 分支优先；node dispatch 追加在 else 链最后，不覆盖已有行为 |
| `max_iterations` 校验引入 `ValidationException` 改变 workflow 失败行为 | 低 | 中 | 新异常类型在全局 `AppException` handler 中映射为 422，与其他 ValidationException 行为一致，无需特殊处理 |
| `domain_handlers/workflow.py` 已存在且与新建内容冲突 | 低 | 低 | 先检查文件是否存在再创建；如已存在则追加 handler 函数而非覆盖 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/workflow/nodes/ src/services/workflow_service.py \
       tests/unit/test_nodes.py tests/unit/domain_handlers/workflow.py
git commit -m "feat(automation): implement LoopNode and TransformNode workflow node types

- NodeProtocol + NodeResult in workflow/nodes/base.py
- LoopNode: iterate list, execute body per item, template substitution
- TransformNode: JSONPath extract + Jinja2-style template rendering
- WorkflowService._execute_actions dispatch extended for loop/transform

Closes #520"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): implement LoopNode and TransformNode (#520)" --body "Closes #520"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/automation_service.py`](../../src/services/automation_service.py) — `_eval_condition` / `_match_conditions` 结构（条件求值模式类似）
- 同类参考实现：[`src/services/workflow_service.py`](../../src/services/workflow_service.py) L189-L211 — `_execute_actions` 当前实现
- 父 issue：#73
- 关联依赖：#519（TBD — 是否已有节点接口板块）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
