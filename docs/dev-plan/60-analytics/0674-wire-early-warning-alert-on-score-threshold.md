# 0674 · Wire early warning alert on score threshold

#流失预警 · Score阈值超阈值时创建预警记录并触发通知

| 元数据 | 值 |
|---|---|
| Issue | #674 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0685-implement-automationrule-service](../50-automation/0685-implement-automationrule-service.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ChurnPredictionService` 已实现 `get_high_risk_customers(threshold=70.0)`，可以返回分数达到阈值的客户列表。但没有持久化机制记录"何时为哪个客户创建了预警"，也没有调用任何通知分发函数。业务需要：当客户流失风险分突破阈值时，系统应自动创建预警记录并触发通知，即使通知接收方是 stub 也必须闭环。

### 1.2 做完后

- **用户视角**：「无用户可见变化 — 纯后端」
- **开发者视角**：`ChurnAlertService.create_alert_if_threshold_crossed(customer_id, tenant_id)` 每调用一次，若该客户 score ≥ 70 且今日尚无同客户预警，则在 `churn_alerts` 表插入记录并调用 `NotificationService` 的 stub notify 方法。开发者可在业务代码中调用此方法完成实时预警兜底。

### 1.3 不做什么（剔除）

- [ ] 不实现完整的调度器（APScheduler / Celery）；在 `ChurnService` 提供同步入口方法，由 cron / 调用方自行按需调度- [ ] 不接入真实通知渠道（NotificationService stub，即 `pass`；真实集成依赖 #47）
- [ ] 不创建 REST API router（路由属于下游 #673 板块）

### 1.4 关键 KPI

- `ruff check src/db/models/churn_alert.py src/services/churn_service.py tests/unit/test_churn_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → ≥5 passed（3 个成功 + 1 个边界 + 1 个错误）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `PYTHONPATH=src mypy src/db/models/churn_alert.py src/services/churn_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/services/churn_service.py` 和 `src/db/models/churn_alert.py` 均不存在，需要从零创建。

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../src/main.py) — 在 `ensure_engine()` 后注册 `ChurnService` 的调度初始化钩子（可选，按需）
- 要建：
  - `src/db/models/churn_alert.py` — `ChurnAlertModel` ORM 模型，对应 `churn_alerts` 表
  - `src/services/churn_service.py` — `ChurnService`：查询高风险客户 → 创建预警记录 → 调用 NotificationService stub
  - `alembic/versions/<id>_create_churn_alerts.sql` — 创建 `churn_alerts` 表的 Alembic migration
  - `tests/unit/test_churn_service.py` — 单元测试覆盖 ChurnAlertModel 和 ChurnService

### 2.3 缺什么

- [ ] 无 `ChurnAlertModel` ORM 模型 — 无法持久化预警记录
- [ ] 无 `ChurnService` — 无业务逻辑将分数阈值与预警创建关联
- [ ] 无 Alembic migration — `churn_alerts` 表未创建- [ ] `get_high_risk_customers` 只是返回列表，并未在 DB 中留下"已预警"痕迹
- [ ] 无幂等性控制 — 若不加去重，重复调用会产生重复预警记录

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/churn_alert.py` | `ChurnAlertModel` ORM 模型，含 customer_id、score、threshold、status、created_by 等字段 |
| `src/services/churn_service.py` | `ChurnService`：提供 `create_alert_if_threshold_crossed`同步入口方法，含幂等检查 |
| `alembic/versions/<id>_create_churn_alerts.sql` | Alembic migration：创建 `churn_alerts` 表（含 tenant_id 索引） |
| `tests/unit/test_churn_service.py` | 单元测试：Model序列化、Service成功/边界/错误路径 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | 可选：若要自动触发预警，可在 lifespan add startup hook 里调用 `ChurnService.check_all_customers`；暂无需改 |

### 3.3 新增能力

- **ORM model**：`ChurnAlertModel` in `src/db/models/churn_alert.py`
- **Service method**：`ChurnService.create_alert_if_threshold_crossed(self, customer_id: int, tenant_id: int) -> ChurnAlertModel | None`
- **Service method**：`ChurnService.check_and_alert_customer(self, customer_id: int, tenant_id: int, threshold: float = 70.0) -> ChurnAlertModel | None` — 若 score ≥ threshold 且今日无记录则创建；否则返回 None
- **Migration**：`alembic upgrade head` 创建 `churn_alerts` 表（含 `tenant_id`索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选在 Service 层做幂等而非 DB唯一索引**：在 `check_and_alert_customer` 方法内先 `SELECT` 查询今日是否有相同 customer_id 记录，再决定 `INSERT`。避免唯一约束冲突，逻辑更可控。
- **选同步调用而非事件队列**：通知触发以函数调用为载体（stub），简单直接。真实通知渠道接入（#47）后可替换为事件发布机制。
- **选复用 `NotificationService.send_notification` 而非新建 Channel**：直接复用现有 `NotificationService`，减少耦合。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 表名列名不可用 `metadata`（与 `Base.metadata` 冲突）→ 用 `event_metadata` 或 `alert_metadata`

### 4.4 已知坑

1. **Alembic autogen 把 JSONB写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 规避：生成 migration 后手动复查并改为 `sa.JSONB()` / `sa.DateTime(timezone=True)`
2. **幂等 check 的 WHERE条件需要覆盖索引** →规避：`SELECT id FROM churn_alerts WHERE tenant_id = :tenant_id AND customer_id = :customer_id AND created_at >= :today_start` 加 `LIMIT 1`，利用 `(tenant_id, customer_id, created_at)` 复合索引

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/churn_alert.py`

操作：
- a) 创建 `src/db/models/churn_alert.py`：

```python
"""ChurnAlert ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChurnAlertModel(Base):
    """预警记录 entity mapped to the `churn_alerts` table."""

    __tablename__ = "churn_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)
    alert_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notification_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "score": self.score,
            "threshold": self.threshold,
            "status": self.status,
            "alert_metadata": self.alert_metadata or {},
            "created_by": self.created_by,
            "notification_sent": self.notification_sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- b) 运行 ruff格式化：`ruff format src/db/models/churn_alert.py`

**完成判定**：`ruff check src/db/models/churn_alert.py` → 0 errors

---

### Step 2: 创建 Alembic migration `churn_alerts`

操作：
- a) 启动 test-db 并创建 alembic_dev：
  ```bash
  docker compose -f configs/docker-compose.test.yml up -d test-db
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
  docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
  ```
- b)导出环境变量并升级到最新：
  ```bash
  export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
  export PYTHONPATH=src
  export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
  alembic upgrade head
  ```
- c) 确认当前 revision：`alembic current` → 输出 revision hash
- d) 生成 migration：
  ```bash
  alembic revision --autogenerate -m "create churn_alerts table"
  ```
- e) 打开生成的 migration 文件（`alembic/versions/<id>_create_churn_alerts.py`）并手动修复以下项：
  - 确认 `(tenant_id, customer_id, created_at)` 复合索引存在
  - 确认 JSONB 列使用 `sa.JSONB()` 而非 `sa.JSON()`
  - 确认 TIMESTAMPTZ 列使用 `sa.DateTime(timezone=True)` 而非 `sa.DateTime`
 - `downgrade()` 必须调用 `op.drop_table('churn_alerts')`

示例结构（需要手动校验后使用）：

```python
# alembic/versions/<id>_create_churn_alerts.py
def upgrade() -> None:
    op.create_table('churn_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'created'")),
        sa.Column('alert_metadata', a(JSONB()), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_churn_alerts_tenant_id'), 'churn_alerts', ['tenant_id'])
    op.create_index(op.f('ix_churn_alerts_customer_id'), 'churn_alerts', ['customer_id'])
```

**完成判定**：`alembic downgrade -1 && alembic upgrade head`两次 exit 0；`docker exec configs-test-db-1 psql -U test_user -d alembic_dev -c "\\dt churn_alerts"` 显示表存在

---

### Step 3: 创建 `src/services/churn_service.py`

操作：
- a) 创建 `src/services/churn_service.py`：

```python
"""Churn alert service — creates alert records when customer churn score crosses threshold."""
from datetime import UTC, datetime

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.churn_alert import ChurnAlertModel
from db.models.customer import CustomerModel
from services.churn_prediction import ChurnPredictionService
from services.notification_service import NotificationService


class ChurnService:
    """流失预警服务 — queries churn score, creates alert records, dispatches notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.churn_pred = ChurnPredictionService(session)
        self.notification_svc = NotificationService(session)

    async def _alert_exists_today(
        self, customer_id: int, tenant_id: int
    ) -> bool:
        """检查今日是否已为该客户创建过预警（幂等控制）."""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(ChurnAlertModel.id).where(
                and_(
                    ChurnAlertModel.tenant_id == tenant_id,
                    ChurnAlertModel.customer_id == customer_id,
                    ChurnAlertModel.created_at >= today_start,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def check_and_alert_customer(
        self,
        customer_id: int,
        tenant_id: int,
        threshold: float = 70.0,
    ) -> ChurnAlertModel | None:
        """检查单客户分数，若超阈值且今日无预警则创建记录并 stub 触发通知."""
        score = await self.churn_pred.calculate_churn_score(customer_id, tenant_id)
        if score < threshold:
            return None
        if await self._alert_exists_today(customer_id, tenant_id):
            return None

 alert = ChurnAlertModel(
            tenant_id=tenant_id,
            customer_id=customer_id,
            score=score,
            threshold=threshold,
            status="created",
            alert_metadata={"trigger": "threshold_crossed", "score_at_creation": score},
            created_by=0,
            notification_sent=False,
        )
        self.session.add(alert)
        await self.session.flush()
        await self.session.refresh(alert)

        # Stub notification dispatch — real integration via #47
        try:
            await self.notification_svc.send_notification(
                user_id=0,
                notification_type="churn_alert",
                title=f"Churn alert: customer {customer_id}",
                content=f"Churn score {score} exceeds threshold {threshold}",
                tenant_id=tenant_id,
                related_type="customer",
                related_id=customer_id,
            )
            alert.notification_sent = True
            await self.session.flush()
            await self.session.refresh(alert)
        except Exception:
            # Stub: notification failure must not roll back alert creation
            pass

        return alert

    async def create_alert_if_threshold_crossed(
        self,
        customer_id: int,
        tenant_id: int,
        threshold: float = 70.0,
    ) -> ChurnAlertModel | None:
        """Alias for check_and_alert_customer for callers that want explicit semantics."""
        return await self.check_and_alert_customer(customer_id, tenant_id, threshold)
```

- b) `ruff format src/services/churn_service.py`

**完成判定**：`ruff check src/services/churn_service.py` → 0 errors；`ruff format --check src/services/churn_service.py` → pass---

### Step 4: 创建 `tests/unit/test_churn_service.py`

操作：
- a) 在 `tests/unit/test_churn_service.py` 中新建 5 个测试用例：

  - **Test1** `test_churn_alert_model_to_dict`：导入 `ChurnAlertModel`，验证 `to_dict()` 返回所有字段（id、tenant_id、customer_id、score、threshold、status、alert_metadata、created_by、notification_sent、created_at）
  - **Test 2** `test_check_and_alert_customer_score_below_threshold`：mock `ChurnPredictionService.calculate_churn_score` → 返回 50.0，调用 `check_and_alert_customer`，断言返回 `None` 且无 DB INSERT
  - **Test 3** `test_check_and_alert_customer_score_above_threshold_creates_alert`：mock `calculate_churn_score` → 返回 80.0，mock `_alert_exists_today` → 返回 `False`，断言返回 `ChurnAlertModel` 实例且 `score == 80.0`
  - **Test 4** `test_idempotent_no_duplicate_alert_same_day`：mock score 85.0，`_alert_exists_today` → 返回 `True`，断言返回 `None`（幂等跳过）
  - **Test 5** `test_notification_stub_failure_does_not_rollback_alert`：mock score75.0，`_alert_exists_today` → `False`，`send_notification` raise `Exception`，断言 alert记录仍被创建且 `notification_sent == False`

示例代码结构：

```python
# tests/unit/test_churn_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from src.services.churn_service import ChurnService
from src.db.models.churn_alert import ChurnAlertModel
from tests.unit.conftest import MockState


class TestChurnService:
    @pytest.fixture
    def mock_session(self):
        state = MockState()
        from tests.unit.conftest import make_mock_session
        return make_mock_session([], state=state)

    @pytest.fixture
    def churn_service(self, mock_session):
        return ChurnService(mock_session)

    def test_churn_alert_model_to_dict(self):
        now = datetime.now(timezone.utc)
        alert = ChurnAlertModel.__new__(ChurnAlertModel)
        alert.id = 1
        alert.tenant_id = 42
        alert.customer_id = 7
        alert.score = 80.0
        alert.threshold = 70.0
        alert.status = "created"
        alert.alert_metadata = {"trigger": "threshold_crossed"}
        alert.created_by = 0
        alert.notification_sent = False
        alert.created_at = now
        d = alert.to_dict()
        assert d["id"] == 1
        assert d["customer_id"] == 7
        assert d["score"] == 80.0
        assert d["alert_metadata"] == {"trigger": "threshold_crossed"}
```

- b) 运行测试：`PYTHONPATH=src pytest tests/unit/test_churn_service.py -v`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → `5 passed`

---

## 6. 验收

- [ ] `ruff check src/db/models/churn_alert.py src/services/churn_service.py` → 0 errors
- [ ] `ruff format --check src/db/models/churn_alert.py src/services/churn_service.py` → pass
- [ ] `PYTHONPATH=src mypy src/db/models/churn_alert.py src/services/churn_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_service.py -v` → `5 passed`
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Autogenerate 产生错误的 JSONB / TIMESTAMPTZ 类型 | 中 | 中 | 手动修改 migration 文件后重新 `alembic upgrade head` |
| 幂等检查 query 未走索引（大数据量下性能差） | 低 | 中 | 在 `churn_alerts` 表加 `(tenant_id, customer_id, created_at)` 复合索引；可在第一版就加上 |
| NotificationService.send_notification stub 抛出异常导致 alert 回滚 | 低 | 高 | 已用 `try/except`包裹，alert 创建不会因通知失败而回滚 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/churn_alert.py src/services/churn_service.py alembic/versions/*churn_alerts*.py tests/unit/test_churn_service.py
git commit -m "feat(analytics): add ChurnAlert model and ChurnService with threshold-crossed alert trigger"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#674): wire early warning alert on score threshold" --body "Closes #674"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- `ChurnPredictionService`（现有）：[`src/services/churn_prediction.py`](../../src/services/churn_prediction.py) L49-L268
- `NotificationService`（复用）：[`src/services/notification_service.py`](../../src/services/notification_service.py) L23-L47
- ORM 参考模型：[`src/db/models/notification.py`](../../src/db/models/notification.py) L11-L40
-依赖板块（#673）：尚无板块文档，需后续下游 #673 创建 router 后方可暴露 REST endpoint
- 父 issue：#35

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
