# 自动化 · 实现 Trigger 与 Condition 节点类型

| 元数据 | 值 |
|---|---|
| Issue | #518 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [自动化 · 实现基础节点接口与引擎调度循环](./0517-implement-base-node-interface-and-engine-scheduling-loop.md) |
| 启用后赋能 | 自动化 · 实现 Action 与终态节点类型, 自动化 · 实现循环与子流程节点类型 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #517 establishes the base node interface (`execute(ctx) → NodeResult`) and the engine's scheduling loop. Without node types, the engine has no work to schedule. Trigger and condition nodes are the two fundamental building blocks needed to make a real workflow executable: trigger provides the event-driven entry point that reads the external event payload, and condition enables branching logic so different branches can be taken based on context values.

Neither node type exists today — the workflow module is greenfield beyond the interface defined in #517.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层节点实现，为后续 action 节点编排提供前置条件。
- **开发者视角**：`TriggerNode` can be registered with the engine as an entry point, routing by `event_type` field in the incoming trigger payload. `ConditionNode` can be placed in the graph; its `execute(ctx)` evaluates a JSON-path expression against `ctx` and returns the branch name selected.

### 1.3 不做什么（剔除）

- [ ] Persistence of trigger events to a database table — handled by a separate inbound integration layer.
- [ ] Scheduler / cron-based trigger variants — only event-driven (HTTP/webhook payload) trigger is in scope.
- [ ] Variable mutation / context modification inside condition branches — read-only evaluation only.
- [ ] Unit tests beyond `tests/unit/test_nodes.py` — integration tests belong to #688.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → `4 passed` (trigger + condition × success path + error path)
- `ruff check src/workflow/nodes/trigger.py src/workflow/nodes/condition.py` → `0 errors`
- `ruff check tests/unit/test_nodes.py` → `0 errors`
- `mypy src/workflow/nodes/trigger.py src/workflow/nodes/condition.py` → `0 errors`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

Issue #517 establishes the base interface in `src/workflow/nodes/base.py` (expected: `class BaseNode`, `execute(self, ctx: NodeContext) -> NodeResult`). The workflow module directory (`src/workflow/`) exists. All other node files are absent.

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_nodes.py` — append `TestTriggerNode` and `TestConditionNode` classes
- 要建：
  - `src/workflow/nodes/trigger.py` — `TriggerNode` class
  - `src/workflow/nodes/condition.py` — `ConditionNode` class
  - `src/workflow/nodes/__init__.py` — `TriggerNode`, `ConditionNode` exports

### 2.3 缺什么

- [ ] `TriggerNode` — no event-driven entry point; engine cannot receive external events
- [ ] `ConditionNode` — no branching capability; workflow graph must be strictly linear
- [ ] JSON-path evaluation library — no dependency for `ConditionNode.execute` to evaluate expressions
- [ ] `NodeContext` dataclass fields — issue #517's base interface should define `ctx.trigger_payload: dict`, `ctx.variables: dict`; if absent, coordinate with #517 author

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/workflow/nodes/trigger.py` | Event-driven entry node; routes execution based on `event_type` in trigger_payload |
| `src/workflow/nodes/condition.py` | Branching node; evaluates JSON-path expressions against NodeContext |
| `src/workflow/nodes/__init__.py` | Exports `TriggerNode`, `ConditionNode` alongside existing `BaseNode` |
| `tests/unit/test_nodes.py` | Unit tests: `TestTriggerNode`, `TestConditionNode` |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/test_nodes.py` | Add `TestTriggerNode` (3 cases) + `TestConditionNode` (3 cases) |

### 3.3 新增能力

- **ORM model**：N/A — no DB models in this scope
- **Service method**：N/A
- **Node class**：`TriggerNode(BaseNode)` — `execute(ctx) -> NodeResult`, routes to `next_node_id` based on `ctx.trigger_payload.get("event_type")`
- **Node class**：`ConditionNode(BaseNode)` — `execute(ctx) -> NodeResult`, evaluates `self.expression` (JSON-path) against `ctx.variables`, selects `branch_key`
- **Engine hook**：Trigger node registered via `WorkflowEngine.register_trigger(event_type, node_id)`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `jsonpath-ng` 不选 `jsonpath-rw` / `JMESPath`**：`jsonpath-ng` is actively maintained, supports both JSONPath (draft goessner.net style) and Pythonic syntax, and has no known security advisories as of 2025. `jsonpath-rw` is unmaintained. JMESPath requires different expression syntax than JSONPath.
- **选字典分发 (`{"event_type": node_id}`) 不选反射 / 插件注册**：keeps routing logic explicit and unit-testable. A registry dict in `TriggerNode.__init__` is injected, not hard-coded, enabling test doubles without loading the full engine.
- **Condition node returns `branch_key` field inside `NodeResult.metadata`** not a separate enum — aligns with existing `NodeResult` shape from #517, avoids schema proliferation.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `jsonpath-ng` | `>=1.5.0` | JSON-path expression evaluation |

### 4.3 兼容性约束

- `BaseNode` interface from #517: `execute(self, ctx: NodeContext) -> NodeResult`
- `NodeContext` must expose at minimum `ctx.trigger_payload: dict` and `ctx.variables: dict`
- `NodeResult` structure from #517: `success: bool`, `output: Any`, `next_node_id: str | None`, `metadata: dict`
- All node classes live in `src/workflow/nodes/` with `__init__.py` re-exporting them
- Imports: `from workflow.nodes.base import BaseNode, NodeContext, NodeResult` (do NOT use `from src.workflow...`)
- Multi-tenant: trigger routing is tenant-agnostic at the node level; per-tenant filtering is the engine's responsibility

### 4.4 已知坑

1. **`jsonpath-ng` compile-time cache is not thread-safe by default** → 规避：`TriggerNode` and `ConditionNode` should compile JSONPath expressions once at `__init__` time and store compiled objects as instance attributes; do not re-compile in hot path.
2. **`NodeContext` fields not confirmed in #517** → 规避：write the nodes against the expected fields (`trigger_payload`, `variables`) as documented here; if #517 defines different names, open a follow-up issue immediately rather than blocking.
3. **Condition node with empty expression list** → 规避：default branch is `"default"` when no condition matches; raise `ValidationException` if a required branch is missing at `__init__` time, not at runtime.

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold `src/workflow/nodes/__init__.py` and verify base interface

Create `src/workflow/nodes/__init__.py` that re-exports `BaseNode`, `NodeContext`, `NodeResult` from `base.py` (established by #517) and adds exports for the new node classes as they are written.

```python
# src/workflow/nodes/__init__.py
from workflow.nodes.base import BaseNode, NodeContext, NodeResult

__all__ = ["BaseNode", "NodeContext", "NodeResult", "TriggerNode", "ConditionNode"]
```

**完成判定**：`ruff check src/workflow/nodes/__init__.py` → `0 errors`

---

### Step 2: Implement `TriggerNode` in `src/workflow/nodes/trigger.py`

Write `TriggerNode` class that:
- Inherits `BaseNode`
- `__init__(self, routing_table: dict[str, str | None])` — maps `event_type` → `next_node_id`; value `None` means terminal (no next node)
- `execute(self, ctx: NodeContext) -> NodeResult`: reads `ctx.trigger_payload.get("event_type")`, dispatches to routing table, returns `NodeResult(success=True, output={"event_type": ..., "node_id": ...}, next_node_id=..., metadata={})`
- Default `event_type` key is `"event_type"`; add `self.event_type_key` constructor param for override

```python
# src/workflow/nodes/trigger.py
from workflow.nodes.base import BaseNode, NodeContext, NodeResult
from services.errors import ValidationException

class TriggerNode(BaseNode):
    def __init__(
        self,
        node_id: str,
        routing_table: dict[str, str | None],
        event_type_key: str = "event_type",
    ):
        self.node_id = node_id
        self.routing_table = routing_table
        self.event_type_key = event_type_key

    def execute(self, ctx: NodeContext) -> NodeResult:
        payload = ctx.trigger_payload or {}
        event_type = payload.get(self.event_type_key)
        next_node_id = self.routing_table.get(event_type)
        if next_node_id is None and event_type not in self.routing_table:
            next_node_id = self.routing_table.get("*")  # wildcard fallback
        return NodeResult(
            success=True,
            output={"event_type": event_type, "routed_to": next_node_id},
            next_node_id=next_node_id,
            metadata={"event_type": event_type},
        )
```

**完成判定**：`ruff check src/workflow/nodes/trigger.py` → `0 errors`; `mypy src/workflow/nodes/trigger.py` → `0 errors`

---

### Step 3: Install `jsonpath-ng` dependency and add to `pyproject.toml`

Add `jsonpath-ng = ">=1.5.0"` to `[project.dependencies]` in `pyproject.toml`.

**完成判定**：`grep -q "jsonpath-ng" pyproject.toml`

---

### Step 4: Implement `ConditionNode` in `src/workflow/nodes/condition.py`

Write `ConditionNode` class that:
- Inherits `BaseNode`
- `__init__(self, conditions: list[dict], default_branch: str)` — each condition dict: `{"expression": "<jsonpath>", "branch_key": "<branch_name>", "next_node_id": "<node_id>"}`
- Compiles each `expression` once at `__init__` (store compiled `jsonpath.Compiled` object)
- `execute(self, ctx: NodeContext) -> NodeResult`: iterates conditions in order; first matching condition wins; if none match, uses `default_branch`. Returns `NodeResult(success=True, output={"branch_key": ..., "matched": ...}, next_node_id=..., metadata={})`
- Raises `ValidationException` if any `expression` fails to compile

```python
# src/workflow/nodes/condition.py
from workflow.nodes.base import BaseNode, NodeContext, NodeResult
from services.errors import ValidationException
from jsonpath_ng import parse as parse_jsonpath
from jsonpath_ng.exceptions import JsonPathParserException

class ConditionNode(BaseNode):
    def __init__(
        self,
        node_id: str,
        conditions: list[dict],
        default_branch: str = "default",
        default_next_node_id: str | None = None,
    ):
        self.node_id = node_id
        self.default_branch = default_branch
        self.default_next_node_id = default_next_node_id
        self._compiled = []
        for cond in conditions:
            try:
                compiled = parse_jsonpath(cond["expression"])
            except JsonPathParserException as e:
                raise ValidationException(f"Invalid JSONPath expression: {cond['expression']}") from e
            self._compiled.append({
                "compiled": compiled,
                "branch_key": cond["branch_key"],
                "next_node_id": cond.get("next_node_id"),
            })

    def execute(self, ctx: NodeContext) -> NodeResult:
        data = ctx.variables or {}
        for item in self._compiled:
            matches = item["compiled"].find(data)
            if matches:
                return NodeResult(
                    success=True,
                    output={"branch_key": item["branch_key"], "matched": True},
                    next_node_id=item["next_node_id"],
                    metadata={"branch_key": item["branch_key"], "expression_hit": True},
                )
        return NodeResult(
            success=True,
            output={"branch_key": self.default_branch, "matched": False},
            next_node_id=self.default_next_node_id,
            metadata={"branch_key": self.default_branch, "expression_hit": False},
        )
```

**完成判定**：`ruff check src/workflow/nodes/condition.py` → `0 errors`; `mypy src/workflow/nodes/condition.py` → `0 errors`

---

### Step 5: Update `src/workflow/nodes/__init__.py` with new exports

Add `from workflow.nodes.trigger import TriggerNode` and `from workflow.nodes.condition import ConditionNode` to the `__init__.py` file.

**完成判定**：`ruff check src/workflow/nodes/__init__.py` → `0 errors`

---

### Step 6: Write unit tests in `tests/unit/test_nodes.py`

Append to existing `tests/unit/test_nodes.py` (or create if #517 did not create it):

```python
# tests/unit/test_nodes.py — additions only

class TestTriggerNode:
    def test_routes_known_event_type(self):
        node = TriggerNode("trigger-1", {"order.created": "node-a", "order.cancelled": "node-b"})
        ctx = NodeContext(trigger_payload={"event_type": "order.created"}, variables={})
        result = node.execute(ctx)
        assert result.success is True
        assert result.next_node_id == "node-a"
        assert result.metadata["event_type"] == "order.created"

    def test_routes_unknown_event_type_to_none(self):
        node = TriggerNode("trigger-1", {"order.created": "node-a"})
        ctx = NodeContext(trigger_payload={"event_type": "order.shipped"}, variables={})
        result = node.execute(ctx)
        assert result.success is True
        assert result.next_node_id is None

    def test_empty_payload(self):
        node = TriggerNode("trigger-1", {"order.created": "node-a"})
        ctx = NodeContext(trigger_payload={}, variables={})
        result = node.execute(ctx)
        assert result.success is True
        assert result.next_node_id is None


class TestConditionNode:
    def test_matched_condition_returns_branch(self):
        node = ConditionNode(
            "cond-1",
            [{"expression": "$.status", "branch_key": "active", "next_node_id": "node-a"}],
            default_branch="inactive",
            default_next_node_id="node-b",
        )
        ctx = NodeContext(trigger_payload={}, variables={"status": "active"})
        result = node.execute(ctx)
        assert result.success is True
        assert result.metadata["branch_key"] == "active"
        assert result.next_node_id == "node-a"

    def test_no_match_falls_back_to_default(self):
        node = ConditionNode(
            "cond-1",
            [{"expression": "$.status", "branch_key": "active", "next_node_id": "node-a"}],
            default_branch="inactive",
            default_next_node_id="node-b",
        )
        ctx = NodeContext(trigger_payload={}, variables={"status": "unknown"})
        result = node.execute(ctx)
        assert result.success is True
        assert result.metadata["branch_key"] == "inactive"
        assert result.next_node_id == "node-b"

    def test_invalid_expression_raises(self):
        with pytest.raises(ValidationException):
            ConditionNode(
                "cond-1",
                [{"expression": "$.[invalid", "branch_key": "bad", "next_node_id": "node-a"}],
            )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_nodes.py::TestTriggerNode tests/unit/test_nodes.py::TestConditionNode -v` → `5 passed`

---

## 6. 验收

- [ ] `ruff check src/workflow/nodes/trigger.py src/workflow/nodes/condition.py src/workflow/nodes/__init__.py` → `0 errors`
- [ ] `ruff check tests/unit/test_nodes.py` → `0 errors`
- [ ] `mypy src/workflow/nodes/trigger.py src/workflow/nodes/condition.py` → `0 errors`
- [ ] `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → `5 passed` (3 trigger + 2 condition cases; note that if #517 pre-populated existing test_nodes.py with base tests the total may be higher — accept any number ≥ 5 with zero failures)
- [ ] `grep -q "jsonpath-ng" pyproject.toml`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `NodeContext` fields in #517 differ from the names assumed here (`trigger_payload`, `variables`) | 低 | 高 — both nodes fail at runtime | Open immediate follow-up issue; revert the two node files and re-implement once #517 schema is confirmed |
| `jsonpath-ng` expression fails on valid-looking but non-matching JSONPath | 中 | 中 — condition always falls to default branch, silently wrong | Add a log statement at DEBUG level when no condition matches; add a test with a deliberately broken expression; raise `ValidationException` at `__init__` if expression is unparseable (already in design) |
| Engine's trigger registration API is not defined in #517, blocking integration | 低 | 中 — nodes are unit-testable but cannot be wired to engine | Implement nodes standalone; add `WorkflowEngine.register_trigger` stub with a comment `TBD — wire to engine after #517 engine API is confirmed` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/workflow/nodes/trigger.py \
       src/workflow/nodes/condition.py \
       src/workflow/nodes/__init__.py \
       tests/unit/test_nodes.py \
       pyproject.toml
git commit -m "feat(automation): implement TriggerNode and ConditionNode

- TriggerNode routes by event_type field in trigger_payload
- ConditionNode evaluates JSON-path expressions via jsonpath-ng
- 5 unit tests: 3 trigger, 2 condition
- Closes #518"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): implement trigger and condition node types" --body "Closes #518

## Summary
- Add TriggerNode (event-driven entry point, routing by event_type)
- Add ConditionNode (branching via JSON-path evaluation against ctx.variables)
- Add jsonpath-ng dependency for expression evaluation
- Add 5 unit tests (3 trigger + 2 condition)

## Test plan
- [ ] ruff check src/workflow/nodes/ → 0 errors
- [ ] mypy src/workflow/nodes/trigger.py src/workflow/nodes/condition.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_nodes.py -v → all passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行 (YYYY-MM-DD | 实现 Trigger 与 Condition 节点 | <your-name>)
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD — 待验证：`src/services/` 目录下现有 service 中是否有类似的 `execute` 分发模式可作参考（search for `def execute` across src/services/）
- 第三方文档：[jsonpath-ng PyPI](https://pypi.org/project/jsonpath-ng/) — JSONPath expression parsing and evaluation
- 父 issue：#73
- 前置依赖 issue：#517
- 后续依赖 issue：TBD — 待补充：#686 (action node), #687 (loop/subflow node)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
