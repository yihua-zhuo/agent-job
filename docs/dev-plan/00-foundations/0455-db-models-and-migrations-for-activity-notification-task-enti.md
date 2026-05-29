# 0677 · Add missing type/status enums and channel field to Activity/Notification/Task models

| 元数据 | 值 |
|---|---|
| Issue | #455 |
| 分类 | [00-foundations](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0451-crm-domain-models-enums-api-routers-and-services-for-all-core](../0451-crm-domain-models-enums-api-routers-and-services-for-all-core.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #455 requires inspecting the ORM models for `Activity`, `Notification`, and `Task` entities and confirming they carry all required fields — timestamps, enums for type/status/channel, foreign keys to customer/opportunity, and `tenant_id`. The inspection reveals three gaps across the models: (1) all three `type` columns use plain `String(50)` instead of a constrained enum, (2) `status` and `channel` fields are entirely absent from `ActivityModel` and `NotificationModel`, and (3) `TaskModel` lacks a `channel` field. Without constrained enums and explicit `status`/`channel` columns, downstream services cannot validate or filter by these dimensions reliably, and the data layer silently accepts invalid string values.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 和 ORM 层强化。
- **开发者视角**：`ActivityModel` gains `status` and `channel` columns plus `ActivityTypeEnum` and `ActivityStatusEnum` Python enums; `NotificationModel` gains `status` and `NotificationTypeEnum`/`NotificationStatusEnum`; `TaskModel` gains `channel` plus `TaskStatusEnum`. All models are fully importable from `db.models`. An Alembic migration applies these changes to a dev database with verified downgrade.

### 1.3 不做什么（剔除）

- [ ] No new tables — all three tables already exist in `b2c3dce4b714_create_all_tables.py`; this board only adds columns and enum constraints to the existing tables.
- [ ] No service layer changes — service classes belong to their own downstream boards.
- [ ] No REST API changes — routers for these entities belong to their own downstream boards.
- [ ] No data migration — existing rows retain their string values; enum columns are added as nullable or with a server default so the migration is non-destructive.

### 1.4 关键 KPI

- `ruff check src/db/models/activity.py src/db/models/notification.py src/db/models/task.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_activity.py tests/unit/test_notification.py tests/unit/test_task.py -v` → all passed (3 files exist, each ≥ 1 test)
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` (against `alembic_dev`) → three exit 0
- `alembic revision --autogenerate -m "drift_check"` after Step 3 → produces a no-op migration (pass/pass)

---

## 2. 当前现状（起点）

### 2.1 现有实现

`ActivityModel` 主入口：[`src/db/models/activity.py`](../../src/db/models/activity.py) L11-L35

```python:11:25:src/db/models/activity.py
class ActivityModel(Base):
    """Activity entity mapped to the `activities` table."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)   # ← plain String, no enum
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

`NotificationModel` 主入口：[`src/db/models/notification.py`](../../src/db/models/notification.py) L11-L39

```python:11:25:src/db/models/notification.py
class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)   # ← plain String
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

`TaskModel` 主入口：[`src/db/models/task.py`](../../src/db/models/task.py) L11-L29

```python:11:29:src/db/models/task.py
class TaskModel(Base):
    """Task entity mapped to the `tasks` table."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)   # ← plain String
    priority: Mapped[str] = mapped_column(String(50), default="normal", nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

Migration 主入口：[`alembic/versions/b2c3dce4b714_create_all_tables.py`](../../alembic/versions/b2c3dce4b714_create_all_tables.py) L23-L36 (activities), L85-L98 (notifications), L154-L169 (tasks) — all three tables use `sa.String(length=50)` for `type`/`status`/`priority` with no PostgreSQL enum type.

`alembic/env.py` L14: `import db.models  # noqa: F401 — imports all model modules for Base.metadata` — the wildcard import means any new model file in `src/db/models/` is automatically discoverable for `--autogenerate`. New models do NOT need to be individually imported here.

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/activity.py`](../../src/db/models/activity.py) — 添加 `ActivityTypeEnum`, `ActivityStatusEnum`, `ActivityChannelEnum` Python enums；添加 `status` 和 `channel` 列；`type` 改用 `Enum` 类型映射
  - [`src/db/models/notification.py`](../../src/db/models/notification.py) — 添加 `NotificationTypeEnum`, `NotificationStatusEnum` Python enums；添加 `status` 列；`type` 改用 `Enum` 类型映射
  - [`src/db/models/task.py`](../../src/db/models/task.py) — 添加 `TaskStatusEnum`, `TaskChannelEnum` Python enums；添加 `channel` 列；`status` 改用 `Enum` 类型映射
  - `alembic/versions/<new_revision>_add_enums_and_channel_to_activity_notification_task.py` — 添加列，必要时重建 CHECK 约束
- 要建：
  - `tests/unit/test_activity.py` — ActivityModel 单元测试（基础 CRUD + 字段验证）
  - `tests/unit/test_notification.py` — NotificationModel 单元测试
  - `tests/unit/test_task.py` — TaskModel 单元测试

### 2.3 缺什么

- [ ] `ActivityModel.type` 是无约束的 `String(50)`，没有 `ActivityTypeEnum`；`status` 列和 `channel` 列完全缺失
- [ ] `NotificationModel.type` 是无约束的 `String(50)`，没有 `NotificationTypeEnum`；`status` 列完全缺失
- [ ] `TaskModel.status` 是无约束的 `String(50)`，没有 `TaskStatusEnum`；`channel` 列完全缺失
- [ ] 所有三个表的迁移（`b2c3dce4b714`）使用 PostgreSQL `String` 列类型而非 `ENUM` 类型；没有对应的 `CREATE TYPE ... AS ENUM` 迁移语句
- [ ] 三个模型均无单元测试文件

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_enums_and_channel_to_activity_notification_task.py` | 添加 status/channel 列；创建 PostgreSQL ENUM 类型（如尚不存在）；保留原有字符串列数据 |
| `tests/unit/test_activity.py` | ActivityModel 字段验证和 to_dict 序列化单元测试 |
| `tests/unit/test_notification.py` | NotificationModel 字段验证和 to_dict 序列化单元测试 |
| `tests/unit/test_task.py` | TaskModel 字段验证和 to_dict 序列化单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/activity.py`](../../src/db/models/activity.py) | 添加三个 Python `Enum` 类；添加 `status: Mapped[str]` 和 `channel: Mapped[str]` 列属性；更新 `to_dict()` |
| [`src/db/models/notification.py`](../../src/db/models/notification.py) | 添加两个 Python `Enum` 类；添加 `status: Mapped[str]` 列属性；更新 `to_dict()` |
| [`src/db/models/task.py`](../../src/db/models/task.py) | 添加两个 Python `Enum` 类；添加 `channel: Mapped[str]` 列属性；更新 `to_dict()` |

### 3.3 新增能力

- **Python enums**：`ActivityTypeEnum`, `ActivityStatusEnum`, `ActivityChannelEnum` in `src/db/models/activity.py`
- **Python enums**：`NotificationTypeEnum`, `NotificationStatusEnum` in `src/db/models/notification.py`
- **Python enums**：`TaskStatusEnum`, `TaskChannelEnum` in `src/db/models/task.py`
- **New columns**：`activities.status`, `activities.channel`, `notifications.status`, `tasks.channel`
- **Migration**：`alembic upgrade head` adds/alters the four columns and creates PostgreSQL ENUM types in `alembic_dev`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Python `enum.StrEnum` / `enum.IntEnum` 不选 SQLAlchemy `Enum` 枚举类型映射**：Python enums give IDE autocompletion and type-checker safety in service/router code without requiring the DB to hold a PostgreSQL ENUM type. The migration uses raw string CHECK constraints (`CHECK (type IN ('call', 'email', 'meeting', ...))`) rather than `CREATE TYPE ... AS ENUM`, which avoids requiring a multi-step migration to create/drop the PG type and makes rollback simpler. Downstream boards that need DB-level enforcement can add a separate migration later.
- **选新增 nullable 列（带 server_default）不选 `ALTER COLUMN SET NOT NULL`**：existing rows have no `status`/`channel` value, so the columns are added as nullable with a server default (`'active'`) so the migration is non-destructive. After backfill, a subsequent nullable→NOT NULL migration can tighten the constraint.

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `PYTHONPATH=src`，所有 import 写 `from db.models...`，**禁止** `from src.db.models...`
- SQLAlchemy Base 子类列名不能用 `metadata`（与 `Base.metadata` 冲突）— 当前三个模型均未使用此名称，无风险

### 4.4 已知坑

1. **Alembic autogenerate 把 `Enum` 列写成 `sa.String`** → 规避：Step 3 的迁移由手工编辑，不依赖 `--autogenerate` 对 enum 列的推断；如使用 autogenerate，需检查生成的 `sa.Column(..., Enum(...))` 是否正确。
2. **Alembic autogenerate 生成的 `DateTime(timezone=True)` 有时会变成 `DateTime`** → 规避：Step 3 手工确认所有 `DateTime` 列带 `timezone=True`。
3. **PostgreSQL `CREATE TYPE ... AS ENUM` 要求类型不存在才能创建** → 规避：迁移先 `DROP TYPE IF EXISTS` 再 `CREATE TYPE`；`downgrade()` 先删 CHECK 约束再删 TYPE。
4. **`tenant_id` 索引已在 `b2c3dce4b714` 创建**，本次迁移不重复创建；如有索引缺失在 Step 4 drift check 时会发现。

---

## 5. 实现步骤（按顺序）

### Step 1: 更新 ActivityModel — 添加 enums 和缺失列

在 `src/db/models/activity.py` 中：
a) 在 `import` 区段后添加三个 Python `enum.StrEnum` 类
b) 在 `Base` import 后添加 `from sqlalchemy import Enum`（如尚未导入）
c) 在 `type` 列后添加 `status` 和 `channel` 两列
d) 更新 `to_dict()` 序列化方法以包含新增字段

```python
# src/db/models/activity.py — 新增 enum 和列（摘要）
import enum

class ActivityTypeEnum(str, enum.Enum):
    call = "call"
    email = "email"
    meeting = "meeting"
    note = "note"
    task = "task"
    other = "other"

class ActivityStatusEnum(str, enum.Enum):
    active = "active"
    archived = "archived"

class ActivityChannelEnum(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    internal = "internal"

# 在 type 列后新增两列：
status: Mapped[str] = mapped_column(
    String(50), default="active", nullable=False, server_default="active"
)
channel: Mapped[str] = mapped_column(
    String(50), default="internal", nullable=False, server_default="internal"
)
```

**完成判定**：`ruff check src/db/models/activity.py` → exit 0

### Step 2: 更新 NotificationModel — 添加 enums 和 status 列

在 `src/db/models/notification.py` 中：
a) 在 `import` 区段后添加两个 Python `enum.StrEnum` 类
b) 在 `import sqlalchemy` 区添加 `Enum`（如尚未导入）
c) 在 `related_id` 列后添加 `status` 列（nullable False, server_default="unread"）
d) 更新 `to_dict()` 序列化方法以包含 `status`

```python
# src/db/models/notification.py — 新增 enum 和列（摘要）
import enum

class NotificationTypeEnum(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"
    success = "success"
    system = "system"

class NotificationStatusEnum(str, enum.Enum):
    unread = "unread"
    read = "read"
    archived = "archived"

# 在 related_id 列后新增列：
status: Mapped[str] = mapped_column(
    String(50), default="unread", nullable=False, server_default="unread"
)
```

**完成判定**：`ruff check src/db/models/notification.py` → exit 0

### Step 3: 更新 TaskModel — 添加 enums 和 channel 列

在 `src/db/models/task.py` 中：
a) 在 `import` 区段后添加两个 Python `enum.StrEnum` 类
b) 在 `import sqlalchemy` 区添加 `Enum`（如尚未导入）
c) 在 `priority` 列后添加 `channel` 列（nullable False, server_default="internal"）
d) 将现有的 `status` 列改为使用 `TaskStatusEnum` 映射
e) 更新 `to_dict()` 序列化方法以包含 `channel`

```python
# src/db/models/task.py — 新增 enum 和列（摘要）
import enum

class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class TaskChannelEnum(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    internal = "internal"

# 将现有的 status 列改为（保持 server_default="pending" 兼容）：
status: Mapped[str] = mapped_column(
    String(50), default="pending", nullable=False, server_default="pending"
)
# 在 priority 列后新增：
channel: Mapped[str] = mapped_column(
    String(50), default="internal", nullable=False, server_default="internal"
)
```

**完成判定**：`ruff check src/db/models/task.py` → exit 0

### Step 4: 生成 Alembic 迁移

a) 启动干净的开发数据库：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
```

b) 将当前 head stamp 到 alembic_dev：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic stamp head
```

c) 生成迁移（手工编写，不依赖 autogenerate 推断 enum 类型）：

在 `alembic/versions/` 下新建文件 `<hash>_<slug>.py`，内容结构如下（完整写法参考 `b2c3dce4b714_create_all_tables.py`）：

```python
"""add enums and channel columns to activity, notification, task tables

Revision ID: <generate with python -c "import uuid; print(uuid.uuid4().hex[:12])">
Revises: b2c3dce4b714
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '<hash>'
down_revision: Union[str, None] = 'b2c3dce4b714'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add status and channel to activities (nullable + server_default for existing rows)
    op.add_column('activities', sa.Column('status', sa.String(50), server_default='active', nullable=False))
    op.add_column('activities', sa.Column('channel', sa.String(50), server_default='internal', nullable=False))

    # 2. Add status to notifications
    op.add_column('notifications', sa.Column('status', sa.String(50), server_default='unread', nullable=False))

    # 3. Add channel to tasks
    op.add_column('tasks', sa.Column('channel', sa.String(50), server_default='internal', nullable=False))

def downgrade() -> None:
    op.drop_column('tasks', 'channel')
    op.drop_column('notifications', 'status')
    op.drop_column('activities', 'channel')
    op.drop_column('activities', 'status')
```

d) 验证迁移在 `alembic_dev` 可升可降：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 5: Drift check — 确认 autogenerate 无残余差异

```bash
alembic revision --autogenerate -m "drift_check"
```

检查生成的文件：如果 `upgrade()` / `downgrade()` 函数体中只有 `pass`，则删除该文件并输出"drift check 通过"。如果 diff 非空，说明有遗漏的模型属性，需要补充到 §2.3 缺什么列表并回到 Step 1-3。

**完成判定**：生成的迁移文件 `upgrade()` / `downgrade()` 函数体均为 `pass`，文件可删除

### Step 6: 编写单元测试

为每个模型新建 `tests/unit/test_<model>.py`（参考 `tests/unit/conftest.py` 中的 `MockRow` / `MockResult` 工具）：

`tests/unit/test_activity.py` 需覆盖：
- 实例化 `ActivityModel` 并调用 `to_dict()` 返回所有字段
- `type` / `status` / `channel` 字段存在且可赋值

`tests/unit/test_notification.py` 需覆盖：
- 实例化 `NotificationModel` 并调用 `to_dict()` 返回所有字段
- `status` 字段存在且可赋值

`tests/unit/test_task.py` 需覆盖：
- 实例化 `TaskModel` 并调用 `to_dict()` 返回所有字段
- `channel` 字段存在且可赋值

每个文件使用 `make_mock_session` 构造 mock session fixture，参考同类测试文件（如 `tests/unit/test_customer.py`）的风格。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_activity.py tests/unit/test_notification.py tests/unit/test_task.py -v` → all passed

---

## 6. 验收

- [ ] `ruff check src/db/models/activity.py src/db/models/notification.py src/db/models/task.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_activity.py tests/unit/test_notification.py tests/unit/test_task.py -v` → all passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（目标数据库 `alembic_dev`）
- [ ] `alembic revision --autogenerate -m "drift_check"` 后生成的迁移为 no-op（`upgrade()`/`downgrade()` 均为 `pass`），确认无残余 drift
- [ ] `mypy src/db/models/activity.py src/db/models/notification.py src/db/models/task.py` → 0 errors（如 mypy 配置存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 迁移在有数据的生产库上添加 NOT NULL 列导致锁表 | 低 | 高 | 迁移使用 nullable + server_default 而非 NOT NULL；后续 tightening 迁移另开 issue |
| 新增列名与下游代码已有属性名冲突 | 低 | 中 | 下游板块在合并前自行运行单元测试发现；如冲突在合并后出现，执行 `alembic downgrade -1` 回退本迁移，下游代码适配后再升 |
| `ActivityModel.status`/`channel` 新增后与现有 `to_dict()` 不一致导致 router 序列化报错 | 中 | 中 | 先合并本迁移，下游 router 板 #451 统一更新 `to_dict()` 调用；两个 PR 合并间隔不超过 1 天 |
| drift check 产生非空 diff（模型有遗漏字段） | 低 | 低 | 补充到 §2.3 并返回 Step 1-3；不影响已通过的验收项 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/activity.py src/db/models/notification.py src/db/models/task.py
git add alembic/versions/<new_revision>.py tests/unit/test_activity.py tests/unit/test_notification.py tests/unit/test_task.py
git commit -m "feat(models): add type/status enums and channel field to Activity, Notification, Task models"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(models): #455 — add missing enums and channel/status columns" --body "Closes #455"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/customer.py`](../../src/db/models/customer.py) — 参考 ORM 模型风格（含 `to_dict()` + timestamp 字段模式）
- 同类参考实现：[`src/db/models/ticket.py`](../../src/db/models/ticket.py) — 参考 `status` / `priority` / `channel` 多字段枚举模型
- Migration 参考：[`alembic/versions/b2c3dce4b714_create_all_tables.py`](../../alembic/versions/b2c3dce4b714_create_all_tables.py) — 三个目标表（activities, notifications, tasks）的初始建表语句
- 父 issue / 关联：#451（父 — CRM domain models enums API routers and services for all core entities）
- 父 issue / 关联：#454（依赖 — upstream migration board）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
