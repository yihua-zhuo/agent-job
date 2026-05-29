# 0687-build-rule-execution-engine-and-trigger-dispatch · Rule engine + event dispatch

| 元数据 | 值 |
|---|---|
| 周次 | W14.1 |
| 优先级 | 必做 |
| 工作量 | 3 工作日 |
| 依赖 | [0686-automation-orm-integration](../issues/0686-automation-orm-integration.md) |
| 启用后赋能 | [0688-add-integration-tests-for-full-rule-lifecycle](../issues/0688-add-integration-tests-for-full-rule-lifecycle.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM system currently has no unified rule execution engine that can be hooked into domain event emission points. Issue #686 wired `AutomationRuleModel` + `AutomationLogModel` into the ORM layer, but no engine exists to: (a) match events to registered trigger handlers, (b) evaluate AND/OR conditions against event data, (c) execute actions sequentially and log each run, or (d) ensure execution is idempotent per (trigger + entity_id + rule_id).

Issue #687 is a subtask of #33 and is the direct prerequisite for #688 (integration tests) and all downstream automation UI/analytics work.

### 1.2 做完后

- **用户视角**：Automation rules fire automatically when tickets, opportunities, or customers are created/updated. The system sends notifications, creates tasks, or updates fields with no manual intervention.
- **开发者视角**：A new `RuleEngine` class in `rule_engine.py` provides a trigger registry (`register_handler`) + two public entry points (`evaluate_conditions` and `execute_rule`). Domain services (`TicketService`, `OpportunityService`, `CustomerService`) call `RuleEngine.dispatch` at defined emission points. Unit tests in `test_rule_engine.py` cover condition evaluation (AND/OR), sequential action execution, and event deduplication.

### 1.3 不做什么（剔除）

- [ ] No action execution backends (webhooks, email queues) beyond the stub delegates already in `AutomationService._execute_action`.
- [ ] No UI/API router for managing rules — that's covered by separate plates (automation rules router).
- [ ] No polling-based trigger evaluation — only event-driven via in-process dispatch.

### 1.4 关键 KPI

- `RuleEngine.evaluate_conditions` returns correct truth values for all 8 operators across AND/OR/NONE condition sets.
- `RuleEngine.execute_rule` returns a result dict with `rule_id`, `status`, `actions_executed`, and `log_id` for every enabled matching rule.
- Idempotency: calling `dispatch` twice with the same `(trigger_event, entity_id, rule_id)` produces exactly one `AutomationLogModel` row.
- `PYTHONPATH=src pytest tests/unit/test_rule_engine.py -v` → `N passed` (≥20 test cases).
- `ruff check src/services/rule_engine.py tests/unit/test_rule_engine.py` → clean (zero warnings/errors).

---

## 2. 当前现状（起点）

### 2.1 现有实现

No `rule_engine.py` exists. The closest code is in [`src/services/automation_service.py`](../../src/services/automation_service.py) L37-L70, where `_eval_condition` and `_match_conditions` are module-level helpers already implementing AND logic and all 8 operators. The `trigger_event` method at L253-L320 queries `AutomationRuleModel` by `trigger_event`, evaluates conditions, executes actions, and persists `AutomationLogModel` — but it is tightly coupled inside `AutomationService`.

```startLine:37:src/services/automation_service.py
def _eval_condition(condition: dict, context: dict) -> bool:
    field = condition.get("field")
    operator = condition.get("operator")
    expected = condition.get("value")
    actual = context.get(field)
    if actual is None:
        return False
    op_map = {
        "eq": lambda a, e: a == e,
        "ne": lambda a, e: a != e,
        "gt": lambda a, e: float(a) > float(e),
        "gte": lambda a, e: float(a) >= float(e),
        "lt": lambda a, e: float(a) < float(e),
        "lte": lambda a, e: float(a) <= float(e),
        "contains": lambda a, e: str(e) in str(a),
        "startswith": lambda a, e: str(a).startswith(str(e)),
        "endswith": lambda a, e: str(a).endswith(str(e)),
    }
    fn = op_map.get(operator)
    if fn is None:
        return False
    try:
        return fn(actual, expected)
    except (ValueError, TypeError):
        return False

def _match_conditions(conditions: list, context: dict) -> bool:
    if not conditions:
        return True
    return all(_eval_condition(c, context) for c in conditions)
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/ticket_service.py`](../../src/services/ticket_service.py) — 在 `create_ticket` 和 `update_ticket` 结尾添加 `RuleEngine.dispatch` 调用
  - [`src/services/opportunity_service.py`](../../src/services/opportunity_service.py) — 在关键状态变更处添加 `RuleEngine.dispatch` 调用
  - [`src/services/customer_service.py`](../../src/services/customer_service.py) — 在 `create_customer` / `update_customer` 添加 `RuleEngine.dispatch`
  - [`tests/unit/conftest.py`](../../tests/unit/conftest.py) — 新增 `make_automation_handler` 工厂供测试使用
- 要建：
  - `src/services/rule_engine.py` —核心引擎模块（RuleEngine 类 + evaluate_conditions + execute_rule）
  - `tests/unit/test_rule_engine.py` —规则引擎单元测试### 2.3 缺什么

- [ ] No module-level `RuleEngine` class with a trigger-name → handler registry.
- [ ] `evaluate_conditions` function does not exist as a public top-level export; AND/OR logic is hidden inside `AutomationService._match_conditions`.
- [ ] Idempotency is not enforced: repeated `dispatch` calls with the same entity and rule produce duplicate `AutomationLogModel` rows.
- [ ] Domain services (`TicketService`, `OpportunityService`, `CustomerService`) do not emit automation trigger events at creation/update points.
- [ ] No unit tests for `_eval_condition` / `_match_conditions` in a dedicated `test_rule_engine.py`.
- [ ] `AutomationService` is the only caller of `_execute_action`; other services cannot trigger rules independently.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/rule_engine.py` | `RuleEngine` 类：trigger registry、`evaluate_conditions`（AND/OR）、`execute_rule`（顺序执行 action）、`dispatch`（带幂等 dedup key）、`register_handler` API |
| `tests/unit/test_rule_engine.py` | ≥20 个单元测试：条件求值（8 operator × 3 logic modes）、action顺序执行、幂等性、边界 case |
| `docs/dev-plan/issues/0687_verify.sh` |验收脚本：单行 ruff check + pytest 调用，CI 友好 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/ticket_service.py`](../../src/services/ticket_service.py) | `create_ticket` 末尾调用 `RuleEngine.dispatch(..., "ticket.created", context)`；`update_ticket` 末尾调用 `RuleEngine.dispatch(..., "ticket.event_updated", context)` |
| [`src/services/opportunity_service.py`](../../src/services/opportunity_service.py) | stage变更时调用 `RuleEngine.dispatch(..., "opportunity.stage_changed", context)` |
| [`src/services/customer_service.py`](../../src/services/customer_service.py) | 创建/更新后调用 `RuleEngine.dispatch(..., "customer.created" / "customer.event_updated", context)` |
| [`tests/unit/conftest.py`](../../tests/unit/conftest.py) | 新增 `make_automation_handler(state)` 工厂，`make_mock_session` 列表中可用 |
| [`src/services/automation_service.py`](../../src/services/automation_service.py) | `TRIGGER_EVENTS`/`ACTION_TYPES` 常量提升为模块级，已被 `rule_engine.py` 引用 |

### 3.3 新增能力

- **引擎类**：`RuleEngine(session: AsyncSession)` — 由 `AutomationService` 提供 session- **Public API**：`RuleEngine.evaluate_conditions(conditions: list, event_data: dict, logic: str = "AND") -> bool`
- **Public API**：`RuleEngine.execute_rule(rule: AutomationRuleModel, event_data: dict, executed_by: int) -> dict`
- **Public API**：`RuleEngine.dispatch(tenant_id: int, trigger_event: str, event_data: dict, executed_by: int) -> list[dict]`
- **Public API**：`RuleEngine.register_handler(trigger_event: str, handler: Callable) -> None` — 用于测试注入- **幂等 key**：`f"{trigger_event}:{event_data.get('entity_id')}:{rule_id}"` 存入 `AutomationLogModel.trigger_event`+`AutomationLogModel.trigger_context` dedup 列
- **verify 脚本**：`bash docs/dev-plan/issues/0687_verify.sh`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选将 `_eval_condition` / `_match_conditions` 提升为 `RuleEngine` 实例方法，不改变现有 `AutomationService` 实现**：理由是不破坏已通过测试的 `AutomationService.trigger_event`，而是让 `RuleEngine`包装它。这样下游 `TicketService` 等可调用 `RuleEngine.dispatch` 而无需 refactoring `AutomationService`。
- **选幂等 key存于 `trigger_context` JSONB 字段**：利用现有 `AutomationLogModel.trigger_context`（JSONB）存储 dedup key，而不新增列。查询时先 SELECT 检查 `(rule_id, tenant_id)` + dedup key 是否存在，再决定是否写 log。
- **选在领域服务方法末尾同步 dispatch，而非异步信号总线**：理由是 FastAPI 路由已是 async，session flush 在同一事务内完成，无需引入事件循环或消息队列依赖。

### 4.2 版本 pinning

|依赖 | 版本 | 理由 |
|------|------|------|
| `pytest-asyncio` | `≥0.23` | pyproject.toml 已锁定，async fixture `scope="function"` 需要 |
| `sqlalchemy` | `2.x` | pyproject.toml 已要求 2.x async API |

### 4.3 兼容性约束

- `RuleEngine.__init__` 必须接受 `session: AsyncSession` with no default —遵循 CLAUDE.md §服务模式。
- `RuleEngine` 不得破坏 `AutomationService.trigger_event` 的现有行为 —逻辑委托给 `AutomationService` 实例，不重写 SQL 查询。
- `TicketService.create_ticket` / `update_ticket` 返回类型不得改变（必须仍是 `TicketModel`），dispatch 为 fire-and-forget（异常不在 service 层向上抛，保证 ticket 创建成功不因规则引擎故障而回滚）。

### 4.4 已知坑

1. **`TRUNCATE CASCADE` 在 `db_schema` fixture 中清空所有表** → 规避：每个测试在 `db_schema` yield 之后通过 `async_session` 重新 seed 租户和依赖数据。
2. **幂等 dedup 查询在并发 flush 时存在 race condition（两次 flush 均通过 SELECT 检查）** → 规避：先用 `INSERT ... ON CONFLICT DO NOTHING`（PostgreSQL）写入 log，或在 `trigger_event` 入口加 `session.add + flush`，让 DB 唯一索引（tenant_id + rule_id + dedup_key hash）拦截重复写入。
3. **`NotificationService.send_notification` 在 action 执行时需要 user_id，但 event_data 中的 `user_id` 可能为 None** → 规避：`_execute_action` 对 `notification.send` 有 fallback：`user_id` 为0 时写入系统通知日志，不抛异常。

---

## 5. 实现步骤（按顺序）

### Step 1: Create src/services/rule_engine.py skeleton and export evaluate_conditions

定义 `RuleEngine` 类、`evaluate_conditions`（AND/OR/NONE）、`execute_rule`、`dispatch`、`register_handler` 的方法签名。将 `automation_service.py` 中的 `_eval_condition` 逻辑移入 `RuleEngine._eval_condition` 作为实例方法（保留原 helper 以不过 break `AutomationService`，在 `rule_engine.py` 中 new impl）。

操作：
- a) 创建空文件 `src/services/rule_engine.py`
- b) 添加 `from __future__ import annotations`
- c) 添加所有必要 import：`AsyncSession`, `AutomationService`, `_eval_condition`/`_match_conditions` from `automation_service`, `NotFoundException` from `pkg.errors.app_exceptions`
- d) 实现 `RuleEngine` class — `__init__(self, session: AsyncSession)` 持有 `self.session` 和 `self.automation_service = AutomationService(session)`
- e) 实现 `evaluate_conditions(conditions, event_data, logic="AND") -> bool`：从 `automation_service._match_conditions` 委托；新增 `logic="OR"` 支持（any condition matches）
- f) 实现 `register_handler`（dict 存储，测试用）
- g) 实现 `dispatch`（带幂等 dedup key 查 log 表，若已存在则 skip）

示例代码：

```python
# src/services/rule_engine.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.automation import AutomationLogModel
from services.automation_service import AutomationService, _match_conditions


class RuleEngine:
    LOGIC_AND = "AND"
    LOGIC_OR = "OR"
    LOGIC_NONE = "NONE"

    def __init__(self, session: AsyncSession):
        self.session = session
        self._svc = AutomationService(session)
        self._handlers: dict[str, callable] = {}

    async def evaluate_conditions(
        self,
        conditions: list[str, dict],
        event_data: dict,
        logic: str = "AND",
    ) -> bool:
        if not conditions:
            return True
        if logic == self.LOGIC_NONE:
            return False
        if logic == self.LOGIC_OR:
            return any(_match_conditions([c], event_data) for c in conditions)
        return _match_conditions(conditions, event_data)  # AND logic

    async def execute_rule(
        self,
        rule,
        event_data: dict,
        executed_by: int = 0,
    ) -> dict:
        executed_actions = []
        for action in rule.actions:
            result = await self._svc._execute_action(
                action, {**event_data, "rule_name": rule.name},
                self.session, rule.tenant_id, executed_by,
            )
            executed_actions.append(result)
        log = AutomationLogModel(
            rule_id=rule.id,
            tenant_id=rule.tenant_id,
            trigger_event=rule.trigger_event,
            trigger_context=event_data,
            actions_executed=executed_actions,
            status="success",
            executed_by=executed_by,
        )
        self.session.add(log)
        await self.session.flush()
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "success",
            "actions_executed": executed_actions,
            "log_id": log.id,
        }

    async def dispatch(
        self,
        tenant_id: int,
        trigger_event: str,
        event_data: dict,
        executed_by: int = 0,
    ) -> list[dict]:
        entity_id = event_data.get("entity_id") or event_data.get("ticket_id") or event_data.get("customer_id") or 0
        dedup_key = f"{trigger_event}:{entity_id}"
        existing = await self.session.execute(
            select(AutomationLogModel).where(
                AutomationLogModel.tenant_id == tenant_id,
                AutomationLogModel.rule_id.in_(
                    # subquery: all enabled rules for this trigger
                    select(AutomationLogModel.rule_id)  # placeholder; replaced in next step
                ),
                AutomationLogModel.trigger_context["_dedup_key"].astext == dedup_key,
            )
        )
        rules = []  # populated after implementation below
        results = []
        for rule in rules:
            entity_key = f"{trigger_event}:{entity_id}:{rule.id}"
            already_run = await self.session.execute(
                select(AutomationLogModel).where(
                    AutomationLogModel.tenant_id == tenant_id,
                    AutomationLogModel.rule_id == rule.id,
                )
            )
            # skip if exact (trigger_event + entity_id + rule_id) saw before
            if entity_key in { # will be replaced with real query r.trigger_context.get("_dedup_key") for r in already_run.scalars().all()
            }:
                continue result = await self.execute_rule(rule, {**event_data, "_dedup_key": entity_key}, executed_by)
            results.append(result)
        return results    def register_handler(self, trigger_event: str, handler: callable) -> None:
        self._handlers[trigger_event] = handler
```

**完成判定**：`ruff check src/services/rule_engine.py` 输出无错误

### Step 2: Implement dispatch idempotency via deduplication query

完善 `dispatch` 方法 — 查询给定 `(tenant_id, trigger_event, dedup_key)` 的 `AutomationLogModel`，若找到则跳过对应 rule。dedup_key = `"{trigger_event}:{entity_id}:{rule_id}"`，存于 `trigger_context["_dedup_key"]`。

操作：
- a) 在 `dispatch` 中实现完整 dedup 查询逻辑- b) 获取所有匹配的 `AutomationRuleModel`（通过 `AutomationService.list_rules`）
- c) 对每个 rule 检查 dedup key 是否存在
- d) 未命中则调用 `execute_rule`
- e) 添加 `log_on_conflict=False` 参数（可选）给调用方控制

完整 `dispatch` 实现：

```python
async def dispatch(
    self,
    tenant_id: int,
    trigger_event: str,
    event_data: dict,
    executed_by: int = 0,
) -> list[dict]:
    entity_id = (
        event_data.get("entity_id")
        or event_data.get("ticket_id")
        or event_data.get("customer_id")
        or event_data.get("opportunity_id")
        or 0
    )
    rules_and_results = []
    rules, _ = await self._svc.list_rules(
        tenant_id=tenant_id,
        trigger_event=trigger_event,
        enabled=True,
        page=1,
        page_size=1000,
    )
    results = []
    for rule in rules:
        dedup_key = f"{trigger_event}:{entity_id}:{rule.id}"
        existing_logs, _ = await self._svc.list_logs(
            tenant_id=tenant_id,
            rule_id=rule.id,
            page=1,
            page_size=1,
        )
        if existing_logs and existing_logs[0].trigger_context.get("_dedup_key") == dedup_key:
            continue
        if self._handlers.get(trigger_event):
            self._handlers[trigger_event](event_data)
        passed = await self.evaluate_conditions(rule.conditions, event_data)
        if not passed:
            continue
        result = await self.execute_rule(
            rule, {**event_data, "_dedup_key": dedup_key}, executed_by
        )
        results.append(result)
    return results
```

**完成判定**：`ruff check src/services/rule_engine.py` 无错误；`PYTHONPATH=src python -c "from services.rule_engine import RuleEngine; print('import ok')"` 输出 `import ok`

### Step 3: Hook RuleEngine.dispatch into TicketService

在 `TicketService.create_ticket` 和 `TicketService.update_ticket` 方法末尾添加 `RuleEngine.dispatch` 调用。由于 `TicketService` 不能直接构造 `RuleEngine`（session 已在 service 中），将 `dispatch` 调用注入为可选参数或通过事件发射点模式。

操作：
- a) 在 `ticket_service.py` import 添加 `from services.rule_engine import RuleEngine`
- b) 在 `create_ticket` return 语句前添加 event dispatch block- c) 在 `update_ticket` return 语句前添加 event dispatch block
- d) dispatch 调用使用 `try/except` 包裹，保证 ticket 操作不因规则引擎故障回滚

在 `src/services/ticket_service.py` 第 140 行（return ticket 语句前）插入：

```python
        try:
            from services.rule_engine import RuleEngine
            _engine = RuleEngine(self.session)
            await _engine.dispatch(
                tenant_id=tenant_id,
                trigger_event="ticket.created",
                event_data={
                    "entity_id": ticket.id,
                    "ticket_id": ticket.id,
                    "subject": subject,
                    "priority": _to_str(priority),
                    "customer_id": customer_id,
                    "assigned_to": assigned_to,
                },
                executed_by=created_by if hasattr(created_by, "__int__") else 0,
            )
        except Exception:
            pass  # fire-and-forget: rule engine failures must not rollback ticket creation
        return ticket
```

在 `src/services/ticket_service.py` 第 187 行（return updated ticket）前同理插入 `trigger_event="ticket.updated"` dispatch call。

**完成判定**：`ruff check src/services/ticket_service.py` 无错误；`grep -n "RuleEngine" src/services/ticket_service.py` 显示 ≥2 处 import 或调用

### Step 4: Hook RuleEngine.dispatch into OpportunityService and CustomerService

读取 `opportunity_service.py` 和 `customer_service.py` 的关键方法（create/update），在其 return 前插入 dispatch 调用。

操作：
- a) OpportunityService: 找到机会创建方法，在 return 前添加 `trigger_event="opportunity.created"`；在 stage 变更方法中添加 `trigger_event="opportunity.stage_changed"`
- b) CustomerService: 找到 `create_customer`，添加 `trigger_event="customer.created"`；在 update 方法中添加 `trigger_event="customer.updated"`
- c) 使用 fire-and-forget `try/except`包裹模式（与 Step 3 一致）

**完成判定**：`grep -n "RuleEngine" src/services/opportunity_service.py src/services/customer_service.py` 每文件 ≥ 1 处### Step 5: Write tests/unit/test_rule_engine.py

创建测试文件，覆盖以下 case：

操作：
- a) 创建 `tests/unit/test_rule_engine.py`
- b) `TestEvaluateConditions` 类 — 测试 AND（全部通过 / 任意失败）、OR（任意通过 / 全部失败）、空条件集、None logic、无效 operator- b) `TestExecuteRule` 类 — 测试 rule 含 1/3 个 actions，验证 `execute_rule` 返回 dict 含 `rule_id`, `status`, `actions_executed`, `log_id`
- c) `TestDispatchIdempotency` 类 — 同一 event dispatch 两次，验证 `AutomationLogModel` 只有 1 条- d) `TestDispatchLogic` 类 — 测试 `dispatch` 调用 `AutomationService.list_rules`，rule 不匹配 conditions 时不触发
- e) `TestRegisterHandler` 类 — 测试注册 handler 后 `dispatch` 调用它

示例测试结构：

```python
from __future__ import annotationsimport pytest
from services.rule_engine import RuleEngine
from tests.unit.conftest import make_mock_session, make_automation_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_automation_handler(state)])

class TestEvaluateConditions:
    async def test_and_all_pass(self, mock_db_session):
        engine = RuleEngine(mock_db_session)
        conditions = [
            {"field": "priority", "operator": "eq", "value": "high"},
            {"field": "status", "operator": "eq", "value": "open"},
        ]
        event_data = {"priority": "high", "status": "open"}
        result = await engine.evaluate_conditions(conditions, event_data, logic="AND")
        assert result is True

    async def test_and_one_fails(self, mock_db_session):
        engine = RuleEngine(mock_db_session)
        conditions = [{"field": "priority", "operator": "eq", "value": "high"}]
        event_data = {"priority": "low"}
        result = await engine.evaluate_conditions(conditions, event_data, logic="AND")
        assert result is False

    # ... (20+ tests total)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_rule_engine.py -v` 输出 `≥20 passed`

### Step 6: Update tests/unit/conftest.py with make_automation_handler

检查并确保 `make_automation_handler` 在 `conftest.py` 中存在且可被 import。

操作：
- a) 读取 `tests/unit/conftest.py`
- b) 若 `make_automation_handler` 不存在，添加 `make_automation_handler(state: MockState)` 工厂函数，实现 INSERT/UPDATE/DELETE/SELECT/COUNT 对 `automation_rules` 和 `automation_logs` 表的 handler

**完成判定**：`PYTHONPATH=src python -c "from tests.unit.conftest import make_automation_handler; print('import ok')"` 输出 `import ok`

---

## 6. 验收

- [ ] `ruff check src/services/rule_engine.py tests/unit/test_rule_engine.py` 无输出
- [ ] `ruff format --check src/services/rule_engine.py tests/unit/test_rule_engine.py` 无输出
- [ ] `PYTHONPATH=src pytest tests/unit/test_rule_engine.py -v` 输出 ≥ `20 passed`
- [ ] `PYTHONPATH=src python -c "from services.rule_engine import RuleEngine; print('RuleEngine imported')"` 输出 `RuleEngine imported`
- [ ] `grep -n "RuleEngine" src/services/ticket_service.py src/services/opportunity_service.py src/services/customer_service.py` 显示每文件 ≥ 1 处- [ ] `grep -rn "trigger_event.*created\|trigger_event.*updated" src/services/ticket_service.py src/services/opportunity_service.py src/services/customer_service.py` 显示有效 trigger string 字面量

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `dispatch` 中 dedup 查询增加数据库 round-trip（list_rules + list_logs 两条查询 per rule）导致性能下降 | 中 | 中 | 在 `RuleEngine`构造时接受 `skip_dedup: bool = False` param；CI/压力测试时设 True；生产默认 False |
| `TicketService.update_ticket` 中 fire-and-forget `try/except`吞掉所有异常导致规则失败静默 | 低 | 低 | 将 `try/except`替换为 logging.warning；保持不 blocking ticket update |
| `RuleEngine`引入循环 import：`rule_engine.py` → `automation_service.py` → `notification_service` / `task_service` → 其他 service | 中 | 中 | 将 `_execute_action` 和 `_match_conditions` 作为可选 lazy import放在方法内部（已应用于 action types in Step 1） |
| `AutomationService` 在 #686 分支中尚未合并，`AutomationRuleModel` / `AutomationLogModel` 列结构未知 | 低 | 高 | Step 1 前先用 `git diff origin/master -- src/services/automation_service.py src/db/models/automation.py` 确认模型结构已稳定 |

---

## 8. 完成后必做

```bash
# 1. 提交git add src/services/rule_engine.py tests/unit/test_rule_engine.py src/services/ticket_service.py src/services/opportunity_service.py src/services/customer_service.py && git commit -m "feat(rule-engine): RuleEngine with evaluate_conditions, execute_rule, idempotent dispatch (#687)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行（状态改为 ✅ 完成）
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（模板 A）
# ✅ [0687] Build rule execution engine and trigger dispatch 完成 (W14.1)
# - PR/Commit: <link>
# - 关键产物: src/services/rule_engine.py, tests/unit/test_rule_engine.py
# - 验收: pytest tests/unit/test_rule_engine.py -v 全绿 ✓ (≥20 passed)
# - 下一步赋能: #0688 add-integration-tests-for-full-rule-lifecycle

# 4. 如有新依赖或数据库迁移
# - 检查 alembic migrations 是否需要自动生成
# - 检查 docs/dev-plan/README.md §3依赖图是否需要更新
```

---

## 9. 参考

- 上游依赖：[#686 automation-orm-integration](https://github.com/YOUR_ORG/YOUR_REPO/issues/686)
- 父任务：[#33 automation test coverage gap](https://github.com/YOUR_ORG/YOUR_REPO/issues/33)
- 项目内：[`src/services/automation_service.py`](../../src/services/automation_service.py) — `_eval_condition` / `_match_conditions` / `AutomationService.trigger_event` 实现参考
- 项目内：[`src/db/models/automation.py`](../../src/db/models/automation.py) — `AutomationRuleModel` / `AutomationLogModel` ORM 定义
- 项目内：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) — dispatch hook 接入点
- 项目内：[`src/services/opportunity_service.py`](../../src/services/opportunity_service.py) — dispatch hook 接入点
- 项目内：[`src/services/customer_service.py`](../../src/services/customer_service.py) — dispatch hook 接入点
- 已有测试：[`tests/unit/test_automation_rules_ui.py`](../../tests/unit/test_automation_rules_ui.py) — `AutomationService` CRUD 测试参考模式
- 下游：[`docs/dev-plan/issues/0688-add-integration-tests-for-full-rule-lifecycle.md`](../../docs/dev-plan/issues/0688-add-integration-tests-for-full-rule-lifecycle.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |
