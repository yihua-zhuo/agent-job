# Automation · Add agent_tasks ORM model and database migration

| 元数据 | 值 |
|---|---|
| Issue | #620 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：后续服务层和路由所在的文档路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #42 introduces an agent-task execution system to the CRM. The first foundational piece is the persistence layer: a database table and ORM model to store agent task records. Without this, no downstream service or API can exist. The `agent_tasks` table is the source-of-truth for every task's lifecycle (pending → dispatched → running → completed/failed).

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema + ORM。
- **开发者视角**：`src/db/models/agent_tasks.py` exposes a `AgentTask` SQLAlchemy ORM model that other services (`AgentTaskService`) can import and use. The alembic migration creates the physical table with `(task_id, tenant_id)` composite index for fast lookups.

### 1.3 不做什么（剔除）

- [ ] No `AgentTaskService` class — service layer is out of scope.
- [ ] No FastAPI router / endpoint for agent tasks — API layer is out of scope.
- [ ] No seeding script or data migration.
- [ ] No background worker or queue integration.

### 1.4 关键 KPI

- `ruff check src/db/models/agent_tasks.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_agent_tasks_model.py -v` → all passed (≥ 3 cases)
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- `alembic current` after upgrade reports revision hash for the new migration (non-empty)

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待补充：检查 `src/db/models/` 目录下已有的 ORM 模型文件结构，确认父类 `Base` 导入路径、mixin 使用方式、枚举列写法。参考 `src/db/models/customers.py` 或 `src/db/models/tickets.py` 获取具体行号和字段定义模式。

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 添加 `AgentTask` model import（autogenerate 可见）
- 要建：
  - `src/db/models/agent_tasks.py` — ORM model 定义
  - `alembic/versions/<id>_create_agent_tasks_table.py` — 数据库 migration
  - `tests/unit/test_agent_tasks_model.py` — 单元测试

### 2.3 缺什么

- [ ] `src/db/models/agent_tasks.py` — 不存在，需要新建
- [ ] `alembic/versions/` 中没有 `create_agent_tasks_table` migration
- [ ] 没有 `AgentTask` ORM model 的单元测试
- [ ] `alembic/env.py` 没有 import `AgentTask`，autogenerate 不会生成对应迁移

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/agent_tasks.py` | `AgentTask` SQLAlchemy ORM model（继承 `Base`） |
| `alembic/versions/<id>_create_agent_tasks_table.py` | 创建 `agent_tasks` 表，含复合索引 |
| `tests/unit/test_agent_tasks_model.py` | 模型单元测试（mock DB） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../../alembic/env.py) | 添加 `from db.models.agent_tasks import AgentTask`（autogenerate 扫描用） |

### 3.3 新增能力

- **ORM model**：`AgentTask` in `src/db/models/agent_tasks.py` — columns: `id`, `task_id`, `tenant_id`, `description`, `status`, `subtasks`, `created_at`, `updated_at`
- **Migration**：`alembic upgrade head` 创建 `agent_tasks` 表（含 `(task_id, tenant_id)` 索引、`tenant_id` 索引）
- **Status enum**：`AgentTaskStatus` Python enum (`pending` / `dispatched` / `running` / `completed` / `failed`)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `sqlalchemy.Enum` 而非 `PostgreSQL ENUM` 类型**：避免每次修改 enum 值需要 migration；Python enum 在应用层控制，DB 存 `String`（VARCHAR），保持 migration 简单。
- **复合索引 `(task_id, tenant_id)`**：task_id 唯一但查询时同时带 tenant_id 过滤，复合索引覆盖最常见查询模式。
- **tenant_id 独立索引**：确保跨任务查询（按 tenant 筛选所有任务）不走全表扫描。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`tenant_id` 列非空，每个查询必须 `WHERE tenant_id = :tenant_id`。
- 列名禁止用 `metadata`（与 `Base.metadata` 冲突）→ 使用 `task_metadata` 或在 JSONB 列中存储。
- ORM model 文件 import 路径：`from db.models.agent_tasks import AgentTask`（`PYTHONPATH=src`）。
- Service 层返回 ORM 对象，不调用 `.to_dict()`；序列化由 router 负责（本板块暂无 router）。

### 4.4 已知坑

1. **Alembic autogenerate 把 `JSONB` 写成 `JSON`，`TIMESTAMPTZ` 写成 `DateTime`** → 手动改回：`server_default=func.now()` for timestamps.
2. **autogenerate 漏掉 enum 的 `create_type=False`** → 迁移不加 `op.create_enum(...)`，手动补 `status_server_default=text("'pending'")` 或让应用层初始化 enum。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/agent_tasks.py` ORM model

在 `src/db/models/` 下新建文件，定义 `AgentTaskStatus` enum 和 `AgentTask` ORM model。

操作：
- a) 创建 `src/db/models/agent_tasks.py`
- b) 定义 `AgentTaskStatus` Python enum（5 个值）
- c) 定义 `AgentTask(Base)` 类，映射到 `agent_tasks` 表
- d) 列：`id` (Integer PK auto-increment)、`task_id` (String, not null, indexed)、`tenant_id` (Integer, not null, index)、`description` (Text, nullable)、`status` (Enum, not null, default 'pending')、`subtasks` (JSONB, nullable)、`created_at` (TIMESTAMPTZ, not null, server_default=func.now())、`updated_at` (TIMESTAMPTZ, not null, server_default=func.now())
- e) 在 `alembic/env.py` 添加 `from db.models.agent_tasks import AgentTask`

```python
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import func, Index, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AgentTaskStatus(str, PyEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index("ix_agent_tasks_task_id_tenant_id", "task_id", "tenant_id"),
        Index("ix_agent_tasks_tenant_id", "tenant_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[int] = mapped_column(nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    subtasks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

**完成判定**：`ruff check src/db/models/agent_tasks.py` → 0 errors

---

### Step 2: 生成 Alembic migration

操作：
- a) 确保 docker compose test-db 运行：`docker compose -f configs/docker-compose.test.yml up -d test-db`
- b) 确保 alembic_dev DB 存在且在 head：
  ```
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
  ```
- c) `export PYTHONPATH=src && export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" && alembic upgrade head`
- d) `PYTHONPATH=src alembic revision --autogenerate -m "create_agent_tasks_table"`
- e) 检查 `alembic/versions/<new_rev>_create_agent_tasks_table.py`：确认列类型为 `JSONB`（不是 JSON）、`TIMESTAMP WITH TIME ZONE`（不是 DateTime）；`server_default` 存在；复合索引存在
- f) 如类型错误，手动修正迁移文件中的 `server_onupdate=func.now()` 和 JSONB

**完成判定**：`ruff check alembic/versions/<id>_create_agent_tasks_table.py` → 0 errors

---

### Step 3: 验证 migration 可双向执行

操作：
- a) `alembic downgrade -1`（回退上一条）
- b) `alembic upgrade head`（重新应用）
- c) 确认两次 exit 0
- d) 再次 `alembic downgrade -1 && alembic upgrade head` 确认可重复

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 4: 创建单元测试 `tests/unit/test_agent_tasks_model.py`

操作：
- a) 创建 `tests/unit/test_agent_tasks_model.py`
- b) 测试用例（见 §7）：
  - `test_agent_task_status_enum_values`：验证 5 个枚举值
  - `test_agent_task_columns_present`：验证 model 有所有必需列
  - `test_agent_task_default_values`：验证 status/server_default

```python
import pytest
from db.models.agent_tasks import AgentTask, AgentTaskStatus

class TestAgentTaskModel:
    def test_status_enum_values(self):
        assert AgentTaskStatus.PENDING.value == "pending"
        assert AgentTaskStatus.DISPATCHED.value == "dispatched"
        assert AgentTaskStatus.RUNNING.value == "running"
        assert AgentTaskStatus.COMPLETED.value == "completed"
        assert AgentTaskStatus.FAILED.value == "failed"

    def test_model_has_required_columns(self):
        cols = [c.name for c in AgentTask.__table__.columns]
        for col in ("id", "task_id", "tenant_id", "description", "status", "subtasks", "created_at", "updated_at"):
            assert col in cols, f"Missing column: {col}"

    def test_status_default_is_pending(self):
        col = AgentTask.__table__.columns["status"]
        assert col.server_default is not None
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_tasks_model.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/db/models/agent_tasks.py` → 0 errors
- [ ] `ruff check alembic/versions/<id>_create_agent_tasks_table.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_tasks_model.py -v` → `3 passed`
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0
- [ ] `alembic current` after upgrade reports non-empty revision hash

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogenerate 生成错误的列类型（JSON vs JSONB，DateTime vs TIMESTAMPTZ） | 中 | 中 | 手动编辑迁移文件修正类型，revert 后 re-autogenerate |
| tenant_id 索引遗漏导致跨 tenant 查询慢 | 低 | 中 | 后续添加 `CREATE INDEX CONCURRENTLY` 迁移，不阻塞下游 |
| enum server_default 未设置导致新行 status 为 NULL | 低 | 高 | 手动编辑迁移添加 `server_default="'pending'"`，再 upgrade |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/agent_tasks.py alembic/versions/<id>_create_agent_tasks_table.py alembic/env.py tests/unit/test_agent_tasks_model.py
git commit -m "feat(automation): add AgentTask ORM model and migration for issue #620

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add AgentTask ORM model and migration (#620)" --body "Closes #620

## Summary
- Add `AgentTask` SQLAlchemy ORM model in `src/db/models/agent_tasks.py`
- Add Alembic migration `create_agent_tasks_table` with composite index on (task_id, tenant_id)
- Add unit tests for model structure and enum values

## Test plan
- [ ] ruff check src/db/models/agent_tasks.py → 0 errors
- [ ] pytest tests/unit/test_agent_tasks_model.py -v → 3 passed
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/customers.py`](../../../src/db/models/customers.py) — 参照 ORM model 结构 + enum 列写法
- 父 issue / 关联：#42

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
