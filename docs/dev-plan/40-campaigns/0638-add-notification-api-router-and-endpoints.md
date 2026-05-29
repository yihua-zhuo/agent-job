# 通知 · 实现通知 API 路由与全部端点

| 元数据 | 值 |
|---|---|
| Issue | #638 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#637 Add email and SMS delivery integrations](../20-sales/0637-add-email-and-sms-delivery-integrations.md) |
| 启用后赋能 | 自动化规则（automation_rules）、线索路由（lead_routing_service）、工作流（workflow_service）均通过 NotificationService 发送通知，本板块完成前这些下游服务无法完整测试 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 需要通知能力以驱动用户参与（engagement）。当前 `NotificationService` 已存在（`src/services/notification_service.py`），但：
- `src/api/routers/notifications.py` 虽已编写完成，但偏好设置端点（`GET/PUT /notifications/preferences`）仅返回硬编码默认值，尚未连接数据库，存在 TODO 注释。
- `src/main.py` 通过 `iter_routers()` 自动发现并注册所有 router，已确认 `notifications_router` 在其中；但偏好设置的数据层（`notification_preferences` 表）缺失。
- 没有覆盖 Service 层的集成测试（只有 router 的 mock 测试）。

### 1.2 做完后

- **用户视角**：管理员可向指定用户发送通知；用户可分页查看自己的通知列表、标记单条/全部已读、配置接收偏好（含 email/sms/in_app/push 四通道）。
- **开发者视角**：下游服务（automation_rules、workflow_service、lead_routing_service）可通过 `NotificationService.send_notification()` 推送通知，无需直接操作 DB。

### 1.3 不做什么（剔除）

- [ ] email/SMS 通道的实际发送逻辑（第 637 号板块负责）
- [ ] WebSocket / SSE 实时推送
- [ ] 通知批量导入/导出

### 1.4 关键 KPI

- `ruff check src/api/routers/notifications.py src/services/notification_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → ≥ 28 passed
- `PYTHONPATH=src pytest tests/integration/test_notification_service_integration.py -v` → ≥ 5 passed
- `ruff check src/db/models/notification.py src/db/models/reminder.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) L1-L269

```python
1:"""Notifications router — /api/v1/notifications and /api/v1/reminders endpoints.
2:
3:Services raise AppException on errors (caught by global handler in main.py).
4:Router wraps service return values in success envelopes.
5:"""
6:
7:from fastapi import APIRouter, Depends, HTTPException, Path, Query
8:from pydantic import BaseModel, Field
9:from sqlalchemy.ext.asyncio import AsyncSession
10:
11:from db.connection import get_db
12:from internal.middleware.fastapi_auth import AuthContext, require_auth
13:from services.notification_service import NotificationService
14:
15:notifications_router = APIRouter(prefix="/api/v1", tags=["notifications"])
```

Service 层：[`src/services/notification_service.py`](../../src/services/notification_service.py) L1-L208

已实现方法：
- `send_notification()` — 写 notifications 表
- `get_user_notifications()` — 分页读，含 unread_only 过滤
- `mark_as_read()` — 单条标记已读，找不到抛 `NotFoundException`
- `mark_all_as_read()` — 批量标记已读
- `delete_notification()` — 按 ID 删除
- `get_unread_count()` — 计数
- `create_reminder()` / `cancel_reminder()` / `get_reminders()` — 提醒 CRUD

Model 层：
- [`src/db/models/notification.py`](../../src/db/models/notification.py) — `NotificationModel`，已实现 `to_dict()`
- [`src/db/models/reminder.py`](../../src/db/models/reminder.py) — `ReminderModel`，已实现 `to_dict()`

已有单元测试：[`tests/unit/test_notifications_router.py`](../../tests/unit/test_notifications_router.py) — 28 个测试用例，覆盖所有端点 + 无效 tenant 边界情况。

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) — 清除 L181、L196 的 TODO 注释，实现 preferences 读写至 DB
- 要建：
  - `src/db/models/notification_preferences.py` — 存储用户通知偏好（含 tenant_id multi-tenancy）
  - `alembic/versions/<id>_add_notification_preferences_table.py` — 创建 notification_preferences 表
  - `tests/integration/test_notification_service_integration.py` — 集成测试（真实 DB）

### 2.3 缺什么

- [ ] `notification_preferences` 表及 ORM model — preferences 端点数据无持久化
- [ ] integration test for `NotificationService` — 只有 router mock 测试，无真实 DB 端到端覆盖
- [ ] preferences 端点还回硬编码默认值（`PreferencesData(email=True, sms=False, in_app=True, push=False).model_dump()`），未连接 DB

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/notification_preferences.py` | ORM model：存储 user_id / tenant_id / email/sms/in_app/push 四通道开关 |
| `alembic/versions/<id>_add_notification_preferences_table.py` | 创建 `notification_preferences` 表，含 tenant_id + user_id 复合索引 |
| `tests/integration/test_notification_service_integration.py` | Service 层集成测试（真 DB）：send / list / mark_read / mark_all_read / preferences CRUD |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/notifications.py`](../../src/api/routers/notifications.py) | 实现 `get_notification_preferences` / `update_notification_preferences` 读写 `NotificationPreferences` model（消除 TODO） |

### 3.3 新增能力

- **ORM model**：`NotificationPreferences` in `src/db/models/notification_preferences.py`
- **API endpoint**：`GET /api/v1/notifications/preferences` → 从 DB 读取用户偏好（不存在时返回默认）
- **API endpoint**：`PUT /api/v1/notifications/preferences` → 写入/更新用户偏好（UPSERT）
- **Migration**：`alembic upgrade head` 创建 `notification_preferences` 表（含 `(tenant_id, user_id)` 唯一索引）
- **Integration test**：`NotificationService` 覆盖 send / list / mark_as_read / mark_all_as_read / preferences get+update 全部路径

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **UPSERT 而非先查后改**：preferences 只有一条记录，用 `INSERT ... ON CONFLICT (tenant_id, user_id) DO UPDATE`，避免两次 DB round-trip。
- **默认值放在 DB 而非代码**：preferences 记录不存在时返回 `{email: True, sms: False, in_app: True, push: False}`，与硬编码默认值一致；UPSERT 时以此为默认值 INSERT。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- 所有 endpoints 在 `require_auth` 保护下，`tenant_id=0` 或 `tenant_id=None` 时返回 401（已在 router 层面拦截，无需 service 处理）

### 4.4 已知坑

1. **SQLAlchemy Base 子类列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ 本板块新增 `NotificationPreferences` 模型，列名已规避（用 `email_enabled` / `sms_enabled` 等字段名，不含 `metadata`）
2. **Alembic autogen 会把 JSONB 写成 JSON、TIMESTAMPTZ 写成 DateTime** → 本次迁移无 JSONB/TIMESTAMPTZ 类型，手动审查 migration 文件
3. **PYTHONPATH=src** → 本板块所有测试运行前必须 `export PYTHONPATH=src`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 NotificationPreferences ORM model

在 `src/db/models/notification_preferences.py` 新建文件。

操作：
- a) 创建 `src/db/models/notification_preferences.py`，定义 `NotificationPreferences` 类，继承 `Base`，表名 `notification_preferences`
- b) 列：`id`(PK, autoincrement), `tenant_id`(Integer, nullable=False, index=True), `user_id`(Integer, nullable=False, index=True), `email_enabled`(Boolean, default=True), `sms_enabled`(Boolean, default=False), `in_app_enabled`(Boolean, default=True), `push_enabled`(Boolean, default=False), `created_at`(DateTime, server_default=func.now()), `updated_at`(DateTime, onupdate=func.now())
- c) 添加唯一约束：`(tenant_id, user_id)` 复合唯一索引（确保每用户只有一条偏好记录）
- d) 实现 `to_dict()` 方法

```python
class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id"), Index("ix_notification_preferences_tenant_user", "tenant_id", "user_id", unique=True))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
```

**完成判定**：`ruff check src/db/models/notification_preferences.py` → 0 errors

---

### Step 2: 生成 Alembic migration

操作：
- a) 确保 `alembic/env.py` 已通过 `import db.models` 加载了 `notification_preferences` model（已验证：`db.models/__init__.py` 使用 pkgutil 自动发现，notification_preferences.py 会被自动纳入）
- b) 生成 migration：`alembic revision --autogenerate -m "add notification_preferences table"`
- c) 审查生成文件：确认 `tenant_id`、`user_id` 列类型为 Integer（非 JSON），`email_enabled` 等为 Boolean；手动修正任何类型偏差
- d) 验证：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次均 exit 0

---

### Step 3: 实现 NotificationPreferencesService（在 NotificationService 中增加 preferences 方法）

在 `src/services/notification_service.py` 末尾增加两个方法：

```python
async def get_preferences(self, user_id: int, tenant_id: int) -> NotificationPreferences:
    """获取用户通知偏好，找不到返回 None（router 层转默认）"""
    result = await self.session.execute(
        select(NotificationPreferences).where(
            and_(
                NotificationPreferences.tenant_id == tenant_id,
                NotificationPreferences.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()

async def upsert_preferences(
    self,
    user_id: int,
    tenant_id: int,
    email_enabled: bool = True,
    sms_enabled: bool = False,
    in_app_enabled: bool = True,
    push_enabled: bool = False,
) -> NotificationPreferences:
    """UPSERT 用户通知偏好（INSERT ON CONFLICT DO UPDATE）"""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(NotificationPreferences).values(
        tenant_id=tenant_id,
        user_id=user_id,
        email_enabled=email_enabled,
        sms_enabled=sms_enabled,
        in_app_enabled=in_app_enabled,
        push_enabled=push_enabled,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "user_id"],
        set_={
            "email_enabled": stmt.excluded.email_enabled,
            "sms_enabled": stmt.excluded.sms_enabled,
            "in_app_enabled": stmt.excluded.in_app_enabled,
            "push_enabled": stmt.excluded.push_enabled,
        },
    )
    await self.session.execute(stmt)
    await self.session.flush()
    prefs = await self.get_preferences(user_id, tenant_id)
    return prefs
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

---

### Step 4: 改造 preferences 端点（清除 TODO，接 DB）

在 `src/api/routers/notifications.py` 修改 `get_notification_preferences` 和 `update_notification_preferences`：

```python
@notifications_router.get(
    "/notifications/preferences",
    summary="Get notification preferences for current user",
)
async def get_notification_preferences(
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get the current user's notification preferences (from DB)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    svc = NotificationService(session)
    prefs = await svc.get_preferences(current_user.user_id, tenant_id=current_user.tenant_id)
    if prefs is None:
        return {"success": True, "data": PreferencesData().model_dump()}
    return {"success": True, "data": prefs.to_dict()}


@notifications_router.put(
    "/notifications/preferences",
    summary="Update notification preferences for current user",
)
async def update_notification_preferences(
    body: PreferencesData,
    current_user: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update the current user's notification preferences (UPSERT)."""
    if current_user.tenant_id is None or current_user.tenant_id == 0:
        raise HTTPException(status_code=401, detail="无效的租户信息")
    svc = NotificationService(session)
    prefs = await svc.upsert_preferences(
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        email_enabled=body.email,
        sms_enabled=body.sms,
        in_app_enabled=body.in_app,
        push_enabled=body.push,
    )
    return {"success": True, "data": prefs.to_dict()}
```

操作：
- a) 删除 `src/api/routers/notifications.py` L181 和 L196 的 `# TODO: notification_preferences table not yet in schema` 注释
- b) 将两个 preferences 端点的 `session: AsyncSession = Depends(get_db)` 注入补上（`get_notification_preferences` 缺少 session 注入）
- c) 实现上述两个函数体

**完成判定**：`ruff check src/api/routers/notifications.py` → 0 errors

---

### Step 5: 编写集成测试

创建 `tests/integration/test_notification_service_integration.py`：

```python
import pytest
from sqlalchemy import text
from internal.middleware.fastapi_auth import AuthContext
from services.notification_service import NotificationService
from db.models.notification import NotificationModel
from db.models.notification_preferences import NotificationPreferences


async def test_send_and_list_notifications(async_session, tenant_id):
    svc = NotificationService(async_session)
    n = await svc.send_notification(1, "info", "Test", "Content", tenant_id=tenant_id)
    items, total = await svc.get_user_notifications(1, tenant_id=tenant_id)
    assert total >= 1
    assert any(x.title == "Test" for x in items)


async def test_mark_as_read_not_found(async_session, tenant_id):
    svc = NotificationService(async_session)
    with pytest.raises(NotFoundException):
        await svc.mark_as_read(99999, tenant_id=tenant_id)


async def test_mark_all_as_read(async_session, tenant_id):
    svc = NotificationService(async_session)
    await svc.send_notification(2, "info", "A", "A", tenant_id=tenant_id)
    await svc.send_notification(2, "info", "B", "B", tenant_id=tenant_id)
    result = await svc.mark_all_as_read(2, tenant_id=tenant_id)
    assert result["marked_count"] >= 2


async def test_preferences_upsert(async_session, tenant_id):
    svc = NotificationService(async_session)
    prefs = await svc.upsert_preferences(5, tenant_id, email_enabled=False, sms_enabled=True)
    assert prefs.email_enabled is False
    assert prefs.sms_enabled is True
    prefs2 = await svc.upsert_preferences(5, tenant_id, push_enabled=True)
    assert prefs2.email_enabled is False
    assert prefs2.push_enabled is True


async def test_preferences_get_default(async_session, tenant_id):
    svc = NotificationService(async_session)
    prefs = await svc.get_preferences(999, tenant_id=tenant_id)
    assert prefs is None
```

操作：
- a) 创建 `tests/integration/test_notification_service_integration.py`
- b) 实现上述 5 个集成测试（真实 DB session fixture）

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_notification_service_integration.py -v` → 5 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/notifications.py src/services/notification_service.py src/db/models/notification_preferences.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notifications_router.py -v` → ≥ 28 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_notification_service_integration.py -v` → ≥ 5 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `ruff check src/db/models/notification.py src/db/models/reminder.py src/db/models/notification_preferences.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| preferences UPSERT 在其他数据库（MySQL）不兼容 | 低 | 中 | PostgreSQL only — 已在 CLAUDE.md 确定使用 postgresql+asyncpg；如需多 DB 支持，将 `pg_insert` 替换为 ORM `merge()` |
| migration 生成时遗漏 `tenant_id` 索引 | 低 | 高 | 手动修改 migration 文件，在 `notification_preferences` 表上补加 `Index("ix_nfp_tenant_user", "tenant_id", "user_id", unique=True)` |
| integration test fixture `async_session` 未正确清理导致测试间数据污染 | 中 | 低 | `db_schema` fixture 已使用 TRUNCATE CASCADE 自动清理每测试函数结束后的所有表 |
| `iter_routers()` 无法发现新增的 notification_preferences model（自动发现机制失效） | 极低 | 中 | `db.models/__init__.py` 使用 pkgutil 自动发现，只需确保 `src/db/models/notification_preferences.py` 在 `db.models` 包下，model 会自动注册到 `Base.metadata` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification_preferences.py \
        src/api/routers/notifications.py \
        src/services/notification_service.py \
        alembic/versions/<id>_add_notification_preferences_table.py \
        tests/integration/test_notification_service_integration.py
git commit -m "feat(notifications): add preferences model, migration and preferences endpoints"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(notifications): add preferences storage + integration tests" --body "Closes #638

## Summary
- Add NotificationPreferences ORM model + alembic migration
- Wire GET/PUT /api/v1/notifications/preferences to DB (UPSERT)
- Add NotificationService.get_preferences() + upsert_preferences() methods
- Add 5 integration test cases for NotificationService

## Test plan
- [ ] ruff check — 0 errors
- [ ] pytest tests/unit/test_notifications_router.py -v → ≥ 28 passed
- [ ] pytest tests/integration/test_notification_service_integration.py -v → ≥ 5 passed
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`src/api/routers/customers.py`](../../src/api/routers/customers.py) — router 中 `session: AsyncSession = Depends(get_db)` 注入模式
- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — service 层返回 ORM + 抛异常模式
- 父 issue：#39
- 依赖 issue：#637（email/SMS delivery）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
