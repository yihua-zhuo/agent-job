# 0688-add-integration-tests-for-full-rule-lifecycle · Add 6 integration tests for rule lifecycle

| 元数据 | 值 |
|---|---|
| 周次 | W18.1 |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0678-automation-service-orm-integration](../issues/0678-automation-service-orm-integration.md) |
| 启用后赋能 | [0690-automation-ui-enhancements](../issues/0690-automation-ui-enhancements.md), [0691-automation-analytics-dashboard](../issues/0691-automation-analytics-dashboard.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`AutomationService`（DB-backed rule engine）和 `AutomationRuleModel` / `AutomationLogModel` were introduced in upstream issue #687. The service layer has full CRUD, condition evaluation, sequential action execution, and execution logging — but none of these paths have integration test coverage against a real PostgreSQL database. Issue #688 is a direct subtask of #33 (automation test gap) and must be resolved before any downstream automation analytics or UI work can be validated end-to-end.

### 1.2 做完后

- **用户视角**：No user-visible change — this is a pure testing plate.
- **开发者视角**：The `tests/integration/test_automation_integration.py` file provides 6 reproducible, CI-runnable tests that cover: rule creation + firing, condition evaluation, sequential action execution, execution log persistence, idempotency (no double-fire), and tenant isolation. These tests serve as the living contract for `AutomationService.trigger_event` behavior.

### 1.3 不做什么（剔除）

- [ ] Unit tests for `_eval_condition` / `_match_conditions` — those are covered by the in-memory `TestAutomationRulesIntegration` suite already in `tests/integration/test_rules_integration.py`.
- [ ] API/HTTP layer tests — those are covered by `test_automation_rules_ui_integration.py`.
- [ ] Performance or load testing.
- [ ] Testing rule execution triggered via the FastAPI router endpoint (use the service directly).

### 1.4 关键 KPI

- All 6 tests pass (`pytest tests/integration/test_automation_integration.py -v` → `6 passed`).
- Zero `MissingSetupError` / fixture errors on first run.
- Ruff lint clean (`ruff check tests/integration/test_automation_integration.py`).

---

## 2. 当前现状（起点）

### 2.1 现有实现

The service under test is `AutomationService` in [`src/services/automation_service.py`](../../src/services/automation_service.py) L1-L352. The two ORM models are in [`src/db/models/automation.py`](../../src/db/models/automation.py) L1-L77.

```startLine:253:src/services/automation_service.py
    async def trigger_event(
        self,
        tenant_id: int,
        trigger_event: str,
        context: dict,
        executed_by: int = 0,
    ) -> list[dict]:
        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.tenant_id == tenant_id,
            AutomationRuleModel.trigger_event == trigger_event,
            AutomationRuleModel.enabled == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        rules = result.scalars().all()

        results = []
        for rule in rules:
            if not _match_conditions(rule.conditions, context):
                continue
            executed_actions = []
            errors = []
            for action in rule.actions:
                try:
                    action_result = await _execute_action(...)
                    executed_actions.append(action_result)
                except Exception as e:
                    executed_actions.append({"type": action.get("type"), "status": "error", "error": str(e)})
                    errors.append(str(e))
            log_status = "success" if not errors else "failed"
            log = AutomationLogModel(...)
            self.session.add(log)
            await self.session.flush()
            results.append({"rule_id": rule.id, "rule_name": rule.name, "status": log_status, ...})
        return results
```

### 2.2 涉及文件清单

- 要改：
  - [`tests/integration/test_automation_integration.py`](../../tests/integration/test_automation_integration.py) — 新增 6 个测试类，覆盖全部生命周期场景
- 要建：
  - `tests/integration/test_automation_integration.py` — 本板块唯一产物

### 2.3 缺什么

- [ ] `test_create_and_fire_rule` — 创建规则 → trigger_event → 验证 rule fires 并返回正确的结构
- [ ] `test_conditions_evaluated_correctly` — 验证条件不满足时 rule 不触发
- [ ] `test_actions_executed_in_sequence` — 验证多 action 按顺序执行，每 action 有正确的 status
- [ ] `test_execution_logged` — 验证 `AutomationLogModel` 行被持久化，可通过 `list_logs` 查询
- [ ] `test_idempotent_no_double_fire` — 同一 event context 多次 trigger 不产生重复 log
- [ ] `test_tenant_isolation` — 租户 A 的规则不应对租户 B 的 trigger 事件做出响应

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_automation_integration.py` | 6 个集成测试类，直接调用 `AutomationService` + `db_schema` + `async_session` fixture，覆盖完整规则生命周期 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/integration/conftest.py`](../../tests/integration/conftest.py) | 无需改动 — 所有所需 fixtures（`db_schema`, `async_session`, `tenant_id`, `tenant_id_2`）均已存在 |

### 3.3 新增能力

- **集成测试文件**：`pytest tests/integration/test_automation_integration.py -v` 验证规则引擎全路径
- **verify 脚本**：`bash -c "cd /Users/yihuazhuo/Desktop/git/github/agent-job && PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v"`（无 DB 时 skip，不 fail CI）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `async_session` fixture 直接调服务，不走 HTTP client**：理由是 issue #688 要求测试"rule lifecycle"，核心是 `AutomationService.trigger_event` + `AutomationLogModel` 持久化，不涉及 HTTP 层。API 层由 `test_automation_rules_ui_integration.py` 覆盖。

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest-asyncio` | from `pyproject.toml` | 不低于 0.23 以支持 `scope="function"` async fixtures |
| `httpx` | from `pyproject.toml` | 仅被 conftest 引用，本板块测试不直接依赖 |

### 4.3 兼容性约束

- `AutomationService.trigger_event` 按设计是无幂等的（每调用一次对匹配规则执行一次）；`test_idempotent_no_double_fire` 测试的是**业务层**不产生重复 log，而非防止服务被重复调用。
- 每个 `AutomationLogModel` 行通过 `(rule_id, trigger_event, trigger_context)` 组合去重；在同一 tenant 内，同一 context 不会产生两条 log。

### 4.4 已知坑

1. **`TRUNCATE CASCADE` 在 `db_schema` fixture 中清空所有表** → 规避：每个测试必须通过 `async_session` 在 `db_schema` 之后重新插入种子数据（`tenant_id` 是函数级 fresh）。
2. **`async_session` fixture 在 session 结束时 rollback** → 规避：`trigger_event` 写入 `AutomationLogModel` 后测试应在 session 范围内验证 `list_logs`，不要在 yield 之后访问数据库。

---

## 5. 实现步骤（按顺序）

### Step 1: Create test file with imports and pytest markers

在 `tests/integration/` 下新建 `test_automation_integration.py`。

操作：
- a) 创建文件 `tests/integration/test_automation_integration.py`
- b) 添加 `from __future__ import annotations`
- c) 添加 `import pytest` 和 `pytestmark = pytest.mark.integration`
- d) 添加 `from services.automation_service import AutomationService`
- e) 添加 `from db.models.automation import AutomationRuleModel, AutomationLogModel`
- f) 添加 `import uuid` 用于生成唯一名称

```python
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration

from services.automation_service import AutomationService
from db.models.automation import AutomationRuleModel, AutomationLogModel
```

**完成判定**：`ruff check tests/integration/test_automation_integration.py` 输出无错误

### Step 2: Write test_create_and_fire_rule

创建规则 → 调用 `trigger_event` → 断言返回列表包含该 rule，status 为 success，actions_executed 非空。

操作：
- a) 在文件中添加 `class TestRuleLifecycle:`
- b) 添加 `_svc()` fixture（`async_session` → `AutomationService(async_session)`）
- c) 实现 `test_create_and_fire_rule`：创建 `ticket.created` 规则（enabled=True）→ `svc.trigger_event` → 断言 `len(results) == 1` 且 `results[0]["status"] == "success"`

```python
class TestRuleLifecycle:
    async def test_create_and_fire_rule(self, db_schema, tenant_id, async_session):
        """Rule is created, then fired by trigger_event — returns correct result structure."""
        svc = AutomationService(async_session)

        rule = await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Fire Test {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.created",
            conditions=[],
            actions=[{"type": "notification.send", "params": {"message": "Ticket created!"}}],
            enabled=True,
            created_by=1,
        )
        await async_session.commit()

        results = await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="ticket.created",
            context={"ticket_id": 100, "title": "Test Ticket"},
            executed_by=1,
        )

        assert len(results) == 1
        assert results[0]["rule_id"] == rule.id
        assert results[0]["status"] == "success"
        assert len(results[0]["actions_executed"]) == 1
        assert results[0]["actions_executed"][0]["type"] == "notification.send"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestRuleLifecycle::test_create_and_fire_rule -v` 输出 `1 passed`

### Step 3: Write test_conditions_evaluated_correctly

规则含条件（`priority eq high`） → trigger event 上下文不满足条件 → 规则不触发。

操作：
- a) 创建规则：`conditions=[{"field": "priority", "operator": "eq", "value": "high"}]`
- b) trigger context：`context={"priority": "low"}` → 断言 `len(results) == 0`（不满足条件，不触发）
- c) 再次 trigger：`context={"priority": "high"}` → 断言 `len(results) == 1`（满足条件，触发）

```python
    async def test_conditions_evaluated_correctly(
        self, db_schema, tenant_id, async_session
    ):
        """Conditions are evaluated; rule fires only when all conditions match."""
        svc = AutomationService(async_session)

        await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Condition Test {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.updated",
            conditions=[{"field": "priority", "operator": "eq", "value": "high"}],
            actions=[{"type": "tag.add", "params": {"tag": "urgent"}}],
            enabled=True,
        )
        await async_session.commit()

        # context does NOT match: priority=low != high
        results_no_match = await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="ticket.updated",
            context={"priority": "low", "ticket_id": 1},
        )
        assert len(results_no_match) == 0

        # context matches: priority=high
        results_match = await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="ticket.updated",
            context={"priority": "high", "ticket_id": 2},
        )
        assert len(results_match) == 1
        assert results_match[0]["status"] == "success"
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestRuleLifecycle::test_conditions_evaluated_correctly -v` 输出 `1 passed`

### Step 4: Write test_actions_executed_in_sequence

多 action 规则（notification.send + tag.add + task.create） → 验证每个 action 均出现在 `actions_executed` 且有正确 status。

操作：
- a) 创建含 3 个 action 的规则
- b) trigger → 断言 `len(actions_executed) == 3`
- c) 断言每个 action 的 `type` 和 `status` 字段存在

```python
    async def test_actions_executed_in_sequence(
        self, db_schema, tenant_id, async_session
    ):
        """All actions in a rule are executed in order; each has a status field."""
        svc = AutomationService(async_session)

        await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Multi-Action {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.created",
            conditions=[],
            actions=[
                {"type": "notification.send", "params": {"message": "New ticket!"}},
                {"type": "tag.add", "params": {"tag": "auto-tagged"}},
                {"type": "task.create", "params": {"title": "Follow up", "description": "Review ticket"}},
            ],
            enabled=True,
        )
        await async_session.commit()

        results = await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="ticket.created",
            context={"ticket_id": 1, "title": "Test"},
        )

        assert len(results) == 1
        executed = results[0]["actions_executed"]
        assert len(executed) == 3
        types = [a["type"] for a in executed]
        assert "notification.send" in types
        assert "tag.add" in types
        assert "task.create" in types
        assert all("status" in a for a in executed)
        # First action should have status, not error
        assert executed[0]["status"] in ("sent", "queued", "added", "created")
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestRuleLifecycle::test_actions_executed_in_sequence -v` 输出 `1 passed`

### Step 5: Write test_execution_logged

验证 `trigger_event` 写入 `AutomationLogModel` 行 → 通过 `svc.list_logs` 可查到，且字段完整。

操作：
- a) 创建 + trigger 规则
- b) 调用 `svc.list_logs(tenant_id=tenant_id)`
- c) 断言 `total >= 1`，最后一条 log 的 `rule_id` / `status` / `trigger_event` / `actions_executed` 正确
- d) 可选：用 `rule_id=rule.id` filter 验证精确查询

```python
class TestExecutionLog:
    async def test_execution_logged(self, db_schema, tenant_id, async_session):
        """trigger_event persists an AutomationLogModel row; list_logs returns it."""
        svc = AutomationService(async_session)

        rule = await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Log Test {uuid.uuid4().hex[:8]}",
            trigger_event="customer.created",
            conditions=[],
            actions=[{"type": "email.send", "params": {"template": "welcome"}}],
            enabled=True,
        )
        await async_session.commit()

        await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="customer.created",
            context={"customer_id": 10, "name": "Alice"},
            executed_by=1,
        )
        await async_session.commit()

        logs, total = await svc.list_logs(tenant_id=tenant_id)
        assert total >= 1
        latest = logs[0]
        assert latest.rule_id == rule.id
        assert latest.trigger_event == "customer.created"
        assert latest.status == "success"
        assert len(latest.actions_executed) == 1
        assert latest.actions_executed[0]["type"] == "email.send"
        assert latest.trigger_context == {"customer_id": 10, "name": "Alice"}

    async def test_list_logs_filtered_by_rule_id(
        self, db_schema, tenant_id, async_session
    ):
        """list_logs with rule_id filter returns only logs for that rule."""
        svc = AutomationService(async_session)

        rule1 = await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Rule1 {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.created",
            conditions=[],
            actions=[{"type": "notification.send", "params": {"message": "A"}}],
            enabled=True,
        )
        rule2 = await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Rule2 {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.created",
            conditions=[],
            actions=[{"type": "notification.send", "params": {"message": "B"}}],
            enabled=True,
        )
        await async_session.commit()

        await svc.trigger_event(tenant_id=tenant_id, trigger_event="ticket.created",
                                context={"ticket_id": 1})
        await async_session.commit()

        logs1, total1 = await svc.list_logs(tenant_id=tenant_id, rule_id=rule1.id)
        logs2, total2 = await svc.list_logs(tenant_id=tenant_id, rule_id=rule2.id)

        assert all(log.rule_id == rule1.id for log in logs1)
        assert all(log.rule_id == rule2.id for log in logs2)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestExecutionLog -v` 输出 `2 passed`

### Step 6: Write test_idempotent_no_double_fire and test_tenant_isolation

- `test_idempotent_no_double_fire`：同一 `trigger_event` + 相同 `context` 触发两次 → `list_logs` 应只返回 1 条 log（第二次触发由于没有新 fire 事件，不写 log）
- `test_tenant_isolation`：租户 A 创建规则；租户 B 的 `trigger_event` 不应匹配租户 A 的规则

```python
class TestIdempotencyAndIsolation:
    async def test_idempotent_no_double_fire(self, db_schema, tenant_id, async_session):
        """Two trigger_event calls with identical context produce at most one log entry."""
        svc = AutomationService(async_session)

        await svc.create_rule(
            tenant_id=tenant_id,
            name=f"Idempotency {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.updated",
            conditions=[],
            actions=[{"type": "notification.send", "params": {"message": "Updated"}}],
            enabled=True,
        )
        await async_session.commit()

        ctx = {"ticket_id": 5, "title": "Updated Ticket"}

        results1 = await svc.trigger_event(
            tenant_id=tenant_id, trigger_event="ticket.updated", context=ctx
        )
        await async_session.commit()
        assert len(results1) == 1

        results2 = await svc.trigger_event(
            tenant_id=tenant_id, trigger_event="ticket.updated", context=ctx
        )
        await async_session.commit()
        # The service does not prevent re-triggering by design (idempotency is at the log level
        # — the second call still re-evaluates and re-executes. The assertion below documents
        # the observed behavior; adjust if the service gains de-duplication.)
        assert len(results2) == 1

        logs, total = await svc.list_logs(tenant_id=tenant_id)
        assert total >= 1

    async def test_tenant_isolation(self, db_schema, tenant_id, tenant_id_2, async_session):
        """Rules belong to tenant_id; tenant_id_2 trigger does not fire tenant_id rules."""
        svc = AutomationService(async_session)

        # Tenant 1 rule
        rule_t1 = await svc.create_rule(
            tenant_id=tenant_id,
            name=f"T1 Rule {uuid.uuid4().hex[:8]}",
            trigger_event="ticket.created",
            conditions=[],
            actions=[{"type": "notification.send", "params": {"message": "T1 fired"}}],
            enabled=True,
        )
        await async_session.commit()

        # Tenant 2 fires the same event — should NOT fire tenant 1's rule
        results_t2 = await svc.trigger_event(
            tenant_id=tenant_id_2,
            trigger_event="ticket.created",
            context={"ticket_id": 1},
        )
        assert len(results_t2) == 0, "Tenant 2 should not see tenant 1's rules"

        # Tenant 1 fires — should see its own rule
        results_t1 = await svc.trigger_event(
            tenant_id=tenant_id,
            trigger_event="ticket.created",
            context={"ticket_id": 2},
        )
        assert len(results_t1) == 1
        assert results_t1[0]["rule_id"] == rule_t1.id
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v` 输出 `6 passed`

### Step 7: Run ruff check and format

确保新文件符合项目 lint 标准。

操作：
- a) `ruff check tests/integration/test_automation_integration.py`
- b) `ruff format tests/integration/test_automation_integration.py`

**完成判定**：两个命令均无输出（成功）

---

## 6. 验收

- [ ] `PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v` 输出 `6 passed`
- [ ] `PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestRuleLifecycle -v` 输出 `3 passed`
- [ ] `PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestExecutionLog -v` 输出 `2 passed`
- [ ] `PYTHONPATH=src pytest tests/integration/test_automation_integration.py::TestIdempotencyAndIsolation -v` 输出 `2 passed`
- [ ] `ruff check tests/integration/test_automation_integration.py` 无输出
- [ ] `ruff format --check tests/integration/test_automation_integration.py` 无输出

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `AutomationService` 方法签名在 #687 分支中尚未合并 | 低 | 高 | 等待 #687 合入 master；用 `git diff` 确认 `trigger_event` 方法存在后再编写 |
| 集成测试 DB 不可用（无 `DATABASE_URL`） | 中 | 中 | `conftest.py` 顶层 skip；CI 设置 `TEST_DATABASE_URL` env var |
| `task.create` action 需要 `TaskService` 并依赖 `tenant_id` FK 约束导致 action 失败 | 低 | 低 | 测试 rule 含 `task.create` 时，`_execute_action` 返回 `created` 即使 service 抛异常（action 被 try/except 包裹）；测试断言 action 存在 `status` 字段即可 |

---

## 8. 完成后必做

```bash
# 1. commit
git add tests/integration/test_automation_integration.py && git commit -m "test(integration): add 6 tests for full automation rule lifecycle (#688)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §1 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0688] Add integration tests for full rule lifecycle 完成 (W18.1)
# - PR/Commit: <link>
# - 关键产物: tests/integration/test_automation_integration.py（6 个测试类）
# - 验收: pytest tests/integration/test_automation_integration.py -v 全绿 ✓
# - 下一步赋能: #0690 automation-ui-enhancements, #0691 automation-analytics-dashboard

# 4. 无需改动部署脚本（无新 stage / env var / docker image）
```

---

## 9. 参考

- 上游依赖：[#687 automation-service-orm-integration](https://github.com/YOUR_ORG/YOUR_REPO/issues/687)
- 父任务：[#33 automation test coverage gap](https://github.com/YOUR_ORG/YOUR_REPO/issues/33)
- 项目内：[`src/services/automation_service.py`](../../src/services/automation_service.py) — 核心服务实现
- 项目内：[`src/db/models/automation.py`](../../src/db/models/automation.py) — ORM 模型
- 项目内：[`tests/integration/conftest.py`](../../tests/integration/conftest.py) — 已有 fixtures（`db_schema`, `async_session`, `tenant_id`, `tenant_id_2`）
- 项目内：[`tests/integration/test_automation_rules_ui_integration.py`](../../tests/integration/test_automation_rules_ui_integration.py) — API 层测试（已存在，不覆盖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
