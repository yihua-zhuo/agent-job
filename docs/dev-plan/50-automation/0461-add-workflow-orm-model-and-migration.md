# Workflow ORM Model and Migration · Add Workflow ORM model and migration

| 元数据 | 值 |
|---|---|
| Issue | #461 |
| 分类 | [20-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [#462](../50-automation/0462-add-executionhistory-orm-model-and-migration.md), [#463](../50-automation/0463-build-workflowservice-with-crud-execute-methods.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #461 是 #449（Automation 模块）的子任务。当前数据库层没有任何 Workflow 表，无法存储自动化工作流的配置（触发条件、动作列表、启用状态）。缺少 ORM model 会导致后续的 WorkflowService、API router 和前端无法持久化任何工作流数据，所有上层开发都会因此阻塞。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动。
- **开发者视角**：`src/db/models/workflow.py` 提供 `Workflow` ORM model，可被 `WorkflowService` 直接使用；migration 自动在 PostgreSQL 创建 `workflows` 表，含 JSONB 列存储 `conditions` 和 `actions`，以及 `tenant_id` 索引。

### 1.3 不做什么（剔除）

- [ ] 不实现 WorkflowService（属于 #463）
- [ ] 不实现 Workflow API router（属于 #465）
- [ ] 不实现 ExecutionHistory model（属于 #462）
- [ ] 不在前端做任何改动

### 1.4 关键 KPI

- `ruff check src/db/models/workflow.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `psql -c "\d workflows"` 显示表含 `id`, `tenant_id`, `name`, `trigger_type`, `conditions`, `actions`, `status`, `created_at`, `updated_at`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/db/models/` 下已有 `customer.py`、`pipeline.py` 等 ORM model 可作参照。

TBD - 待验证：`src/db/models/` 下现有 model 的字段命名和 Base 继承方式

参考已有 model 结构（推断）：

```python
# src/db/models/customer.py (推断结构)
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base
import datetime

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
```

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 新增 `from db.models.workflow import Workflow` 导入行
- 要建：
  - `src/db/models/workflow.py` — Workflow ORM model
  - `alembic/versions/<id>_add_workflow_table.py` — 迁移文件（由 alembic autogenerate 生成，需人工修正）
  - `tests/unit/test_workflow_model.py` — 模型单元测试

### 2.3 缺什么

- [ ] 无 `src/db/models/workflow.py` — Workflow model 未定义
- [ ] `alembic/env.py` 未导入 Workflow — autogenerate 会漏掉该表
- [ ] 无 migration 文件 — 无法在生产/测试 DB 创建 `workflows` 表
- [ ] 无 `workflows` 表 schema — JSONB 列和 tenant_id 索引未落地

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/workflow.py` | Workflow ORM model（id, tenant_id, name, trigger_type, conditions, actions, status, created_at, updated_at） |
| `alembic/versions/<id>_add_workflow_table.py` | 创建 `workflows` 表的 migration（含 JSONB 列和 tenant_id 索引） |
| `tests/unit/test_workflow_model.py` | Workflow model 单元测试（MockRow / MockState 模式） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../alembic/env.py) | 新增 `from db.models.workflow import Workflow` 导入，使 autogenerate 能识别该 model |

### 3.3 新增能力

- **ORM model**：`Workflow` in `src/db/models/workflow.py`
- **Migration**：`alembic upgrade head` 创建 `workflows` 表（含 `tenant_id` 索引、`conditions` JSONB、`actions` JSONB、`status` 枚举/字符串、`created_at`/`updated_at` TIMESTAMPTZ）
- **测试覆盖**：`tests/unit/test_workflow_model.py` 验证 model 实例化、字段映射

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSON vs JSONB**：选 `JSONB`（`postgresql.JSONB`）而非 `JSON`。JSONB 在 PostgreSQL 内以二进制存储，支持 GIN 索引和高效包含查询，适合存储 conditions（可能需要按条件键查询）和 actions 配置。
- **trigger_type / status 存储方式**：选 `String(50)` 而非 ENUM — 减少 migration 复杂度，后续可用 ENUM 替换；初始上线足够。
- **created_at / updated_at**：选 `server_default=func.now()` + `onupdate=func.now()`（DB 侧默认值），而非 Python 侧默认值 — 防止应用层时钟漂移导致的不一致。

### 4.2 版本约束

无新外部依赖。

### 4.3 兼容性约束

- 多租户：每条记录必须含 `tenant_id`，所有查询必须 `WHERE tenant_id = :tenant_id`
- SQLAlchemy 列名禁用 `metadata`（与 `Base.metadata` 冲突） → 本 model 无此字段，不受影响
- `AsyncSession` 在 Service 层注入，model 本身无 session 依赖
- JSON 列序列化由 SQLAlchemy 负责，不在 model 层调用 `.to_dict()`

### 4.4 已知坑

1. **Alembic autogenerate 把 JSONB 写成 JSON** → 规避：migration 手动将 `sa.JSON()` 改为 `sa.JSONB()`（`from sqlalchemy.dialects.postgresql import JSONB`）
2. **Alembic autogenerate 省略 `timezone=True`** → 规避：`created_at`/`updated_at` 手动加 `timezone=True`（`DateTime(timezone=True)`），防止时区歧义
3. **Alembic autogenerate 漏掉 server_default** → 规避：检查 autogenerate 输出的 `server_default=` 是否正确，必要时手动补 `server_default=func.now()`
4. **PYTHONPATH=src** → 规避：所有 import 写 `from db.models...` 而非 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 Workflow ORM model

在 `src/db/models/workflow.py` 新建文件，内容如下：

```python
import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="inactive")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
```

**完成判定**：`PYTHONPATH=src ruff check src/db/models/workflow.py` → 0 errors

---

### Step 2: 导入 Workflow 到 alembic/env.py

在 `alembic/env.py` 的 model 导入区块新增一行：

```python
from db.models.workflow import Workflow
```

确保 import 语句与其他 `from db.models import ...` 放在一起。

**完成判定**：`grep -n "from db.models.workflow import Workflow" alembic/env.py` 输出匹配行

---

### Step 3: 生成 migration（autogenerate）

启动本地 postgres 容器（如未运行），然后执行：

```bash
# 1. 创建空的 alembic_dev DB
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. 将 alembic_dev stamp 到当前 head（不含本次 migration）
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic stamp head

# 3. autogenerate
alembic revision --autogenerate -m "add workflow table"
```

**完成判定**：`ls alembic/versions/*_add_workflow_table.py` 文件存在

---

### Step 4: 修正 migration（JSONB + timezone）

读取 autogenerate 输出的 migration 文件，手动修正：

- 将 `from sqlalchemy import JSON` 改为 `from sqlalchemy.dialects.postgresql import JSONB`
- 将 `mapped_column(JSON)` 改为 `mapped_column(JSONB)`
- 将 `DateTime` 改为 `DateTime(timezone=True)`
- 确保 `server_default=func.now()` 存在于 `created_at`

修正后的 up() 片段示例：

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("conditions", JSONB(), nullable=False),
        sa.Column("actions", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflows_tenant_id", "workflows", ["tenant_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_workflows_tenant_id", table_name="workflows")
    op.drop_table("workflows")
```

**完成判定**：`PYTHONPATH=src ruff check alembic/versions/<id>_add_workflow_table.py` → 0 errors

---

### Step 5: 验证 migration 可双向运行

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：三次命令均 exit 0

---

### Step 6: 验证表结构

```bash
docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\d workflows"
```

**完成判定**：输出含 `id`, `tenant_id`, `name`, `trigger_type`, `conditions`, `actions`, `status`, `created_at`, `updated_at`

---

### Step 7: 编写单元测试

新建 `tests/unit/test_workflow_model.py`，使用 MockState + MockRow 模式验证：

```python
import pytest
from tests.unit.conftest import MockState, MockRow, make_mock_session

# 基本结构验证：实例化 Workflow 并检查 __tablename__ 和列定义
def test_workflow_tablename():
    from db.models.workflow import Workflow
    assert Workflow.__tablename__ == "workflows"

def test_workflow_has_expected_columns():
    from db.models.workflow import Workflow
    cols = [c.name for c in Workflow.__table__.columns]
    expected = {"id", "tenant_id", "name", "trigger_type",
                "conditions", "actions", "status", "created_at", "updated_at"}
    assert set(cols) == expected

# TODO: CRUD mock 测试（参考其他 test_*.py 的 handler 写法）
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_workflow_model.py -v` → passed

---

## 6. 验收

- [ ] `ruff check src/db/models/workflow.py alembic/versions/<id>_add_workflow_table.py` → 0 errors
- [ ] `PYTHONPATH=src ruff check alembic/env.py` → 0 errors（确认 import 无语法错误）
- [ ] `PYTHONPATH=src pytest tests/unit/test_workflow_model.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\d workflows"` 输出含全部 9 个列

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogenerate 生成错误的列类型（JSON 而非 JSONB） | 高 | 高 | 人工修正 migration 后再运行（已在 Step 4 覆盖） |
| migration 漏掉 tenant_id 索引 | 中 | 高 | 人工补 `op.create_index("ix_workflows_tenant_id", ...)` |
| alembic/env.py 导入顺序导致循环依赖 | 低 | 高 | 将 `from db.models.workflow` 移到其他 db.model import 之后 |
| pytest fixture 与其他 unit test 并发冲突 | 低 | 低 | 每个 unit test 独立 MockState，无共享状态 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/workflow.py alembic/env.py alembic/versions/<id>_add_workflow_table.py tests/unit/test_workflow_model.py
git commit -m "feat(automation): add Workflow ORM model and migration

Closes #461"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add Workflow ORM model and migration (#461)" --body "Closes #461"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/customer.py` L? — 现有 CRM model 字段定义参考；`src/db/models/pipeline.py` L? — 现有 JSON 字段 model 参考
- 父 issue：#449
- 关联：#462（ExecutionHistory ORM model）、#463（WorkflowService CRUD）、#465（Workflow API router）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
