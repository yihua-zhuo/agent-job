# Automation · 实现 action 和 approval 节点类型

| 元数据 | 值 |
|---|---|
| Issue | #519 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [#518 实现基础节点执行器骨架](../30-tickets/0518-implement-basic-node-execution-engine.md) |
| 启用后赋能 | [#520 实现条件路由节点并联触发](../50-automation/0520-implement-conditional-routing-and-parallel-triggering.md), [#68x 系列](/) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前工作流引擎已有基础节点骨架（#518），但缺少两种关键节点类型的实现：执行外部操作的 **action node** 和需要人工介入审批的 **approval node**。没有 action node，工作流无法真正执行业务操作（发邮件、调用 API、更新记录）；没有 approval node，无法实现「人肉审批」类审批流（CRM 中的线索分配审批、报价审批等）。这两个节点是自动化能力的基本拼板。

### 1.2 做完后

- **用户视角**：工作流设计器中可以拖入「执行动作」节点（指定服务方法）和「人工审批」节点（执行时进入 pending状态，等待审批接口触发）。无直接 UI 变化（UI 在后续板块）。
- **开发者视角**：`WorkflowEngine` 新增 `approve(execution_id, approver_id)` 方法；可注入任意 service 调用；可通过 `POST /workflows/executions/{id}/approve` 为 approval 节点提供审批回调。

### 1.3 不做什么（剔除）

- [ ] 工作流设计器 UI（在前端后续板块）
- [ ] 具体的邮件发送实现（由注入的 service 负责，本模块只调用已知接口）
- [ ]持久化审批历史记录表（本模块仅标记 pending，工程化放在后续板块）
- [ ] 审批超时自动拒绝逻辑

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` →至少8 passed（含4 新增用例）
- `ruff check src/workflow/nodes/` →0 errors
- `ruff check src/workflow/nodes/approval.py && ruff check src/workflow/nodes/action.py` →0 errors
- `PYTHONPATH=src pytest tests/unit/test_nodes.py::TestActionNode -v` →至少 4 passed
- `PYTHONPATH=src pytest tests/unit/test_nodes.py::TestApprovalNode -v` → 至少 4 passed

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/workflow/nodes/`目录及基础节点骨架（#518 成果）。建议先用 `ls src/workflow/nodes/` 确认现有文件结构，并查看是否有 `base.py` 或 `engine.py`。

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_nodes.py` — 新增 TestActionNode / TestApprovalNode 测试类
- 要建：
  - `src/workflow/nodes/action.py` — action node 实现  - `src/workflow/nodes/approval.py` — approval node 实现  - `src/workflow/engine.py` 或 `src/workflow/engine.py`（如 approval Engine 方法需要放此处）— 新增 `approve` 方法
  - `tests/unit/test_nodes.py` 中的新测试类（本板块不需要新建文件，仅扩展现有）

### 2.3 缺什么

- [ ] `action.py` Node 子类：根据 node config 中的 `action_name` 和 `params` 调用注入的 service 方法- [ ] `approval.py` Node 子类：执行时返回 `Pending`状态并持久化；提供 `resume()` 方法由 engine 在审批通过后触发
- [ ] `WorkflowEngine.approve(execution_id, approver_id)` 方法：调用 approval node 的 resume，完成执行链路
- [ ] `tests/unit/test_nodes.py` 对两种新 node 的全覆盖测试---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/workflow/nodes/action.py` | ActionNode：执行命名动作（service 调用）的节点类 |
| `src/workflow/nodes/approval.py` | ApprovalNode：人工审批门岗节点，执行时挂起等待审批回调 |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| `src/workflow/engine.py` | 新增 `approve(execution_id, approver_id: int, tenant_id: int)` 方法 |
| `src/api/routers/workflows.py` | 新增 `POST /workflows/executions/{id}/approve` 审批回调端点（调用 engine.approve） |
| `tests/unit/test_nodes.py` |扩展：新增 TestActionNode（含至少 4 个用例）和 TestApprovalNode（含至少 4 个用例） |

### 3.3 新增能力

- **Node class**：`ActionNode(BaseNode)` — 接收 `action_name: str`, `service_name: str`, `params: dict` 配置，执行注入的 service 方法- **Node class**：`ApprovalNode(BaseNode)` — 接收 `approvers: list[int]`，执行时将 execution标记为 pending，回调后触发后续节点
- **Engine method**：`WorkflowEngine.approve(execution_id: int, approver_id: int, tenant_id: int) -> bool` — 验证审批人权限，调用对应 approval node resume，执行后续节点链
- **API endpoint**：`POST /workflows/executions/{execution_id}/approve` — 请求体 `{"approver_id": int}`, 返回 `{"success": true, "data": {...}}`
- **Node execution status**：`PENDING` 状态（approval node 专用），engine 侧识别并等待---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **action node 用 config字典注入 service 而非硬编码接口**：灵活支持邮件/API/记录更新等多种动作；一个 node type 对应多种 action，避免为每种动作写独立 node class。
- **approval node 采用 engine.approve() 方法而非独立 endpoint 自行处理**：审批结果触发下游节点链需要 engine上下文，将此逻辑集中在 engine 避免跨模块耦合。
- **不新建 pending 表，直接复用 execution 表状态字段**：减少 schema复杂度；审批 pending状态作为 execution上下文的一部分，而非独立实体。

### 4.2 版本约束

本板块无新依赖引入。

### 4.3 兼容性约束

- 多租户：`approve()` 中查询 execution 记录时必须 `WHERE tenant_id = :tenant_id`
- Node 的 `execute()` 方法必须接收 `tenant_id: int` 参数并透传
- Node 不直接操作 session，通过 engine注入的 service 层进行持久化
- 已有的 node execute 接口（`execute(ctx: ExecutionContext) -> NodeResult`）保持不变，新 node 必须兼容此接口

### 4.4 已知坑

1. **ActionNode 调用未注册的 service 方法时 crash** → 规避：node config校验阶段（`validate_config`）检查 `service_name` 是否在注入的 registry 中，不存在则抛出 `ValidationException`
2. **ApprovalNode 审批通过后 parent_execution 被错误查询（缺 tenant_id 过滤）** → 规避：所有查询必须带 `WHERE tenant_id = :tenant_id`，并在 approve 方法入口处注入 tenant_id
3. **Alembic autogen 会把 JSONB 写成 JSON**（如后续 approval 节点状态存入 JSONB 列时）→ 规避：迁移文件中手动将 `sa.JSON()` 改回 `sa.JSONB()`，将 `DateTime`改回 `DateTime(timezone=True)`（时序合规用 TIMESTAMPTZ）

---

## 5. 实现步骤（按顺序）

### Step 1: 调研现有 engine 和 node 基类结构

确认 `#518` 的产物：读取 `src/workflow/engine.py`（或 `src/workflow/nodes/base.py`），了解 `BaseNode.execute()` 接口签名、`ExecutionContext` 内容、`WorkflowEngine.run()`循环结构。

操作：
- a) `grep -r "class BaseNode\|class ExecutionContext\|class WorkflowEngine" src/workflow/` 查询现有 class 定义
- b) 确认 `tests/unit/test_nodes.py` 现有测试结构（`TestActionNode` 是否已存在）

**完成判定**：`ls src/workflow/nodes/` 输出已知文件列表 / `grep "def execute" src/workflow/nodes/base.py` 有结果

### Step 2: 实现 ActionNode

在 `src/workflow/nodes/action.py` 新建 `ActionNode(BaseNode)` 类：

操作：
- a) 定义 `class ActionNode(BaseNode):`
- b) `config_schema`包含 `action_name: str`, `service_name: str`, `params: dict`
- c) `validate_config()`校验 service 在 registry 中存在- d) `execute(ctx)` 调用 `ctx.services[service_name](**params)` 并返回 `NodeResult(status="completed", output={...})`
- e) 执行出错返回 `NodeResult(status="failed", error="...")`

示例代码：

```python
from typing import Any
from .base import BaseNode, ExecutionContext, NodeResult

class ActionNode(BaseNode):
    config_schema = {"action_name": str, "service_name": str, "params": dict}

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        cfg = self.config
        service_name: str = cfg["service_name"]
        if service_name not in ctx.services:
            return NodeResult(status="failed", error=f"Service '{service_name}' not found")
        action_fn = ctx.services[service_name]
        try:
            result = await action_fn(**cfg.get("params", {}))
            return NodeResult(status="completed", output={"result": result})
        except Exception as e:
            return NodeResult(status="failed", error=str(e))
```

**完成判定**：`ruff check src/workflow/nodes/action.py` exit 0

### Step 3: 实现 ApprovalNode

在 `src/workflow/nodes/approval.py` 新建 `ApprovalNode(BaseNode)`：

操作：
- a) 定义 `class ApprovalNode(BaseNode):`
- b) `config_schema` 包含 `approvers: list[int]`（允许审批的用户 ID 列表）
- c) `execute(ctx)` 将 execution标记为 `PENDING` 状态，写入 `execution.context["approval_pending"] = True`
- d) 返回 `NodeResult(status="pending", output={...})` — engine收到 pending 即暂停- e) 新增 `resume(ctx, approved: bool, comment: str | None)` 方法：审批通过则 forward 执行后续节点；拒绝则直接结束示例代码：

```python
from typing import Literal, Optional
from .base import BaseNode, ExecutionContext, NodeResult

class ApprovalNode(BaseNode):
    config_schema = {"approvers": list}

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        if not self.can_approve(ctx.current_user_id):
            return NodeResult(status="failed", error="User not in approvers list")
        ctx.execution.context["approval_pending"] = True
        ctx.execution.context["pending_node_id"] = self.node_id
        await ctx.persist_execution()
        return NodeResult(status="pending", output={"message": "Awaiting approval"})

    async def resume(self, ctx: ExecutionContext, approved: bool, comment: Optional[str] = None) -> NodeResult:
        if approved:
            return NodeResult(status="forward", output={"comment": comment})
        return NodeResult(status="completed", output={"comment": comment, "approved": False})

    def can_approve(self, user_id: int) -> bool:
        return user_id in self.config.get("approvers", [])
```

**完成判定**：`ruff check src/workflow/nodes/approval.py` exit 0

### Step 4: 在 WorkflowEngine 新增 approve 方法

操作：
- a) 在 `src/workflow/engine.py` 找到或新增 `approve(execution_id: int, approver_id: int, tenant_id: int)` 方法
- b) 用 `execution_id`加载对应 execution，检查 `execution.context["approval_pending"] == True`
- c) 验证 `approver_id` 在该 approval node 的 `approvers` 列表中（通过 `execution.context["pending_node_type"]` 推断或直接读 node graph）
- d) 调用 approval_node.resume(ctx, approved=True)
- e) 继续执行后续节点链（复用 `run()`循环逻辑）

```python
async def approve(self, execution_id: int, approver_id: int, tenant_id: int) -> dict:
    execution = await self._load_execution(execution_id, tenant_id)
    if not execution.context.get("approval_pending"):
        raise ValidationException("Execution is not pending approval")
    pending_node_id = execution.context.get("pending_node_id")
    node = self._get_node(pending_node_id)
    if not node.can_approve(approver_id):
        raise ForbiddenException("User is not authorized to approve")
    ctx = self._build_context(execution)
    result = await node.resume(ctx, approved=True)
    await self._continue_execution(ctx)
    return {"execution_id": execution_id, "status": "approved"}
```

**完成判定**：`ruff check src/workflow/engine.py` exit 0

### Step 5: 新增审批回调 API端点

操作：
- a) 在 `src/api/routers/workflows.py` 新增 `POST /workflows/executions/{execution_id}/approve`
- b) 由 `require_auth` 注入 `ctx: AuthContext`
- c) 调用 `WorkflowEngine(session).approve(execution_id, ctx.user_id, ctx.tenant_id)`
- d) 返回 `{"success": True, "data": result}`

```python
@router.post("/executions/{execution_id}/approve")
async def approve_execution(
    execution_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    engine = WorkflowEngine(session)
    result = await engine.approve(execution_id, ctx.user_id, ctx.tenant_id)
    return {"success": True, "data": result}
```

**完成判定**：`ruff check src/api/routers/workflows.py` exit 0

### Step 6: 补充单元测试

操作：
- a) 在 `tests/unit/test_nodes.py` 新增 `TestActionNode` 类（新文件不存在则新建）：

```python
class TestActionNode:
    @pytest.fixture
    def mock_services(self):
        async def dummy_service(**kwargs):
            return {"sent": True}
        return {"email_service": dummy_service}

    @pytest.fixture
    def action_node(self, mock_services):
        cfg = {"action_name": "send", "service_name": "email_service", "params": {"to": "test@example.com"}}
        return ActionNode(node_id="n1", config=cfg, services=mock_services)

    async def test_action_node_completes(self, action_node, mock_ctx):
        result = await action_node.execute(mock_ctx)
        assert result.status == "completed"

    async def test_action_node_unknown_service(self, mock_services, mock_ctx):
        node = ActionNode(node_id="n1", config={"service_name": "nonexistent"})
        result = await node.execute(mock_ctx)
        assert result.status == "failed"

    async def test_action_node_raises_on_empty_service_name(self, mock_ctx):
        with pytest.raises(Exception):
            ActionNode(node_id="n1", config={"service_name": ""})
```

- b) 新增 `TestApprovalNode` 类：

```python
class TestApprovalNode:
    @pytest.fixture
    def approval_node(self):
        cfg = {"approvers": [1, 2]}
        return ApprovalNode(node_id="n2", config=cfg)

    async def test_approval_node_sets_pending(self, approval_node, mock_ctx):
        result = await approval_node.execute(mock_ctx)
        assert result.status == "pending"

    async def test_approval_node_invalid_approver(self, approval_node, mock_ctx):
        mock_ctx.current_user_id = 99
        result = await approval_node.execute(mock_ctx)
        assert result.status == "failed"

    async def test_approval_node_resume_approved(self, approval_node, mock_ctx):
        result = await approval_node.resume(mock_ctx, approved=True)
        assert result.status == "forward"

    async def test_approval_node_resume_rejected(self, approval_node, mock_ctx):
        result = await approval_node.resume(mock_ctx, approved=False)
        assert result.status == "completed"
```

- c) 补全 `mock_ctx` fixture（已在 conftest.py 中则跳过；参考现有 node 测试的 fixture）

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → ≥ 8 passed（含新增用例）

---

## 6. 验收

- `ruff check src/workflow/nodes/action.py` →0 errors
- `ruff check src/workflow/nodes/approval.py` → 0 errors
- `ruff check src/workflow/engine.py` → 0 errors
- `ruff check src/api/routers/workflows.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_nodes.py::TestActionNode -v` → 至少4 passed
- `PYTHONPATH=src pytest tests/unit/test_nodes.py::TestApprovalNode -v` → 至少 4 passed
- `PYTHONPATH=src pytest tests/unit/test_nodes.py -v` → 所有用例 passed---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ApprovalNode 的 pending状态被 engine 意外 forward（engine原有循环不识别 pending） | 中 | 高 | 在 engine.run() 有条件分支处理 pending node result；回退本板块合并前 engine 不感知 pending |
| action node注入的 service 签名不统一导致运行时错误 | 中 | 中 | validate_config 在 node 加载时校验，不在执行时 crash；如运行时仍失败则记录 error状态而非抛异常 |
| approver 权限校验逻辑与全系统 auth 体系耦合松散 | 低 | 中 | engine.approve() 复用 `require_auth` 注入的 `ctx.user_id`，在 Service 层做校验，不引入独立权限系统 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/workflow/nodes/action.py src/workflow/nodes/approval.py src/workflow/engine.py src/api/routers/workflows.py tests/unit/test_nodes.py
git commit -m "feat(automation): implement ActionNode and ApprovalNode workflow node types, add engine.approve method"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "#519 Implement action and approval node types" --body "Implements ActionNode (service calls via injected services) and ApprovalNode (human-approval gate with pending/resume). Adds WorkflowEngine.approve() and POST /workflows/executions/{id}/approve endpoint. Closes #519."

#2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#73（工作流引擎总体规划）
- 前置依赖：#518（基础节点执行器骨架）
- 同类参考实现：TBD - 待验证：`src/workflow/nodes/`目录下 #518 产物（如有 `condition.py` 或 `base.py` 可参考 node 接口模式）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
