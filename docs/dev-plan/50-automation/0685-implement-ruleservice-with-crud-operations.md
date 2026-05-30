# 0685-implement-automationrule-service · Build AutomationRuleService with full CRUD

| 元数据 | 值 |
|---|---|
| 周次 | W13.2 |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0686-add-post-get-put-delete-automation-rules-router-endpoints](../50-automation/0108-backend-automation-rules-api-missing-router-and-endpoints.md) |
| 启用后赋能 | [0687-build-rule-execution-engine-and-trigger-dispatch](../50-automation/0464-build-automation-rules-engine-and-4-preset-rules.md), [0688-add-integration-tests-for-full-rule-lifecycle](../50-automation/0464-build-automation-rules-engine-and-4-preset-rules.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #685 is the service-layer companion to #686 (REST API for automation rules). Issue #686 exposes CRUD endpoints that depend on a service class `AutomationRuleService` to wrap SQL operations. At present, no `AutomationRuleService` exists in `src/services/` — the router (once built in #686) would have nowhere to delegate. Building this service now provides the single authoritative source of truth for all rule CRUD operations, with proper multi-tenancy filtering, exception handling, and no `.to_dict()` in the service layer.

### 1.2 做完后

- **用户视角**：No user-facing change yet — this is a backend-only service layer. Downstream boards (#686 router, #687 execution engine) gain a stable interface to call.
- **开发者视角**：New `AutomationRuleService(session)` in `src/services/automation_rule_service.py` provides `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `activate_rule`, `deactivate_rule`. All methods accept `tenant_id: int` and filter every query accordingly. Raises `NotFoundException` / `ValidationException` on errors.

### 1.3 不做什么（剔除）

- [ ] No rule execution logic — that is handled by #687 (`RuleEngine` + trigger dispatch).
- [ ] No API router — that is handled by #686 (`automation_rules.py` router).
- [ ] No new ORM models — `AutomationRuleModel` / `AutomationLogModel` are already defined in `src/db/models/automation_rule.py` and `src/db/models/automation_log.py`.
- [ ] No `.to_dict()` in the service — serialization is router responsibility.

### 1.4 关键 KPI

- `ruff check src/services/automation_rule_service.py` → zero warnings/errors.
- `ruff check tests/unit/test_automation_rule_service.py` → zero warnings/errors.
- `PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v` → ≥ 21 passed (7 methods × 3 cases minus some edge cases).
- `mypy src/services/automation_rule_service.py` → zero errors.
- Every method filters by `tenant_id` — verifiable by unit test with cross-tenant assertion.

---

## 2. 当前现状（起点）

### 2.1 现有实现

The ORM layer `AutomationRuleModel` is defined but no dedicated CRUD service exists. The existing `AutomationService` in `src/services/automation_service.py` mixes execution logic with CRUD, and its method signatures differ from what the router (#686) requires. A test handler `make_automation_handler` already exists in `tests/unit/domain_handlers/automation.py` covering INSERT / SELECT / UPDATE / DELETE / COUNT for `automation_rules`.

主入口：[`src/db/models/automation_rule.py`](../../../src/db/models/automation_rule.py) L1-L45

```startLine:1:src/db/models/automation.py
class AutomationRuleModel(Base):
    """User-defined automation rules stored in DB."""

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

现有测试 handler：[`tests/unit/domain_handlers/automation.py`](../../../tests/unit/domain_handlers/automation.py) L1-L93

```startLine:1:tests/unit/domain_handlers/automation.py
def make_automation_handler(state: MockState):
    """Handle automation rules SQL (INSERT, SELECT, DELETE, COUNT)."""
    if not hasattr(state, "automation_rules"):
        state.automation_rules = {}
    if not hasattr(state, "automation_rules_next_id"):
        state.automation_rules_next_id = 1000

    def handler(sql_text, params):
        tenant_id = params.get("tenant_id", 0)
        if "insert into automation_rules" in sql_text:
            rid = state.automation_rules_next_id
            state.automation_rules_next_id += 1
            record = {...}  # stores name, trigger_event, conditions (JSONB), actions (JSONB), enabled state.automation_rules[rid] = record
            return MockResult([MockRow(record.copy())], rowcoun=1)
        # ... SELECT by id, list all, count, UPDATE, DELETE
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/automation_service.py`](../../../src/services/automation_service.py) — 确认 `AutomationService` 已有的 CRUD 方法签名，供本板块参考；本板块不修改该文件
- 要建：
  - `src/services/automation_rule_service.py` — 新建 `AutomationRuleService`，实现7 个 CRUD/activate/deactivate 方法
  - `tests/unit/test_automation_rule_service.py` —单元测试，覆盖 7 个方法的成功路径 + 边界 + 错误路径### 2.3 缺什么

- [ ] No `AutomationRuleService` class in `src/services/`.
- [ ] `create_rule`: insert `AutomationRuleModel`, persist conditions/actions as JSONB, return ORM object.
- [ ] `list_rules`: paginated SELECT with count, filter by tenant_id, optional `enabled` filter.
- [ ] `get_rule`: SELECT by id + tenant_id, raise `NotFoundException` if not found.
- [ ] `update_rule`: UPDATE allowed fields, raise `NotFoundException` if no rows updated.
- [ ] `delete_rule`: DELETE by id + tenant_id, raise `NotFoundException` if no rows deleted.
- [ ] `activate_rule` / `deactivate_rule`: set `enabled=True/False`, return updated model.
- [ ] All7 methods must validate `trigger_event` against `TRIGGER_EVENTS` allowlist.
- [ ] All7 methods must include `tenant_id` in every WHERE clause.
- [ ] No `.to_dict()` in service layer.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| `src/services/automation_rule_service.py` | `AutomationRuleService` class: create_rule, list_rules, get_rule, update_rule, delete_rule, activate_rule, deactivate_rule |
| `tests/unit/test_automation_rule_service.py` | Unit tests for all 7 service methods using mock DB session via `make_automation_handler` |
| `docs/dev-plan/issues/0685_verify.sh` | Acceptance script: ruff check + mypy + pytest |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| TBD - 待补充：无修改文件 | 本板块仅新建 service 文件；不影响现有代码 |

### 3.3 新增能力

- **`AutomationService` interface (new file)**：`AutomationRuleService` class with7 async methods.
- **Exception handling**：Raise `NotFoundException` when rule not found; raise `ValidationException` when `trigger_event` not in allowlist or `name` is empty.
- **verify 脚本**：`bash docs/dev-plan/issues/0685_verify.sh`
- **Slack 模板填空**：TBD - 待补充：Slack通知按 README §2.9 模板 A（#progress 频道）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `AutomationRuleService` 为独立文件而非扩展 `AutomationService`**：职责分离，CRUD 服务专注数据访问，不混入执行逻辑。`AutomationService` 中的 `_execute_action` 等属于执行引擎范畴 (#687)，不应与 CRUD 并存。
- **选 `TRIGGER_EVENTS` 常量白名单而非自由文本**：允许 `trigger_event` 自由文本会导致执行引擎无法识别触发器类型。先限定白名单，后续 #687 可放宽为白名单 + 自定义前缀。
- **选 `ValidationException` 而非 `ValueError` 来校验 trigger_event**：按 CLAUDE.md §「Error Handling」，服务层应抛 `AppException` 子类，由全局异常处理器转换为 HTTP 响应。

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `sqlalchemy` | `2.x` | pyproject.toml 已锁定；使用 async API `select().where(...)` |
| `pytest-asyncio` | `≥0.23` | 所有 service 方法均为 `async def`，测试需要 pytest-asyncio |

### 4.3 兼容性约束

- `AutomationRuleService` 不得破坏 `AutomationService`（现有文件）的任何方法签名。
- Service 方法返回 `AutomationRuleModel` ORM 对象，不调用 `.to_dict()`，序列化由 router (#686) 负责。
- 所有 SQL WHERE 必须包含 `tenant_id` 过滤。

### 4.4 已知坑

1. **JSONB conditions/actions传入 dict/list 后 SQLAlchemy 直接报错** → 规避：`AutomationRuleModel.conditions` 和 `actions` 已在 ORM 定义为 `Mapped[list]`，传入 list/dict 时 SQLAlchemy 自动处理 JSONB序列化；无需手动 `json.dumps`。
2. **`tenant_id=0` 的边缘情况** →规避：测试 handler允许 `tenant_id=0` 通过 WHERE过滤（真实环境无此 tenant），单元测试覆盖此场景以确保隔离性。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/automation_rule_service.py` 文件骨架

创建 service 文件，写入类骨架、`__init__`、白名单常量和辅助函数。

操作：
- a) 在 `src/services/` 下新建 `automation_rule_service.py`
- b) 写入 import：`AsyncSession`, `NotFoundException`, `ValidationException`, `AutomationRuleModel`, `and_`, `delete`, `func`, `select`, `update`
- c) 写入 `TRIGGER_EVENTS` 白名单常量（覆盖 `ticket.created`, `ticket.updated`, `ticket.assigned`, `opportunity.stage_changed`, `opportunity.created`, `customer.created`, `customer.updated`, `user.login`, `lead.created`）
- d) 空方法占位：`create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `activate_rule`, `deactivate_rule`

**完成判定**：文件 `src/services/automation_rule_service.py` 存在，`ruff check src/services/automation_rule_service.py` 输出零警告/错误。

---

### Step 2: 实现 `create_rule` 方法

操作：
- a) 在 `AutomationRuleService` 类中实现 `create_rule(tenant_id, name, trigger_event, conditions, actions, description=None, enabled=True, created_by=0) -> AutomationRuleModel`
- b) 前置校验：`name` 非空（否则 `ValidationException("name 不能为空")`）；`trigger_event` 在白名单中（否则 `ValidationException(f"不支持的触发器类型: {trigger_event}")`）
- c) 构造 `AutomationRuleModel` 实例，`utcnow()`填充 `created_at` / `updated_at`
- d) `session.add()` → `await session.flush()` → `return` ORM 对象

示例代码（≤15 行）：

```python
async def create_rule(
    self,
    tenant_id: int,
    name: str,
    trigger_event: str,
    conditions: list,
    actions: list,
    description: str | None = None,
    enabled: bool = True,
    created_by: int = 0,
) -> AutomationRuleModel:
    if not name:
        raise ValidationException("name 不能为空")
    if trigger_event not in TRIGGER_EVENTS:
        raise ValidationException(f"不支持的触发器类型: {trigger_event}")
    now = datetime.now(UTC)
    rule = AutomationRuleModel(
        tenant_id=tenant_id,
        name=name,
        description=description,
        trigger_event=trigger_event,
        conditions=conditions,
        actions=actions,
        enabled=enabled,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    self.session.add(rule)
    await self.session.flush()
    return rule
```

**完成判定**：`ruff check src/services/automation_rule_service.py` 全绿；`mypy src/services/automation_rule_service.py` 全绿。

---

### Step 3: 实现 `list_rules` 和 `get_rule` 方法

操作：
- a) `list_rules(tenant_id, page=1, page_size=20, enabled=None) -> tuple[list[AutomationRuleModel], int]`：用 `select(AutomationRuleModel).where(tenant_id).order_by(created_at.desc()).offset().limit()` 做分页；另发一条 `select(func.count()).where(tenant_id)` 取总数
- b) `get_rule(rule_id, tenant_id) -> AutomationRuleModel`：用 `select(AutomationRuleModel).where(id, tenant_id)`；不存在则 `raise NotFoundException("自动化规则")`

示例代码（list_rules SELECT 片断）：

```python
conditions = [AutomationRuleModel.tenant_id == tenant_id]
if enabled is not None:
    conditions.append(AutomationRuleModel.enabled == enabled)
count_result = await self.session.execute(
    select(func.count(AutomationRuleModel.id)).where(and_(*conditions))
)
total = count_result.scalar() or 0
offset = (page - 1) * page_size
result = await self.session.execute(
    select(AutomationRuleModel)
    .where(and_(*conditions))
    .order_by(AutomationRuleModel.created_at.desc())
    .offset(offset)
    .limit(page_size)
)
return result.scalars().all(), total
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v -k "list_rules or get_rule"` 运行成功（0 failed）。

---

### Step 4: 实现 `update_rule` 方法

操作：
- a) `update_rule(rule_id, tenant_id, data) -> AutomationRuleModel`：用 `get_rule` 先查，若不存在已在 `get_rule`抛 `NotFoundException`
- b) 允许更新字段白名单：`name`, `description`, `trigger_event`, `conditions`, `actions`, `enabled`
- c) 若更新 `trigger_event`，校验白名单
- d) 直接 `setattr`，更新 `updated_at`；`flush()` → `refresh()` → return

示例代码：

```python
async def update_rule(
    self, rule_id: int, tenant_id: int, data: dict
) -> AutomationRuleModel:
    rule = await self.get_rule(rule_id, tenant_id)
    allowed = {"name", "description", "trigger_event", "conditions", "actions", "enabled"}
    any_changes = False
    for key, value in data.items():
        if key in allowed:
            if key == "trigger_event" and value not in TRIGGER_EVENTS:
                raise ValidationException(f"不支持的触发器类型: {value}")
            setattr(rule, key, value)
            any_changes = True
    if not any_changes:
        await self.session.flush()
        await self.session.refresh(rule)
        return rule
    rule.updated_at = datetime.now(UTC)
    await self.session.flush()
    await self.session.refresh(rule)
    return rule
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v -k "update_rule"` 0 failed。

---

### Step 5: 实现 `delete_rule` 方法

操作：
- a) `delete_rule(rule_id, tenant_id) -> dict`：执行 `delete(AutomationRuleModel).where(id, tenant_id)`；检查 `rowcount==0` 则 `raise NotFoundException("自动化规则")`；返回 `{"id": rule_id}`

示例代码：

```python
async def delete_rule(self, rule_id: int, tenant_id: int) -> dict:
    result = await self.session.execute(
        delete(AutomationRuleModel).where(
            and_(AutomationRuleModel.id == rule_id, AutomationRuleModel.tenant_id == tenant_id)
        )
    )
    if (result.rowcount or 0) == 0:
        raise NotFoundException("自动化规则")
    return {"id": rule_id}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v -k "delete_rule"` 0 failed。

---

### Step 6: 实现 `activate_rule` 和 `deactivate_rule` 方法

操作：
- a) `activate_rule(rule_id, tenant_id) -> AutomationRuleModel`：调用 `update_rule(rule_id, tenant_id, {"enabled": True})`
- b) `deactivate_rule(rule_id, tenant_id) -> AutomationRuleModel`：调用 `update_rule(rule_id, tenant_id, {"enabled": False})`

示例代码：

```python
async def activate_rule(self, rule_id: int, tenant_id: int) -> AutomationRuleModel:
    return await self.update_rule(rule_id, tenant_id, {"enabled": True})

async def deactivate_rule(self, rule_id: int, tenant_id: int) -> AutomationRuleModel:
    return await self.update_rule(rule_id, tenant_id, {"enabled": False})
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v -k "activate or deactivate"` 0 failed。

---

### Step 7: 编写 `tests/unit/test_automation_rule_service.py` 单元测试

操作：
- a) 新建 `tests/unit/test_automation_rule_service.py`
- b) `@pytest.fixture mock_db_session`：使用 `make_mock_session([make_automation_handler(state)])`
- c) `@pytest.fixture `：`返回 `AutomationRuleService(mock_db_session)`
- d) 每个方法写 3 个测试用例（共 21 个）：
  - **成功路径**：正常参数 CRUD 操作，断言返回 ORM 对象，检查字段值
  - **边界**：空 name 输入 → `ValidationException`；无效 trigger_event → `ValidationException`；不存在 ID → `NotFoundException`；分页 `page=2, page_size=5` 边界；`enabled=None` list 无过滤
  - **错误路径**：跨租户访问（Tenant A 创建的规则，Tenant B `get_rule` → `NotFoundException`）；`delete_rule` 重复删除 → `NotFoundException`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v` 输出 `21 passed`（允许 skip1-2 个边界用例）。

---

### Step 8: 编写 `docs/dev-plan/issues/0685_verify.sh` 验收脚本

操作：
- a) 新建 `docs/dev-plan/issues/0685_verify.sh`：

```bash
#!/usr/bin/env bash
set -e
export PYTHONPATH=src

echo "=== ruff check ==="
ruff check src/services/automation_rule_service.py
ruff check tests/unit/test_automation_rule_service.py

echo "=== mypy ==="
mypy src/services/automation_rule_service.py

echo "=== pytest ==="
pytest tests/unit/test_automation_rule_service.py -v

echo "ALL CHECKS PASSED"
```

- b) `chmod +x docs/dev-plan/issues/0685_verify.sh`
- c) 本地运行，确认输出 `ALL CHECKS PASSED`

**完成判定**：`bash docs/dev-plan/issues/0685_verify.sh`退出码 0，输出最后一行 `ALL CHECKS PASSED`。

---

## 6. 验收

- [ ] `ruff check src/services/automation_rule_service.py` → zero warnings/errors
- [ ] `ruff check tests/unit/test_automation_rule_service.py` → zero warnings/errors
- [ ] `mypy src/services/automation_rule_service.py` → zero errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_rule_service.py -v` → `21 passed`（或实际用例数，全部 passed）
- [ ] `bash docs/dev-plan/issues/0685_verify.sh` → `ALL CHECKS PASSED`
- [ ] 每个 service 方法测试用例中包含跨租户隔离验证（Tenant A 的 ID 在 Tenant B session 下查 → `NotFoundException`）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ORM 模型字段变更导致 service编译失败 | 低 | 中 | 按失败信息补充/修正字段映射；不影响下游 #686（router 尚未实现） |
| JSONB conditions/actions序列化类型不匹配 | 中 | 中 | 确保 `AutomationRuleModel` 的 `Mapped[list]` 直接接受 Python list，无需 `json.dumps`；测试覆盖验证 |
| `make_automation_handler` 未覆盖 ORDER BY 后的分页偏移 | 低 | 低 | 在 handler 增加 `offset` / `limit` 分支逻辑；测试用 `page=2` 会暴露此问题 |

---

## 8. 完成后必做

```bash
# 1. commit
git add src/services/automation_rule_service.py tests/unit/test_automation_rule_service.py docs/dev-plan/issues/0685_verify.sh
git commit -m "feat(automation): implement AutomationRuleService with full CRUD"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §4 全局进度表本行
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ [0685] AutomationRuleService 完成 (W13.2)
# - PR/Commit: <link>
# - 关键产物: src/services/automation_rule_service.py (7 methods), tests/unit/test_automation_rule_service.py (21 test cases)
# - 验收: bash docs/dev-plan/issues/0685_verify.sh 全绿 ✓
# - 下一步赋能: #686 (automation_rules router), #687 (rule execution engine)

# 4. 如果加了新 stage（部署阶段）
# -改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- 上游 ORM 模型：[`src/db/models/automation_rule.py`](../../../src/db/models/automation_rule.py) L12-L44
- 上游测试 handler：[`tests/unit/domain_handlers/automation.py`](../../../tests/unit/domain_handlers/automation.py) L1-L101
- 姊妹服务参考：[`src/services/customer_service.py`](../../../src/services/customer_service.py) L1-L162（完整 CRUD模式，含 paginated list + tenant_id过滤）
- 异常定义：[`src/pkg/errors/app_exceptions.py`](../../../src/pkg/errors/app_exceptions.py)
- Issue #686 router：[`docs/dev-plan/50-automation/0108-backend-automation-rules-api-missing-router-and-endpoints.md`](../50-automation/0108-backend-automation-rules-api-missing-router-and-endpoints.md)
- Issue #687 执行引擎：[`docs/dev-plan/50-automation/0464-build-automation-rules-engine-and-4-preset-rules.md`](../50-automation/0464-build-automation-rules-engine-and-4-preset-rules.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD - 待补充 |
