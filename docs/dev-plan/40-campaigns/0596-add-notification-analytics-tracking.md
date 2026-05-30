# 通知分析追踪 · 添加通知开启追踪与打开率统计

| 元数据 | 值 |
|---|---|
| Issue | #596 |
| 分类 | 40-campaigns |
| 优先级 | 推荐 |
| 工作量 | 1 工作日 |
| 依赖 | TBD - 待验证：通知核心模块路径（#595，如存在） |
| 启用后赋能 | 自动化规则引擎（#687） — 触发条件依赖打开率数据 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 通知系统只负责发送，不记录用户是否真正查看或点击了通知。营销/客服团队无法量化通知的触达效果，无法区分"已发送但未读"与"已读但未点击"。没有打开率数据，自动化规则引擎（#687）就无法基于用户参与度设计触发条件。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯数据收集层改动。
- **开发者视角**：`NotificationAnalyticsService` 提供 `track_open`（记录开启）和 `get_open_rate`（返回 float 打开率）两个方法；`PATCH /notifications/{id}/open` 端点供前端在用户打开通知时调用；`NotificationAnalytics` ORM model 可供后续查询和规则匹配。

### 1.3 不做什么（剔除）

- [ ] 不实现点击追踪（`clicked_at` 字段结构已预留，但 `track_click` 方法不在本 issue 范围）
- [ ] 不实现通知发送逻辑（发送层属于通知核心模块 #595）
- [ ] 不实现通知已读消息推送或 WebSocket 推送

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_notification_analytics.py -v` → ≥ 5 passed]
- [指标 2：`ruff check src/services/notification_analytics_service.py src/db/models/notification.py src/api/routers/notifications.py` → 0 errors]
- [指标 3：`ruff check src/services/notification_analytics_service.py src/db/models/notification.py src/api/routers/notifications.py` → 0 warnings]

---

## 2. 当前现状（起点）

### 2.1 现有实现

通知模型文件存在，但尚无分析追踪能力。

TBD - 待验证：`src/db/models/notification.py` L? — 现有 Notification ORM model，需确认其字段结构（id, tenant_id, channel 等）以便在同文件添加 NotificationAnalytics

通知服务文件存在，但尚无 AnalyticsService。

TBD - 待验证：`src/services/notification_service.py` L? — 现有 NotificationService，可参考其结构设计 NotificationAnalyticsService

路由文件可能已存在通知相关端点。

TBD - 待验证：`src/api/routers/` 下是否有 `notification.py` 或 `notifications.py` — 如无则新建

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/notification.py` — 新增 `NotificationAnalytics` ORM model
  - `src/api/routers/` — 新增或扩展 `notification.py`，添加 `PATCH /notifications/{id}/open`
- 要建：
  - `src/services/notification_analytics_service.py` — 业务逻辑层
  - `tests/unit/test_notification_analytics.py` — 单元测试

### 2.3 缺什么

- [ ] 无 `NotificationAnalytics` ORM model，无法持久化存储开启事件
- [ ] 无 `NotificationAnalyticsService`，业务逻辑分散或缺失
- [ ] 无 `track_open` 方法，无法记录通知被开启的时间和渠道
- [ ] 无 `get_open_rate` 方法，无法计算单个通知的打开率
- [ ] 无 `PATCH /notifications/{id}/open` 端点，前端无法上报开启事件

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/notification_analytics_service.py` | 通知分析服务：track_open / get_open_rate |
| `tests/unit/test_notification_analytics.py` | NotificationAnalyticsService 单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/notification.py`](../../../src/db/models/notification.py) | 新增 `NotificationAnalytics` ORM model（含 id, notification_id, tenant_id, opened_at, clicked_at, channel） |
| [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py)（或新建） | 新增 `PATCH /notifications/{id}/open` 端点，调用 `NotificationAnalyticsService.track_open` |

### 3.3 新增能力

- **ORM model**：`NotificationAnalytics` in `src/db/models/notification.py`（字段：id, notification_id, tenant_id, opened_at, clicked_at, channel）
- **Service method**：`NotificationAnalyticsService.track_open(self, notification_id: int, tenant_id: int) -> NotificationAnalytics`
- **Service method**：`NotificationAnalyticsService.get_open_rate(self, notification_id: int, tenant_id: int) -> float`
- **API endpoint**：`PATCH /notifications/{id}/open` → `{"success": true, "data": {"opened_at": "...", "open_rate": 0.XX}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **在 notification.py 同文件内新增 model 而非新建文件**：通知分析数据与通知强关联，放同一文件减少 import 复杂度。
- **打开率计算为已开启数 / 已发送总数（float）**：不做百分比字符串，由调用方自行格式化；除零时返回 `0.0`。

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service `__init__` 接受 `session: AsyncSession`，**禁止**设置默认值
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误时抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- SQLAlchemy：ORM model 继承自 `db.base.Base`

### 4.4 已知坑

1. **Alembic autogenerate 把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 本 issue 不涉及 migration（model 在 `create_all` 路径），但如后续生成 migration，需手动修正
2. **SQLAlchemy Base 子类列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ `NotificationAnalytics` 使用 `event_metadata` 或不添加此类字段；已规划字段名均为标准 SQL 类型，无此风险

---

## 5. 实现步骤（按顺序）

### Step 1: 新增 NotificationAnalytics ORM model

在 `src/db/models/notification.py` 中添加 `NotificationAnalytics` 类：

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

class Base(DeclarativeBase):
    pass

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # ... 其他现有字段

class NotificationAnalytics(Base):
    __tablename__ = "notification_analytics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
```

**完成判定**：`ruff check src/db/models/notification.py` → 0 errors

---

### Step 2: 新建 NotificationAnalyticsService

创建 `src/services/notification_analytics_service.py`：

```python
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.notification import NotificationAnalytics

class NotificationAnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def track_open(
        self, notification_id: int, tenant_id: int, channel: str = "email"
    ) -> NotificationAnalytics:
        """记录通知被开启，upsert 语义（重复调用不创建新行）"""
        stmt = select(NotificationAnalytics).where(
            NotificationAnalytics.notification_id == notification_id,
            NotificationAnalytics.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.opened_at = datetime.now(timezone.utc)
            await self.session.commit()
            return existing
        analytics = NotificationAnalytics(
            notification_id=notification_id,
            tenant_id=tenant_id,
            opened_at=datetime.now(timezone.utc),
            channel=channel,
        )
        self.session.add(analytics)
        await self.session.commit()
        await self.session.refresh(analytics)
        return analytics

    async def get_open_rate(self, notification_id: int, tenant_id: int) -> float:
        """返回该通知的打开率 = 已开启记录数 / 1（如有多渠道则按 channel 分组计算）"""
        stmt = select(func.count(NotificationAnalytics.id)).where(
            NotificationAnalytics.notification_id == notification_id,
            NotificationAnalytics.tenant_id == tenant_id,
            NotificationAnalytics.opened_at.isnot(None),
        )
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        if count == 0:
            return 0.0
        return float(count)  # 分母暂为 count 本身，后续联动通知发送总数时可改为 count/total_sent
```

**完成判定**：`ruff check src/services/notification_analytics_service.py` → 0 errors

---

### Step 3: 新增 PATCH /notifications/{id}/open 端点

在 `src/api/routers/notifications.py`（或新建）中添加路由：

```python
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies import AuthContext, require_auth

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.patch("/{notification_id}/open")
async def track_notification_open(
    notification_id: int = Path(..., description="通知 ID"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = NotificationAnalyticsService(session)
    analytics = await svc.track_open(notification_id, tenant_id=ctx.tenant_id)
    rate = await svc.get_open_rate(notification_id, tenant_id=ctx.tenant_id)
    return {
        "success": True,
        "data": {
            "opened_at": analytics.opened_at.isoformat() if analytics.opened_at else None,
            "open_rate": rate,
        },
    }
```

**完成判定**：`ruff check src/api/routers/notifications.py` → 0 errors

---

### Step 4: 编写单元测试

创建 `tests/unit/test_notification_analytics.py`，覆盖以下场景：

- `track_open` 首次调用创建记录
- `track_open` 重复调用执行 upsert（更新 `opened_at`）
- `get_open_rate` 无记录返回 `0.0`
- `get_open_rate` 有记录返回正 float
- 异常：`NotificationAnalytics` 查询时 `tenant_id` 不匹配不抛错（空结果）

Mock session 通过 `tests/unit/conftest.py` 的 `make_mock_session` 构建。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_analytics.py -v` → ≥ 5 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_analytics.py -v` → ≥ 5 passed
- [ ] `ruff format --check src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py` → 无需格式化输出（0 differences）
- [ ] `mypy src/services/notification_analytics_service.py` → 0 errors（如 mypy 已配置）
- [ ] 新增 model 已注册到 `db.base.Base.metadata`（确认 `from db.models.notification import NotificationAnalytics` 在 `alembic/env.py` 或 `db/base.py` 中）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `track_open` upsert 与现有通知发送侧事务冲突（如 #595 尚未合并，通知表结构不稳定） | 低 | 中 | 本 issue 完成后将 model 字段对齐 #595 最终结构，如有字段缺失补充 migration |
| `get_open_rate` 暂时分母为 count 而非发送总数，打开率数值初期偏低（无法反映真实触达率） | 中 | 低 | 在 #687 自动化规则引擎中读取通知发送记录，分子分母均改为查询 `Notification` 表总发送数；本 issue 打开率仅衡量"开启用户数"而非"总发送用户数" |
| `NotificationAnalytics` 表未建立索引导致大表查询慢 | 低 | 中 | 通过 migration 添加 `(notification_id, tenant_id)` 联合索引，不阻塞下游 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/notification.py src/services/notification_analytics_service.py src/api/routers/notifications.py tests/unit/test_notification_analytics.py
git commit -m "feat(notifications): add NotificationAnalytics model and tracking service"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#596): notification analytics tracking" --body "Closes #596"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/opportunity_service.py` — 现有 Service 层结构，可参考其 constructor 和方法签名模式
- 同类参考实现：TBD - 待验证：`src/api/routers/ticket.py` — 现有 PATCH 端点模式，可参考参数注入和 response 结构
- 父 issue：#47
- 依赖 issue：#595

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---

**Two fixes applied:**

1. **Line 9** (`../30-tickets/0000-ticket-overview.md`) → replaced with `TBD - 待验证：通知核心模块路径` — no such overview file exists in `30-tickets/`, only numbered feature files, so the correct target cannot be derived.

2. **Line 89** (`../../src/api/routers/notification.py`) → corrected to `../../src/api/routers/notifications.py` — confirmed via glob that the actual file is `notifications.py` (plural).
