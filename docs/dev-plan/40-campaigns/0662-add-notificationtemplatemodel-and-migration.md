# 40-campaigns · Add NotificationTemplateModel and migration

| 元数据 | 值 |
|---|---|
| Issue | #662 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | #646 (完整通知系统) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #646 需要一套完整的通知系统基础设施。通知模板（NotificationTemplate）是通知系统的上游组件——先有模板的定义（标题、正文），后续的 NotificationLog（已由 #664 创建）和通知发送逻辑才能引用模板 ID、填充占位符。缺少 NotificationTemplateModel，则整个通知系统缺少"内容源头"，无法完成通知发送的闭环。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 ORM 模型，为后续的通知模板管理 API 奠定数据基础。
- **开发者视角**：`from db.models import NotificationTemplateModel` 可用；Alembic 迁移创建 `notification_templates` 表；Service 层可直接查询、引用模板。

### 1.3 不做什么（剔除）

- [ ] Service 层 CRUD 操作（由 #646 后续子任务负责）
- [ ] API Router 端点（本板块仅建 Model 和 Migration）
- [ ] 模板变量/占位符解析逻辑（后续通知发送模块负责）
- [ ] 与 NotificationLog 的 FK 关联（两表在当前阶段独立，FK 关联在 #646 后续加入）

### 1.4 关键 KPI

- 指标 1：`ruff check src/db/models/notification_template.py` → 0 errors
- 指标 2：`PYTHONPATH=src pytest tests/unit/test_notification_template_model.py -v` → ≥ 3 passed
- 指标 3：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- 指标 4：第二次 `alembic revision --autogenerate -m "drift_check"` 产生空迁移（仅 `pass`）

---

## 2. 当前现状（起点）

### 2.1 现有实现

现有 Notification 模型（`notification.py`）定义了通知记录结构，是本板块的最近参考：

[`src/db/models/notification.py`](../../../src/db/models/notification.py) L{1}-L{35}

```python
class NotificationModel(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

`notification_template.py` 尚不存在，为新建模块。

### 2.2 涉及文件清单

- 要改：
  - 无需修改现有文件 — `pkgutil.iter_modules` 自动发现新模型
- 要建：
  - `src/db/models/notification_template.py` — NotificationTemplateModel ORM 类
  - `alembic/versions/<id>_add_notification_templates.py` — 表创建迁移
  - `tests/unit/test_notification_template_model.py` — 单元测试（3 个 case）

### 2.3 缺什么

- [ ] `NotificationTemplateModel` ORM 类，字段：id, name, channel, subject, body_html, body_text, created_at
- [ ] `notification_templates` 表迁移脚本（alembic）
- [ ] 模板表的单元测试覆盖
- [ ] `notification_templates` 表的主键、tenant_id 索引

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/notification_template.py` | NotificationTemplateModel ORM 类，字段：id, name, channel, subject, body_html, body_text, created_at |
| `alembic/versions/<id>_add_notification_templates.py` | 创建 `notification_templates` 表的 Alembic 迁移 |
| `tests/unit/test_notification_template_model.py` | ORM 模型单元测试（to_dict、所有字段、tablename） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | pkgutil.iter_modules 自动发现新建的 notification_template.py，无需手动修改 `__init__.py` |

### 3.3 新增能力

- **ORM model**：`NotificationTemplateModel` in `src/db/models/notification_template.py`
- **Migration**：`alembic upgrade head` 创建 `notification_templates` 表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `server_default=func.now()` 而非 `default=datetime.now`**：数据库侧计算创建时间，确保多实例一致性，与本项目所有其他模型（NotificationModel、TicketModel）保持一致。
- **选 `String(50)` 而非 SQLAlchemy `Enum`**：与其他模型（NotificationModel、TicketModel）保持风格统一，应用层维护 channel 常量。
- **表名 `notification_templates` 复数形式**：与本项目 `notifications`、`tickets`、`opportunities` 等表命名惯例一致。

### 4.2 版本约束

无新增外部依赖。

### 4.3 兼容性约束

- 多租户：SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Model 继承自 `db.base.Base`，不多继承 mixin
- 列名避免使用 `metadata`（与 `Base.metadata` 冲突）
- Service 层在后续 #646 子任务中实现，本板块仅提供 ORM 模型

### 4.4 已知坑

1. **Alembic autogen 写 `DateTime` 而非 `DateTime(timezone=True)`** → 症状：迁移后时区信息丢失，PostgreSQL 行为与预期不符 → 规避：手动将生成的 `sa.DateTime` 改为 `sa.DateTime(timezone=True)`
2. **Alembic autogen 不生成 `server_default=sa.text('now()')`** → 症状：`created_at` 列为非空但无默认值，迁移失败 → 规避：迁移 up() 中手动添加 `server_default=sa.text('now()')`，downgrade() 中使用 `drop_column(..., server_onupdate=None)`
3. **Alembic autogen 可能漏掉 `sqlite_autoincrement=True`** → 症状：SQLite 测试环境主键不自增 → 规避：在 `__table_args__` 中补 `"sqlite_autoincrement": True`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 NotificationTemplateModel ORM 类

参考 `notification.py` 模型结构，新建 `notification_template.py`。

操作：
- 在 `src/db/models/notification_template.py` 中写入以下内容：

```python
"""NotificationTemplate ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class NotificationTemplateModel(Base):
    """NotificationTemplate entity mapped to the `notification_templates` table."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_tenant_id", "tenant_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "channel": self.channel,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/notification_template.py` → 0 errors

---

### Step 2: 生成 Alembic 迁移脚本

确保数据库已准备就绪，对齐最新迁移头，生成 `notification_templates` 表的迁移文件。

操作：
- a) 启动干净数据库（如未运行）：
  ```bash
  docker compose -f configs/docker-compose.test.yml up -d test-db
  ```
- b) 重置 alembic_dev 数据库（使用独立 disposable DB，不要用 test_db）：
  ```bash
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
  ```
- c) 将新数据库升至最新迁移头：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  ```
- d) 生成迁移 diff：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic revision --autogenerate -m "add_notification_templates"
  ```
- e) 审查生成的迁移文件 `alembic/versions/<id>_add_notification_templates.py`：
  - 确认 `up()` 中 `sa.DateTime(timezone=True)`（非 `DateTime`）
  - 确认 `created_at` 有 `server_default=sa.text('now()')`
  - 确认 `down_revision = 'c94d682d4b03'`
  - 如有偏差，手动修正后再执行 f
- f) 验证迁移双向可用：
  ```bash
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic downgrade -1
  PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head
  ```

**完成判定**：三次命令均 exit 0

---

### Step 3: 编写单元测试

创建 `tests/unit/test_notification_template_model.py`，覆盖 to_dict、字段存在性、tablename。

操作：
- 在 `tests/unit/test_notification_template_model.py` 写入：

```python
"""Unit tests for NotificationTemplateModel."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, UTC

from db.models.notification_template import NotificationTemplateModel


class TestNotificationTemplateModel:
    def _make_instance(self, **overrides):
        attrs = {
            "id": 1,
            "tenant_id": 10,
            "name": "welcome_email",
            "channel": "email",
            "subject": "Welcome!",
            "body_html": "<h1>Hello</h1>",
            "body_text": "Hello",
            "created_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        }
        attrs.update(overrides)
        obj = NotificationTemplateModel.__new__(NotificationTemplateModel)
        for k, v in attrs.items():
            setattr(obj, k, v)
        return obj

    def test_to_dict_returns_all_fields(self):
        obj = self._make_instance()
        d = obj.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["name"] == "welcome_email"
        assert d["channel"] == "email"
        assert d["subject"] == "Welcome!"
        assert d["body_html"] == "<h1>Hello</h1>"
        assert d["body_text"] == "Hello"
        assert d["created_at"] == "2026-01-01T12:00:00+00:00"

    def test_to_dict_with_null_optional_fields(self):
        obj = self._make_instance(subject=None, body_html=None, body_text=None)
        d = obj.to_dict()
        assert d["subject"] is None
        assert d["body_html"] is None
        assert d["body_text"] is None

    def test_table_name(self):
        assert NotificationTemplateModel.__tablename__ == "notification_templates"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_template_model.py -v` → 3 passed

---

### Step 4: Drift check（确保 Model 与 DB 完全对齐）

再次运行 autogenerate，确认无新 diff 产生。

操作：
```bash
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic revision --autogenerate -m "drift_check"
```
检查新生成的迁移文件 — up() 和 down() 应各只有一行 `pass`。

如有非空内容，说明 Model 定义与迁移有偏差，返回 Step 1 修正。

**完成判定**：生成的 drift_check 迁移文件 up/down 均只有 `pass`，无其他操作

---

## 6. 验收

- [ ] `ruff check src/db/models/notification_template.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_template_model.py -v` → 3 passed
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic downgrade -1` → exit 0
- [ ] `PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" alembic upgrade head` → exit 0
- [ ] drift check autogenerate 产生空迁移

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic autogen 生成了错误类型（如 DateTime 而非 DateTimeTZ），导致迁移语法错误 | 中 | 高 | 手动修正迁移文件中的类型；revert 后修正 Model 再重新 autogenerate |
| 迁移成功后，后续 #646 的 Service 层引入新字段导致 Model 需要变更 | 低 | 中 | 本板块仅建 Model；后续在独立迁移中添加新列，不改已有迁移 |
| 在已有 test_db（而非独立的 alembic_dev）上运行 autogenerate，产生虚假空 diff | 中 | 低 | 始终使用独立的 disposable alembic_dev 数据库；不重用在测试套件中初始化的 test_db |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification_template.py alembic/versions/<id>_add_notification_templates.py tests/unit/test_notification_template_model.py
git commit -m "feat(40-campaigns): add NotificationTemplateModel and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(40-campaigns): add NotificationTemplateModel for #662" --body "Closes #662"

# 2. 更新进度
# - 在本板块文档 docs/dev-plan/40-campaigns/0662-add-notificationtemplatemodel-and-migration.md §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/notification.py`](../../../src/db/models/notification.py) — 最近的 Notification 模型，本板块直接参考字段声明风格
- 同类参考实现：[`src/db/models/ticket.py`](../../../src/db/models/ticket.py) — to_dict 序列化风格参考
- 父 issue / 关联：#646 (完整通知系统), #661 (依赖的前置迁移), #664 (NotificationLogModel，并行板块)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
