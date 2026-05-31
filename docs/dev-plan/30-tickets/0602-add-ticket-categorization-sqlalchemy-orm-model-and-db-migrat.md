# 票据分类 SQLAlchemy ORM 模型与数据库迁移

| 元数据 | 值 |
|---|---|
| Issue | #602 |
| 分类 | [30-tickets](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：其他 AI 分类相关板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #45 的子任务。AI 分类结果（type、priority、confidence、reasons、suggested_assignee_id、suggested_team、human_override）目前无处持久化。TicketModel 已存在，但 AI 分类元数据不应混入主表——独立表允许同一 Ticket 保留多版本分类历史，也避免主表列膨胀。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层数据模型。
- **开发者视角**：可通过 `TicketCategorizationModel` 持久化和查询 AI 分类结果；后续在 Service 层封装 CRUD 逻辑后即可被 endpoint 调用。

### 1.3 不做什么（剔除）

- [ ] 不创建任何 API endpoint（issue 明确"暂不接入"）。
- [ ] 不创建 TicketCategorizationService — 仅建 ORM model 和 migration。
- [ ] 不修改 TicketModel 现有列。

### 1.4 关键 KPI

- `ruff check src/db/models/ticket_categorization.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_model.py -v` → 全 passed
- `PYTHONPATH=src pytest tests/integration/test_ticket_categorization_integration.py -v` → 全 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

参考 ORM 模型（同目录，分割良好）：[`src/db/models/ticket_reply.py`](../../../src/db/models/ticket_reply.py) L{1}-L{30}

```python
class TicketReplyModel(Base):
    __tablename__ = "ticket_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "ticket_id": self.ticket_id, ...}
```

参考迁移（同分支）：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../../alembic/versions/c94d682d4b03_add_ai_conversations.py) L{1}-L{60}

### 2.2 涉及文件清单

- 要改：
  - `alembic/versions/` — 新建迁移文件，parent revision 指向 `c94d682d4b03`
  - `src/db/models/__init__.py` — 新文件自动被 pkgutil 发现，无需手动 import
- 要建：
  - `src/db/models/ticket_categorization.py` — TicketCategorizationModel ORM 模型
  - `alembic/versions/<hash>_add_ticket_categorization.py` — 数据库迁移
  - `tests/unit/test_ticket_categorization_model.py` — ORM 模型单元测试
  - `tests/integration/test_ticket_categorization_integration.py` — 集成测试

### 2.3 缺什么

- [ ] `TicketCategorizationModel` ORM 模型，存储 AI 分类结果（type、priority、confidence、reasons JSON、suggested_assignee_id、suggested_team、categorized_at、human_override）
- [ ] Alembic migration 创建 `ticket_categorizations` 表（含 tenant_id 索引和外键）
- [ ] 模型单元测试（`to_dict()` 方法、字段默认值、datetime 序列化）
- [ ] 集成测试（CREATE + READ 端到端，真实数据库）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/ticket_categorization.py` | TicketCategorizationModel ORM 模型，含 ticket_id FK、tenant_id 索引、reasons JSONB 列 |
| `alembic/versions/<hash>_add_ticket_categorization.py` | 创建 `ticket_categorizations` 表的数据库迁移 |
| `tests/unit/test_ticket_categorization_model.py` | ORM 模型单元测试（to_dict、默认值、datetime 序列化） |
| `tests/integration/test_ticket_categorization_integration.py` | 集成测试（CREATE + READ 端到端，真实 Postgres） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | 本板块不修改任何现有文件 |

### 3.3 新增能力

- **ORM model**：`TicketCategorizationModel` in `src/db/models/ticket_categorization.py`
- **Migration**：`alembic upgrade head` 创建 `ticket_categorizations` 表（含 `tenant_id` 索引和 `ticket_id` FK）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **独立表而非扩展 TicketModel**：允许同一 ticket 保留多版本分类历史；避免主表列膨胀；后续可独立做 `human_override` 审批工作流。
- **reasons 用 JSONB**：AI 返回的分类理由是变长结构化文本，JSONB 支持索引和 PG 原生查询，无需预定义 schema。
- **外键 `ticket_id` 带 `ondelete='CASCADE'`**：当 ticket 被删除时，关联分类记录一并清理。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- ORM 模型放在 `db.models` 下，`__init__.py` 通过 pkgutil 自动发现，无需手动 import
- 迁移文件 `down_revision` 必须指向前一个 head migration `c94d682d4b03`
- Alembic autogen 会把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime — 必须手动改回
- PYTHONPATH=src，import 写 `from db.models...` 而不是 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogenerate 把 JSONB 写成 JSON** → 规避：生成后手动将 `sa.JSON()` 改为 `sa.JSONB()`；运行 `alembic upgrade head` 确认无报错后 `alembic downgrade -1` 验证 downgrade 也正确。
2. **Alembic autogenerate 把 TIMESTAMPTZ 写成 DateTime** → 规避：生成后检查 `DateTime(timezone=True)` 是否正确，PostgreSQL 生产环境必须带 timezone。
3. **模型文件名含 `metadata` 与 `Base.metadata` 冲突** → 规避：本板块字段名使用 `event_metadata` / `payload` 等，不使用 `metadata` 作为列名（本模型不含此字段，纯提醒）。
4. **server_default vs Python default**：datetime 字段在 PostgreSQL 侧用 `server_default=func.now()`，不在 Python 构造函数设默认值。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 TicketCategorizationModel ORM 模型

参考 `ticket_reply.py` 的风格，新建 `src/db/models/ticket_categorization.py`。

操作：
a) 创建 `src/db/models/ticket_categorization.py`：
   - 继承 `db.base.Base`
   - `__tablename__ = "ticket_categorizations"`
   - 列：id（int, PK）、ticket_id（int, FK tickets.id, CASCADE）、tenant_id（int, indexed）、type（str）、priority（str）、confidence（float）、reasons（JSONB）、suggested_assignee_id（int, nullable）、suggested_team（str, nullable）、human_override（bool, default False）、categorized_at（datetime TZ）、created_at（datetime TZ, server_default）、updated_at（datetime TZ, server_default+onupdate）
   - `to_dict()` 方法：返回所有字段，datetime 序列化为 ISO 格式

```python
"""Ticket categorization ORM model."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TicketCategorizationModel(Base):
    """Stores AI classification results for a ticket."""

    __tablename__ = "ticket_categorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    suggested_assignee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    categorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "type": self.type,
            "priority": self.priority,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "suggested_assignee_id": self.suggested_assignee_id,
            "suggested_team": self.suggested_team,
            "human_override": self.human_override,
            "categorized_at": self.categorized_at.isoformat() if self.categorized_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

**完成判定**：`ruff check src/db/models/ticket_categorization.py` → 0 errors

---

### Step 2: 生成 Alembic migration

操作：
a) 启动干净数据库：
   ```
   docker compose -f configs/docker-compose.test.yml up -d test-db
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
   docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
   ```
b) 设置环境变量：
   ```
   export PYTHONPATH=src
   export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
   export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
   ```
c) 将 alembic_dev 推进到当前 head：
   ```
   alembic upgrade c94d682d4b03
   ```
d) 生成 migration：
   ```
   alembic revision --autogenerate -m "add_ticket_categorization"
   ```
e) 审查生成的迁移文件：
   - 确认 `down_revision = 'c94d682d4b03'`
   - 确认 JSON 列已手动改为 `sa.JSONB()`
   - 确认 `tenant_id` 有 `index=True`
   - 确认 `ticket_id` 有 FK + `ondelete='CASCADE'`
   - 确认 `human_override` 用 `server_default=sa.text('false')`（Boolean 在 PG 无 server_default，手动加）
   - 填入 `downgrade()`：删除表

f) 验证 migrate up + down 干净：
   ```
   alembic upgrade head && alembic downgrade -1 && alembic upgrade head
   ```
g) 运行 drift check（应生成空迁移，删掉）：
   ```
   alembic revision --autogenerate -m "drift_check"
   ```
   若新文件 up/down 都是 `pass`，删除它。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 编写 ORM 模型单元测试

参考 `tests/unit/test_customer_model.py` 的 Pydantic 测试风格（测试实例化 + to_dict），但针对 ORM 模型直接实例化（无需 DB）。

操作：
a) 创建 `tests/unit/test_ticket_categorization_model.py`：
   - 测试 `to_dict()` 输出所有字段
   - 测试 `reasons` JSON 字段支持 dict 赋值
   - 测试 `suggested_assignee_id` / `suggested_team` 为 None 时正确序列化
   - 测试 `human_override` 默认为 False
   - 测试 `categorized_at` 传入 datetime 对象后 to_dict 返回 ISO 格式字符串

```python
"""Unit tests for TicketCategorizationModel."""
import pytest
from datetime import datetime, UTC
from db.models.ticket_categorization import TicketCategorizationModel


class TestTicketCategorizationModel:
    def test_to_dict_contains_all_fields(self):
        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            id=1,
            ticket_id=10,
            tenant_id=5,
            type="bug",
            priority="high",
            confidence=0.95,
            reasons={"rule": "matched_keyword", "signal": "urgency_detected"},
            suggested_assignee_id=42,
            suggested_team="support-tier2",
            human_override=False,
            categorized_at=now,
        )
        d = record.to_dict()
        assert d["id"] == 1
        assert d["ticket_id"] == 10
        assert d["tenant_id"] == 5
        assert d["type"] == "bug"
        assert d["priority"] == "high"
        assert d["confidence"] == 0.95
        assert d["reasons"] == {"rule": "matched_keyword", "signal": "urgency_detected"}
        assert d["suggested_assignee_id"] == 42
        assert d["suggested_team"] == "support-tier2"
        assert d["human_override"] is False
        assert d["categorized_at"] == now.isoformat()

    def test_to_dict_suggested_fields_none(self):
        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            ticket_id=10,
            tenant_id=5,
            type="question",
            priority="low",
            confidence=0.60,
            reasons={},
            suggested_assignee_id=None,
            suggested_team=None,
            human_override=False,
            categorized_at=now,
        )
        d = record.to_dict()
        assert d["suggested_assignee_id"] is None
        assert d["suggested_team"] is None

    def test_to_dict_categorized_at_isoformat(self):
        now = datetime.now(UTC)
        record = TicketCategorizationModel(
            ticket_id=10,
            tenant_id=5,
            type="feature",
            priority="medium",
            confidence=0.80,
            reasons={"pattern": "feature_request"},
            human_override=True,
            categorized_at=now,
        )
        d = record.to_dict()
        assert d["categorized_at"] == now.isoformat()
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ticket_categorization_model.py -v` → 全 passed

---

### Step 4: 编写集成测试

参考 `tests/integration/conftest.py` 的 fixture 使用方式。集成测试使用真实数据库，通过 schema fixture 管理表结构。

操作：
a) 创建 `tests/integration/test_ticket_categorization_integration.py`：

```python
"""Integration tests for TicketCategorizationModel."""
import pytest
from datetime import datetime, UTC
from sqlalchemy import select
from db.models.ticket import TicketModel
from db.models.ticket_categorization import TicketCategorizationModel


@pytest.mark.integration
class TestTicketCategorizationIntegration:
    async def test_create_and_read(self, db_schema, tenant_id, async_session):
        # Seed: ticket must exist (FK constraint)
        ticket = TicketModel(
            tenant_id=tenant_id,
            subject="Help needed",
            description="Something is broken",
            status="open",
            priority="medium",
            channel="email",
            customer_id=1,
        )
        async_session.add(ticket)
        await async_session.commit()
        await async_session.refresh(ticket)

        # Insert categorization record
        categorization = TicketCategorizationModel(
            ticket_id=ticket.id,
            tenant_id=tenant_id,
            type="bug",
            priority="high",
            confidence=0.92,
            reasons={"rule": "error_keyword", "confidence_breakdown": {"syntax": 0.9, "stacktrace": 0.95}},
            suggested_assignee_id=7,
            suggested_team="eng-support",
            human_override=False,
            categorized_at=datetime.now(UTC),
        )
        async_session.add(categorization)
        await async_session.commit()
        await async_session.refresh(categorization)

        # Read back
        result = await async_session.execute(
            select(TicketCategorizationModel).where(
                TicketCategorizationModel.id == categorization.id,
                TicketCategorizationModel.tenant_id == tenant_id,
            )
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.ticket_id == ticket.id
        assert found.type == "bug"
        assert found.priority == "high"
        assert found.confidence == 0.92
        assert found.reasons["rule"] == "error_keyword"
        assert found.suggested_assignee_id == 7
        assert found.human_override is False

    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        # Different tenant's record must not be visible
        other_tenant_id = tenant_id + 999
        ticket = TicketModel(
            tenant_id=other_tenant_id,
            subject="Other tenant ticket",
            description="Desc",
            status="open",
            priority="low",
            channel="email",
            customer_id=1,
        )
        async_session.add(ticket)
        await async_session.commit()
        await async_session.refresh(ticket)

        cat = TicketCategorizationModel(
            ticket_id=ticket.id,
            tenant_id=other_tenant_id,
            type="question",
            priority="low",
            confidence=0.5,
            reasons={},
            human_override=False,
            categorized_at=datetime.now(UTC),
        )
        async_session.add(cat)
        await async_session.commit()

        # Query with wrong tenant — should find nothing
        result = await async_session.execute(
            select(TicketCategorizationModel).where(
                TicketCategorizationModel.ticket_id == ticket.id,
                TicketCategorizationModel.tenant_id == tenant_id,
            )
        )
        assert result.scalar_one_or_none() is None
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_ticket_categorization_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/ticket_categorization.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_model.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_ticket_categorization_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `ruff check alembic/versions/<hash>_add_ticket_categorization.py` → 0 errors（如有 lint 规则）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| JSONB 列迁移写法与 PG 版本不兼容（PG < 13 不支持 JSONB） | 低 | 低 | 改用 `JSON` 类型；本项目 PG 已知为现代版本（见 docker-compose） |
| FK 循环依赖：TicketCategorizationModel 依赖 tickets 表，ticket delete 时 CASCADE 正常 | 低 | 中 | downgrade 迁移手动删除 `ticket_categorizations` 表，不影响 tickets 表 |
| migration 合并冲突（多 PR 并行时 revision chain 冲突） | 中 | 中 | 本板块是最新 head（c94d682d4b03 之后），单线程 merge 无冲突风险 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/ticket_categorization.py
git add alembic/versions/<hash>_add_ticket_categorization.py
git add tests/unit/test_ticket_categorization_model.py
git add tests/integration/test_ticket_categorization_integration.py
git commit -m "feat(tickets): add TicketCategorizationModel ORM and migration

Closes #602"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(tickets): add TicketCategorizationModel ORM and migration (closes #602)" --body "## Summary
- Add TicketCategorizationModel with type, priority, confidence, reasons (JSONB), suggested_assignee_id, suggested_team, human_override, categorized_at
- Alembic migration creates ticket_categorizations table with tenant_id index and ticket_id FK (CASCADE)
- Unit tests: to_dict, default values, datetime serialization
- Integration tests: CREATE + READ with tenant isolation

## Test plan
- [x] ruff check src/db/models/ticket_categorization.py — 0 errors
- [x] PYTHONPATH=src pytest tests/unit/test_ticket_categorization_model.py -v — all passed
- [x] PYTHONPATH=src pytest tests/integration/test_ticket_categorization_integration.py -v — all passed
- [x] alembic upgrade head && alembic downgrade -1 && alembic upgrade head — all exit 0

Closes #602"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ticket_reply.py`](../../../src/db/models/ticket_reply.py) — FK + tenant_id 模式完全相同
- 同类参考实现：[`alembic/versions/c94d682d4b03_add_ai_conversations.py`](../../../alembic/versions/c94d682d4b03_add_ai_conversations.py) — JSONB 列 + server_default 迁移范本
- 同类参考实现：[`tests/unit/test_ticket_model.py`](../../../tests/unit/test_ticket_model.py) — 模型测试风格（不过该文件测试 Pydantic 模型；本板块测试 ORM 模型实例化）
- 父 issue：#45

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
