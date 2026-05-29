# NotificationModel Enhancement + Index Migration · Add NotificationModel fields and indexes

| 元数据 | 值 |
|---|---|
| Issue | #661 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：使用 notification 数据的前端/服务层板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

现有的 `NotificationModel`（`src/db/models/notification.py`）缺少通知系统所需的核心字段——没有 `channel`/`template`/`params`（参数化模板）、没有 `status`/`priority`（调度控制）、没有 `delivered_at`/`read_at`（投递/已读时戳）。投递查询（待发送 / 已发送 / 已读 / 失败）和 in-app 未读统计都依赖这些字段，但表上缺少复合索引，高并发场景会导致全表扫描。做完后这些查询将能走索引。

### 1.2 做完后

- **用户视角**：`无用户可见变化 — 纯底层`
- **开发者视角**：`NotificationModel` 包含完整字段：`channel`, `template`, `params`（JSONB），`status`，`priority`，`delivered_at`，`read_at`。Service 层可直接按 `(tenant_id, user_id, status)` 等索引查询，不用扫全表。 Alembic migration 创建复合索引和 partial 索引。

### 1.3 不做什么（剔除）

- [ ] Service 层 / Router 层 — 仅建模和 DB migration，不实现 CRUD 路由
- [ ] 真实投递逻辑（deliver job）— 属于后续 AutomationRule 执行引擎板块
- [ ] 历史数据迁移脚本 — 仅新建结构， nullable 字段默认值不触发回填

### 1.4 关键 KPI

- `ruff check src/db/models/notification.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → ≥ 3 passed（3 个测试用例全部通过）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `ruff check alembic/versions/<new_revision>.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/db/models/notification.py`](../../src/db/models/notification.py) L{1}-L{40}

```{python}:src/db/models/notification.py
class NotificationModel(Base):
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

    def to_dict(self) -> dict: ...
```

缺失：缺少 `channel`, `template`, `params` (JSONB), `status`, `priority`, `delivered_at`, `read_at` 字段；缺少复合索引 `(user_id, tenant_id, status)` 和 partial 索引。

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/notification.py`](../../src/db/models/notification.py) — 新增字段 + `__table_args__` 索引声明
  - `alembic/versions/<new_revision>.py` — 新建 migration（由 alembic autogenerate 生成模板后手动补全）
- 要建：
  - `tests/unit/test_notification_model.py` — 3 个测试用例（to_dict 序列化、字段类型、Mapped 映射）
  - `alembic/versions/<id>_add_notification_extended_fields.py` — 新建 migration 文件

### 2.3 缺什么

- [ ] `NotificationModel` 缺少 `channel`（通知渠道：email/sms/push/in_app）、`template`（模板标识）、`params`（JSONB 参数）
- [ ] 缺少 `status`（pending/sent/failed/read）和 `priority`（normal/high/low）字段
- [ ] 缺少 `delivered_at` 和 `read_at` 两个时戳字段
- [ ] 缺少复合索引 `(tenant_id, user_id, status)` — 查询"某租户某用户待读通知"需全表扫描
- [ ] 缺少 partial 索引 `WHERE channel='in_app' AND read_at IS NULL` — 未读 in-app 统计
- [ ] 缺少针对新模型的单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_notification_model.py` | 3 个测试用例：to_dict 序列化、字段映射完整性、索引字段存在性 |
| `alembic/versions/<id>_add_notification_extended_fields.py` | 创建 notifications 表扩展字段 + 复合索引 + partial 索引 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/notification.py`](../../src/db/models/notification.py) | 新增 `channel`, `template`, `params` (JSONB), `status`, `priority`, `delivered_at`, `read_at` 字段；`__table_args__` 声明复合索引和 partial 索引；更新 `to_dict()` |

### 3.3 新增能力

- **ORM model**：`NotificationModel` 在 `src/db/models/notification.py`，包含 channel/template/params/status/priority/delivered_at/read_at + 索引
- **Migration**：`alembic upgrade head` 创建/修改 `notifications` 表含复合索引和 partial 索引

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **channel 用 String(20) 不选 Enum**：兼容未来新增渠道（webhook 等），不改 schema
- **params 用 JSONB 不选 JSON**：PostgreSQL JSONB 有独立索引（GIN），支持 `?` 操作符查询键值
- **status 用 String(20) 不选 Enum**：与现有 String status 风格一致（如 WorkflowModel.status）
- **Partial index 不在 ORM `__table_args__` 里声明**：SQLAlchemy 2.x 对 `postgresql_where` 支持需 `Index()` 对象，在 migration 中写 `op.execute()` 更可靠且显式

### 4.2 版本约束

<!-- 无新依赖引入，整段删掉 -->

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `notification.py` 的 `__tablename__` 保持 `notifications` — 不改名，防止历史数据丢失

### 4.4 已知坑

1. **Alembic autogenerate 对 JSONB 默认写成 JSON、DateTime 时区丢失** → 手动改回 `JSONB` 和 `DateTime(timezone=True)`
2. **Partial index（WHERE 子句）autogenerate 不会生成** → Step 4 中用 `op.execute()` 显式创建
3. **PYTHONPATH=src**，import 路径写 `from db.models.notification import NotificationModel`，不写 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 更新 NotificationModel — 新增字段 + 索引声明

在 `src/db/models/notification.py` 中新增 7 个字段和 `__table_args__`：

操作：
a) 在 `import` 区新增 `from sqlalchemy.dialects.postgresql import JSONB` 和 `from sqlalchemy import Index`
b) 在 `created_at` 之后新增字段声明
c) 在 `to_dict()` 中补充新增字段的序列化
d) 在类末尾添加 `__table_args__`

示例代码（完整新增字段块，替换 `created_at` 后）：

```python
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal", nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_notifications_user_tenant_status", "tenant_id", "user_id", "status"),
        {"sqlite_autoincrement": True},
    )
```

`to_dict()` 新增 7 个键：
```python
        "channel": self.channel,
        "template": self.template,
        "params": self.params or {},
        "status": self.status,
        "priority": self.priority,
        "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
        "read_at": self.read_at.isoformat() if self.read_at else None,
```

**完成判定**：`ruff check src/db/models/notification.py` → 0 errors

---

### Step 2: 准备 alembic_dev 数据库（clean DB）

操作：
a) 确保 docker test-db 运行：`docker compose -f configs/docker-compose.test.yml up -d test-db`
b) 在 alembic_dev 上执行 head：`docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;" && docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
c) 设置环境变量：`export PYTHONPATH=src` 和 `export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"`
d) 执行当前 head：`alembic upgrade head`

**完成判定**：`alembic current` 输出最新 revision，exit 0

---

### Step 3: 生成 migration 模板（autogenerate）

操作：
a) 执行 `alembic revision --autogenerate -m "add notification extended fields"`

预期产出：`alembic/versions/<new_id>_add_notification_extended_fields.py`

**完成判定**：文件存在且 `alembic history --verbose` 显示新增 revision

---

### Step 4: 手工修正 migration — JSONB 类型 + partial index

autogenerate 会把 `JSONB` 错写成 `JSON`，把 `DateTime(timezone=True)` 错写成 `DateTime`。手动修正：

操作：
a) 在 `import sqlalchemy as sa` 块添加：`from sqlalchemy.dialects.postgresql import JSONB`
b) 将 `params` 列的 `sa.JSON()` 改为 `JSONB().with_variant(sa.JSON(), "sqlite")`
c) 将 `delivered_at` / `read_at` 列恢复为 `DateTime(timezone=True)`
d) 在 `upgrade()` 末尾添加 partial index（autogenerate 不会生成）：

```python
    op.execute(
        "CREATE INDEX ix_notifications_in_app_unread "
        "ON notifications (tenant_id, user_id, created_at) "
        "WHERE channel = 'in_app' AND read_at IS NULL"
    )
```

e) 在 `downgrade()` 添加对应 drop：

```python
    op.drop_index("ix_notifications_in_app_unread", table_name="notifications")
```

**完成判定**：`ruff check alembic/versions/<new_id>_add_notification_extended_fields.py` → 0 errors

---

### Step 5: 验证 migration 可双向执行

操作：
a) `alembic upgrade head`
b) `alembic downgrade -1`
c) `alembic upgrade head`

**完成判定**：三次命令全部 exit 0，无错误

---

### Step 6: 编写单元测试

创建 `tests/unit/test_notification_model.py`，3 个测试用例：

```python
import pytest
from unittest.mock import MagicMock
from datetime import datetime

# Test 1: to_dict 序列化包含新字段
def test_to_dict_includes_all_fields():
    model = NotificationModel(
        id=1, tenant_id=1, user_id=42,
        channel="in_app", template="welcome", params={"name": "Alice"},
        status="pending", priority="high",
        delivered_at=None, read_at=None,
        created_at=datetime(2026, 5, 29, 12, 0, 0),
    )
    d = model.to_dict()
    assert d["channel"] == "in_app"
    assert d["template"] == "welcome"
    assert d["params"] == {"name": "Alice"}
    assert d["status"] == "pending"
    assert d["priority"] == "high"
    assert d["delivered_at"] is None
    assert d["read_at"] is None
    assert "created_at" in d

# Test 2: params 默认值（None -> {}）
def test_to_dict_params_defaults_to_empty_dict():
    model = NotificationModel(id=1, tenant_id=1, user_id=1)
    assert model.to_dict()["params"] == {}

# Test 3: __table_args__ 包含复合索引名
def test_table_args_has_composite_index():
    assert hasattr(NotificationModel, "__table_args__")
    names = [arg.name if hasattr(arg, "name") else str(arg) for arg in NotificationModel.__table_args__]
    assert any("ix_notifications_user_tenant_status" in n for n in names)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → `3 passed`

---

## 6. 验收

- [ ] `ruff check src/db/models/notification.py` → 0 errors
- [ ] `ruff check alembic/versions/<new_id>_add_notification_extended_fields.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → `3 passed`
- [ ] `alembic upgrade head` → exit 0
- [ ] `alembic downgrade -1` → exit 0
- [ ] `alembic upgrade head` → exit 0（三次连续验证）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| partial index WHERE 子句在 SQLite 环境下报错（SQLite 不支持此语法） | 低 | 中 | migration 中用 `op.execute()` 并加 `IF NOT EXISTS`，SQLite 测试环境跳过该语句，生产 PG 不受影响 |
| autogenerate 产生空 migration（autoinc 列与现有列重合） | 低 | 高 | 手动写完整 migration（参考 `alembic/versions/9d8e7f6a5b3c_add_auth_tables.py` 风格） |
| 字段重名覆盖已有列（如 `read_at` 与遗留字段冲突） | 极低 | 高 | 预检查 `DESCRIBE notifications` 输出，确认无重名字段后再 upgrade |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification.py
git add tests/unit/test_notification_model.py
git add alembic/versions/<new_id>_add_notification_extended_fields.py
git commit -m "feat(notifications): add extended fields and indexes to NotificationModel

Closes #661"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#661): add NotificationModel extended fields and indexes" --body "Closes #661"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现（ORM model + migration）：[`alembic/versions/9d8e7f6a5b3c_add_auth_tables.py`](../../alembic/versions/9d8e7f6a5b3c_add_auth_tables.py) — 多个表的复合索引 + FK
- 同类参考实现（JSONB + composite index in ORM）：[`src/db/models/workflow.py`](../../src/db/models/workflow.py) — JSONB 字段声明参考
- 同类参考实现（partial index pattern）：[`src/db/models/device_trust.py`](../../src/db/models/device_trust.py) — `__table_args__` 索引声明参考
- 父 issue：#646

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
