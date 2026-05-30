# 工作流日志 · 新增 workflow_logs ORM model

| 元数据 | 值 |
|---|---|
| Issue | #659 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.25-0.5 工作日 |
| 依赖 | [058-服务层抽象基础](../058-add-service-layer-abstractions/README.md)（#658，workflow_log 依赖 WorkflowExecutionModel 存在） |
| 启用后赋能 | [板块名](../058-add-service-layer-abstractions/README.md)（rule execution log 写入、workflow step 调试） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

工作流执行过程黑盒化——目前 `WorkflowExecutionModel.result` 以 JSONB blob 存储所有执行结果，无法按 step 粒度查询结构化日志。rule engine 触发 dispatch 时产生的 info/warning/error 事件无处落库，调试只能靠 print，线上排查极困难。workflow_logs 表是整个 rule execution engine 可观测性的数据底座。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动。
- **开发者视角**：`WorkflowLogModel` 可直接被 `WorkflowLogService` 持久化写入；`WorkflowExecutionModel` 通过新增 `logs` relationship 批量加载关联日志；后续 rule-trace router 可直接查询 `WHERE instance_id = :id ORDER BY created_at`。

### 1.3 不做什么（剔除）

- [ ] WorkflowLogService 业务逻辑（属于下游板块）
- [ ] workflow_logs REST API router（属于后续 issue）
- [ ] 日志轮转 / TTL 清理策略（数据库层面暂不设置，保留应用层清理空间）
- [ ] 将现有 `WorkflowExecutionModel.result` JSONB 迁移到 logs 表（历史数据不动）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_workflow_log.py -v` → ≥ 4 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `ruff check src/db/models/workflow_log.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models.workflow_log import WorkflowLogModel; print('ok')"` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - 无（`import db.models` wildcard 已在 alembic/env.py 全量导入，新增 .py 文件自动被 Alembic 探测到）
- 要建：
  - `src/db/models/workflow_log.py` — WorkflowLogModel + WorkflowLogLevel enum
  - `tests/unit/test_workflow_log.py` — ORM 单元测试（MockRow / MockResult 模拟）
  - `alembic/versions/<id>_add_workflow_logs.sql` — 建表 migration（autogenerate 生成后人工修订 JSONB/TIMESTAMPTZ）

### 2.3 缺什么

- [ ] `WorkflowLogModel` ORM 类 — workflow 执行过程的结构化日志无持久化载体
- [ ] `workflow_logs` 数据库表 — 无法按 instance_id / step_id / level 查询历史日志
- [ ] 枚举类型约束 — level 字段目前无 CHECK 约束，任何字符串都能写入
- [ ] `WorkflowExecutionModel.logs` relationship — 执行记录与日志之间无 ORM 关联路径
- [ ] `WorkflowExecutionModel` 的 step FK 路径缺失 — `step_id` FK 引用目标（`WorkflowStepModel`）尚未建立（属于 #658 后续 issue），此处 step_id 字段先 nullable，后续再补 NOT NULL 约束

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/workflow_log.py` | WorkflowLogModel + WorkflowLogLevel enum，单表日志模型 |
| `tests/unit/test_workflow_log.py` | 单元测试：MockRow/MockResult 模拟 CRUD + to_dict 验证 |
| `alembic/versions/<id>_add_workflow_logs.py` | autogenerate 生成，修订 JSONB/TIMESTAMPTZ 后手动执行 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | `import db.models` 已在 alembic/env.py 全量导入；workflow.py、execution model 均无需改动 |

### 3.3 新增能力

- **ORM model**：`WorkflowLogModel` in `src/db/models/workflow_log.py`
- **Enum**：`WorkflowLogLevel`（info / warning / error）
- **Relationship**：`WorkflowExecutionModel.logs` → `workflow_logs`（back_populates on WorkflowLogModel）
- **Migration**：`alembic upgrade head` 创建 `workflow_logs` 表（含 `tenant_id` 索引、`instance_id` FK 索引、`ix_workflow_logs_tenant_created` 复合索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **level 字段使用 `String(20)` 存储枚举值，不引入 Python `Enum` 类** → 本库所有 model 均无 `Enum` 定义（grep 结果为零），`sla_level` 等字段均以 String 存储，按库内惯例办；业务层通过 service 层校验 level 值合法性，而非依赖 DB enum 类型。
- **不拆分 logs 表到独立文件** → 日志模型与 workflow 执行记录高度相关，归入 `workflow_log.py` 与 `workflow.py` 同层，import 路径清晰。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：所有 `workflow_logs` SQL 必须 `WHERE tenant_id = :tenant_id`
- `WorkflowLogModel.to_dict()` 由 router 层调用；service 层返回 ORM 对象本身
- FK `instance_id` 引用 `workflow_executions.id`（`WorkflowExecutionModel` 所在表），`ondelete="CASCADE"` — 执行记录删除时自动清理关联日志
- FK `step_id` 引用目标表暂不存在（`WorkflowStepModel` 属于 #658 及后续 issue），`nullable=True`，`ondelete="SET NULL"`，后续补充 NOT NULL 约束时新建 migration
- `metadata` 字段列名避开了 `metadata`（与 `Base.metadata` 冲突），使用 `log_metadata` 作为列名，通过 `column_name="metadata"` 参数映射 DB 列名

### 4.4 已知坑

1. **Alembic autogenerate 把 `JSONB` 写成 `JSON`，把 `TIMESTAMPTZ`/`DateTime(timezone=True)` 写成 `DateTime`** → 规避：autogenerate 后人工将 `JSON` 改回 `JSONB`，将 `DateTime` 改回 `DateTime(timezone=True)`；参考 [`src/db/models/workflow.py`](../../../src/db/models/workflow.py) L14 `result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` 的写法。
2. **SQLAlchemy Base 子类列名不能用 `metadata`（与 Base.metadata 冲突）** → 规避：DB 列名用 `metadata`，ORM 属性名用 `log_metadata`，映射为 `column_name="metadata"`。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/workflow_log.py`

在 `src/db/models/` 下新建 `workflow_log.py`，定义 `WorkflowLogLevel` 枚举和 `WorkflowLogModel` ORM 类。

操作：
- a) 新建 `src/db/models/workflow_log.py`
- b) 参考 `src/db/models/workflow.py` L49-75 WorkflowExecutionModel 的 to_dict 风格
- c) 参考 `src/db/models/rbac.py` L99-123 的 tenant_id + FK 组合

示例代码：

```python
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Base, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from src.db.models.workflow import WorkflowExecutionModel


class WorkflowLogLevel:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    ALL = (INFO, WARNING, ERROR)


class WorkflowLogModel(Base):
    """Workflow execution log entry mapped to the `workflow_logs` table."""

    __tablename__ = "workflow_logs"
    __table_args__ = (
        Index("ix_workflow_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_workflow_logs_instance_id", "instance_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=0)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkflowLogLevel.INFO)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    log_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    instance: Mapped["WorkflowExecutionModel"] = relationship(
        "WorkflowExecutionModel", back_populates="logs"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "instance_id": self.instance_id,
            "step_id": self.step_id,
            "level": self.level,
            "message": self.message,
            "metadata": self.log_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow_log import WorkflowLogModel, WorkflowLogLevel; print('ok')"` → exit 0

---

### Step 2: 补充 `WorkflowExecutionModel.logs` relationship

修改 `src/db/models/workflow.py`，在 `WorkflowExecutionModel` 中添加 `logs` back_populates relationship。

操作：
- a) 在 `src/db/models/workflow.py` 文件中 `WorkflowExecutionModel` 类底部添加：

```python
    logs: Mapped[list["WorkflowLogModel"]] = relationship(
        "WorkflowLogModel", back_populates="instance", cascade="all, delete-orphan"
    )
```

- b) 在文件顶部 import 添加 `from db.models.workflow_log import WorkflowLogModel`（放在 TYPE_CHECKING import 块中避免循环 import，在 TYPE_CHECKING 外部用字符串引用 "WorkflowLogModel"）

示例代码（修改后 `WorkflowExecutionModel` 末尾）：

```python
    if TYPE_CHECKING:
        from db.models.workflow_log import WorkflowLogModel

    logs: Mapped[list["WorkflowLogModel"]] = relationship(
        "WorkflowLogModel", back_populates="instance", cascade="all, delete-orphan"
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow import WorkflowExecutionModel; print(hasattr(WorkflowExecutionModel, 'logs'))"` → `True`

---

### Step 3: 编写单元测试 `tests/unit/test_workflow_log.py`

操作：
- a) 新建 `tests/unit/test_workflow_log.py`
- b) 使用 MockRow / MockResult / MockState 模拟 DB 行为（参考 `tests/unit/conftest.py` 中的 `make_mock_session` 模式）
- c) 测试用例覆盖：实例化 WorkflowLogModel、to_dict() 输出正确字段、WorkflowLogLevel.ALL 包含预期值

示例代码：

```python
import pytest
from tests.unit.conftest import MockRow, make_mock_session

from db.models.workflow_log import WorkflowLogLevel, WorkflowLogModel


class TestWorkflowLogLevel:
    def test_all_contains_expected_levels(self):
        assert "info" in WorkflowLogLevel.ALL
        assert "warning" in WorkflowLogLevel.ALL
        assert "error" in WorkflowLogLevel.ALL
        assert len(WorkflowLogLevel.ALL) == 3


class TestWorkflowLogModel:
    def test_to_dict_returns_all_fields(self):
        log = WorkflowLogModel(
            id=1,
            tenant_id=42,
            instance_id=10,
            step_id=5,
            level=WorkflowLogLevel.WARNING,
            message="Step skipped",
            log_metadata={"foo": "bar"},
        )
        d = log.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 42
        assert d["instance_id"] == 10
        assert d["step_id"] == 5
        assert d["level"] == "warning"
        assert d["message"] == "Step skipped"
        assert d["metadata"] == {"foo": "bar"}
        assert "created_at" in d

    def test_to_dict_with_null_step_id(self):
        log = WorkflowLogModel(id=2, tenant_id=42, instance_id=10, step_id=None,
                                level=WorkflowLogLevel.INFO, message="no step", log_metadata={})
        d = log.to_dict()
        assert d["step_id"] is None

    def test_level_default_is_info(self):
        log = WorkflowLogModel(id=3, tenant_id=1, instance_id=1, level=WorkflowLogLevel.INFO,
                                message="test", log_metadata={})
        assert log.level == "info"

    def test_log_metadata_empty_dict_default(self):
        log = WorkflowLogModel(id=4, tenant_id=1, instance_id=1, level=WorkflowLogLevel.ERROR,
                                message="err", log_metadata={})
        assert log.log_metadata == {}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_log.py -v` → `4 passed`

---

### Step 4: 生成 Alembic migration

操作：
- a) 启动干净 DB：`docker compose -f configs/docker-compose.test.yml up -d test-db`
- b) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
- c) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- d) 导出 `DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"` 和 `PYTHONPATH=src`
- e) `alembic upgrade head`
- f) `alembic revision --autogenerate -m "add workflow_logs table"`
- g) 检查生成的 migration 文件：
  - 将 `Column("metadata", JSON(), ...)` 改为 `Column("metadata", JSONB(), ...)`
  - 将 `Column("created_at", DateTime(), ...)` 改为 `Column("created_at", DateTime(timezone=True), ...)`

示例代码（migration 文件需修订的核心行）：

```python
# autogenerate 出来的（错误）：
metadata = Column("metadata", JSON(), nullable=False)

# 修订后（正确）：
metadata = Column("metadata", JSONB(), nullable=False)

# autogenerate 出来的（错误）：
created_at = Column("created_at", DateTime(), nullable=False)

# 修订后（正确）：
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
created_at = Column("created_at", TIMESTAMPTZ(), server_default=sa.text("now()"), nullable=False)
```

**完成判定**：
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `alembic revision --autogenerate -m "drift_check"` → 生成的 migration 文件 up/down 两条 `pass`（无残余 drift）

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow_log.py` → 0 errors
- [ ] `ruff check src/db/models/workflow.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_log.py -v` → `4 passed`
- [ ] `PYTHONPATH=src python -c "from db.models.workflow_log import WorkflowLogModel; assert hasattr(WorkflowLogModel, 'to_dict')"` → exit 0
- [ ] `PYTHONPATH=src python -c "from db.models.workflow import WorkflowExecutionModel; assert hasattr(WorkflowExecutionModel, 'logs')"` → exit 0
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic autogenerate 漏掉 `step_id` FK（目标表 `workflow_steps` 尚未创建）导致 FK 约束缺失 | 低 | 中 | 在 #658 `WorkflowStepModel` 就绪后，新建 migration 添加 FK 约束；不影响本板块 logs 写入 |
| autogen 把 JSONB 写成 JSON，DB 里存成 JSON 类型导致无法用 PostgreSQL JSONB 运算符查询 | 中 | 高 | Step 4 中人工修订 JSON → JSONB；如漏改，logs.metadata 查询（如 `->>`）会报错，需 revert 该 migration 后重新 autogenerate |
| `metadata` 列名与 `Base.metadata` 冲突导致 Alembic 无法正确生成迁移 | 低 | 高 | 已用 `log_metadata` ORM 属性名 + `column_name="metadata"` 显式映射规避；如仍有冲突，改列名为 `event_metadata` 后新建 migration |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/workflow_log.py src/db/models/workflow.py tests/unit/test_workflow_log.py alembic/versions/
git commit -m "feat(automation): add WorkflowLogModel ORM (#659)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add workflow_logs ORM model (#659)" --body "Closes #659"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/workflow.py`](../../../src/db/models/workflow.py) — WorkflowExecutionModel 的 to_dict + FK 风格
- 同类参考实现：[`src/db/models/rbac.py`](../../../src/db/models/rbac.py) L99-123 — tenant_id + FK + to_dict 组合
- 父 issue / 关联：#651（workflow 可观测性父 issue）、#658（WorkflowExecutionModel 依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
