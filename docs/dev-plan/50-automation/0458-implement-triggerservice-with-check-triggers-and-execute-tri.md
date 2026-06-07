# TriggerService · 实现 check_triggers 和 execute_trigger

| 元数据 | 值 |
|---|---|
| Issue | #458 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 后续 trigger 相关的自动化规则引擎 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #450 规划了完整的自动化工作流系统。 Issue #457 提供了 trigger API 层（`POST /triggers` 等端点），但没有底层 service 逻辑来支撑这些端点。业务代码（各 domain service、各 event-listener hook）无法调用 trigger 逻辑，除非 TriggerService 存在。本板块是 #457 的下游依赖，也是整个 automation 模块的基石。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层服务，未暴露新的 UI 或 API 端点。
- **开发者视角**：`TriggerService` 可被各 domain service 和 event-handler 调用：
  - `check_triggers(event_type, entity_id, tenant_id)` → 返回待执行的 `TriggerModel` 列表
  - `execute_trigger(trigger_id, tenant_id)` → 执行 action（占位），返回结果 dict

### 1.3 不做什么（剔除）

- [ ] 不实现 trigger 持久化（`TriggerModel` ORM 建表、trigger 表 migration）— 属于 #457 范畴
- [ ] 不实现 action 执行逻辑（发邮件、Webhook 调用、外部系统集成）— 占位实现，真实 integration 点待后续
- [ ] 不实现 trigger 编辑/删除 API — 由 #457 的 router 层覆盖
- [ ] 不实现 trigger 历史记录或执行日志 — 属于后续自动化执行历史板块

### 1.4 关键 KPI

- [`PYTHONPATH=src pytest tests/unit/test_trigger_service.py -v` → all passed]
- [`ruff check src/services/trigger_service.py` → 0 errors]
- `check_triggers` 返回正确类型的 trigger 列表（USER_REGISTER / USER_INACTIVE / PURCHASE_MADE / CUSTOM）
- `execute_trigger` 对占位 action 返回符合格式的 dict，从不 raise 未预期异常

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - 无
- 要建：
  - `src/services/trigger_service.py` — TriggerService，含 `check_triggers` 和 `execute_trigger`
  - `src/models/trigger_types.py` — 触发条件枚举定义（USER_REGISTER / USER_INACTIVE / PURCHASE_MADE / CUSTOM）
  - `tests/unit/test_trigger_service.py` — 两个方法的单元测试
  - `src/__init__.py`（如需要 exports）

### 2.3 缺什么

- [ ] `TriggerService` 类 — 无任何 trigger 相关 service
- [ ] `check_triggers` 方法 — 各 domain service / event-listener 无法评估哪些 trigger 应触发
- [ ] `execute_trigger` 方法 — 缺少统一的 trigger 执行入口（当前无占位实现）
- [ ] trigger 类型枚举（USER_REGISTER 等）— 散落在各处或缺失，无统一类型定义

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/trigger_service.py` | TriggerService，含 `check_triggers(event_type, entity_id, tenant_id)` 和 `execute_trigger(trigger_id, tenant_id)` |
| `src/models/trigger_types.py` | TriggerEventType 枚举（USER_REGISTER / USER_INACTIVE / PURCHASE_MADE / CUSTOM） |
| `tests/unit/test_trigger_service.py` | 两个 public 方法的单元测试（MockRow / MockResult mock） |
| `src/services/__init__.py` | 新增 `TriggerService` export（如现有 `__init__.py` 存在） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | — |

### 3.3 新增能力

- **Service class**：`TriggerService(session: AsyncSession)` — 遵循 CLAUDE.md §Service Pattern，session 无默认值
- **Service method**：`check_triggers(event_type: str, entity_id: int, tenant_id: int) -> list[TriggerModel]`
- **Service method**：`execute_trigger(trigger_id: int, tenant_id: int) -> dict`
- **Enum**：`TriggerEventType` with values USER_REGISTER, USER_INACTIVE, PURCHASE_MADE, CUSTOM
- **Unit tests**：`TestTriggerService` with `test_check_triggers_returns_matching` and `test_execute_trigger_dispatches_action`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **枚举 `TriggerEventType` 放在 `src/models/trigger_types.py` 而非 service 文件内**：避免循环 import；各 domain service 和 event-handler 可以 `from src.models.trigger_types import TriggerEventType` 引用，保持清晰分层
- **占位 execute_trigger 返回 dict 而非 ORM 对象**：action 逻辑尚未实现，返回 dict 是合理的中间状态；后续替换为 `ExecutionResultModel` 时调用方无需修改签名

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 构造函数的 `session: AsyncSession` 无默认值；拒绝 None
- Service 方法错误时抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- Service 方法返回 ORM 对象（若 DB 已就绪）或 dataclass / dict（占位），**不**在 service 内调用 `.to_dict()`
- import 路径：`from models.trigger_types import TriggerEventType`，**不**用 `from src.models...`

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名禁止用 `metadata`** → 与 `Base.metadata`（MetaData 对象）冲突，类定义时 crash。触发器模型若需元数字段，用 `event_metadata`、`payload` 或 `attrs` 命名，本板块暂不建 ORM 故无此风险，但后续实现 persistence 时须注意

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 trigger 类型枚举

在 `src/models/trigger_types.py` 新建文件，定义 `TriggerEventType` 枚举。

```python
from enum import Enum


class TriggerEventType(str, Enum):
    USER_REGISTER = "USER_REGISTER"
    USER_INACTIVE = "USER_INACTIVE"
    PURCHASE_MADE = "PURCHASE_MADE"
    CUSTOM = "CUSTOM"
```

在 `src/models/__init__.py`（如存在）中添加 export。

**完成判定**：`ruff check src/models/trigger_types.py` exit 0

---

### Step 2: 创建 TriggerService 类骨架

在 `src/services/trigger_service.py` 新建文件，实现类骨架（含 `check_triggers` 和 `execute_trigger` 方法签名和 docstring）。方法体暂时返回空列表和空 dict 占位。

```python
from sqlalchemy.ext.asyncio import AsyncSession

from models.trigger_types import TriggerEventType


class TriggerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check_triggers(
        self, event_type: str, entity_id: int, tenant_id: int
    ) -> list:
        return []

    async def execute_trigger(self, trigger_id: int, tenant_id: int) -> dict:
        return {"trigger_id": trigger_id, "status": "pending"}
```

在 `src/services/__init__.py` 中添加 export。

**完成判定**：`ruff check src/services/trigger_service.py` exit 0

---

### Step 3: 实现 check_triggers 业务逻辑

在 `check_triggers` 方法中实现：根据 `event_type` 查询匹配的 trigger 记录。

逻辑：
- 根据 event_type 过滤 active trigger（`is_active = True`）
- 必须包含 `tenant_id` 过滤
- 返回匹配的 trigger 对象列表（目前为 list of dict 或 MockResult 对象）
- 支持 USER_REGISTER / USER_INACTIVE / PURCHASE_MADE / CUSTOM 四种 event_type

```python
async def check_triggers(
    self, event_type: str, entity_id: int, tenant_id: int
) -> list:
    stmt = select(Trigger).where(
        Trigger.tenant_id == tenant_id,
        Trigger.event_type == event_type,
        Trigger.is_active == True,
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_trigger_service.py -v -k check_triggers` → all passed

---

### Step 4: 实现 execute_trigger 业务逻辑

在 `execute_trigger` 方法中实现：根据 trigger_id 查询 trigger 配置，取出 action_type 和 action_payload，执行占位 action。

逻辑：
- 根据 trigger_id 和 tenant_id 查询 trigger 记录；若不存在则抛 `NotFoundException("Trigger")`
- 读取 action_type 和 action_config（占位：打 log 或 return metadata）
- 返回执行结果 dict（包含 trigger_id / action_type / status / 执行时间戳）

```python
async def execute_trigger(self, trigger_id: int, tenant_id: int) -> dict:
    stmt = select(Trigger).where(
        Trigger.id == trigger_id,
        Trigger.tenant_id == tenant_id,
    )
    result = await self.session.execute(stmt)
    trigger = result.scalar_one_or_none()
    if trigger is None:
        raise NotFoundException("Trigger")

    return {
        "trigger_id": trigger_id,
        "action_type": trigger.action_type,
        "status": "dispatched",
    }
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_trigger_service.py -v -k execute_trigger` → all passed

---

### Step 5: 编写单元测试

在 `tests/unit/test_trigger_service.py` 新建文件，定义 `mock_db_session` fixture（使用 `make_mock_session` 辅助函数），测试两个方法：

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([])  # trigger_service 无额外 handler 需求

@pytest.fixture
def trigger_service(mock_db_session):
    from services.trigger_service import TriggerService
    return TriggerService(mock_db_session)

class TestTriggerService:
    async def test_check_triggers_returns_list(self, trigger_service):
        result = await trigger_service.check_triggers("USER_REGISTER", 1, tenant_id=1)
        assert isinstance(result, list)

    async def test_execute_trigger_returns_dict(self, trigger_service):
        result = await trigger_service.execute_trigger(trigger_id=1, tenant_id=1)
        assert isinstance(result, dict)
        assert "trigger_id" in result
        assert "status" in result
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_trigger_service.py -v` → all passed

---

### Step 6: Lint + 最终验证

```bash
ruff check src/services/trigger_service.py src/models/trigger_types.py
```

**完成判定**：`ruff check src/services/trigger_service.py src/models/trigger_types.py tests/unit/test_trigger_service.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/trigger_service.py src/models/trigger_types.py tests/unit/test_trigger_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_trigger_service.py -v` → all passed
- [ ] `TriggerService` constructor accepts `session: AsyncSession` with no default
- [ ] `check_triggers` accepts `(event_type: str, entity_id: int, tenant_id: int)` and returns `list`
- [ ] `execute_trigger` accepts `(trigger_id: int, tenant_id: int)` and returns `dict`
- [ ] `TriggerEventType` enum exists with values USER_REGISTER / USER_INACTIVE / PURCHASE_MADE / CUSTOM

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `Trigger` ORM 模型尚未建好（migration 未 apply）导致 `select(Trigger)` 报错 | 中 | 中 | 单元测试使用 Mock，不依赖真实 DB；integration 测试需先确认 migration 已 apply（#457 已处理 trigger 表） |
| `Trigger` 表字段名与 service 内引用不匹配 | 低 | 高 | 按实际 ORM 列名修正 `check_triggers` 和 `execute_trigger` 中的字段引用（event_type / action_type / is_active 等） |
| 依赖 #457 的 trigger 表 migration 尚未合并阻塞 integration 测试 | 低 | 低 | 单元测试已隔离；integration 测试可延后至 #457 合并后执行 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/trigger_service.py src/models/trigger_types.py src/services/__init__.py tests/unit/test_trigger_service.py
git commit -m "feat(automation): implement TriggerService with check_triggers and execute_trigger

- add TriggerEventType enum (USER_REGISTER, USER_INACTIVE, PURCHASE_MADE, CUSTOM)
- add TriggerService.check_triggers(event_type, entity_id, tenant_id) -> list
- add TriggerService.execute_trigger(trigger_id, tenant_id) -> dict
- add unit tests

Closes #458"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): TriggerService check_triggers + execute_trigger" --body "Closes #458"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/customer_service.py` — service 模式范本
- 父 issue / 关联：#450（automation 工作流系统顶层规划）
- 上游依赖：#457（TriggerApiRouter + trigger 表 migration）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
