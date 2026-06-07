# 智能通知 · 新增 SmartNotification ORM 模型与数据库迁移

| 元数据 | 值 |
|---|---|
| Issue | #593 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：根据 issue #47 主任务确定哪下游模块依赖通知模型（如自动化规则触发、CRM客户通知等） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #47 sets up a multi-tenant CRM campaign automation system. At present the codebase has no persistent entity to record notification records — no `notification` table, no ORM model, no migration. Without this, any downstream automation feature (e.g. "send alert when campaign KPI threshold is breached") has nowhere to log what was dispatched. Building the `SmartNotification` model now establishes the foundation all campaign notification features will depend on.

### 1.2 做完后

- **用户视角**：无用户可见 changes — this is pure backend schema work.
- **开发者视角**：`SmartNotification` ORM model is available for import via `from db.models.notification import SmartNotification`. Services and routers can CREATE / READ records; the model is visible to Alembic for future autogenerate diffs.

### 1.3 不做什么（剔除）

- [ ] No REST API router for SmartNotification (CRUD endpoints belong to a future `#N` router issue, not this board)
- [ ] No business logic in services (no `NotificationService` class — that belongs to a future service-layer board)
- [ ] No actual notification delivery code (email/SMS/push sending logic is out of scope)
- [ ] No multi-tenant access-control logic beyond the mandatory `tenant_id` column and WHERE clauses

### 1.4 关键 KPI

- [`SmartNotification` model class is importable](../../../src/db/models/notification.py) without raising `ImportError`
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0 exits
- `PYTHONPATH=src ruff check src/db/models/notification.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：在 `src/db/models/` 目录下是否已存在 `notification.py`（搜索 `notification` 相关的 model 文件确认）

现有 campaign 相关 ORM 模型可参考注册方式：

```python
# TBD - 待验证：src/db/models/campaign.py 或其他已注册的 model 文件
# 查找 Base declarative 注册模式作为参考
```

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/notification.py` — 新建 SmartNotification 模型文件
  - `src/db/base.py` — 注册新模型（添加 import / 含 `Base.metadata` 的列表）
  - `alembic/env.py` — 新增模型的 import 列表，供 autogenerate 识别
- 要建：
  - `alembic/versions/<id>_add_smart_notification.py` — Alembic autogenerate 输出文件### 2.3 缺什么

- [ ] No `src/db/models/notification.py` file — the `SmartNotification` ORM entity does not exist
- [ ] `src/db/base.py` does not import or register `SmartNotification` — Alembic autogenerate will miss it
- [ ] `alembic/env.py` does not import `SmartNotification` from the new module — migration generation fails silently
- [ ] No migration creates the `smart_notification` table in the target database
- [ ] No unit tests for the new model (fixture + basic import test)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/notification.py` | SmartNotification SQLAlchemy ORM model (declarative Base) |
| `alembic/versions/<id>_add_smart_notification.py` | Alembic autogenerate migration creating `smart_notification` table |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/base.py` | import SmartNotification; add to `__all__` or metadata registry |
| `alembic/env.py` | import SmartNotification so `Base.metadata` includes it |

### 3.3 新增能力

- **ORM model**：`SmartNotification` in `src/db/models/notification.py` with fields: id, tenant_id, summarized_content, priority (enum), channel (enum), timing (enum), recipient_filter JSON, created_at
- **Migration**：`alembic upgrade head` creates `smart_notification` table (with `tenant_id` index)
- **Registered model**：visible to all future autogenerate diffs via `Base.metadata`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSON column for `recipient_filter` not individual scalar columns**：recipient filtering criteria vary widely per use-case ( tags, segments, role masks, user IDs). A JSONB column accommodates any future filter shape without schema migrations. SQLAlchemy's `JSONB` renders as `jsonb` in Postgres, enabling GIN-index queries if needed.
- **SQLAlchemy Enum over Python enum class**：SQLAlchemy's `Enum(..., native_enum=False)` emits a CHECK constraint like `CHECK (priority IN ('urgent','normal','low'))` in Postgres, which is more expressive than a Python-side `enum.Enum` and self-documents in the DB schema.

### 4.2 版本约束

|依赖 | 版本 | 理由 |
|------|------|------|
| `sqlalchemy` | `>=2.0` | async ORM, `Mapped[]` typed columns, `mapped_column()` |
| `alembic` | `>=1.12` | autogenerate with async SQLAlchemy driver |
| `psycopg2-binary` / `asyncpg` | current | already in use per `pyproject.toml` |

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (model includes `tenant_id` index)
- Column named `recipient_filter` (not `metadata`) — avoids collision with `Base.metadata`
- Enum columns use `native_enum=False` / string CHECK constraint for Postgres compatibility
- Model registered via `Base.metadata` in `src/db/base.py` so Alembic sees it
- `created_at` is `DateTime(timezone=True)` to match the Alembic autogen known坑### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` for JSONB columns** → 规避：生成 migration 后，手动将 `sa.JSON()`改为 `sa.JSONB()`，并在 column specification 中确认 `server_default` literal 不覆盖 JSONB 类型
2. **Alembic autogenerate emits `DateTime` without `timezone=True`** → 规避：生成后找到 `sa.DateTime()` 调用，手动添入 `timezone=True`；全小写 `TIMESTAMPTZ` 在 DOWNGRADE 里也要对应改回 `TIMESTAMP` + `with time zone` 判断
3. **`Base.metadata` collision — no column may be named `metadata`** → 规避：本模型使用 `recipient_filter`（而非 `metadata`）作为 JSON字段名

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 SmartNotification ORM model 文件

在 `src/db/models/` 下新建 `notification.py`，使用 SQLAlchemy 2.x async风格声明模型。

```python
import enum
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Enum, JSON, DateTime, Integer, String, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PriorityLevel(enum.Enum):
    urgent = "urgent"
    normal = "normal"
    low = "low"


class NotificationChannel(enum.Enum):
    email = "email"
    sms = "sms"
    push = "push"
    in_app = "in_app"


class TimingMode(enum.Enum):
    immediate = "immediate"
    batch = "batch"


class SmartNotification(Base):
    __tablename__ = "smart_notification"
    __table_args__ = (
        Index("ix_smart_notification_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    summarized_content: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(
        Enum(PriorityLevel, name="priority_level", native_enum=False),
        nullable=False,
        default=PriorityLevel.normal,
    )
    channel: Mapped[str] = mapped_column(
        Enum(NotificationChannel, name="notification_channel", native_enum=False),
        nullable=False,
        default=NotificationChannel.in_app,
    )
    timing: Mapped[str] = mapped_column(
        Enum(TimingMode, name="timing_mode", native_enum=False),
        nullable=False,
        default=TimingMode.immediate,
    )
    recipient_filter: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.notification import SmartNotification; print('ok')"` → stdout 输出 `ok`，无 `AttributeError`

### Step 2: 注册模型到 db/base.py

在 `src/db/base.py` 中添加 `SmartNotification` 的 import，使 `Base.metadata` 包含新表（参考 `base.py` 中的现有 import列表添加对应行）。

**完成判定**：`PYTHONPATH=src python -c "from db.base import Base; from db.models.notification import SmartNotification; assert SmartNotification.__table__ in Base.metadata.tables.values()"` → 无异常退出

### Step 3: 注册模型到 alembic/env.py

在 `alembic/env.py` 的 import区块添加：

```python
from src.db.models.notification import SmartNotification
```

确保 Alembic autogenerate 能看到该模型。

**完成判定**：`grep -n "notification" alembic/env.py` → 找到新增的 import 行

### Step 4: 运行 Alembic autogenerate

```bash
# Ensure a clean disposable DB exists (alembic_dev)
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "add_smart_notification"
```

**完成判定**：`test -f "alembic/versions/*_add_smart_notification.py" && echo "migration_created"` → `migration_created`

### Step 5: 修正 Migration 中的常见坑

打开 `\alembic/versions\<新文件>.py`，手工修正以下两处：

a) 将 `sa.JSON()` 替换为 `sa.JSON().with_variant(...)` 的 JSONB声明（或直接 `sa.JSONB()`视 alembic 版本）：

```python
# 确认 JSONB（若 alembic 版本老不支持 JSONB，用 postgresql.JSONB 类型）
from sqlalchemy.dialects.postgresql import JSONB
recipient_filter: Mapped[dict] = mapped_column(JSONB, nullable=True)
```

b) 确认 `created_at` 使用 `timezone=True` 的 `DateTime`：

```python
from sqlalchemy import DateTime
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**完成判定**：`grep -E "(JSONB|timezone=True)" alembic/versions/*_add_smart_notification.py` → 两行均出现

### Step 6: 验证 Migration上下双向正确```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：三次命令各自 exit 0，且 `alembic history` 末尾显示 `add_smart_notification`

### Step 7: 清理 Drift Check

```bash
alembic revision --autogenerate -m "drift_check"
```

若新生成的 `drift_check` migration 文件只有 `pass`，删除该文件。

**完成判定**：`test -f "alembic/versions/*_drift_check.py" && wc -l alembic/versions/*_drift_check.py` 或 `mv alembic/versions/*_drift_check.py /tmp/` 可确认无副作用

### Step 8:单元测试占位

在 `tests/unit/` 下新建 `describe_smart_notification.py`（或类似 xUnit 文件），至少验证：

- import of `SmartNotification` does not raise
- `SmartNotification.__table__.columns` contains expected field names
- `tenant_id` column is indexed**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification.py -v` → ≥ 3 passed（若暂不写测试则标注 `TBD` 并在下游板块补齐）

---

## 6. 验收

- [ ] `ruff check src/db/models/notification.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.notification import SmartNotification; print('ok')"` → stdout `ok`
- [ ] `PYTHONPATH=src python -c "from db.base import Base; from db.models.notification import SmartNotification; assert SmartNotification.__table__ in Base.metadata.tables.values()"` → exit 0
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `grep -E "(JSONB|timezone=True)" alembic/versions/*_add_smart_notification.py` → 两个模式均出现
- [ ] `PYTHONPATH=src pytest tests/unit/ -v`（相关单元测试文件）→ 全 passed

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate produces incorrect column types (JSON vs JSONB, missing timezone) and breaks future queries | 中 | 高 | 手动修正 migration 文件后 commit；已在 Step 5 中预防性修正 |
| Not registering model in `alembic/env.py` causes future autogenerate to miss it (schema drift goes undetected) | 低 | 中 | 在 `alembic/env.py` 中补加 import 后重新 autogenerate drift_check |
| `metadata` column name collision with `Base.metadata` crashes at import time | 极低 | 高 | 已确认使用 `recipient_filter` 和 `created_at` 等非冲突名称 |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/db/models/notification.py src/db/base.py alembic/env.py alembic/versions/*_add_smart_notification.py
git commit -m "feat(campaigns): add SmartNotification ORM model and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#593): add SmartNotification ORM model and migration" --body "Closes #593"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/` 目录下的现有 model 文件注册模式（如 `campaign.py`、`ticket.py`），参考其 Enum 列定义和 JSON 列处理方式
- 父 issue /关联：#47（campaign automation 主任务）
- 关联子任务：#593（本文档对应）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
