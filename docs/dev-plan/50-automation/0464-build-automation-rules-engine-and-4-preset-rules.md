# Automation Rules Engine · Rule evaluation and 4 preset rules

| 元数据 | 值 |
|---|---|
| Issue | #464 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [043-workflow-job-queue-and-scheduled-execution](../040-cross-functional/043-workflow-job-queue-and-scheduled-execution.md) |
| 启用后赋能 | TBD — 待补充：哪些下游功能依赖本板块完成后才能开始 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The workflow system (issue #463) provides a job-queue execution infrastructure, but it currently lacks a declarative rules engine that can evaluate entity conditions and fire actions automatically. Without a rules engine, every automation must be hand-coded in WorkflowService, leading to duplicated condition-logic and making it impossible for operators to add new rules without a code change. Issue #449 (Automation Framework) is blocked until the engine core and its first set of preset rules exist.

### 1.2 做完后

- **用户视角**：No direct user-visible change — this is a pure backend foundation. Once the engine and rules are wired into WorkflowService, the system will automatically trigger welcome emails, alert reps to stale deals, and celebrate closed wins without manual intervention.
- **开发者视角**：`AutomationEngine` in `src/services/automation/engine.py` provides a `register_rule()`, `evaluate()`, and `execute()` API. Four preset rule modules live under `src/services/automation/rules/`. Adding a new rule means creating one Python file and calling `engine.register_rule(NewRule())` — no changes to WorkflowService core logic.

### 1.3 不做什么（剔除）

- [ ] Persistent rule storage (DB-backed rule registry) — rules are code-only for v1; DB-backed rule CRUD is a future issue.
- [ ] Rule chaining / pipelines with fan-out; all rules evaluate and execute independently.
- [ ] UI for rule configuration — operator-facing rule editing is out of scope.

### 1.4 关键 KPI

- [4 new rule files exist under `src/services/automation/rules/` — verified by `ls src/services/automation/rules/`]
- [`pytest tests/unit/test_automation_engine.py -v` → all passed]
- [`ruff check src/services/automation/` → 0 errors]
- [`ruff check src/services/workflow_service.py` → 0 errors after wiring]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/workflow_service.py` L? — existing WorkflowService.execute_workflow signature and whether it currently delegates to any sub-engine, or handles all logic inline.

TBD - 待验证：`src/services/automation/` — directory may already exist as an empty `__init__.py` package (part of #463 work), or may not exist at all.

### 2.2 涉及文件清单

- 要改：
  - `src/services/workflow_service.py` — wire `AutomationEngine` into `execute_workflow`, delegate rule evaluation and action execution to the engine
  - `tests/unit/test_workflow_service.py` — add test cases for rule-delegation path
- 要建：
  - `src/services/automation/engine.py` — `AutomationEngine` class with `register_rule`, `evaluate`, `execute` methods
  - `src/services/automation/rules/__init__.py` — package init, no logic
  - `src/services/automation/rules/new_customer_welcome.py` — preset rule
  - `src/services/automation/rules/opportunity_stage_changed.py` — preset rule
  - `src/services/automation/rules/inactive_customer_alert.py` — preset rule
  - `src/services/automation/rules/deal_won_celebration.py` — preset rule
  - `tests/unit/test_automation_engine.py` — unit tests for the engine
  - `tests/unit/test_automation_rules.py` — unit tests for each preset rule

### 2.3 缺什么

- [ ] `AutomationEngine` class — no central place to register rules and evaluate/execute them against entity state]
- [ ] A common rule interface — `evaluate(entity, context) -> bool` + `execute(entity, context) -> None` contract
- [ ] Four concrete preset rule implementations as working examples]
- [ ] Integration of the engine into `WorkflowService.execute_workflow` — currently no delegation]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/automation/engine.py` | `AutomationEngine` — rule registry, evaluate, and execute |
| `src/services/automation/rules/__init__.py` | Package marker, exports rule classes |
| `src/services/automation/rules/new_customer_welcome.py` | Preset rule: fires welcome email when a new Customer is created |
| `src/services/automation/rules/opportunity_stage_changed.py` | Preset rule: logs stage-change events when an Opportunity moves stage |
| `src/services/automation/rules/inactive_customer_alert.py` | Preset rule: sends alert to rep when a Customer has no activity for 30 days |
| `src/services/automation/rules/deal_won_celebration.py` | Preset rule: fires a "deal won" notification when an Opportunity closes as won |
| `tests/unit/test_automation_engine.py` | Unit tests for `AutomationEngine` |
| `tests/unit/test_automation_rules.py` | Unit tests for the four preset rules |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/workflow_service.py` | Import `AutomationEngine`; in `execute_workflow`, call `engine.evaluate()` then `engine.execute()` instead of inline condition logic |
| `tests/unit/test_workflow_service.py` | Add test asserting that `execute_workflow` delegates to engine; mock engine to isolate unit |

### 3.3 新增能力

- **Service class**：`AutomationEngine` in `src/services/automation/engine.py` — `register_rule(rule)`, `evaluate(entity, context) -> list[Rule]`, `execute(rules, entity, context) -> None`
- **Rule interface**：all preset rules conform to `evaluate(entity: Any, context: dict) -> bool` and `execute(entity: Any, context: dict) -> None`
- **Four preset rules** under `src/services/automation/rules/`, each independently testable
- **Wiring**：`WorkflowService.execute_workflow` calls `self.engine.evaluate(entity, ctx)` and `self.engine.execute(matching_rules, entity, ctx)`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Rules as Python objects, not dict config** — each rule is a class instance with `evaluate` and `execute` methods. This avoids a DSL parser, keeps type checking (mypy/ruff) active on rule code, and makes unit testing trivial (just instantiate and call methods). A DB-backed rule registry is deferred to a future issue.
- **`evaluate` returns `bool` not a rule object** — keeps the interface minimal. The engine collects all rules where `evaluate == True` and passes that list to `execute`. This mirrors the pattern used in existing CRM services (handlers return bool, caller decides what to do next).
- **Engine is a singleton on WorkflowService** — not a global singleton. `WorkflowService.__init__` creates one `AutomationEngine` instance and holds it as `self.engine`. This avoids hidden global state while keeping wiring straightforward.
- **Context dict carries tenant_id, actor, trigger** — instead of threading `tenant_id` through every method call, the caller passes a `context` dict (containing at minimum `tenant_id`, `actor`, `trigger`). Each rule reads from context as needed. This matches how `AuthContext` is used in routers.

### 4.2 版本约束

No new external dependencies beyond what already exists in `pyproject.toml`. All implementation uses the existing async SQLAlchemy 2.x stack.

### 4.3 兼容性约束

- Multi-tenant: every rule that queries the DB must include `tenant_id` from `context["tenant_id"]` in the SQL WHERE clause.
- Service pattern: `AutomationEngine` is instantiated by `WorkflowService` and passed the session in `__init__` (session: `AsyncSession`, no default). Rules receive `entity` and `context`; they do not receive the session directly — they delegate to injected service helpers where needed.
- Rules must not call `.to_dict()` on ORM objects; they operate on domain objects and pass them to action helpers.

### 4.4 已知坑

1. **Rules calling session directly couples them to the DB** →规避：rules receive pre-built helper objects (e.g., `email_service`, `log_service`) via context, not a raw session. The engine adds these to context before calling `evaluate`/`execute`.
2. **Alembic autogen emits `sa.JSON()` instead of `sa.JSONB()`** →规避：any migration created for this issue that touches a JSON column must manually replace `sa.JSON()` with `sa.JSONB()` and add `timezone=True` to any `DateTime` columns. No migrations are expected for v1 of this engine (rules are code-only), but the warning applies to any follow-on migration.
3. **Column name `metadata` on a Base subclass crashes at class definition** →规避：if any future migration adds a column to an existing model, name it `event_metadata` or `payload`, never `metadata`.

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/services/automation/` package and `AutomationEngine` skeleton

Create the package directory and `__init__.py` files. Define `AutomationEngine` with `__init__(self, session: AsyncSession)`, `register_rule(self, rule)`, `evaluate(self, entity, context) -> list[Rule]`, and `execute(self, rules, entity, context) -> None`. Add a `Rule` protocol / ABC with `name: str`, `evaluate(self, entity, context) -> bool`, `execute(self, entity, context) -> None`. Use `Protocol` from `typing` so mypy can check rule implementations without a hard ABC dependency.

```
src/services/automation/
├── __init__.py          # exports AutomationEngine
├── engine.py             # AutomationEngine + Rule Protocol
└── rules/
    ├── __init__.py       # from .new_customer_welcome import NewCustomerWelcomeRule, etc.
    ├── new_customer_welcome.py
    ├── opportunity_stage_changed.py
    ├── inactive_customer_alert.py
    └── deal_won_celebration.py
```

**完成判定**：`ruff check src/services/automation/engine.py` → 0 errors / `mypy src/services/automation/engine.py` → 0 errors

### Step 2: Write four preset rule stubs

For each rule file, define the class inheriting from the `Rule` Protocol:

- `NewCustomerWelcomeRule.evaluate` → `entity.__class__.__name__ == "Customer" and context.get("is_new")`
- `OpportunityStageChangedRule.evaluate` → `entity.__class__.__name__ == "Opportunity" and "stage" in context.get("changed_fields", [])`
- `InactiveCustomerAlertRule.evaluate` → `entity.__class__.__name__ == "Customer" and entity.last_activity_at is not None and (now - entity.last_activity_at).days >= 30`
- `DealWonCelebrationRule.evaluate` → `entity.__class__.__name__ == "Opportunity" and entity.stage == "closed_won"`

Each `execute` method logs via Python `logging` (logger named `automation.rules.<rule_name>`) — no email/http calls in v1 (those go in follow-on issues). Stub classes compile to valid Python.

**完成判定**：`python -c "from src.services.automation.rules import NewCustomerWelcomeRule, OpportunityStageChangedRule, InactiveCustomerAlertRule, DealWonCelebrationRule; print('ok')"` → `ok`

### Step 3: Write unit tests for `AutomationEngine`

`tests/unit/test_automation_engine.py` — use `make_mock_session` from `tests/unit/conftest.py`. Test cases:

- `test_register_rule_appends_to_list` — register two rules, assert both present
- `test_evaluate_returns_only_matching_rules` — mock `entity` and `context`, one rule returns True, one returns False, assert only the True rule is in the result
- `test_execute_calls_execute_on_every_rule` — mock `entity` and `context`, assert `execute` called on each matching rule

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_engine.py -v` → `3 passed`

### Step 4: Write unit tests for four preset rules

`tests/unit/test_automation_rules.py` — each rule gets 2-3 test cases covering the `evaluate` condition and confirming `execute` does not raise.

For `InactiveCustomerAlertRule` and `DealWonCelebrationRule`, use `freezegun` or `unittest.mock.patch("datetime.datetime")` to control `now` in the evaluate logic.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rules.py -v` → `N passed` (≥ 8)

### Step 5: Wire `AutomationEngine` into `WorkflowService`

In `src/services/workflow_service.py`:

1. Import `AutomationEngine` and all four preset rules
2. In `WorkflowService.__init__`: `self.engine = AutomationEngine(session)` then call `self.engine.register_rule(NewCustomerWelcomeRule())` etc. for all 4 rules
3. In `execute_workflow` (or whichever method handles rule evaluation): replace inline condition checks with:
   ```python
   matching_rules = self.engine.evaluate(entity, {"tenant_id": tenant_id, "actor": actor, "trigger": trigger})
   if matching_rules:
       self.engine.execute(matching_rules, entity, {"tenant_id": tenant_id, "actor": actor, "trigger": trigger})
   ```

Use `text()` for any raw SQL inside rule action helpers. Ensure every WHERE clause includes `tenant_id`.

**完成判定**：`ruff check src/services/workflow_service.py` → 0 errors / `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → all existing tests pass + new delegation test passes

### Step 6: Verify full test suite and lint

Run the full lint and unit test pipeline. Fix any errors.

**完成判定**：`ruff check src/services/ && ruff check src/services/workflow_service.py && PYTHONPATH=src pytest tests/unit/ -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/services/automation/` → 0 errors
- [ ] `ruff check src/services/workflow_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_engine.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_rules.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_service.py -v` → all passed (no regression)
- [ ] `mypy src/services/automation/engine.py src/services/workflow_service.py` → 0 errors (type check)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Rule `evaluate` logic has a bug causing False negatives (rule doesn't fire when it should) | 中 | 中 | Add a catch-all fallback in `execute_workflow` that still calls the original inline logic as a fallback; feature flag controls which path runs |
| `WorkflowService.execute_workflow` interface changes in #463, breaking the wiring | 低 | 中 | Keep the wiring minimal (only one call to `engine.evaluate` and one to `engine.execute`); if the interface changes, only these two call sites need updating |
| Introducing `AutomationEngine` creates a circular import with an existing service | 低 | 高 | Move `AutomationEngine` to a standalone file with no imports from `services/` except `from db.connection import get_db` and `from sqlalchemy.ext.asyncio import AsyncSession`; tests mock the engine at the WorkflowService level |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/automation/ tests/unit/test_automation_engine.py tests/unit/test_automation_rules.py
git add src/services/workflow_service.py tests/unit/test_workflow_service.py
git commit -m "feat(automation): add AutomationEngine and 4 preset rules
Closes #464"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): AutomationEngine + 4 preset rules (closes #464)" --body "## Summary
- Add `AutomationEngine` class with `register_rule`, `evaluate`, `execute` methods
- Add 4 preset rules: new_customer_welcome, opportunity_stage_changed, inactive_customer_alert, deal_won_celebration
- Wire engine into `WorkflowService.execute_workflow`
- Add unit tests for engine and rules

## Test plan
- [ ] `ruff check src/services/automation/ src/services/workflow_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_engine.py tests/unit/test_automation_rules.py tests/unit/test_workflow_service.py -v` → all passed
- [ ] `mypy src/services/automation/engine.py src/services/workflow_service.py` → 0 errors

Closes #464"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/workflow_service.py` — existing WorkflowService pattern to follow for `__init__` session injection and method signatures
- 同类参考实现：TBD - 待验证：`tests/unit/conftest.py` — MockState / make_mock_session pattern used in all existing unit tests
- 父 issue / 关联：#449 (Automation Framework parent), #463 (WorkflowService job queue)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
