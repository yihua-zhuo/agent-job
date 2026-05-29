# 通知日志 · 新增 NotificationLogModel 及数据库迁移

| 元数据 | 值 |
|---|---|
| Issue | #664 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统在发送通知（Email / SMS / Push 等）时，需要对每次投递尝试做持久化记录，用于排障、重试和统计。当前没有 `notification_logs` 表，下游业务（如自动化规则触发通知）无法审计投递历史。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层数据模型。
- **开发者视角**：`NotificationLogModel` ORM 类可用，后续 `NotificationService` 可调用 `session` 写入日志记录；数据库有 `notification_logs` 表（含 `tenant_id` 索引）。

### 1.3 不做什么（剔除）

- [ ] 不实现 Service 层写入逻辑（属于后续板块 #646）。
- [ ] 不实现 Router 层 API（属于后续板块 #646）。
- [ ] 不添加重复投递策略字段（属于后续板块 #646）。

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_notification_log_model.py -v` → ≥ 3 passed]
- [指标 2：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0]
- [指标 3：`ruff check src/db/models/notification_log.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

通知主表（存在）：

```python:src/db/models/notification.py
"""Notification ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

通知日志表不存在 — 这是本板块需要新建的内容。

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — `pkgutil.iter_modules` 自动发现，无需手动修改
- 要建：
  - `src/db/models/notification_log.py` — `NotificationLogModel` ORM 类
  - `alembic/versions/<id>_add_notification_logs.py` — 迁移文件
  - `tests/unit/test_notification_log_model.py` — ORM 单元测试

### 2.3 缺什么

- [ ] `notification_logs` 表不存在，无法记录通知投递历史]
- [ ] `NotificationLogModel` ORM 类不存在，Service 无法引用]
- [ ] 无针对新 model 的单元测试]

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/notification_log.py` | `NotificationLogModel` ORM 类，映射 `notification_logs` 表 |
| `alembic/versions/<new_id>_add_notification_logs.py` | 数据库迁移：创建 `notification_logs` 表（含 `tenant_id` 索引） |
| `tests/unit/test_notification_log_model.py` | 验证 `NotificationLogModel` 的 `to_dict()` / 字段定义 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/__init__.py` | 无需手动修改，`pkgutil.iter_modules` 自动发现新 model |

### 3.3 新增能力

- **ORM model**：`NotificationLogModel` in `src/db/models/notification_log.py`
- **Migration**：`alembic upgrade head` 创建 `notification_logs` 表（含 `tenant_id` 索引、`notification_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `String(50)` 而非 `Enum` 做 channel/status**：SQLAlchemy Enum 迁移复杂度高；先用 String(50) 存储，Python 侧用 `Literal["email", "sms", "push"]` 做类型提示。
- **用 `Text` 存 error 字段**：投递失败时的错误信息长度不可控，`Text` 比 `String(500)` 更安全。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）。
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责。
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`。
- 所有 ORM model 文件必须 `from db.base import Base`，不得直接 import `DeclarativeBase`。

### 4.4 已知坑

1. **Alembic autogen 把 `TIMESTAMPTZ` 写成 `DateTime`，把 `JSONB` 写成 `JSON`** → 手动改回 `DateTime(timezone=True)` / `JSONB`。
2. **Alembic autogen 不生成 `server_default=sa.text('now()')`，只生成 `nullable=False`** → 手动补上 `server_default=sa.text('now()')`。
3. **`__init__.py` 使用 `pkgutil.iter_modules` 自动发现 model，无需手动注册** → 新 model 不需要手动加 import/export。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `NotificationLogModel` ORM 类

参考 `ReminderModel` 和 `NotificationModel` 的结构，新建 `src/db/models/notification_log.py`。

字段定义：
- `id: int` (PK, autoincrement)
- `tenant_id: int` (nullable=False, index=True)
- `notification_id: int` (nullable=False, index=True) — 外键指向 `notifications.id`
- `channel: str` — 通知渠道：email / sms / push
- `status: str` — 投递状态：pending / sent / failed
- `attempts: int` — 尝试次数，默认 1
- `error: str | None` — 错误信息，可为空
- `created_at: datetime` — server_default=func.now()

```python
"""Notification log ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationLogModel(Base):
    """NotificationLog entity mapped to the `notification_logs` table."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    notification_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "notification_id": self.notification_id,
            "channel": self.channel,
            "status": self.status,
            "attempts": self.attempts,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

`pkgutil.iter_modules` 在 `__init__.py` 中自动发现并注册，无需手动修改任何文件。

**完成判定**：`ruff check src/db/models/notification_log.py` → 0 errors

---

### Step 2: 生成 Alembic 迁移

确保数据库容器运行（参考 CLAUDE.md §Alembic Migrations）：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db

docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

alembic upgrade head

alembic revision --autogenerate -m "add_notification_logs"
```

审查生成文件 `alembic/versions/<id>_add_notification_logs.py`：

- 确认 `op.create_table('notification_logs', ...)` 存在
- 确认 `server_default=sa.text('now()')` 出现在 `created_at` 列定义中
- 确认 `sa.DateTime(timezone=True)` 而非普通 `sa.DateTime`
- 确认存在 `op.create_index(op.f('ix_notification_logs_tenant_id'), ...)` 索引
- 确认存在 `op.create_index(op.f('ix_notification_logs_notification_id'), ...)` 索引
- 确认 `down_revision` 指向 `c94d682d4b03`（当前最新迁移）

手动修正 autogen 不足之处。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 验证无新增 drift（second autogen 空白检测）

```bash
alembic revision --autogenerate -m "drift_check"
```

若生成的迁移文件只有 `pass` in both up/down，删除该空迁移。

若出现真实 diff（不应该发生），说明 Step 2 的迁移不完整，补上。

**完成判定**：second autogen 只产生空迁移文件

---

### Step 4: 编写 ORM 单元测试

创建 `tests/unit/test_notification_log_model.py`：

```python
"""Unit tests for NotificationLogModel."""
import pytest

from db.models.notification_log import NotificationLogModel


class TestNotificationLogModel:
    def test_to_dict_returns_all_fields(self):
        log = NotificationLogModel(
            id=1,
            tenant_id=10,
            notification_id=100,
            channel="email",
            status="sent",
            attempts=2,
            error=None,
        )
        d = log.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["notification_id"] == 100
        assert d["channel"] == "email"
        assert d["status"] == "sent"
        assert d["attempts"] == 2
        assert d["error"] is None

    def test_to_dict_with_error_field(self):
        log = NotificationLogModel(
            id=2,
            tenant_id=20,
            notification_id=200,
            channel="sms",
            status="failed",
            attempts=3,
            error="Connection timeout after 30s",
        )
        d = log.to_dict()
        assert d["error"] == "Connection timeout after 30s"

    def test_table_name(self):
        assert NotificationLogModel.__tablename__ == "notification_logs"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_log_model.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/db/models/notification_log.py` → 0 errors
- [ ] `ruff check alembic/versions/<new_id>_add_notification_logs.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_log_model.py -v` → 3 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `alembic revision --autogenerate -m "drift_check"` → 空迁移（无 drift）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogen 漏掉 `server_default` 导致迁移与 ORM 不一致 | 低 | 中 | 手动补上 `server_default=sa.text('now()')`，re-run upgrade |
| 新表与旧迁移 down_revision 不兼容（依赖链错误） | 低 | 高 | 修正 `down_revision` 指向 `c94d682d4b03`，重跑 upgrade |
| 外键约束导致删除 notifications 时卡住 | 低 | 中 | downgrade 时先删 `notification_logs` 再删其他表 |

---

## 8. 完成后必做

```bash
git add src/db/models/notification_log.py
git add alembic/versions/<new_id>_add_notification_logs.py
git add tests/unit/test_notification_log_model.py
git commit -m "feat(campaigns): add NotificationLogModel and migration for #664"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add NotificationLogModel and migration (#664)" --body "Closes #664"
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/reminder.py`](../../src/db/models/reminder.py) — ReminderModel 结构与字段模式一致
- 同类参考实现：[`src/db/models/notification.py`](../../src/db/models/notification.py) — NotificationModel
- 第三方文档：[Alembic autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- 父 issue / 关联：#646, #663

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
