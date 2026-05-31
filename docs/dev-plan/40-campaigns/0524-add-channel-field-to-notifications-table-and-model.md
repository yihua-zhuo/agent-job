# 40-campaigns · 为 notifications 表添加 channel 字段

| 元数据 | 值 |
|---|---|
| Issue | #524 |
| 分类 | 40-campaigns |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `notifications` 表缺少 `channel` 字段，无法区分通知的发送渠道（email/sms/whatsapp/im）。随着营销自动化功能推进，需要在记录层面区分不同渠道的通知发送行为，以便后续做渠道级分析和报告。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层数据库 schema 和 model 变更。
- **开发者视角**：`Notification` ORM 模型和 Pydantic schema 均包含 `channel` 字段，默认值为 `'email'`。Service 层可以直接访问 `notification.channel`，API 响应（via `.to_dict()`）自动包含该字段。

### 1.3 不做什么（剔除）

- [ ] 不实现渠道选择逻辑（前端下拉、后端 trigger 路由）— 仅建字段
- [ ] 不修改其他表的 schema（`notification_logs` 等关联表不在范围内）
- [ ] 不添加表级 unique/index 约束（channel 列暂不需要单独索引）
- [ ] 不修改现有 service 业务逻辑（`send_notification` 等方法保持原样）

### 1.4 关键 KPI

- `alembic upgrade head` → exit 0，无 pending dependency 报错
- `alembic downgrade -1` → exit 0，现有 rows 不受影响
- `PYTHONPATH=src ruff check src/db/models/notifications.py src/models/schemas.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → 全 passed（含 channel 默认值断言）
- API 响应 JSON 中含 `"channel": "email"` 字段

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：`TBD - 待验证：src/db/models/notification*.py 或 src/db/models/notifications.py L? — 现有 Notification ORM 模型定义`

当前 `notifications` 表 schema 大致如下（从 Alembic 历史推断）：

```python
# 推断结构，非实际文件内容
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # title, body, sent_at 等已有列
```

Pydantic schema 位置：`TBD - 待验证：src/models/schemas.py 或 src/models/notification*.py L? — Notification Pydantic schema`

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/notifications.py` — 添加 `channel` 列映射
  - `src/models/schemas.py` — 添加 `NotificationBase/NotificationResponse` 中的 `channel` 字段
  - `alembic/versions/<id>_add_channel_to_notifications.py` — 新建 migration
- 要建：
  - `tests/unit/test_notification_model.py` — unit test（channel 默认值验证）
  - `tests/integration/test_notification_channel_integration.py` — integration test（migration 落地验证）

### 2.3 缺什么

- [ ] `notifications` 表无 `channel` 列 — Alembic migration 缺失
- [ ] ORM model 无 `channel` 属性 — 查询/序列化时字段丢失
- [ ] Pydantic schema 无 `channel` 字段 — API 请求/响应类型不完整
- [ ] 现有单元测试无 channel 相关覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_channel_to_notifications.py` | 添加 `channel` 列的 Alembic migration |
| `tests/unit/test_notification_model.py` | ORM model channel 字段 unit test |
| `tests/integration/test_notification_channel_integration.py` | migration 落地 integration test |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/notifications.py` | 添加 `channel: Mapped[str] = mapped_column(String(20), server_default='email', nullable=False)` |
| `src/models/schemas.py` | NotificationSchema 中添加 `channel: str = 'email'` |

### 3.3 新增能力

- **ORM model**：`Notification.channel` 属性（`Mapped[str]`，非空，默认 `'email'`）
- **Pydantic schema**：`NotificationResponse.channel: str`（default `'email'`）
- **Migration**：`alembic upgrade head` 创建 `channel` 列（String(20)，server_default='email'）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `String(20)` 不选 PostgreSQL ENUM 类型**：当前 channel 枚举值集合小且稳定（email/sms/whatsapp/im），String 类型足够承载，且避免后续新增渠道时需要额外 migration 修改 ENUM 定义。
- **用 `server_default='email'` 不选 `default='email'`**：Alembic migration 中的 `server_default` 在数据库侧生效，保证历史行自动填充；Python 侧 `default` 仅影响 new instance 创建，不保证历史行。

### 4.2 版本约束

无新依赖引入。沿用现有 `alembic`，Python ≥ 3.11。

### 4.3 兼容性约束

- 多租户：`notifications` 表已有 `tenant_id` 列，migration 不修改该列
- Service 返回 ORM 对象，不在 service 层调用 `.to_dict()`
- Router 负责 Pydantic 序列化 — schema 变更后 API 响应自动包含 `channel`
- 不修改已有 API endpoint 路径 — 属 additive schema 变更，向后兼容

### 4.4 已知坑

1. **Alembic autogen 误将 `server_default` 写为 `default`** → 规避：手动编辑 migration 文件，确认使用 `server_default='email'` 而非 `default='email'`（前者写入 DB DDL，后者仅影响 SQLAlchemy ORM 层，不保证历史行填充）
2. **Alembic autogen 可能省略 `timezone=True` on DateTime 列**（若 migration 触及时间戳列）→ 规避：本 migration 仅添加 `channel` 列，不涉及 DateTime 列，跳过此坑
3. **SQLAlchemy Base 子类列名不能用 `metadata`**（与 `Base.metadata` 冲突）→ 规避：channel 列名不冲突；若未来有 metadata 类需求，改用 `event_metadata` 等
4. **`String` 长度若留空则默认 255** → 规避：显式指定 `String(20)`，足够覆盖 `whatsapp`（8字符）

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 Notification ORM 模型文件路径

验证 `src/db/models/` 目录下 Notification 相关文件实际路径和当前列定义（确认现有 `id`、`tenant_id` 等列写法），为本步和 Step 2 提供精确路径。

**完成判定**：`ls src/db/models/ | grep -i notif` 输出文件名

---

### Step 2: 生成 Alembic migration

在 clean 状态（alembic_dev DB 无 pending dependency）的数据库上执行：

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"

# 1. 确保目标 DB 存在且已 apply 到 head
docker compose -f configs/docker-compose.test.yml up -d test-db
alembic upgrade head

# 2. 生成 migration
alembic revision --autogenerate -m "add channel to notifications"
```

检查生成的 `alembic/versions/<id>_add_channel_to_notifications.py`，确认：

```python
# 正确的 migration 结构（手动验证后使用）
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column('notifications',
        sa.Column('channel', sa.String(20),
                  server_default='email', nullable=False))

def downgrade() -> None:
    op.drop_column('notifications', 'channel')
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 更新 Notification ORM 模型

在 `src/db/models/notifications.py` 的 `Notification` 类中添加 `channel` 列：

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # ... 现有列 ...

    # 新增
    channel: Mapped[str] = mapped_column(
        String(20),
        server_default='email',
        nullable=False,
    )
```

**完成判定**：`PYTHONPATH=src ruff check src/db/models/notifications.py` → 0 errors

---

### Step 4: 更新 Notification Pydantic schema

在 `src/models/schemas.py` 的 `NotificationBase` / `NotificationResponse` 中添加：

```python
from pydantic import BaseModel, Field

class NotificationBase(BaseModel):
    # ... 现有字段 ...
    channel: str = Field(default="email", max_length=20)

class NotificationResponse(NotificationBase):
    id: int
    # ... 继承 channel ...
```

**完成判定**：`PYTHONPATH=src ruff check src/models/schemas.py` → 0 errors

---

### Step 5: 编写 unit test

在 `tests/unit/test_notification_model.py` 新建：

```python
import pytest
from unittest.mock import Mock
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from tests.unit.conftest import make_mock_session

class TestNotificationChannel:
    def test_channel_default_value(self):
        # 验证 channel 默认值为 'email'
        ...

    def test_channel_serializes_in_to_dict(self):
        # 验证 .to_dict() 输出包含 'channel' 键
        ...
```

每个 test 需要自行定义 `mock_db_session` fixture（参考 CLAUDE.md §New unit test）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → 全 passed

---

### Step 6: 编写 integration test（可选，如已有迁移覆盖可跳过）

验证 migration 落地行为：

```python
@pytest.mark.integration
async def test_channel_default_is_email(db_schema, tenant_id, async_session):
    # 插入无 channel 值的 notification，查询后确认 channel == 'email'
    ...
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_notification_channel_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/db/models/notifications.py src/models/schemas.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_model.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_notification_channel_integration.py -v` → 全 passed（如执行了 Step 6）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：使用 `psql` 查询 `notifications.channel` 列，验证历史行值均为 `'email'`；API 响应 JSON 含 `"channel": "email"`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| migration 文件中 `server_default` 拼写错误导致历史行 null 值违反 NOT NULL | 低 | 高 | `alembic downgrade -1` 回退 migration，修正拼写后重新 upgrade |
| Pydantic schema 添加后 API 响应格式变更导致下游消费者破坏 | 低 | 中 | schema 变更属 additive（新增字段不删除/修改现有字段），向后兼容；如发现不兼容问题，revert schema 变更 |
| ORM 模型与 migration 不同步（模型先于 migration merge） | 低 | 中 | PR 合并顺序控制：migration commit 先于 model commit；CI 会 catch（ruff check 报错） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add alembic/versions/<id>_add_channel_to_notifications.py \
        src/db/models/notifications.py \
        src/models/schemas.py \
        tests/unit/test_notification_model.py \
        tests/integration/test_notification_channel_integration.py
git commit -m "feat(campaigns): add channel field to notifications table and model"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add channel field to notifications table and model" --body "Closes #524"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`TBD - 待验证：src/db/models/campaign.py L? — 现有 campaign 表的 ORM 列定义示例（用于参考 mapped_column + server_default 写法）`
- 第三方文档：[Alembic migration documentation](https://alembic.sqlalchemy.org/en/latest/)
- 父 issue / 关联：#71

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
