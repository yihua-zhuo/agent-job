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
b) 在 `import` sqlalchemy 区添加 `Enum`（如尚未导入）
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

class NotificationStatusCode(str, enum.Enum):
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
    op.drop_column('tasks_task', 'channel')
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

- 同类参考实现：[`src/db/models/customer.py`](../../../src/db/models/customer.py) — 参考 ORM 模型风格（含 `to_dict()` + timestamp 字段模式）
- 同类参考实现：[`src/db/models/ticket.py`](../../../src/db/models/ticket.py) — 参考 `status` / `priority` / `channel` 多字段枚举模型
- Migration 参考：[`alembic/versions/b2c3dce4b714_create_all_tables.py`](../../../alembic/versions/b2c3dce4b714_create_all_tables.py) — 三个目标表（activities, notifications, tasks）的初始建表语句
- 父 issue / 关联：#451（父 — CRM domain models enums API routers and services for all core entities）
- 父 issue / 关联：#454（依赖 — upstream migration board）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**Fixes applied:**

1. **`../../src/db/models/...`** and **`../../alembic/...`** → **`../../../src/db/models/...`** and **`../../../alembic/...`** — the board lives in `docs/dev-plan/`, so relative paths to `src/` and `alembic/` at the repo root need two extra `../` levels (docs/dev-plan → repo root → src).

2. **`../0451-crm-domain-models...`** → **`TBD - 待验证：关联 issue #451 的实现板块路径`** — no `0451-*.md` file exists in `docs/dev-plan/`, so the downstream-board link cannot be resolved and is replaced with a TBD marker.
