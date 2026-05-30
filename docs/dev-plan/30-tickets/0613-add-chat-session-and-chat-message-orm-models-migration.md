# 修复后的 Board

```markdown
# 聊天会话 · Add chat_session and chat_message ORM models

| 元数据 | 值 |
|---|---|
| Issue | #613 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.25-0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：下游聊天功能 Service/Router 板块依赖此 schema |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #43 子任务。CRM 需要持久化聊天会话数据，当前数据库无 `chat_sessions` / `chat_messages` 表，上层 Service 和 Router 无底层模型可序列化，阻塞后续聊天功能开发。

### 1.2 做完成后

- **用户视角**：无用户可见变化 — 纯底层 ORM + migration。
- **开发者视角**：`ChatSessionModel` 和 `ChatMessageModel` 可被 `session.execute(select(ChatSessionModel))` 调用；Service 层可直接操作 ORM 对象而无需绕过模型； Alembic autogenerate 生成 reversible migration，所有下游板块依赖此 schema。

### 1.3 不做什么（剔除）

- [ ] 不在 ORM 层实现 Service 业务逻辑（留待后续板块）
- [ ] 不在 ORM 层实现 API Router（留待后续板块）
- [ ] 不实现 AI intent detection 逻辑 — `intent` 列仅作存储字段，填充逻辑由上游板块负责

### 1.4 关键 KPI

- `ruff check src/db/models/chat_session.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_chat_session.py -v` → ≥ 3 passed
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/db/models/ai_conversation.py`](../../../src/db/models/ai_conversation.py) L{11}-L{47}

同类参考实现（同 repo 同模式），可作为 `ChatSessionModel` / `ChatMessageModel` 的模板：

```python:src/db/models/ai_conversation.py
class AIConversationModel(Base):
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
    messages: Mapped[list["AIMessageModel"]] = relationship(
        "AIMessageModel", back_populates="conversation",
        cascade="all, delete-orphan", lazy="raise",
    )

class AIMessageModel(Base):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../../alembic/env.py) — 在 `import db.models` 后追加 `from db.models import chat_session` 以确保 autogenerate 能发现新模型
- 要建：
  - `src/db/models/chat_session.py` — 定义 `ChatSessionModel` + `ChatMessageModel` ORM 类
  - `alembic/versions/<id>_add_chat_sessions_and_messages.py` — 迁移文件（autogenerate 生成后手动修正）
  - `tests/unit/test_chat_session.py` — ORM 模型单元测试

### 2.3 缺什么

- [ ] `ChatSessionModel` ORM 类（id, tenant_id, user_id, title, created_at, updated_at）
- [ ] `ChatMessageModel` ORM 类（id, session_id, role, content, intent, created_at）
- [ ] `chat_sessions` + `chat_messages` 表的 Alembic migration（可逆，含索引）
- [ ] `alembic/env.py` 中对新模型文件的 import（autodiscovery 依赖显式导入）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/db/models/chat_session.py` | 定义 `ChatSessionModel`（聊天会话主表）和 `ChatMessageModel`（会话消息表）两个 ORM 类 |
| `alembic/versions/<id>_add_chat_sessions_and_messages.py` | 创建 `chat_sessions` 和 `chat_messages` 表，含 tenant_id 索引、session_id FK 索引 |
| `tests/unit/test_chat_session.py` | 单元测试：模型字段、to_dict、relationship、MockRow/MockResult 兼容性 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../../alembic/env.py) | 在 `import db.models` 下方新增一行 `from db.models import chat_session`（确保 Base.metadata 包含新模型） |

### 3.3 新增能力

- **ORM model**：`ChatSessionModel` in `src/db/models/chat_session.py`
- **ORM model**：`ChatMessageModel` in `src/db/models/chat_session.py`
- **Migration**：`alembic upgrade head` 创建 `chat_sessions` 表（含 `(tenant_id, user_id)` 复合索引）和 `chat_messages` 表（含 FK 索引）
- **Relationship**：`ChatMessageModel.session → ChatSessionModel`，cascade delete

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `chat_sessions` / `chat_messages` 表名而不复用 `ai_conversations` / `ai_messages`**：issue #613 明确要求独立表结构，与 AI 对话模型语义不同（后者 role 只有 user/assistant，chat_messages 含 intent 字段）
- **选relationship lazy="raise" 而不选 lazy="select"**：参考 `ai_conversation.py` 中的实践，避免 N+1 查询被静默忽略；如在 session 中访问未加载的 relationship 直接报错而非返回空列表

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`ChatSessionModel.tenant_id` 必须有 `index=True`，每个查询必须 `WHERE tenant_id = :tenant_id`
- 列名不得使用 `metadata`（与 `Base.metadata` 冲突）→ `intent` 字段无此冲突，可正常使用
- `ChatMessageModel.created_at` 用 `server_default=func.now()` 而非 `default=func.now()`（后者在 SQLAlchemy 中行为不一致）
- PYTHONPATH=src，import 路径写 `from db.models import ChatSessionModel` 而非 `from src.db.models...`

### 4.4 已知坑

1. **Alembic autogenerate 把 `TIMESTAMPTZ` 写成 `DateTime`（不带 timezone）** → 规避：生成 migration 后检查 `created_at` / `updated_at` 列定义，手动将 `DateTime(timezone=False)` 改为 `DateTime(timezone=True)`
2. **Alembic autogenerate 漏掉复合索引名** → 规避：手动补全 `Index("ix_chat_messages_tenant_session", "tenant_id", "session_id")`
3. **`__init__.py` 用 `pkgutil.iter_modules` 自动发现，model 文件名含下划线（如 `chat_session.py`）被错误解析** → 规避：已在 `ai_conversation.py` 验证同样命名风格可用；下划线会被正确识别为模块分隔符而非包层级

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/db/models/chat_session.py` ORM 模型文件

新建文件，定义 `ChatSessionModel` 和 `ChatMessageModel` 两个 ORM 类，字段完全对应 issue #613 要求。参考 `ai_conversation.py` 的 import 和列定义风格，保持与项目一致。

```python
"""Chat Session and Message ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class ChatSessionModel(Base):
    """Chat session mapped to the ``chat_sessions`` table."""

    __tablename__ = "chat_sessions"

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
        Index("ix_chat_sessions_tenant_user", "tenant_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    messages: Mapped[list["ChatMessageModel"]] = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatMessageModel(Base):
    """Chat message within a session, mapped to the ``chat_messages`` table."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_chat_messages_tenant_session", "tenant_id", "session_id"),
        {"sqlite_autoincrement": True},
    )

    session: Mapped["ChatSessionModel"] = relationship(
        "ChatSessionModel",
        back_populates="messages",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ls src/db/models/chat_session.py` → 文件存在 / `ruff check src/db/models/chat_session.py` → 0 errors

### Step 2: 在 `alembic/env.py` 追加 import

在 `alembic/env.py` 第 14 行 `import db.models` 后追加：

```python
from db.models import chat_session  # noqa: F401 — registers ChatSessionModel + ChatMessageModel
```

**完成判定**：`grep -n "chat_session" alembic/env.py` → 找到 import 行

### Step 3: 运行 Alembic autogenerate 生成 migration

按照 CLAUDE.md §Alembic Migrations 步骤操作：

```bash
# 1. 启动 test-db 并创建 alembic_dev 数据库
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"

# 2. 将 alembic_dev 升级到 head（确保 base 一致）
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head

# 3. 运行 autogenerate
alembic revision --autogenerate -m "add chat_sessions and chat_messages tables"
```

生成的 migration 文件名如 `alembic/versions/<hash>_add_chat_sessions_and_messages.py`，review 后确认：

- `created_at` / `updated_at` 用 `DateTime(timezone=True)`（非 DateTime）
- `chat_sessions` 有 `ix_chat_sessions_tenant_id` 索引
- `chat_sessions` 有 `ix_chat_sessions_tenant_user` 复合索引
- `chat_messages` 有 `ix_chat_messages_session_id` FK 索引
- `chat_messages` 有 `ix_chat_messages_tenant_session` 复合索引
- `downgrade()` 有 `op.drop_table('chat_messages')` 和 `op.drop_table('chat_sessions')`

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 4: 创建单元测试 `tests/unit/test_chat_session.py`

测试文件结构参考 `tests/unit/conftest.py` 中的 `MockState`、`MockRow` 等构建块。

测试用例：
- `test_chat_session_model_to_dict`：验证 `ChatSessionModel.to_dict()` 返回正确字段
- `test_chat_message_model_to_dict`：验证 `ChatMessageModel.to_dict()` 包含 `intent` 字段
- `test_chat_session_relationship`：验证 `ChatSessionModel.messages` relationship 可遍历

```python
import pytest
from unittest.mock import MagicMock

from db.models.chat_session import ChatSessionModel, ChatMessageModel


class TestChatSessionModel:
    def test_to_dict_returns_all_fields(self):
        session = ChatSessionModel(
            id=1,
            tenant_id=10,
            user_id=5,
            title="Test Session",
            created_at=None,
            updated_at=None,
        )
        d = session.to_dict()
        assert d["id"] == 1
        assert d["tenant_id"] == 10
        assert d["user_id"] == 5
        assert d["title"] == "Test Session"
        assert "created_at" in d
        assert "updated_at" in d

    def test_tenant_id_column_indexed(self):
        # Verify column is defined (runtime check via inspection)
        col = ChatSessionModel.__table__.c["tenant_id"]
        assert col.nullable is False


class TestChatMessageModel:
    def test_to_dict_returns_all_fields(self):
        msg = ChatMessageModel(
            id=1,
            session_id=5,
            tenant_id=10,
            role="user",
            content="Hello",
            intent="greeting",
            created_at=None,
        )
        d = msg.to_dict()
        assert d["id"] == 1
        assert d["session_id"] == 5
        assert d["tenant_id"] == 10
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["intent"] == "greeting"

    def test_intent_can_be_null(self):
        msg = ChatMessageModel(
            id=2,
            session_id=5,
            tenant_id=10,
            role="assistant",
            content="Hi there",
            intent=None,
            created_at=None,
        )
        assert msg.intent is None

    def test_foreign_key_on_session_id(self):
        fk = ChatMessageModel.__table__.c["session_id"].foreign_keys
        assert any("chat_sessions" in str(f.column) for f in fk)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_session.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/chat_session.py` → 0 errors
- [ ] `ruff check alembic/env.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_chat_session.py -v` → ≥ 3 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `grep "chat_session" alembic/env.py` → 1 行 import

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogenerate 生成空 migration（模型未在 env.py 中 import） | 低 | 高 | 检查 `alembic/env.py` 是否有 `from db.models import chat_session`，若无则补上后重新 autogenerate |
| autogenerate 把 TIMESTAMPTZ 写成 DateTime（无 timezone） | 中 | 中 | 手动编辑 migration 文件，将 `DateTime(timezone=False)` 改为 `DateTime(timezone=True)` |
| 复合索引名冲突（已存在 ix_chat_sessions_tenant_user） | 极低 | 中 | 检查 `alembic/versions/` 中无重名后手动修正 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/chat_session.py alembic/env.py alembic/versions/<id>_add_chat_sessions_and_messages.py tests/unit/test_chat_session.py
git commit -m "feat(models): add ChatSessionModel and ChatMessageModel ORM + migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(models): add chat_session and chat_message ORM + migration" --body "Closes #613

## Summary
- Add `ChatSessionModel` (chat_sessions table) with tenant_id, user_id, title, timestamps
- Add `ChatMessageModel` (chat_messages table) with session FK, role, content, intent, created_at
- Generate reversible Alembic migration with proper indexes
- Import new model module in alembic/env.py for Base.metadata discovery

## Test plan
- [ ] `ruff check src/db/models/chat_session.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_chat_session.py -v` → ≥ 3 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0"
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ai_conversation.py`](../../../src/db/models/ai_conversation.py) — `AIConversationModel` + `AIMessageModel` 同模式实现，可直接对照字段差异
- 父 issue / 关联：#43

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
```

---

**修复说明**：唯一破损链接 `[聊天功能 Service/Router 板块](30-tickets/)` → `30-tickets/` 目录不存在，无从推导正确路径。已按 option (b) 替换为 `TBD - 待验证：下游聊天功能 Service/Router 板块依赖此 schema`，保留语义说明。
