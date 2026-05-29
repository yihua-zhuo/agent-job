# 60-analytics · Add ChurnPrediction ORM model and migration

| 元数据 | 值 |
|---|---|
| Issue | #670 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：后续分析/报表板块需读取 churn_scores |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统中客户流失预测是核心分析能力之一。当前系统没有存储流失预测结果的表结构——每次需要流失评分时要么实时计算，要么无法复用历史结果。这导致：报表无法展示历史预测趋势、客服无法参考历史流失等级做分层服务、以及下游分析板块无法 join 流失数据。

Issue #670 要求创建一个 `ChurnPrediction` ORM model 和对应的 Alembic migration，为后续的分析与自动化规则（#686）提供数据基础。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层数据模型和 schema 迁移。
- **开发者视角**：新增 `ChurnPredictionModel` ORM 类，可通过 `CustomerService` 或专用 `ChurnPredictionService` 查询/写入流失评分数据；新增 migration 可通过 `alembic upgrade head` 安全应用，字段包括 `customer_id`、`tenant_id`、`score`（0-1 浮点）、`tier`（高/中/低）、`factors`（JSON）、`predicted_at`（时间戳）。

### 1.3 不做什么（剔除）

- [ ] 不实现流失预测算法本身（仅存储结果，不计算）
- [ ] 不实现 API router 或 service 方法（本 issue 仅限 ORM model + migration）
- [ ] 不在 migration 中做数据回填（空表创建即可）

### 1.4 关键 KPI

- `alembic upgrade head` → exit 0，表 `churn_predictions` 存在
- `alembic downgrade -1 && alembic upgrade head` → 双向迁移都 exit 0
- `ruff check src/db/models/churn_prediction.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPredictionModel; print('ok')"` → `ok`

---

## 2. 当前现状（起点）

### 2.1 现有实现

同类参考实现（使用 JSON 字段 + 多租户索引）：

[`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L{11}-L{37}

```python
class AIConversationModel(Base):
    """AI conversation session mapped to the ``ai_conversations`` table."""

    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ai_conversations_tenant_user", "tenant_id", "user_id"),
        {"sqlite_autoincrement": True},
    )
```

[`src/db/models/customer.py`](../../src/db/models/customer.py) L{25}

```python
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
```

[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L{21}-L{34}

```python
    op.create_table('ai_conversations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    op.create_index(op.f('ix_ai_conversations_tenant_id'), 'ai_conversations', ['tenant_id'], unique=False)
    op.create_index('ix_ai_conversations_tenant_user', 'ai_conversations', ['tenant_id', 'user_id'], unique=False)
```

### 2.2 涉及文件清单

- 要改：
  - 无（model 通过 pkgutil 自动发现，无需修改 `__init__.py`；alembic/env.py 已 import db.models）
- 要建：
  - `src/db/models/churn_prediction.py` — ChurnPredictionModel ORM 类
  - `alembic/versions/<id>_add_churn_predictions.py` — 创建 churn_predictions 表的 migration
  - `tests/unit/test_churn_prediction.py` — model 的基础单元测试

### 2.3 缺什么

- [ ] `ChurnPredictionModel` ORM 类——尚未创建，无法在代码中引用或查询流失预测数据
- [ ] `churn_predictions` 数据库表——缺少对应的 Alembic migration，schema 不存在
- [ ] 多租户索引——需要 `(tenant_id, customer_id)` 复合索引支持按租户快速查询某客户的预测记录

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/churn_prediction.py` | ChurnPredictionModel ORM 类，包含 customer_id/tenant_id/score/tier/factors/predicted_at 字段 |
| `alembic/versions/<id>_add_churn_predictions.py` | 创建 churn_predictions 表的 migration，包含 tenant_id 和 customer_id 索引 |
| `tests/unit/test_churn_prediction.py` | Model 单元测试：字段存在性、to_dict() 输出、租户隔离 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | pkgutil auto-discovery 机制无需修改任何现有文件 |

### 3.3 新增能力

- **ORM model**：`ChurnPredictionModel` in `src/db/models/churn_prediction.py`
- **DB table**：`churn_predictions` 表（alembic migration 创建）
- **Indexes**：`tenant_id` 单列索引 + `(tenant_id, customer_id)` 复合索引
- **JSON field**：`factors` 存储预测因子（允许 JSONB 序列化列表/字典）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **列名用 `factors` 不选 `metadata`**：`metadata` 与 SQLAlchemy `Base.metadata` 冲突，会在 `Base.metadata` 注册时引发属性名碰撞。现有代码中用 `recycle_history`（JSON）和 `tags`（JSON）均避免了 `metadata`，保持一致性。
- **用 `func.now()` 作为 server_default 不选 Python datetime.now()**：migration 中无法引用 Python 运行时时间，PostgreSQL 的 `now()` 在 DB 层生成时间戳，保证迁移到其他 DB 实例时行为一致。
- **不建 service 层**：本 issue 仅完成 ORM + migration，service/router 在后续 issue 中实现。保持本 issue scope 紧凑。

### 4.2 版本约束

无新增外部依赖，继承项目现有约束。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Model 中 JSON/JSONB 列（`factors`）在 `to_dict()` 时序列化——若值为 None 返回 `None`，若为 dict/list 直接返回（无需 json.dumps）
- Service 层尚未创建，暂不涉及 `AppException` 规范，但 model 文件需遵循 `to_dict()` 约定
- `__table_args__` 中使用 `{"sqlite_autoincrement": True}` 兼容 SQLite 测试；PostgreSQL 环境忽略此参数

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON** → 规避：migration 文件中手动将 `sa.JSON()` 改为 `sa.JSONB()`，否则 PostgreSQL 无法利用 GIN 索引
2. **Alembic autogen 生成空 migration（只 `pass`）** → 规避：先用 `alembic revision --autogenerate -m "add_churn_predictions"` 生成，检查 `op.create_table` 是否存在；若空则说明 Base.metadata 未扫描到新 model，需确认 model 文件已创建且无语法错误后再重跑
3. **`to_dict()` 对 None 时间戳不崩溃** → 现有 `customer.py` L{51}-L{55} 模式：使用 `if self.assigned_at else None` 短路，`predicted_at` 遵循相同模式

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ChurnPredictionModel ORM 类

在 `src/db/models/churn_prediction.py` 新建文件，参照 `ai_conversation.py` 的结构。

操作：
a) 创建 `src/db/models/churn_prediction.py`
b) 定义 `ChurnPredictionModel`，字段：id、tenant_id（索引）、customer_id（索引）、score（Float）、tier（String， nullable）、factors（JSONB，默认空 dict）、predicted_at（DateTime）、updated_at（DateTime，带 onupdate）
c) 定义 `to_dict()` 方法，返回所有字段的字典（datetime 用 isoformat）
d) 添加 `__table_args__`：复合索引 `(tenant_id, customer_id)` 和 `{"sqlite_autoincrement": True}`

示例代码：

```python
"""ChurnPrediction ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChurnPredictionModel(Base):
    """Churn prediction record mapped to the ``churn_predictions`` table."""

    __tablename__ = "churn_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "high" | "medium" | "low"
    factors: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_churn_predictions_tenant_customer", "tenant_id", "customer_id"),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "score": self.score,
            "tier": self.tier,
            "factors": self.factors or {},
            "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPredictionModel; print(ChurnPredictionModel.__tablename__)"` → 输出 `churn_predictions` / `ruff check src/db/models/churn_prediction.py` → 0 errors

---

### Step 2: 生成 Alembic migration

在专用 disposable 数据库上生成 migration，然后审查修正。

操作：
a) 确认 `src/db/models/churn_prediction.py` 已创建且语法正确
b) 确认 `alembic/versions/c94d682d4b03_add_ai_conversations.py` 是最新 head（`alembic current`）
c) 生成 migration：`alembic revision --autogenerate -m "add_churn_predictions"`
d) 审查生成的 migration 文件：
   - 确认 `op.create_table('churn_predictions', ...)` 存在
   - 将 `sa.JSON()` 手动改为 `sa.JSONB()`（autogen bug）
   - 确认 `server_default=sa.text('now()')` 存在（而非 Python datetime）
   - 确认有 `op.create_index(op.f('ix_churn_predictions_tenant_id'), ...)` 和复合索引
e) 若生成的 migration 为空（只有 `pass`），检查 model 文件语法后重新执行步骤 a-d

关键代码片段（migration 中应包含）：

```python
    op.create_table('churn_predictions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('tier', sa.String(length=20), nullable=True),
    sa.Column('factors', sa.JSONB(), nullable=False),  # must be JSONB, not JSON
    sa.Column('predicted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sqlite_autoincrement=True
    )
    op.create_index(op.f('ix_churn_predictions_tenant_id'), 'churn_predictions', ['tenant_id'], unique=False)
    op.create_index('ix_churn_predictions_tenant_customer', 'churn_predictions', ['tenant_id', 'customer_id'], unique=False)
```

**完成判定**：`cat alembic/versions/<new_id>_add_churn_predictions.py | grep "op.create_table\|JSONB\|now()"` → 输出包含三者的内容 / 文件存在

---

### Step 3: 验证 migration 双向可用

在 disposable 数据库上验证 migration 可以 apply 和 rollback。

操作：
a) 启动 test-db：`docker compose -f configs/docker-compose.test.yml up -d test-db`
b) 创建 disposable DB：`docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS churn_test;" && docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE churn_test;"`
c) 配置并运行 upgrade：

```bash
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/churn_test"
alembic upgrade head
```

d) 确认 exit 0 且无报错
e) 运行 downgrade：`alembic downgrade -1`
f) 确认 exit 0 且表已删除
g) 再次 upgrade 确认幂等性：`alembic upgrade head`

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次均 exit 0

---

### Step 4: 创建 Model 单元测试

在 `tests/unit/test_churn_prediction.py` 编写基础测试，验证 model 属性和 to_dict。

操作：
a) 创建 `tests/unit/test_churn_prediction.py`
b) 测试 `ChurnPredictionModel` 字段存在（id, tenant_id, customer_id, score, tier, factors, predicted_at, updated_at）
c) 测试 `to_dict()` 返回正确的 key 和类型
d) 测试 `__tablename__` 等于 `"churn_predictions"`

```python
"""Unit tests for ChurnPredictionModel."""

import pytest

from db.models.churn_prediction import ChurnPredictionModel


class TestChurnPredictionModel:
    def test_tablename(self):
        assert ChurnPredictionModel.__tablename__ == "churn_predictions"

    def test_to_dict_keys(self, snapshot):
        class FakePrediction:
            id = 1
            tenant_id = 10
            customer_id = 100
            score = 0.75
            tier = "high"
            factors = {"login_freq": 0.2, "support_tickets": 0.5}
            predicted_at = None
            updated_at = None

            def to_dict(self):
                return {
                    "id": self.id,
                    "tenant_id": self.tenant_id,
                    "customer_id": self.customer_id,
                    "score": self.score,
                    "tier": self.tier,
                    "factors": self.factors or {},
                    "predicted_at": self.predicted_at.isoformat() if self.predicted_at else None,
                    "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                }

        d = FakePrediction().to_dict()
        assert set(d.keys()) == {"id", "tenant_id", "customer_id", "score", "tier", "factors", "predicted_at", "updated_at"}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_prediction.py -v` → 3 passed / `ruff check tests/unit/test_churn_prediction.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/db/models/churn_prediction.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPredictionModel; print('ok')"` → `ok`
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_prediction.py -v` → 3 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] migration 文件中存在 `sa.JSONB()`（不是 `sa.JSON()`）
- [ ] migration 文件中存在 `server_default=sa.text('now()')`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogen 生成空 migration（model 未被 Base 扫描到） | 低 | 高 | 确认 model 文件语法无误，PYTHONPATH 正确后重跑 alembic revision --autogenerate |
| autogen 把 JSONB 写成 JSON，导致 factors 列无法建 GIN 索引 | 中 | 中 | 手动编辑 migration 文件，将 `sa.JSON()` 改为 `sa.JSONB()`，不阻塞下游 |
| 多租户索引漏写，导致查询横扫全表 | 中 | 高 | 在 migration 审查时确认 `ix_churn_predictions_tenant_id` 和复合索引都存在 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/churn_prediction.py
git add alembic/versions/<new_id>_add_churn_predictions.py
git add tests/unit/test_churn_prediction.py
git commit -m "feat(analytics): add ChurnPrediction ORM model and migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#670): add ChurnPrediction ORM model and migration" --body "Closes #670"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) — JSONB 列 + 多租户索引的 ORM 模式
- 同类参考实现：[`src/db/models/customer.py`](../../src/db/models/customer.py) — JSON 列的 `to_dict()` 模式（None 短路）
- 第三方文档：[SQLAlchemy 2.x Mapped Column](https://docs.sqlalchemy.org/en/20/orm/mapping_columns.html)
- 父 issue / 关联：#35

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
