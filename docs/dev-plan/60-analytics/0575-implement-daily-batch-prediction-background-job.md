# 每日流失预测批量任务 · Churn batch job for daily score refresh

| 元数据 | 值 |
|---|---|
| Issue | #575 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#574 ChurnPredictionService](https://github.com/yihuazhuo/agent-job/issues/574), #51 (父任务) |
| 启用后赋能 | #47 (通知层) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 ChurnPredictionService 仅支持单客户同步预测（#574），没有机制对全量客户做定期批量评分。业务要求每日刷新所有活跃客户的流失分，以便阈值告警（score ≥ 70）能及时触发。没有批量任务就没有端到端评分流水线，这是一个上游依赖。

### 1.2 做完后

- **用户视角**：无直接可见变化 — 纯后台定时任务。但每日运行后，系统能自动识别高风险客户并通过 #47 通知销售/客服。
- **开发者视角**：`src/jobs/churn_batch_job.py` 提供 `run_daily_churn_predictions(tenant_id: int)` 函数，可由 CLI 手动触发或接入 APScheduler / cron。`check_and_alert_threshold()` 提供阈值跨越告警钩子（stub，真实通知在 #47 实现）。

### 1.3 不做什么（剔除）

- [ ] 不实现 APScheduler / cron 调度框架（只提供入口函数，调度由运维层负责）
- [ ] 不实现真实的 Slack / Email 通知（#47 的 scope，仅留 placeholder 方法）
- [ ] 不实现增量预测（仅全量扫描，本期不做 delta 判断）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 全 passed
- `ruff check src/jobs/churn_batch_job.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（若涉及 migration）
- `python -m jobs.churn_batch_job --tenant-id 1` → exit 0，打印 "Processed N customers, M alerts raised"

---

## 2. 当前现状（起点）

### 2.1 现有实现

`src/services/churn_prediction_service.py` — 单客户预测逻辑（#574）。

TBD - 待验证：`src/services/churn_prediction_service.py` 第 1-50 行 — ChurnPredictionService 现有接口，确认方法签名

`src/db/models/churn_prediction.py` — 预测结果 ORM 模型（若已创建）。

TBD - 待验证：`src/db/models/` 中是否存在 churn_prediction 相关文件

`src/jobs/` 目录 — 当前不存在，需新建。

### 2.2 涉及文件清单

- 要改：
  - `tests/integration/conftest.py` — 新增 `seed_customer` / `seed_churn_result` 等 helper（若尚未提供）
- 要建：
  - `src/jobs/churn_batch_job.py` — 批量任务主模块
  - `src/services/churn_notification_service.py` — 通知服务桩（placeholder）
  - `tests/integration/test_churn_batch_job_integration.py` — 集成测试
  - `alembic/versions/<id>_create_churn_prediction_table.py` — 迁移（如 DB 表尚未建立）

### 2.3 缺什么

- [ ] 无批量遍历全租户活跃客户的 job 入口
- [ ] 无"上次分值 < 70，本次 ≥ 70"的跨 run 阈值检测机制
- [ ] 无通知桩（#47 前置条件）
- [ ] 无 CLI 可执行入口（`python -m jobs.churn_batch_job`）
- [ ] 无针对批量任务的集成测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/jobs/churn_batch_job.py` | 每日批量流失预测主模块，含 `run_daily_churn_predictions()` 和 `check_and_alert_threshold()` |
| `src/services/churn_notification_service.py` | 通知服务桩，提供 `send_churn_alert()` placeholder |
| `tests/integration/test_churn_batch_job_integration.py` | 验证批量运行 + 结果持久化的集成测试 |
| `alembic/versions/<id>_create_churn_prediction_table.py` | 建表迁移（若 churn_prediction 表尚未创建） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/churn_prediction_service.py` | 如 #574 尚未提供 `predict(customer_id, tenant_id)` 方法，本文件为依赖基准 |
| `tests/integration/conftest.py` | 新增 `_seed_customer`、`_seed_churn_result` 等 helper（如缺失） |

### 3.3 新增能力

- **Job function**：`run_daily_churn_predictions(tenant_id: int, session: AsyncSession) -> dict` — 全量活跃客户遍历，调用 ChurnPredictionService，持久化结果
- **Helper function**：`check_and_alert_threshold(session: AsyncSession, tenant_id: int) -> int` — 对比上次预测分，返回本次新增高风险客户数，并触发通知桩
- **CLI entry point**：`python -m jobs.churn_batch_job --tenant-id <id>` — 带健康检查输出
- **Service stub**：`ChurnNotificationService.send_churn_alert(customer_id, old_score, new_score)` — #47 前桩

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `async def` + `AsyncSession` 不选同步函数**：项目已全面使用 SQLAlchemy 2.x async（见 CLAUDE.md），保持一致避免混用协程模型。
- **选"上次分值存 DB"方案，不选内存/Redis 方案**：多实例部署时 Redis 需额外基础设施，DB 记录天然持久化且可审计。
- **选 placeholder 不选真实通知**：#47 尚未实现，提前接入真实 SDK 会造成无测试的隐式依赖；桩保证接口契约正确。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| SQLAlchemy | 2.x（已有）| async session / AsyncSession 已是项目基线 |
| alembic | 已有 | 迁移管理已接入 |

### 4.3 兼容性约束

- 多租户：所有查询必须 `WHERE tenant_id = :tenant_id`，传入 tenant_id 参数，禁止全局扫描
- Service 签名：`__init__(self, session: AsyncSession)` — **无默认值**
- Service 返回 ORM 对象，Router 负责 `.to_dict()` 序列化；Job 函数直接操作 session，无需 Router 层
- Job 使用 `AsyncSession` via `Depends(get_db)`，**不用** `async with get_db() as session:`
- 错误处理：Job 函数捕获业务异常（`NotFoundException` 等）后记录 logger 并继续处理下一客户，不中断整批任务

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON** → 迁移文件中手动改回 `sa.JSONB()`（churn_prediction 表若有 payload / metadata 字段）
2. **Alembic autogen 丢失 `timezone=True`** → DateTime 字段加 `timezone=True`，如 `server_default=text("NOW()")` 需显式带时区
3. **SQLAlchemy 列名 `metadata` 冲突** → churn_prediction 模型如需存配置，用 `prediction_metadata` / `attrs` 等名称，禁止用 `metadata`（与 `Base.metadata` 冲突）
4. **PYTHONPATH=src** → 所有 import 写 `from services...`、`from db.models...`，禁止 `from src.services...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ChurnPrediction ORM model（如不存在）

描述：检查 `src/db/models/churn_prediction.py` 是否存在，若无则按项目规范（多租户 + AsyncSession）创建 ORM 模型，包含 `tenant_id`、`customer_id`、`score`、`predicted_at`、`previous_score`（nullable，用于跨 run 比对）。

操作：
a) 新建 `src/db/models/churn_prediction.py`：

```python
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChurnPrediction(Base):
    __tablename__ = "churn_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    # nullable — 第一条预测没有"上次分值"
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    __table_args__ = (
        Index("ix_churn_predictions_tenant_customer", "tenant_id", "customer_id"),
    )
```

b) 在 `src/db/models/__init__.py` 导出 `ChurnPrediction`
c) 在 `alembic/env.py` 添加 `from src.db.models.churn_prediction import ChurnPrediction`（等效 import）

**完成判定**：`ruff check src/db/models/churn_prediction.py` → 0 errors；`python -c "from db.models.churn_prediction import ChurnPrediction; print('ok')"` → ok

### Step 2: 生成 Alembic migration

描述：autogenerate churn_predictions 表迁移，修正 JSONB 和 timezone 陷阱。

操作：
a) 启动干净 DB：`docker compose -f configs/docker-compose.test.yml up -d test-db`
b) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;" && docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
c) `PYTHONPATH=src alembic revision --autogenerate -m "create_churn_predictions_table"`
d) 打开生成文件，修正：把 `sa.JSON()` 改为 `sa.JSONB()`，在 `DateTime` 加 `timezone=True`
e) `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: 创建 ChurnNotificationService placeholder

描述：建立通知服务桩，使 #47 接入时只需实现 `send_churn_alert()` 方法体，不破坏已有调用点。

操作：
a) 新建 `src/services/churn_notification_service.py`：

```python
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ChurnNotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_churn_alert(
        self,
        customer_id: int,
        tenant_id: int,
        old_score: float | None,
        new_score: float,
    ) -> None:
        """
        Placeholder — 真实 Slack/Email 通知在 #47 实现。
        当前仅打印日志，不阻塞任务。
        """
        logger.warning(
            "[STUB] Churn alert: customer_id=%d tenant_id=%d "
            "old_score=%s new_score=%.2f (threshold=70)",
            customer_id,
            tenant_id,
            old_score,
            new_score,
        )
```

**完成判定**：`ruff check src/services/churn_notification_service.py` → 0 errors

### Step 4: 实现批量任务主模块

描述：实现 `src/jobs/churn_batch_job.py`，包含全量遍历、逐客户预测、阈值检测、CLI 入口。

操作：
a) 新建 `src/jobs/churn_batch_job.py`：

```python
import argparse
import asyncio
import logging
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 假设 ChurnPrediction 模型已存在
from db.models.churn_prediction import ChurnPrediction
from db.models.customer import Customer  # 确认模型名
from db.connection import get_db
from services.churn_prediction_service import ChurnPredictionService
from services.churn_notification_service import ChurnNotificationService

THRESHOLD = 70.0
logger = logging.getLogger(__name__)


async def check_and_alert_threshold(
    session: AsyncSession, tenant_id: int
) -> int:
    """
    查找本次 score >= THRESHOLD 且上次 score < THRESHOLD 的客户，
    对每个触发通知桩。返回新增高风险客户数。
    """
    threshold = THRESHOLD
    stmt = (
        select(ChurnPrediction)
        .where(
            ChurnPrediction.tenant_id == tenant_id,
            ChurnPrediction.score >= threshold,
        )
        .order_by(ChurnPrediction.customer_id, ChurnPrediction.predicted_at.desc())
    )
    result = await session.execute(stmt)
    all_predictions = result.scalars().all()

    # 按 customer_id 分组，取最新一条
    latest_by_customer: dict[int, ChurnPrediction] = {}
    for p in all_predictions:
        if p.customer_id not in latest_by_customer:
            latest_by_customer[p.customer_id] = p

    notification_svc = ChurnNotificationService(session)
    alerts_raised = 0
    for pred in latest_by_customer.values():
        if pred.previous_score is not None and pred.previous_score < threshold:
            await notification_svc.send_churn_alert(
                customer_id=pred.customer_id,
                tenant_id=tenant_id,
                old_score=pred.previous_score,
                new_score=pred.score,
            )
            alerts_raised += 1
    return alerts_raised


async def run_daily_churn_predictions(
    session: AsyncSession, tenant_id: int
) -> dict:
    """
    查询 tenant 下所有 active 客户，调用 ChurnPredictionService，
    持久化结果到 churn_predictions 表。
    """
    # 查询活跃客户
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.is_active == True,  # 或 Customer.status == "active"，确认字段名
    )
    result = await session.execute(stmt)
    customers = result.scalars().all()

    churn_svc = ChurnPredictionService(session)
    processed = 0
    errors = 0

    for customer in customers:
        try:
            new_score = await churn_svc.predict(
                customer_id=customer.id, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error("predict failed for customer %d: %s", customer.id, exc)
            errors += 1
            continue

        # 取最新已有分值（上次）
        prev_stmt = (
            select(ChurnPrediction)
            .where(
                ChurnPrediction.tenant_id == tenant_id,
                ChurnPrediction.customer_id == customer.id,
            )
            .order_by(ChurnPrediction.predicted_at.desc())
            .limit(1)
        )
        prev_result = await session.execute(prev_stmt)
        prev_pred = prev_result.scalar_one_or_none()
        previous_score = prev_pred.score if prev_pred else None

        record = ChurnPrediction(
            tenant_id=tenant_id,
            customer_id=customer.id,
            score=new_score,
            previous_score=previous_score,
        )
        session.add(record)
        processed += 1

    await session.commit()
    alerts = await check_and_alert_threshold(session, tenant_id)
    return {"processed": processed, "errors": errors, "alerts": alerts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily churn batch prediction job")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID")
    args = parser.parse_args()

    async def _run():
        async for session in get_db():
            result = await run_daily_churn_predictions(session, args.tenant_id)
            print(
                f"Processed {result['processed']} customers, "
                f"{result['errors']} errors, "
                f"{result['alerts']} alerts raised"
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

b) 在 `src/jobs/__init__.py` 导出关键函数（若文件不存在则创建空 `__init__.py`）

**完成判定**：`ruff check src/jobs/churn_batch_job.py` → 0 errors；`python -m jobs.churn_batch_job --tenant-id 1` 可执行（依赖 DB）

### Step 5: 补充集成测试

描述：写集成测试，启动真实 DB，创建客户数据，触发批量任务，验证分值持久化和告警计数。

操作：
a) 新建 `tests/integration/test_churn_batch_job_integration.py`：

```python
import pytest
from sqlalchemy import select
from db.models.churn_prediction import ChurnPrediction
from db.models.customer import Customer
from jobs.churn_batch_job import run_daily_churn_predictions


@pytest.mark.integration
class TestChurnBatchJob:
    async def test_batch_persists_predictions(self, db_schema, tenant_id, async_session):
        # seed 两个活跃客户
        c1 = Customer(tenant_id=tenant_id, name="Customer One", is_active=True)
        c2 = Customer(tenant_id=tenant_id, name="Customer Two", is_active=True)
        async_session.add_all([c1, c2])
        await async_session.commit()
        await async_session.refresh(c1)
        await async_session.refresh(c2)

        result = await run_daily_churn_predictions(async_session, tenant_id)

        assert result["processed"] == 2
        assert result["errors"] == 0

        stmt = select(ChurnPrediction).where(ChurnPrediction.tenant_id == tenant_id)
        preds = (await async_session.execute(stmt)).scalars().all()
        assert len(preds) == 2
        assert all(p.score is not None for p in preds)

    async def test_threshold_alert_on_score_cross(
        self, db_schema, tenant_id, async_session
    ):
        # seed 客户 + 已有预测（low score）
        c = Customer(tenant_id=tenant_id, name="High Risk", is_active=True)
        async_session.add(c)
        await async_session.commit()
        await async_session.refresh(c)

        # 插入旧预测
        old_pred = ChurnPrediction(
            tenant_id=tenant_id,
            customer_id=c.id,
            score=55.0,
            previous_score=None,
        )
        async_session.add(old_pred)
        await async_session.commit()

        # 第二次运行，新分值 >= 70，应触发 alert 计数
        result = await run_daily_churn_predictions(async_session, tenant_id)
        assert result["alerts"] >= 1  # stub 仅打印，计数非零即通过
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 全 passed

### Step 6: 最终 lint 检查并 commit

操作：
- `ruff check src/jobs/churn_batch_job.py src/services/churn_notification_service.py`
- `ruff check src/db/models/churn_prediction.py`（若新建）
- `git add ... && git commit -m "feat(analytics): daily batch churn prediction job (#575)"`

**完成判定**：`ruff check src/...` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/jobs/churn_batch_job.py src/services/churn_notification_service.py src/db/models/churn_prediction.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_notification_service.py -v` → 全 passed（如有单元测试）
- [ ] `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如有新建迁移）
- [ ] 端到端：`python -m jobs.churn_batch_job --tenant-id 1` → exit 0，输出 "Processed N customers"

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #574 ChurnPredictionService 尚未完成，批量任务无法调用 | 中 | 高 | 本板块依赖 #574，先在 mock 上开发测试，#574 合并后切换真实 service |
| 大量客户时单事务 commit 过重（OOM） | 低 | 中 | 分批 commit（如每 100 客户 commit 一次），不影响下游板块 |
| 客户表 is_active / status 字段名不确定 | 低 | 中 | 用 `TBD - 待验证` 提示字段名，后续 #574 确认后更正；不影响板块间接口 |
| Alembic migration 修正导致 drift 检测误报 | 低 | 低 | 在 PR description 注明手动修正点，reviewer 对齐 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/jobs/churn_batch_job.py src/services/churn_notification_service.py src/db/models/churn_prediction.py tests/integration/test_churn_batch_job_integration.py alembic/versions/
git commit -m "feat(analytics): daily batch churn prediction job (#575)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): daily batch churn prediction job" --body "Closes #575

## Summary
- Add src/jobs/churn_batch_job.py with run_daily_churn_predictions() and check_and_alert_threshold()
- Add ChurnNotificationService stub (real wiring in #47)
- Add integration test for batch + persistence

🤖 Generated with Claude Code"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/` 中是否有其他 jobs/ 目录作为参考（如定期报告、导出任务）
- 父 issue / 关联：#51（父任务）、#574（ChurnPredictionService 依赖）、#47（通知层，待接入）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
