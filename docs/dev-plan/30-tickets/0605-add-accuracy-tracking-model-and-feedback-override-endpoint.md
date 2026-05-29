# 分类准确率追踪 · Add CategorizationFeedback model and PATCH feedback endpoint

| 元数据 | 值 |
|---|---|
| Issue | #605 |
| 分类 | [30-tickets](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0604-构建工单分类数据模型](../0604-构建工单分类数据模型-and-migration.md)（TBD - 待确认该板块文件路径） |
| 启用后赋能 | [0606-构建工单分类准确率指标](../0606-add-accuracy-metrics-endpoint-and-basic-reporting.md) — 依赖 `TicketCategorizationModel` 上的 override 标记字段 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The LLM-based ticket categorization engine (introduced in #604) currently has no mechanism for human agents to correct misclassifications. Without an override record, the system cannot distinguish between LLM-confident predictions and human-corrected ones — making it impossible to measure accuracy, retrain the model, or surface systematic errors. A dedicated `CategorizationFeedback` model and a REST endpoint for recording corrections are prerequisites for the downstream accuracy metrics pipeline (#606).

### 1.2 做完后

- **用户视角**：`PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` allows agents to override the LLM-assigned category and/or priority for a specific ticket. The override is persisted with the corrector's user_id and timestamp.
- **开发者视角**：`CategorizationFeedbackModel` ORM class is available for queries; `TicketCategorizationService.submit_feedback()` can be called from the router; the `overridden` flag on `TicketCategorizationModel` is updated when feedback is submitted.

### 1.3 不做什么（剔除）

- [ ] Do not implement the LLM classification logic itself — that is handled in #604
- [ ] Do not implement the accuracy metrics aggregation (override_rate, avg_confidence) — that belongs to #606
- [ ] Do not add a separate `TicketCategorizationModel` in this issue — the categorization model is provided by #604; this board only adds the feedback/override layer on top

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ticket_categorization.py -v` → ≥ 3 passed
- `ruff check src/db/models/ticket_categorization.py src/services/ticket_service.py src/api/routers/tickets.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

Issue #604 creates `TicketCategorizationModel` in `src/db/models/ticket_categorization.py` — this board takes that model as the base and adds the feedback/override layer. Until #604 is completed, the following file path is speculative and must be verified at implementation time.

> TBD - 待验证：#604 生成 `src/db/models/ticket_categorization.py` 中的 `TicketCategorizationModel` 是否存在；若无此文件，本板块无法实施。

参考同类 ORM 模型定义（reply 模式）：[`src/db/models/ticket_reply.py`](../../src/db/models/ticket_reply.py) L{11}-L{35}

```python:src/db/models/ticket_reply.py
class TicketReplyModel(Base):
    __tablename__ = "ticket_replies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

参考 PATCH 端点模式：[`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) L{196}-L{213}

```python:src/api/routers/tickets.py
@tickets_router.put("/{ticket_id}", ...)
async def update_ticket(ticket_id: int, ...):
    svc = TicketService(session)
    ticket = await svc.get_ticket(ticket_id, tenant_id=ctx.tenant_id)
    updated = await svc.update_ticket(ticket_id, tenant_id=ctx.tenant_id, ...)
    return {"success": True, "data": updated.to_dict()}
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/ticket_service.py`](../../src/services/ticket_service.py) — 新增 `submit_categorization_feedback()` 方法，更新 `TicketCategorizationModel.overridden` 字段并写入 `CategorizationFeedbackModel`
  - [`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) — 新增 `PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` 端点
  - [`tests/unit/test_ticket_service.py`](../../tests/unit/test_ticket_service.py) — 新增 feedback submit 测试用例
  - [`tests/unit/test_tickets_router.py`](../../tests/unit/test_tickets_router.py) — 新增 router feedback 端点测试用例
  - `alembic/env.py` — 如需注册新模型（确认 `db.models` 已导入所有 model 模块）
- 要建：
  - `src/db/models/ticket_categorization.py` — `CategorizationFeedbackModel`（issue #604 会先创建 `TicketCategorizationModel`，本板块在其文件中追加 `CategorizationFeedbackModel`）
  - `alembic/versions/<id>_add_categorization_feedback_table.py` — 创建 `categorization_feedback` 表
  - `tests/unit/test_ticket_categorization.py` — 单元测试（含 happy path、boundary、error）

### 2.3 缺什么

- [ ] `CategorizationFeedbackModel` — ORM model storing original vs corrected classification, corrector user_id, timestamp
- [ ] `TicketService.submit_categorization_feedback()` — persists a feedback record and sets `TicketCategorizationModel.overridden = True`
- [ ] `PATCH /tickets/{ticket_id}/categorization/feedback` endpoint — accepts `{category?, priority?}`, validates ticket ownership, calls service
- [ ] Alembic migration for `categorization_feedback` table
- [ ] Unit test covering override flow (success, ticket-not-found, unauthorized)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/ticket_categorization.py` | `CategorizationFeedbackModel` ORM model (appended to file created by #604) |
| `alembic/versions/<id>_add_categorization_feedback_table.py` | Migration creating `categorization_feedback` table with tenant_id index |
| `tests/unit/test_ticket_categorization.py` | Unit tests: happy path (feedback persisted + overridden=True), boundary (no categorization exists), error (NotFoundException) |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/ticket_service.py`](../../src/services/ticket_service.py) | 新增 `submit_categorization_feedback(ticket_id, tenant_id, user_id, category?, priority?)` 方法 |
| [`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) | 新增 `PATCH /tickets/{ticket_id}/categorization/feedback` 端点 |
| [`tests/unit/test_ticket_service.py`](../../tests/unit/test_ticket_service.py) | 新增 `test_submit_categorization_feedback_*` 测试用例 |
| [`tests/unit/test_tickets_router.py`](../../tests/unit/test_tickets_router.py) | 新增 `test_patch_categorization_feedback_*` 测试用例 |

### 3.3 新增能力

- **ORM model**：`CategorizationFeedbackModel` in `src/db/models/ticket_categorization.py`
- **Service method**：`TicketService.submit_categorization_feedback(self, ticket_id: int, tenant_id: int, user_id: int, category: str | None, priority: str | None) -> CategorizationFeedbackModel`
- **API endpoint**：`PATCH /api/v1/tickets/{ticket_id}/categorization/feedback` → `{"success": true, "data": {...}}`
- **Migration**：`alembic upgrade head` 创建 `categorization_feedback` 表（含 `tenant_id` 索引，FK 到 `tickets`）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **在同一文件追加 `CategorizationFeedbackModel` 而非新建文件**：issue #604 creates `src/db/models/ticket_categorization.py` with `TicketCategorizationModel`; appending `CategorizationFeedbackModel` to that same file keeps related models together and avoids proliferation of small model files.
- **PATCH 不替代原始记录**：feedback 记录是 append-only audit log; we set `TicketCategorizationModel.overridden = True` to signal the classification was corrected, but we never delete or overwrite the original classification row.
- **category 和 priority 均为 optional in PATCH**：agent may correct only one field (e.g., fix category but leave priority); requiring both would be too restrictive.

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- Router 用 `session: AsyncSession = Depends(get_db)` 而非 `async with get_db()`
- Alembic migration 使用 `postgresql+asyncpg` 驱动；所有 timestamp 列使用 `DateTime(timezone=True)`

### 4.4 已知坑

1. **Alembic autogenerate 把 `DateTime(timezone=True)` 写成 `DateTime`** → 规避：生成 migration 后手动检查所有 timestamp 列，手动改为 `DateTime(timezone=True)` 和 `server_default=sa.text('now()')`
2. **PK 名冲突（列名 `id` 在 feedback 表 OK）** → `CategorizationFeedbackModel` has its own `id` PK; no conflict with `ticket_id` FK column
3. **Service 层 import `CategorizationFeedbackModel` 时 PYTHONPATH 问题** → import 写作 `from db.models.ticket_categorization import CategorizationFeedbackModel`，**不是** `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: Append `CategorizationFeedbackModel` to `src/db/models/ticket_categorization.py`

Issue #604 creates this file with `TicketCategorizationModel`. Open the file and append the new model class. The `CategorizationFeedbackModel` stores one row per human override: original vs corrected category/priority, corrector user_id, timestamp.

操作：
- a) 确认 `src/db/models/ticket_categorization.py` 已存在（含 `TicketCategorizationModel`，来自 #604）
- b) 在文件末尾追加 `CategorizationFeedbackModel`

示例代码：

```python
# src/db/models/ticket_categorization.py — append CategorizationFeedbackModel

from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CategorizationFeedbackModel(Base):
    """Audit log of human corrections to LLM-assigned ticket categorizations."""

    __tablename__ = "categorization_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Original LLM-assigned values
    original_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Human-corrected values
    corrected_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    corrected_priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Corrector metadata
    corrected_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "original_category": self.original_category,
            "original_priority": self.original_priority,
            "corrected_category": self.corrected_category,
            "corrected_priority": self.corrected_priority,
            "corrected_by": self.corrected_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/ticket_categorization.py` → 0 errors

### Step 2: Generate Alembic migration for `categorization_feedback` table

操作：
- a) 确保 `docker compose -f configs/docker-compose.test.yml up -d test-db` 运行中
- b) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;" && docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- c) `alembic upgrade head`
- d) `alembic revision --autogenerate -m "add categorization feedback table"`
- e) 打开生成的 `alembic/versions/<id>_add_categorization_feedback_table.py`，检查：
  - `op.create_index(op.f('ix_categorization_feedback_tenant_id'), ...)` 存在
  - 所有 timestamp 列用 `DateTime(timezone=True)`，有 `server_default=sa.text('now()')`
  - FK `ticket_id` 指向 `tickets.id`
- f) 验证：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- g) 若第二次 autogenerate 产生空 migration，删除它

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: Add `submit_categorization_feedback()` to `src/services/ticket_service.py`

在 `TicketService` 类中新增方法：查找 ticket 的 `TicketCategorizationModel`（若不存在抛 `NotFoundException`），将 `overridden` 设为 `True`，写入 `CategorizationFeedbackModel` 行，返回 feedback 对象。

操作：
- a) 在 `ticket_service.py` 顶部追加 import：
  ```python
  from db.models.ticket_categorization import CategorizationFeedbackModel, TicketCategorizationModel
  ```
- b) 在 `TicketService` 类末尾追加方法：

```python
async def submit_categorization_feedback(
    self,
    ticket_id: int,
    tenant_id: int,
    user_id: int,
    corrected_category: str | None = None,
    corrected_priority: str | None = None,
) -> CategorizationFeedbackModel:
    """Record a human override for an LLM-assigned ticket categorization.

    Sets TicketCategorizationModel.overridden = True and appends a
    CategorizationFeedbackModel audit row.
    Raises NotFoundException if the ticket has no categorization record.
    """
    # Fetch existing categorization record
    cat_result = await self.session.execute(
        select(TicketCategorizationModel).where(
            and_(
                TicketCategorizationModel.ticket_id == ticket_id,
                TicketCategorizationModel.tenant_id == tenant_id,
            )
        )
    )
    categorization = cat_result.scalar_one_or_none()
    if categorization is None:
        raise NotFoundException("TicketCategorization")

    # Record override on the categorization row
    categorization.overridden = True

    # Write audit row
    feedback = CategorizationFeedbackModel(
        ticket_id=ticket_id,
        tenant_id=tenant_id,
        original_category=categorization.category,
        original_priority=categorization.priority,
        corrected_category=corrected_category,
        corrected_priority=corrected_priority,
        corrected_by=user_id,
    )
    self.session.add(feedback)
    await self.session.commit()
    await self.session.refresh(feedback)
    return feedback
```

**完成判定**：`ruff check src/services/ticket_service.py` → 0 errors

### Step 4: Add `PATCH /tickets/{ticket_id}/categorization/feedback` endpoint to `src/api/routers/tickets.py`

操作：
- a) 在 `tickets.py` 顶部追加 import：
  ```python
  from services.ticket_service import TicketService
  ```
- b) 在文件末尾（`get_sla_summary` endpoint 之后）追加：

```python
@tickets_router.patch("/{ticket_id}/categorization/feedback")
async def patch_categorization_feedback(
    ticket_id: int,
    feedback_in: CategorizationFeedbackPayload,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Record a human correction to the LLM-assigned category and/or priority.

    At least one of category or priority must be provided.
    Sets TicketCategorizationModel.overridden = True and persists an audit row.
    """
    if feedback_in.category is None and feedback_in.priority is None:
        raise ValidationException("At least one of category or priority must be provided")

    svc = TicketService(session)
    feedback = await svc.submit_categorization_feedback(
        ticket_id=ticket_id,
        tenant_id=ctx.tenant_id or 0,
        user_id=ctx.user_id or 0,
        corrected_category=feedback_in.category,
        corrected_priority=feedback_in.priority,
    )
    return {"success": True, "data": feedback.to_dict()}
```

同时在文件顶部 Pydantic model 区添加请求体 schema：

```python
class CategorizationFeedbackPayload(BaseModel):
    category: str | None = None
    priority: str | None = None
```

**完成判定**：`ruff check src/api/routers/tickets.py` → 0 errors

### Step 5: Create unit tests `tests/unit/test_ticket_categorization.py`

测试 `submit_categorization_feedback()` service 方法和 router 端点。3 个用例：

1. **Happy path**：mock session 返回存在的 `TicketCategorizationModel`，验证 `overridden` 被设为 `True`，`CategorizationFeedbackModel` row 被 added 并 committed，returned object has correct fields
2. **Boundary — ticket has no categorization**：mock session 返回 `scalar_one_or_none() = None`，验证 `NotFoundException("TicketCategorization")` 被 raise
3. **Error — neither category nor priority provided**：router 端点验证 `ValidationException` when both fields are None

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ticket_service import TicketService
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class MockFeedbackRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class TestSubmitCategorizationFeedback:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return TicketService(mock_session)

    async def test_feedback_persisted_and_overridden_flag_set(self, service, mock_session):
        """Happy path: feedback row added, overridden=True on categorization."""
        existing_cat = MagicMock()
        existing_cat.category = "billing"
        existing_cat.priority = "low"
        existing_cat.overridden = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_cat)
        mock_session.execute.return_value = mock_result

        def fake_refresh(obj):
            obj.id = 1
            obj.ticket_id = 5
            obj.tenant_id = 1
            obj.original_category = "billing"
            obj.original_priority = "low"
            obj.corrected_category = "technical"
            obj.corrected_priority = None
            obj.corrected_by = 42
            obj.created_at = None

        mock_session.refresh.side_effect = fake_refresh

        result = await service.submit_categorization_feedback(
            ticket_id=5,
            tenant_id=1,
            user_id=42,
            corrected_category="technical",
            corrected_priority=None,
        )
        assert existing_cat.overridden is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        assert result.corrected_category == "technical"

    async def test_raises_not_found_when_no_categorization_record(self, service, mock_session):
        """Boundary: ticket has no TicketCategorizationModel → NotFoundException."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        with pytest.raises(NotFoundException) as exc_info:
            await service.submit_categorization_feedback(
                ticket_id=999, tenant_id=1, user_id=1,
                corrected_category="billing", corrected_priority=None,
            )
        assert "TicketCategorization" in str(exc_info.value)

    async def test_router_validates_at_least_one_field_provided(self):
        """Error: PATCH with neither category nor priority → ValidationException."""
        from src.api.routers.tickets import CategorizationFeedbackPayload
        payload = CategorizationFeedbackPayload()
        # Validate locally: at least one must be set
        assert payload.category is None and payload.priority is None
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ticket_categorization.py -v` → ≥ 3 passed

### Step 6: Add router integration test to `tests/unit/test_tickets_router.py`

在 `test_tickets_router.py` 中新增 `test_patch_categorization_feedback` 测试：

```python
async def test_patch_categorization_feedback_success(client, auth_headers):
    """PATCH returns 200 and the created feedback record."""
    mock_feedback = {
        "id": 1, "ticket_id": 5, "tenant_id": 1,
        "original_category": "billing", "original_priority": "low",
        "corrected_category": "technical", "corrected_priority": None,
        "corrected_by": 42, "created_at": "2026-05-29T00:00:00Z",
    }
    with patch(
        "services.ticket_service.TicketService.submit_categorization_feedback",
        new_callable=AsyncMock,
    ) as mock_submit:
        mock_submit.return_value = MagicMock(**mock_feedback)
        mock_submit.return_value.to_dict = lambda: mock_feedback
        response = client.patch(
            "/api/v1/tickets/5/categorization/feedback",
            json={"category": "technical"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["corrected_category"] == "technical"
    assert data["data"]["original_category"] == "billing"

async def test_patch_categorization_feedback_not_found(client, auth_headers):
    """PATCH for ticket with no categorization → 404."""
    with patch(
        "services.ticket_service.TicketService.submit_categorization_feedback",
        new_callable=AsyncMock,
        side_effect=NotFoundException("TicketCategorization"),
    ):
        response = client.patch(
            "/api/v1/tickets/999/categorization/feedback",
            json={"category": "billing"},
            headers=auth_headers,
        )
    assert response.status_code == 404
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_patch_categorization_feedback_success tests/unit/test_tickets_router.py::test_patch_categorization_feedback_not_found -v` → 2 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/ticket_categorization.py src/services/ticket_service.py src/api/routers/tickets.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ticket_categorization.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_patch_categorization_feedback_success tests/unit/test_tickets_router.py::test_patch_categorization_feedback_not_found -v` → 2 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：`curl -X PATCH http://localhost:8000/api/v1/tickets/1/categorization/feedback -H "Authorization: Bearer ..." -H "Content-Type: application/json" -d '{"category": "technical"}'` → `{"success": true, "data": {...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #604 未完成导致 `src/db/models/ticket_categorization.py` 不存在，import 失败 | 中 | 高 | 先完成 #604；本板块依赖 #604 的文件，阻塞时暂停并标记本板块为 blocked |
| Alembic autogenerate 生成错误的列类型（JSONB→JSON, TIMESTAMPTZ→DateTime） | 高 | 中 | 手动修正 migration 中所有 timestamp 列；参考 `alembic/versions/3ea69d66514e_sync_models_with_db.py` 中 `server_default=sa.text('now()')` 模式 |
| feedback 端点被未认证用户调用（auth bypass） | 低 | 高 | Router 使用 `require_auth` dependency 注入 `AuthContext`；所有端点均需有效 Bearer token |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/ticket_categorization.py alembic/versions/<id>_add_categorization_feedback_table.py \
       src/services/ticket_service.py src/api/routers/tickets.py \
       tests/unit/test_ticket_categorization.py tests/unit/test_tickets_router.py
git commit -m "feat(tickets): add CategorizationFeedback model and PATCH feedback endpoint"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(tickets): add CategorizationFeedback model and PATCH /tickets/{id}/categorization/feedback" --body "Closes #605

## Summary
- Add CategorizationFeedbackModel ORM (original vs corrected category/priority, corrector user_id, timestamp)
- TicketService.submit_categorization_feedback() sets TicketCategorizationModel.overridden=True and writes audit row
- PATCH /api/v1/tickets/{ticket_id}/categorization/feedback endpoint
- Unit tests: happy path, NotFoundException boundary, ValidationException error

## Test plan
- [ ] ruff check src/db/models/ticket_categorization.py src/services/ticket_service.py src/api/routers/tickets.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_ticket_categorization.py -v → ≥ 3 passed
- [ ] PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_patch_categorization_feedback_* -v → 2 passed
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → three exit 0"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ticket_reply.py`](../../src/db/models/ticket_reply.py) — append-only audit-style ORM model pattern
- 同类参考实现：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) — `submit_categorization_feedback` 参考同文件的 `add_reply` / `change_status` 等写操作模式
- 同类参考实现：[`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) — `PATCH /{ticket_id}/status` endpoint pattern for partial-update semantics
- Migration 参考：[`alembic/versions/3ea69d66514e_sync_models_with_db.py`](../../alembic/versions/3ea69d66514e_sync_models_with_db.py) — `DateTime(timezone=True)` + `server_default=sa.text('now()')` pattern
- 父 issue / 关联：#45
- 依赖 issue / 关联：#604（工单分类数据模型，为本板块提供 `TicketCategorizationModel`）
- 下游 issue / 关联：#606（准确率指标，依赖 `TicketCategorizationModel.overridden` 字段）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
