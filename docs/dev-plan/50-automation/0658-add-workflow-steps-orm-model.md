# 工作流步骤 · 新增 workflow_steps ORM model

| 元数据 | 值 |
|---|---|
| Issue | #658 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [工作流实例 ORM 模型](0657-add-workflow-instances-orm-model.md) |
| 启用后赋能 | 规则执行引擎与触发调度 (待定) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

工作流引擎需要记录、调度并追踪每一条工作流实例（workflow_instances）中各个步骤（step）的执行状态、配置和输出。现有的 ORM 模型只覆盖了 workflow 定义和工作流执行记录，缺少 step 粒度的持久化结构，导致无法可靠地持久化 step 配置、追踪执行时间戳、或在重启后的恢复。issue #658 要求新增 `workflow_steps` ORM model 作为 issue #651 的子任务，且依赖 issue #657 的 `workflow_instances` 模型先行完成。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层 ORM / schema 层改动。
- **开发者视角**：可实例化 `WorkflowStepModel`、持久化 step 配置及执行结果、为规则执行引擎提供查询接口。

### 1.3 不做什么（剔除）

- [ ] 不实现 step 级别的 service 层方法或 API router（留待后续板块）
- [ ] 不实现 `workflow_instances` 模型本身（由 issue #657负责）

### 1.4 关键 KPI

- `ruff check src/db/models/workflow.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models.workflow import WorkflowStepModel; print('ok')"` → `ok`（模块可导入）
- `alembic revision --autogenerate -m "add workflow_steps table"` 后检查 migration 文件含 `op.create_table('workflow_steps')`

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/db/models/workflow.py`](../../src/db/models/workflow.py) L{1}-L{76}

现有文件仅包含 `WorkflowModel` 和 `WorkflowExecutionModel`。`WorkflowExecutionModel` 的 `workflow_id` FK指向 `workflows.id`，但两个模型均不持有 step 相关字段或关联。

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/workflow.py`](../../src/db/models/workflow.py) — 新增 `WorkflowStepModel` 类 及 `to_dict()`
  - [`alembic/env.py`](../../alembic/env.py) —确认 `import db.models` 已覆盖（需验证 `workflow.py` 在 `db/models/__init__.py` 导入链中）
- 要建：
  - `alembic/versions/<id>_add_workflow_steps_table.py` — 迁移文件### 2.3 缺什么

- [ ] `WorkflowStepModel` ORM model — 无 step粒度的持久化结构
- [ ] `workflow_steps` 数据库表（含外键、索引、JSONB 字段、时间戳）
- [ ] `instance_id` FK 到 `workflow_instances`（issue #657 引入）的约束- [ ] `step_type` 和 `status` 两字段的 SQL级别 ENUM 或 CHECK 约束（可留待迁移中以 String代替逐步收紧）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_workflow_steps_table.py` | 创建 `workflow_steps` 表迁移 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/workflow.py`](../../src/db/models/workflow.py) | 新增 `WorkflowStepModel` 类，含全部字段定义和 `to_dict()` |
| [`alembic/env.py`](../../alembic/env.py) | 无需改动（`import db.models` 已覆盖 `workflow.py`） |

### 3.3 新增能力

- **ORM model**：`WorkflowStepModel` in `src/db/models/workflow.py`
- **Migration**：`alembic upgrade head` 创建 `workflow_steps` 表（含 `tenant_id`、`instance_id` 索引及 FK约束）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSONB 而非 JSON**：PostgreSQL JSONB 列支持索引（七文索引、GIN），适合 `config` 和 `output` 字段后续扩展查询场景，选 JSONB 而不选 JSON。
- **String 列而非 PostgreSQL ENUM**：平台 ENUM 类型迁移复杂度高（修改需 DDL + cast）；step_type 和 status 均可在应用层以 String存储，保留率由业务代码控制，降低迁移成本。

### 4.2 版本约束

无新增第三方依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- FK `instance_id` 指向 `workflow_instances.id`，on-delete行为取决于 issue #657 是否指定 CASCADE；若无明确要求，保守使用 `SET NULL`（step独立留存）或在迁移中统一为 `CASCADE`（与平台其他模型一致）
- `executed_at` / `completed_at` 使用 `DateTime(timezone=True)` + `server_default=func.now()` 与平台其他模型保持一致
- `config` / `output` 字段默认值 `dict`（非 list），避免序列化不一致### 4.4 已知坑

1. **Alembic autogen 将 JSONB写成 JSON、将 TIMESTAMPTZ 写成 DateTime** → 规避：迁移文件生成后手动检查，将 `JSON().with_variant(...)` 改回 `JSONB()`，将 `DateTime` 改为 `DateTime(timezone=True)`
2. **SQLAlchemy Base 子类的列名不能用 `metadata`**（与 `Base.metadata`冲突）→ 本板块字段名均不含 `metadata` 关键字，无风险

---

## 5. 实现步骤（按顺序）

### Step 1: 实现 WorkflowStepModel ORM model

在 `src/db/models/workflow.py` 末尾添加 `WorkflowStepModel` 类：

```python
class WorkflowStepModel(Base):
    """Workflow step record mapped to the `workflow_steps` table."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        Index("ix_workflow_steps_tenant_instance", "tenant_id", "instance_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "instance_id": self.instance_id,
            "step_type": self.step_type,
            "step_order": self.step_order,
            "config": self.config or {},
            "status": self.status,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output": self.output,
 }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.workflow import WorkflowStepModel; print('ok')"` → 输出 `ok`，无 `ImportError`

### Step 2: 验证 `db.models`导入链覆盖新模型

确认 `src/db/models/__init__.py`（或通过 `import db.models`间接）已导入 `workflow.py`。当前 alembic/env.py 使用 `import db.models`，因此模块只要在 `src/db/models/` 下即被覆盖，无需额外 import 行。

**完成判定**：`PYTHONPATH=src python -c "import db.models; from db.models.workflow import WorkflowStepModel; print('covered')"` → 输出 `covered`

### Step 3: 生成 Alembic 迁移文件

在干净 DB（`alembic_dev`）上运行 autogenerate：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade head
alembic revision --autogenerate -m "add workflow_steps table"
```

**完成判定**：生成的迁移文件 `alembic/versions/<id>_add_workflow_steps_table.py` 含 `op.create_table('workflow_steps')`

### Step 4: 修正 autogenerate 偏差并验证迁移

打开生成的迁移文件，检查并修正：

- `JSON().with_variant(...)` → 改回 `JSONB()`
- `DateTime` → `DateTime(timezone=True)`
- 确认 `tenant_id`、`instance_id` 上有 `Index`
- 确认 `ForeignKey('workflow_instances.id', ondelete='CASCADE')` 存在

然后验证双向：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：三次命令均 exit 0

### Step 5: 清理 drift-check 空迁移

```bash
alembic revision --autogenerate -m "drift_check"
```

若生成文件 `upgrades`/`downgrades` 均只有 `pass`，删除该文件。

**完成判定**：`ls alembic/versions/ | grep drift_check` 无结果，或 drift_check 文件仅含 `pass`

### Step 6: lint + type check

```bash
ruff check src/db/models/workflow.py
ruff format --check src/db/models/workflow.py
```

**完成判定**：两命令均 exit 0

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.workflow import WorkflowStepModel; print('ok')"` → `ok`
- [ ] `PYTHONPATH=src python -c "import db.models; from db.models.workflow import WorkflowStepModel; print('covered')"` → `covered`
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 生成的迁移文件中 `upgrade` 含 `create_table('workflow_steps')`，含 `ForeignKey` 指向 `workflow_instances`，且 JSON 列类型为 `JSONB`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| issue #657 的 `workflow_instances` 模型尚未合并，导致 FK 引用表不存在 Alembic 报错 | 中 | 中 |暂不加 FK约束（`(nullable=True, index=True)`），待 #657 落地后发单独 migration 添加 FK |
| Alembic autogen 对 JSONB / TIMESTAMPTZ 抽像不准确导致迁移后应用层序列化失败 | 低 | 中 | Step 4 手动修正 JSONB → JSON / DateTime → DateTime(timezone=True) 后提交 |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/db/models/workflow.py alembic/versions/
git commit -m "feat(automation): add WorkflowStepModel and workflow_steps migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#658): add workflow_steps ORM model" --body "Closes #658"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/workflow.py`](../../src/db/models/workflow.py)
- 同类参考实现：[`src/db/models/automation.py`](../../src/db/models/automation.py)
- 父 issue / 关联：#651- 依赖：#657
