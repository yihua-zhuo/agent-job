# 0663 · Add NotificationPreferenceModel and migration

| 元数据 | 值 |
|---|---|
| Issue | #663 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #663 is a schema-first subtask of the notification-preferences epic (#646). Before any notification-preference service or API can be built, the underlying `notification_preferences` table must exist in the database. The ORM model is also absent — `db/models/__init__.py` uses auto-discovery, so adding the file is the only registration step needed. This board captures the minimal vertical slice: model → migration → verification.

### 1.2 做完后

- **用户视角**：No direct change — this is a pure-backend schema addition with no user-facing surface.
- **开发者视角**：`NotificationPreferenceModel` is importable from `db.models` and maps the `notification_preferences` table. Any downstream service or router can query it via the standard `AsyncSession` pattern.

### 1.3 不做什么（剔除）

- [ ] No Service class or business logic — those belong to a separate service-layer board.
- [ ] No API router endpoints — those require a dedicated router board.
- [ ] No unit tests for a non-existent service — tests of the service layer go in its own board.
- [ ] No seed data migration — the table starts empty; apps populate it as needed.

### 1.4 关键 KPI

- `ruff check src/db/models/notification_preference.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print(NotificationPreferenceModel.__tablename__)"` → `notification_preferences`
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0s
- `ruff check alembic/versions/` → 0 errors on the new revision file

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/db/models/` currently has no `notification_preference.py`. The `notification.py` sibling file (`src/db/models/notification.py` L1-L40) is the closest reference for naming conventions and `to_dict()` pattern.

主入口（参考实现）：[`src/db/models/notification.py`](../../src/db/models/notification.py) L1-L40

```python:src/db/models/notification.py
class NotificationModel(Base):
    """Notification entity mapped to the `notifications` table."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/__init__.py`](../../src/db/models/__init__.py) — auto-discovery picks up new model; no explicit change needed, but review to confirm the file is loadable
- 要建：
  - `src/db/models/notification_preference.py` — ORM model class `NotificationPreferenceModel`
  - `alembic/versions/<rev>_<slug>.py` — Alembic migration creating the `notification_preferences` table
  - `tests/unit/test_notification_preference_model.py` — unit tests for the new model (to_dict, field access)

### 2.3 缺什么

- [ ] `src/db/models/notification_preference.py` does not exist; `NotificationPreferenceModel` cannot be imported
- [ ] `notification_preferences` table has no schema in the database; no Alembic revision exists for it
- [ ] No migration verifying that `tenant_id` and `user_id` columns are indexed for multi-tenant query performance
- [ ] No unit test confirming `to_dict()` output shape and field values

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/notification_preference.py` | ORM model `NotificationPreferenceModel` with id, user_id, tenant_id, channel, enabled fields |
| `alembic/versions/<rev>_add_notification_preferences_table.py` | Alembic revision creating the `notification_preferences` table with indexes on tenant_id and user_id |
| `tests/unit/test_notification_preference_model.py` | Unit tests for `to_dict()` output, field defaults, and `__tablename__` value |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/__init__.py`](../../src/db/models/__init__.py) | No code change required; auto-discovery via `pkgutil.iter_modules` loads the new model automatically |

### 3.3 新增能力

- **ORM model**：`NotificationPreferenceModel` in `src/db/models/notification_preference.py`
- **Database table**：`notification_preferences` (created by Alembic migration)
- **Multi-tenant indexes**：composite or single-column indexes on `(tenant_id, user_id)` for efficient per-tenant lookups

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use `String(50)` for `channel`** instead of an Enum: keeps the column schema-compatible with any future notification channels added without needing an ALTER TYPE migration. Validation of valid channel values lives in the service layer, not the DB.
- **Use `Boolean` with `default=False` for `enabled`** instead of nullable: a missing preference row means "disabled" (fail-safe default), consistent with notification opt-in semantics.

### 4.2 版本约束

No new Python package dependencies. Alembic and SQLAlchemy versions are pinned in `pyproject.toml`.

### 4.3 兼容性约束

- Multi-tenant: every SQL query must `WHERE tenant_id = :tenant_id` (see CLAUDE.md §Multi-Tenancy)
- `to_dict()` must return all five fields as native Python types (int, str, bool), with `created_at` as ISO string
- Import path: `from db.models import NotificationPreferenceModel` — PYTHONPATH=src, never `from src.db.models`

### 4.4 已知坑

1. **SQLAlchemy `func.now()` vs `server_default=func.now()`** — the migration must use `server_default=func.now()` (not a Python-side default) so the DB sets the timestamp on INSERT. Autogen may write `server_default=text("now()")`; both are valid for PostgreSQL.
2. **Boolean column default in autogen** — Alembic may generate `default=False` as a Python-side callable; verify the generated migration uses a Postgres-compatible default (e.g., `server_default=fetch_or_default('false')` or `server_default=text('false')`).
3. **Auto-discovery requires a top-level `__init__.py`** — `src/db/models/` already has `__init__.py`; no action needed, but if the file is ever removed the model won't register.

---

## 5. 实现步骤（按顺序）

### Step 1: Create NotificationPreferenceModel ORM class

Create `src/db/models/notification_preference.py` following the established `NotificationModel` convention:

```python
# src/db/models/notification_preference.py
"""NotificationPreference ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationPreferenceModel(Base):
    """Notification preference entity mapped to the `notification_preferences` table."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "channel": self.channel,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

操作：
- a) Write the file at `src/db/models/notification_preference.py` with the code above.
- b) Verify `PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print('ok')"` outputs `ok`.

**完成判定**：`PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print(NotificationPreferenceModel.__tablename__)"` → `notification_preferences`

---

### Step 2: Verify auto-discovery picks up the new model

操作：
- a) Run `PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; m = NotificationPreferenceModel; print(m.__tablename__, [c.name for c in m.__table__.columns])"`
- b) Confirm output lists all five columns: `id`, `user_id`, `tenant_id`, `channel`, `enabled`, `created_at`.

**完成判定**：`PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; assert 'notification_preferences' == NotificationPreferenceModel.__tablename__; assert 'channel' in [c.name for c in NotificationPreferenceModel.__table__.columns]; print('ok')"` → `ok`

---

### Step 3: Generate Alembic migration with --autogenerate

操作：
- a) Bring up clean `alembic_dev` DB: `docker compose -f configs/docker-compose.test.yml up -d test-db`
- b) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
- c) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- d) Set `DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"` (or as per env)
- e) Run `alembic upgrade head` to bring the dev DB to current head.
- f) Run `alembic revision --autogenerate -m "add notification_preferences table"`

**完成判定**：`ls alembic/versions/*notification_preferences*` → at least one `.py` file exists.

---

### Step 4: Review and finalize the migration

审查 `alembic/versions/<rev>_add_notification_preferences_table.py`：

- a) Confirm `op.create_table('notification_preferences', ...)` is present.
- b) Confirm `tenant_id` and `user_id` columns have `index=True` in the migration.
- c) Confirm `channel` uses `String(50)` (not unbounded Text).
- d) Confirm `enabled` uses a boolean type (`Boolean()` or `sa.Boolean()`) with a server-side default.
- e) Confirm `created_at` uses `server_default=func.now()` (not a Python callable).
- f) Fill in the `downgrade()` body: it must call `op.drop_table('notification_preferences')`.

操作：
- a) Edit the generated file to fix any mismatches (Alembic autogen is imperfect — see §4.4 known pitfalls).
- b) Verify `downgrade` is not empty: it must call `op.drop_table('notification_preferences')`.

**完成判定**：`ruff check alembic/versions/<new_rev>.py` → 0 errors

---

### Step 5: Run upgrade / downgrade / upgrade cycle on alembic_dev

操作：
- a) `alembic upgrade head` — must exit 0.
- b) `alembic downgrade -1` — must exit 0.
- c) `alembic upgrade head` — must exit 0 (re-apply cleanly).

**完成判定**：All three commands exit 0. `alembic history --verbose` shows the new revision at head.

---

### Step 6: Create unit test for NotificationPreferenceModel

Create `tests/unit/test_notification_preference_model.py`:

```python
# tests/unit/test_notification_preference_model.py
from __future__ import annotations
from datetime import datetime, timezone
import pytest

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import declarative_base

# Import the real model — no mocking needed for to_dict / field access
from db.models.notification_preference import NotificationPreferenceModel


class TestNotificationPreferenceModel:
    def test_tablename(self):
        assert NotificationPreferenceModel.__tablename__ == "notification_preferences"

    def test_columns_exist(self):
        col_names = {c.name for c in NotificationPreferenceModel.__table__.columns}
        assert col_names >= {"id", "user_id", "tenant_id", "channel", "enabled", "created_at"}

    def test_to_dict_returns_all_fields(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Instantiate via __new__ to avoid DB round-trip
        obj = NotificationPreferenceModel.__new__(NotificationPreferenceModel)
        obj.id = 1
        obj.user_id = 10
        obj.tenant_id = 5
        obj.channel = "email"
        obj.enabled = True
        obj.created_at = now

        d = obj.to_dict()
        assert d["id"] == 1
        assert d["user_id"] == 10
        assert d["tenant_id"] == 5
        assert d["channel"] == "email"
        assert d["enabled"] is True
        assert d["created_at"] == now.isoformat()

    def test_to_dict_disabled_preference(self):
        obj = NotificationPreferenceModel.__new__(NotificationPreferenceModel)
        obj.id = 2
        obj.user_id = 20
        obj.tenant_id = 5
        obj.channel = "sms"
        obj.enabled = False
        obj.created_at = None

        d = obj.to_dict()
        assert d["enabled"] is False
        assert d["created_at"] is None
```

操作：
- a) Write the file at `tests/unit/test_notification_preference_model.py` with the code above.
- b) Run `PYTHONPATH=src pytest tests/unit/test_notification_preference_model.py -v`.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_preference_model.py -v` → `4 passed`

---

### Step 7: Final lint check across all changed files

操作：
- a) `ruff check src/db/models/notification_preference.py alembic/versions/<new_rev>.py tests/unit/test_notification_preference_model.py`
- b) `ruff format --check src/db/models/notification_preference.py tests/unit/test_notification_preference_model.py`

**完成判定**：All `ruff check` and `ruff format --check` commands exit 0.

---

## 6. 验收

- [ ] `ruff check src/db/models/notification_preference.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models import NotificationPreferenceModel; print(NotificationPreferenceModel.__tablename__)"` → `notification_preferences`
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_preference_model.py -v` → `4 passed`
- [ ] `ruff check alembic/versions/<new_rev>.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0s

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic autogen writes wrong column type (e.g. JSON instead of JSONB, DateTime instead of TIMESTAMPTZ) | 中 | 高 | Manually edit the generated migration before committing; re-run autogen in a clean DB to verify the diff is clean |
| Migration drops a column that another migration or app code still references | 低 | 高 | Revert the migration via `alembic downgrade -1` before merging; add a separate board for the downstream dependency |
| `Boolean` server_default not Postgres-compatible, causing silent failures on INSERT | 低 | 中 | Use `server_default=text('false')` (imported from `sqlalchemy.dialects.postgresql`) in the migration to guarantee Postgres behavior |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification_preference.py alembic/versions/<new_rev>.py tests/unit/test_notification_preference_model.py
git commit -m "model: add NotificationPreferenceModel + migration (issue #663)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "model: add NotificationPreferenceModel and migration (closes #663)" --body "Closes #663"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/notification.py`](../../src/db/models/notification.py) — `NotificationModel` used as naming and structure template
- Alembic conventions：[`alembic/versions/b2c3dce4b714_create_all_tables.py`](../../alembic/versions/b2c3dce4b714_create_all_tables.py) — first-create-all-tables migration
- Auto-discovery mechanism：[`src/db/models/__init__.py`](../../src/db/models/__init__.py) — confirms no explicit export needed
- 父 issue / 关联：#646

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
