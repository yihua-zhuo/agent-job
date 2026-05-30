# Notifications · Send in-app notifications

| 元数据 | 值 |
|---|---|
| Issue | #647 |
| 分类 | 40-campaigns |
| 优先级 | 推荐 |
| 工作量 | 2 工作日 |
| 依赖 | [板块名](../50-automation/0646-implement-notification-model-and-preferences-api.md) |
| 启用后赋能 | [板块名](../60-analytics/...), [板块名](../60-analytics/...) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统需要向用户推送应用内通知（in-app notification），但目前没有通知服务。用户无法在系统中查看历史通知、标记已读或管理通知偏好。issue #646 提供了通知数据模型和偏好 API 基础，本板块在此之上实现完整的 `NotificationService`，提供同步 in-app 消息投递、列表查询和已读管理能力。

### 1.2 做完后

- **用户视角**：用户可以在 CRM 中看到自己的通知列表，点击标记为已读，或一键全部已读；可以在偏好设置中开启/关闭通知类型推送开关。
- **开发者视角**：其他 service 可调用 `NotificationService.send_notification()` 存储并同步投递 in-app 通知；`list_notifications()` 支持分页查询；`get_preferences()` / `update_preferences()` 支持通知偏好读写。

### 1.3 不做什么（剔除）

- [ ] 不实现后台任务队列（Celery / RQ 等）—— 投递是同步的，status=queued 仅作为状态标记
- [ ] 不实现 WebSocket / SSE 实时推送 —— in-app 通知通过轮询/刷新获取
- [ ] 不实现邮件 / SMS / Push 外部通道 —— 仅 in-app 存储和展示
- [ ] 不实现通知的软删除（is_deleted 标记）—— 保留数据不做软删

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → `≥ 10 passed`
- `ruff check src/services/notification_service.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 3次 exit 0（migration 验收）
- `ruff check src/services/notification_service.py src/db/models/notification.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

issue #646 已实现 `NotificationModel` ORM 模型和 `NotificationPreferencesModel` 模型，位于 `src/db/models/notification.py`（需验证是否存在）。偏好更新 API 端点已在 `src/api/routers/notifications.py` 中实现。

TBD - 待验证：issue #646 的产出状态，确认 `src/db/models/notification.py` 中 `NotificationModel` 和 `NotificationPreferencesModel` 是否已就绪；若尚未合入，本板块需一并创建 ORM 模型。

### 2.2 涉及文件清单

- 要改：
  - TBD - 待补充：根据 #646 合入情况决定是否需要修改 `src/db/models/notification.py`
- 要建：
  - `src/services/notification_service.py` — 通知业务逻辑层（核心交付物）
  - `tests/unit/test_notification_service.py` — 单元测试（覆盖 send/list/mark_read/preference 路径）
  - `alembic/versions/<id>_add_notification_tables.py` — 如 #646 未包含 migration 则新建

### 2.3 缺什么

- [ ] `NotificationService` — 业务逻辑类，承担所有通知相关操作（当前不存在）
- [ ] `send_notification()` 方法 — 存储通知记录 + 同步 in-app 投递（状态标记为 delivered）
- [ ] `list_notifications()` 方法 — 按 user_id + tenant_id 分页查询通知列表
- [ ] `mark_read()` / `mark_all_read()` 方法 — 标记单条或全部通知为已读
- [ ] `get_preferences()` / `update_preferences()` 方法 — 通知偏好读写（委托 #646 模型）
- [ ] 单元测试覆盖 — send / list / mark_read / preference update 四条路径

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/notification_service.py` | NotificationService：send/list/mark_read/get_prefs/update_prefs |
| `tests/unit/test_notification_service.py` | 单元测试：send、list、mark_read、preference 覆盖 |
| `alembic/versions/<id>_add_notification_tables.py` | 若 #646 未提供 migration 则新建；否则复用 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待确认 #646 合入后状态 | 视合入情况决定是否需要修改模型文件 |

### 3.3 新增能力

- **Service method**：`NotificationService.send_notification(self, user_id: int, tenant_id: int, event_type: str, content: str, metadata: dict | None = None) -> NotificationModel`
- **Service method**：`NotificationService.list_notifications(self, user_id: int, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[NotificationModel], int]`
- **Service method**：`NotificationService.mark_read(self, notification_id: int, tenant_id: int) -> NotificationModel`
- **Service method**：`NotificationService.mark_all_read(self, user_id: int, tenant_id: int) -> int`
- **Service method**：`NotificationService.get_preferences(self, user_id: int, tenant_id: int) -> NotificationPreferencesModel`
- **Service method**：`NotificationService.update_preferences(self, user_id: int, tenant_id: int, preferences: dict) -> NotificationPreferencesModel`
- **ORM model**：`NotificationModel` in `src/db/models/notification.py`（#646 已提供）
- **Migration**：`alembic upgrade head` 创建 `notifications` / `notification_preferences` 表

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **同步 in-app 投递，不选后台任务队列**：CRM 系统通知量可控，同步投递简化架构，避免引入 Celery/RQ 等额外依赖。在 `send_notification()` 中写入 DB 后直接返回，status=delivered 标记已投递。
- **分页用 offset 方案**：当前数据量预期不超过数千条，offset 分页足够；后续如需游标分页可迁移。
- **偏好模型委托给 #646**：preferences 的 CRUD 直接通过 `NotificationPreferencesModel` 操作，本 service 负责调用，不重复实现 ORM 逻辑。

### 4.2 版本约束

TBD - 待补充：根据 #646 合入情况决定是否有新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- 所有 service 方法接受 `tenant_id: int` 参数并在 SQL 中注入过滤条件
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- 通知按 `user_id + tenant_id` 联合索引查询，确保同一租户用户的数据隔离

### 4.4 已知坑

1. **SQLAlchemy 列名 `metadata` 与 Base.metadata 冲突** → 通知元数据列命名为 `event_metadata`（dict 类型），避免与 `Base.metadata` 冲突
2. **Alembic autogenerate 把 JSONB 写成 JSON** → migration 中手动改回 `JSONB` 类型
3. **PYTHONPATH=src，import 路径写 `from db.models...`** → 不写 `from src.db.models...`，否则运行时找不到模块
4. **Async session 使用 `Depends(get_db)` 而非 `async with get_db()`** → 在 router 层通过依赖注入传入，不要手动上下文管理

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 NotificationService 类框架

在 `src/services/notification_service.py` 中定义 `NotificationService`，`__init__` 接收 `AsyncSession`，无默认值。在类中声明 6 个方法签名（send_notification / list_notifications / mark_read / mark_all_read / get_preferences / update_preferences），暂留空实现。

```python
# src/services/notification_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_notification(
        self,
        user_id: int,
        tenant_id: int,
        event_type: str,
        content: str,
        metadata: dict | None = None,
    ) -> NotificationModel:
        ...
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

### Step 2: 实现 send_notification

存储通知记录到 `notifications` 表，status='queued'；立即更新 status='delivered' 表示已同步投递。返回 `NotificationModel` ORM 对象。

```python
    async def send_notification(
        self,
        user_id: int,
        tenant_id: int,
        event_type: str,
        content: str,
        metadata: dict | None = None,
    ) -> NotificationModel:
        from datetime import datetime, timezone
        from src.db.models.notification import NotificationModel

        notification = NotificationModel(
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event_type,
            content=content,
            event_metadata=metadata or {},
            status="delivered",
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

### Step 3: 实现 list_notifications

按 `user_id + tenant_id` 过滤，分页返回通知列表 + 总数。

```python
    async def list_notifications(
        self,
        user_id: int,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NotificationModel], int]:
        from sqlalchemy import func, select
        from src.db.models.notification import NotificationModel

        offset = (page - 1) * page_size
        count_q = select(func.count(NotificationModel.id)).where(
            NotificationModel.user_id == user_id,
            NotificationModel.tenant_id == tenant_id,
        )
        total = (await self.session.execute(count_q)).scalar_one()

        list_q = select(NotificationModel).where(
            NotificationModel.user_id == user_id,
            NotificationModel.tenant_id == tenant_id,
        ).order_by(NotificationModel.created_at.desc()).offset(offset).limit(page_size)
        items = list((await self.session.execute(list_q)).scalars().all())
        return items, total
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

### Step 4: 实现 mark_read 和 mark_all_read

`mark_read`: 按 `notification_id + tenant_id` 查询，单条标记 `is_read=True`；找不到则抛 `NotFoundException`。`mark_all_read`: 按 `user_id + tenant_id` 批量更新，返回影响行数。

```python
    async def mark_read(self, notification_id: int, tenant_id: int) -> NotificationModel:
        from sqlalchemy import select
        from src.db.models.notification import NotificationModel

        q = select(NotificationModel).where(
            NotificationModel.id == notification_id,
            NotificationModel.tenant_id == tenant_id,
        )
        notification = (await self.session.execute(q)).scalar_one_or_none()
        if notification is None:
            raise NotFoundException("Notification")
        notification.is_read = True
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def mark_all_read(self, user_id: int, tenant_id: int) -> int:
        from sqlalchemy import update
        from src.db.models.notification import NotificationModel

        q = update(NotificationModel).where(
            NotificationModel.user_id == user_id,
            NotificationModel.tenant_id == tenant_id,
            NotificationModel.is_read == False,
        ).values(is_read=True)
        result = await self.session.execute(q)
        await self.session.commit()
        return result.rowcount
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

### Step 5: 实现 get_preferences 和 update_preferences

`get_preferences`: 按 `user_id + tenant_id` 查询 `NotificationPreferencesModel`，不存在则自动创建默认偏好记录。`update_preferences`: 接受 dict，逐字段更新已提供的键，提交后返回更新后对象。

```python
    async def get_preferences(self, user_id: int, tenant_id: int) -> NotificationPreferencesModel:
        from sqlalchemy import select
        from src.db.models.notification import NotificationPreferencesModel

        q = select(NotificationPreferencesModel).where(
            NotificationPreferencesModel.user_id == user_id,
            NotificationPreferencesModel.tenant_id == tenant_id,
        )
        pref = (await self.session.execute(q)).scalar_one_or_none()
        if pref is None:
            pref = NotificationPreferencesModel(user_id=user_id, tenant_id=tenant_id)
            self.session.add(pref)
            await self.session.commit()
            await self.session.refresh(pref)
        return pref

    async def update_preferences(
        self, user_id: int, tenant_id: int, preferences: dict
    ) -> NotificationPreferencesModel:
        from sqlalchemy import select
        from src.db.models.notification import NotificationPreferencesModel

        pref = await self.get_preferences(user_id, tenant_id)
        for key, value in preferences.items():
            if hasattr(pref, key):
                setattr(pref, key, value)
        await self.session.commit()
        await self.session.refresh(pref)
        return pref
```

**完成判定**：`ruff check src/services/notification_service.py` → 0 errors

### Step 6: 编写单元测试

在 `tests/unit/test_notification_service.py` 中使用 `make_mock_session` + MockRow/MockResult 模式覆盖：

1. `test_send_notification_success` — 验证写入后返回 ORM 对象
2. `test_send_notification_stores_correct_fields` — 验证 tenant_id / status / is_read 默认值
3. `test_list_notifications_paginated` — 验证 offset 分页逻辑
4. `test_list_notifications_empty` — 验证空列表返回 ( [], 0 )
5. `test_mark_read_success` — 验证单条已读
6. `test_mark_read_not_found` — 验证抛 NotFoundException
7. `test_mark_all_read_returns_count` — 验证批量更新返回行数
8. `test_get_preferences_creates_default` — 验证不存在时自动创建
9. `test_update_preferences_partial` — 验证只更新传入字段

```python
# tests/unit/test_notification_service.py
import pytest
from tests.unit.conftest import make_mock_session, MockState, MockRow, MockResult

# fixtures
@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_notification_handler(state)])

@pytest.fixture
def notification_service(mock_db_session):
    from src.services.notification_service import NotificationService
    return NotificationService(mock_db_session)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → `≥ 9 passed`

### Step 7: 确保 migration 已就绪

检查 `alembic/versions/` 目录是否已有创建 `notifications` / `notification_preferences` 表的 migration（#646 产出）。若不存在，手动编写：

```python
# alembic/versions/<id>_add_notification_tables.py
def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_tenant", "notifications", ["user_id", "tenant_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notif_prefs_user_tenant", "notification_preferences", ["user_id", "tenant_id"])
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 3次 exit 0

---

## 6. 验收

- [ ] `ruff check src/services/notification_service.py` → 0 errors
- [ ] `ruff check src/db/models/notification.py` → 0 errors（如有改动）
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v` → `≥ 9 passed`
- [ ] `PYTHONPATH=src pytest tests/integration/test_notification_integration.py -v` → 全 passed（如有 integration 测试）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `ruff check src/services/notification_service.py src/db/models/notification.py tests/unit/test_notification_service.py` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #646 尚未合入导致 ORM 模型不可用 | 中 | 中 | 本板块先实现 service 骨架，ORM 部分 TBD 占位；待 #646 合入后补全实现 |
| 多租户数据隔离疏漏（漏加 tenant_id 条件） | 低 | 高 | 单元测试覆盖所有查询路径，并在 list/mark_read 等方法中验证 tenant_id 过滤 |
| notification 表 migration 与 #646 模型不同步 | 低 | 高 | 本板块明确注明依赖 #646 的 migration；若存在 drift，重新评审合并顺序 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/notification_service.py tests/unit/test_notification_service.py
git commit -m "feat(notifications): implement NotificationService for in-app delivery"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(notifications): implement NotificationService" --body "Closes #647"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — service 层模式参考
- 第三方文档：[FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- 父 issue / 关联：#39, #646

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
