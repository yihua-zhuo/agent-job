# Webhook 重试调度列 · 为 WebhookDeliveryModel 添加重试调度字段

| 元数据 | 值 |
|---|---|
| Issue | #718 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0720 - 实现 WebhookDeliveryService HMAC 签名与投递](0720-implement-webhookdeliveryservice-hmac-signing-post-delivery.md) |
| 启用后赋能 | [0721 - 实现指数退避重试调度器](0721-implement-background-retry-scheduler-with-exponential-backof.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Webhook 投递失败时，系统当前无法记录失败原因、最后一次尝试时间，也无从调度下一次重试。`WebhookDeliveryModel` 只有基础的投递状态字段，缺少支持指数退避重试策略所必需的时间戳和错误上下文列。没有这些列，重试调度器无法查询「哪些投递待重试」，也无法在重试时携带上次失败的原因。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动。
- **开发者视角**：`WebhookDeliveryModel` 新增 `next_retry_at`、`last_attempt_at`、`error_message` 三个字段；`WebhookDeliveryService` 可以读取和写入这些字段；后台重试调度器（#721）可以按 `next_retry_at` 索引查询待重试记录。

### 1.3 不做什么（剔除）

- [ ] 不实现重试逻辑本身（仅添加列，调度行为在 #721 中实现）。
- [ ] 不修改已有的 `status`、`response_code` 等投递状态列。
- [ ] 不添加 Webhook 级别的重试配置（retry count cap、timeout 等属于 WebhookModel，不在本范畴）。

### 1.4 关键 KPI

- `ruff check src/db/models/webhook.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → 全 passed（#720 中的现有测试不受影响）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- Migration 中 `next_retry_at` 列上存在部分索引 `ix_delivery_next_retry`（`WHERE next_retry_at IS NOT NULL`）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`src/db/models/webhook.py L? — WebhookDeliveryModel 现有字段（至少包含 delivery_url, payload, status, response_code）`

TBD - 待验证：`src/services/webhook_delivery_service.py L? — 现有 deliver() 方法签名和抛出异常时机`

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/webhook.py` — 新增三列：next_retry_at、last_attempt_at、error_message
  - `tests/unit/test_webhook_delivery_service.py` — 补充对新字段的断言（如 #720 已有测试）
- 要建：
  - `alembic/versions/<id>_add_webhook_delivery_retry_columns.py` — 建表变更脚本
  - `tests/unit/test_webhook_delivery_model.py` — 模型字段存在性单元测试（新建）

### 2.3 缺什么

- [ ] `WebhookDeliveryModel` 无 `next_retry_at` 字段，重试调度器无法查询「何时重试」
- [ ] `WebhookDeliveryModel` 无 `last_attempt_at` 字段，无法记录最近一次尝试时间
- [ ] `WebhookDeliveryModel` 无 `error_message` 字段，调用方无法拿到失败原因文本
- [ ] 无 Alembic migration 脚本将上述列加到数据库 schema

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `alembic/versions/<id>_add_webhook_delivery_retry_columns.py` | 为 webhook_delivery 表添加 next_retry_at（部分索引）、last_attempt_at、error_message 列 |
| `tests/unit/test_webhook_delivery_model.py` | 验证 WebhookDeliveryModel 三个新字段存在且类型正确 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/webhook.py` | WebhookDeliveryModel 新增 `next_retry_at`、`last_attempt_at`、`error_message` 三个 `Mapped` 字段 |

### 3.3 新增能力

- **ORM model**：在 `WebhookDeliveryModel` 中新增 `next_retry_at: Mapped[datetime | None]`（nullable, indexed）、`last_attempt_at: Mapped[datetime | None]`（nullable）、`error_message: Mapped[str | None]`（nullable）
- **Migration**：创建 `webhook_delivery` 表的重试列 + 部分索引 `ix_delivery_next_retry`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `next_retry_at` 索引为部分索引（`WHERE next_retry_at IS NOT NULL`）不选普通索引**：绝大多数已完成或永不复重的投递该列为 NULL，普通索引会索引大量无意义行，部分索引只索引真正等待调度的记录，查询性能更优。
- **选 `DateTime(timezone=True)` 不选 naive `DateTime`**：投递时间涉及多租户跨时区场景，带时区的时间戳可避免 UTC 转换歧义。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：migration 不涉及 tenant_id 列（已在原表定义），ALTER TABLE 操作需确保不破坏现有 tenant_id 索引。
- SQLAlchemy 列名禁止使用 `metadata`（与 `Base.metadata` 冲突），本板块新增字段名均无此问题。
- Service 层新增字段写入时不得调用 `.to_dict()`；ORM 直接修改字段值后 `session.flush()`。

### 4.4 已知坑

1. **Alembic autogen 把 `JSONB` 生成 为 `JSON`** → 规避：手动将 `sa.JSON()` 改回 `sa.JSONB()`
2. **Alembic autogen 生成 naive `DateTime` 而非 `DateTime(timezone=True)`** → 规避：autogen 后目视检查所有 `DateTime` 列，显式补全 `timezone=True`
3. **Alembic autogen 不生成部分索引** → 规避：手动在 migration 的 `upgrade()` 中添加 `op.create_index(..., postgresql_where=column('next_retry_at').is_(None))`
4. **autogen 遗漏 `timezone=True` 导致 naive datetime 与 psycopg/asyncpg 时区交互出错** → 规避：第 2 条已在生成阶段处理，CI 加 `ruff check` 前目视复查

---

## 5. 实现步骤（按顺序）

### Step 1: 更新 WebhookDeliveryModel 新增三个字段

在 `src/db/models/webhook.py` 的 `WebhookDeliveryModel` 类中新增三个 `Mapped` 字段：

```python
from datetime import datetime
from sqlalchemy import DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_delivery"
    # ... 现有字段 ...

    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_delivery_next_retry",
            "next_retry_at",
            postgresql_where=column("next_retry_at").is_(None),
        ),
    )
```

**完成判定**：`ruff check src/db/models/webhook.py` → 0 errors

---

### Step 2: 生成 Alembic migration

1. 启动干净 DB：
   `docker compose -f configs/docker-compose.test.yml up -d test-db`
   `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`
   `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`

2. 设置环境变量：
   `export PYTHONPATH=src`
   `export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"`

3. 运行 autogenerate（确保 `src/db/models/webhook.py` 已更新后再执行）：
   `alembic revision --autogenerate -m "add webhook delivery retry columns"`

4. 手动修改生成的 migration 文件（见 §4.4 已知坑）：
   - 将所有 `sa.JSON()` 改为 `sa.JSONB()`
   - 将所有 naive `DateTime` 改为 `DateTime(timezone=True)`
   - 在 `upgrade()` 中添加部分索引：
     `op.create_index("ix_delivery_next_retry", "webhook_delivery", ["next_retry_at"], postgresql_where=text("next_retry_at IS NOT NULL"))`
   - 填写 `downgrade()`：`op.drop_index("ix_delivery_next_retry", table_name="webhook_delivery")` 和三个 `drop_column`

5. 验证迁移双向成功：
   `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 补充单元测试

新建 `tests/unit/test_webhook_delivery_model.py`，使用 `tests/unit/conftest.py` 的 `MockState`/`MockRow` 框架验证：

```python
import pytest
from sqlalchemy import inspect
from db.models.webhook import WebhookDeliveryModel

def test_model_has_retry_columns():
    cols = {c.name for c in inspect(WebhookDeliveryModel).__table__.columns}
    assert "next_retry_at" in cols
    assert "last_attempt_at" in cols
    assert "error_message" in cols

def test_next_retry_at_is_indexed():
    indexes = {i.name for i in inspect(WebhookDeliveryModel).__table__.indexes}
    assert "ix_delivery_next_retry" in indexes
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_delivery_model.py -v` → 全 passed

---

### Step 4: 更新依赖此模块的现有单元测试（如 #720 已建立）

在 `tests/unit/test_webhook_delivery_service.py`（#720）如有构造 `WebhookDeliveryModel` 的 fixture，确认新字段不影响现有 mock（字段默认 None，mock 框架不报错则无需改动）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → 全 passed（如有测试文件）

---

## 6. 验收

- [ ] `ruff check src/db/models/webhook.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_delivery_model.py -v` → 全 passed（如文件已创建）
- [ ] `PYTHONPATH=src pytest tests/unit/test_webhook_delivery_service.py -v` → 全 passed（#720 测试不受影响）
- [ ] `PYTHONPATH=src pytest tests/integration/test_webhook_delivery_integration.py -v` → 全 passed（如有集成测试）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Migration 手工修改（JSON→JSONB、timezone）遗漏导致生产 DB 列类型不符预期 | 低 | 高 | Revert migration：先 `alembic downgrade -1`，再修复 migration 后 `alembic upgrade head` 重跑 |
| 部分索引语法（`postgresql_where`）在旧版 Postgres 不支持 | 低 | 中 | 如目标 PG < 12，改用普通索引作为 fallback，在 #721 调度器查询条件中过滤 NULL |
| #720 尚未合入时并行开发导致 model 定义冲突 | 中 | 低 | 定期 rebase master；model 字段为纯追加（nullable），不破坏 #720 的 fixture |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/webhook.py alembic/versions/*.py tests/unit/test_webhook_delivery_model.py
git commit -m "feat(webhooks): add next_retry_at, last_attempt_at, error_message to WebhookDeliveryModel"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#718): add retry-scheduling columns to WebhookDeliveryModel" --body "Closes #718"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/db/models/ticket.py` — 现有 `status` + nullable 时间戳列的 SQLAlchemy 定义模式
- 第三方文档：[Alembic Operation Reference — create_index postgresql_where](https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.ops.create_index)
- 父 issue / 关联：#496

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
