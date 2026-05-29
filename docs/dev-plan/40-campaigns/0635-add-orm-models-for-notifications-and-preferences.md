# 通知与偏好 · Add ORM models for notifications and preferences

| 元数据 | 值 |
|---|---|
| Issue | #635 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [50-automation/0687-build-rule-execution-engine-and-trigger-dispatch](../50-automation/0687-build-rule-execution-engine-and-trigger-dispatch.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `NotificationModel`（`src/db/models/notification.py`）仅有 9 个基础字段（id, tenant_id, user_id, type, title, content, is_read, related_type, related_id, created_at），缺少 issue #635 要求的 `channel`、`template`、`params`、`priority`、`status`、`sent_at`、`delivered_at`、`read_at` 等通知核心字段。`NotificationPreferenceModel` 完全不存在。这导致通知渠道偏好（email/sms/push）与通知发送状态无法存储，是后续规则引擎（#687）dispatch 层的阻塞依赖。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动
- **开发者视角**：`NotificationModel` 新增所有 issue 指定字段，`NotificationPreferenceModel` 可通过 `from db.models.notification import NotificationModel, NotificationPreferenceModel` 导入；Alembic migration 在 `notifications` 表新增列并创建 `notification_preferences` 表

### 1.3 不做什么（剔除）

- [ ] NotificationService / NotificationPreferenceService 等业务逻辑层（issue 明确排除）
- [ ] API router / endpoint
- [ ] 通知发送（send）、模板渲染、queue 等运行时逻辑
- [ ] 前端界面

### 1.4 关键 KPI

- `ruff check src/db/models/notification.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_notification.py -v` → ≥ 3 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/db/models/notification.py`](../../src/db/models/notification.py) L{1}-L{39}

```{1}:39:src/db/models/notification.py
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
```

### 2.2 涉及文件清单

- 要改：
  - [`src/db/models/notification.py`](../../src/db/models/notification.py) — 扩展 NotificationModel 新增字段，新增 NotificationPreferenceModel
  - [`alembic/versions/b2c3dce4b714_create_all_tables.py`](../../alembic/versions/b2c3dce4b714_create_all_tables.py) — 不直接改，由 autogenerate 产出新 migration
- 要建：
  - `alembic/versions/<id>_add_notification_preferences.py` — notifications 表新增列 + notification_preferences 表
  - `tests/unit/test_notification.py` — NotificationModel + NotificationPreferenceModel 单元测试

### 2.3 缺什么

- [ ] `NotificationModel` 缺少 channel、template、params（JSON）、priority、status、sent_at、delivered_at、read_at 字段
- [ ] `NotificationPreferenceModel` 完全不存在（需要新建）
- [ ] 对应 Alembic migration 未创建
- [ ] 无 unit test 覆盖新字段

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_notification_preferences.py` | notifications 表新增列 + 新建 notification_preferences 表（含 tenant_id 索引） |
| `tests/unit/test_notification.py` | NotificationModel 和 NotificationPreferenceModel 字段正确性单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/db/models/notification.py`](../../src/db/models/notification.py) | NotificationModel 新增 8 个字段；新增 NotificationPreferenceModel；更新 to_dict() |

### 3.3 新增能力

- **ORM model**：`NotificationModel` in `src/db/models/notification.py` — 扩展后含 channel/template/params/priority/status/sent_at/delivered_at/read_at
- **ORM model**：`NotificationPreferenceModel` in `src/db/models/notification.py` — 含 user_id/channel/enabled + tenant_id
- **Migration**：`alembic upgrade head` 创建 notifications 新增列 + notification_preferences 表（含 tenant_id 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **params 用 JSON 而非独立列**：通知参数数量和结构不固定，用 `JSONB` 存储灵活参数（模板变量、跳转参数等），比拆字段更合理。JSONB 支持 GIN 索引，查询 `params->>'key' = 'value'` 性能可接受。
- **read_at 复用 is_read**：is_read 是布尔快速标记，read_at 是精确时间戳；两者并存，is_read 供前端快速过滤，read_at 供时间范围查询。
- **不建 NotificationPreference 到 Notification 的外键**：偏好设置独立存在，与单条通知解耦，外键会引入 cascade 复杂度。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：所有表必须含 `tenant_id` 列并建立索引（`index=True`）
- `tenant_id` 列名不可用 `metadata`（与 SQLAlchemy `Base.metadata` 冲突），本板块已确认使用 `tenant_id`，无冲突
- JSONB 类型：Alembic autogenerate 会将 `JSONB` 误生成为 `JSON`，migration 需手动改回 `JSONB`（见 §4.4）
- `import` 路径：PYTHONPATH=src 时写 `from db.models...`，不是 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogenerate 将 JSONB 写成 JSON** → 迁移中手动改 `sa.JSON()` 为 `sa.JSONB()`
2. **Alembic autogenerate 将 `DateTime(timezone=True)` 写成 `DateTime`** → 迁移中手动改回 `DateTime(timezone=True)`

---

## 5. 实现步骤（按顺序）

### Step 1: 扩展 NotificationModel 新增字段

在 `src/db/models/notification.py` 的 `NotificationModel` 中，在 `related_id` 列后、`created_at` 列前插入 8 个新字段（channel, template, params, priority, status, sent_at, delivered_at, read_at）。参考同文件 `TicketModel` 中 `DateTime(timezone=True)` 和 `String(length=N)` 的写法。

```python
channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
template: Mapped[str | None] = mapped_column(String(255), nullable=True)
params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

同时更新 `to_dict()` 方法，将这 8 个新字段（含 sent_at/delivered_at/read_at 的 `.isoformat()`）加入返回值。

**完成判定**：`ruff check src/db/models/notification.py` → 0 errors

### Step 2: 新增 NotificationPreferenceModel

在 `src/db/models/notification.py` 中，`NotificationModel` 类定义之后，添加 `NotificationPreferenceModel`：

```python
class NotificationPreferenceModel(Base):
    """User notification channel preference."""
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "enabled": self.enabled,
        }
```

**完成判定**：`ruff check src/db/models/notification.py` → 0 errors；`PYTHONPATH=src python -c "from db.models.notification import NotificationModel, NotificationPreferenceModel; print('OK')"` → 输出 OK

### Step 3: 生成 Alembic migration

按照 CLAUDE.md §Alembic Migrations：

在 `alembic_dev` 数据库执行 autogenerate：

docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "add_notification_preferences"

生成文件后手动修正两处坑：
- 将 `sa.JSON()` 改回 `sa.JSONB()`
- 将 `DateTime()` 改回 `DateTime(timezone=True)`

downgrade() 必须包含 `op.drop_table('notification_preferences')` 和 `op.drop_column('notifications', '<each_new_column>')`。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 4: 编写单元测试

创建 `tests/unit/test_notification.py`，MockState 管理通知和偏好的自增 ID：

```python
from tests.unit.conftest import make_mock_session, MockState

def make_notification_handler(state: MockState):
    def handle(session, query):
        pass  # minimal mock for ORM import validation
    return handle

def make_preference_handler(state: MockState):
    def handle(session, query):
        pass
    return handle

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_notification_handler(state),
        make_preference_handler(state),
    ])
```

测试用例（见 §7）覆盖 NotificationModel 字段构造、to_dict() 序列化、NotificationPreferenceModel 字段构造。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/notification.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.notification import NotificationModel, NotificationPreferenceModel; assert hasattr(NotificationModel, 'params'); assert hasattr(NotificationModel, 'priority'); assert hasattr(NotificationModel, 'status'); assert hasattr(NotificationPreferenceModel, 'channel'); assert hasattr(NotificationPreferenceModel, 'enabled'); print('fields OK')"` → 输出 fields OK
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification.py -v` → ≥ 3 passed
- [ ] `export PYTHONPATH=src && export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| alembic autogenerate 误改 JSONB/DateTime 导致 migration 在 prod 失败 | 中 | 高 | 手动修正 migration 中 JSON→JSONB 和 DateTime→DateTime(timezone=True)；#687 规则引擎使用这些模型前必须通过 upgrade+downgrade 验证 |
| notification_preferences 表缺少唯一约束导致同一用户同一 channel 重复记录 | 低 | 中 | 在 migration 中补充 `sa.UniqueConstraint('tenant_id', 'user_id', 'channel')`；如已 apply，手动 psql 执行 `ALTER TABLE notification_preferences ADD CONSTRAINT uq_pref UNIQUE (tenant_id, user_id, channel);` |
| 添加 nullable=False 字段后旧数据 insert 失败 | 低 | 中 | 全部新列均用 `nullable=True` 或带 server_default，不阻塞现有 insert |

---

## 8. 完成后必做

```bash
git add src/db/models/notification.py alembic/versions/<id>_add_notification_preferences.py tests/unit/test_notification.py
git commit -m "feat(campaigns): add ORM models for notifications and preferences"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#635): add NotificationModel fields and NotificationPreferenceModel" --body "Closes #635"
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ticket.py`](../../src/db/models/ticket.py) — TicketModel 字段声明模式（String/DateTime/Boolean）
- 同类参考实现：[`src/db/models/notification.py`](../../src/db/models/notification.py) — 现有 NotificationModel（修改起点）
- 父 issue / 关联：#39

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
