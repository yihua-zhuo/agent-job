# CodeReviewService 板块 · AI-powered code review service

| 元数据 | 值 |
|---|---|
| Issue | #610 |
| 分类 | [99-misc](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0627](0627-add-llmservice-with-multi-provider-support.md)（需要 LLMService 作为 AI provider 底座）；AI agent framework (#41) |
| 启用后赋能 | 代码审查 Router endpoints（future issue） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

目前 CRM 没有代码审查能力。用户（或开发者）需要将对一段代码进行 AI 驱动的审查（按语言 +审查类型构造 prompt，调用 LLM，返回 issue列表 / 评分 / 摘要），并将审查结果持久化到数据库。没有 `CodeReviewService`，这一能力完全缺失。

### 1.2 做完后

- **用户视角**：无直接可见变化 —纯后端 service 层，通过 API 调用触发代码审查。
- **开发者视角**：`CodeReviewService` 提供 `create_review()`（调用 LLM，解析结构化结果，写 DB）和 `list_history()`（分页查询租户审查记录）两个公开方法；依赖现有的 `AIChatGateway` 或 `LLMService` 进行 LLM 调用。

### 1.3 不做什么（剔除）

- [ ] FastAPI router 暴露（router属于 future issue，本板块仅实现 service）。
- [ ] 代码审查结果的 Web UI / 前端展示。
- [ ]持久化 LLM 调用产生的 raw prompt / response（仅保存结构化 parsed 结果）。
- [ ] 多文件批量审查（单次 `create_review` 只处理一段代码）。

### 1.4 关键 KPI

- `ruff check src/services/code_review_service.py src/db/models/code_review.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_code_review_service.py -v` → ≥ 5 passed- `PYTHONPATH=src mypy src/services/code_review_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。`src/db/models/` 下不存在 `code_review.py`；`src/services/` 下不存在 `code_review_service.py`。

### 2.2 涉及文件清单

- 要改：无- 要建：
  - `src/db/models/code_review.py` — `CodeReviewModel` ORM 模型，存储审查记录  - `src/services/code_review_service.py` — `CodeReviewService` 类，含 `create_review` 和 `list_history`
  - `tests/unit/test_code_review_service.py` — 单元测试，mock LLM 调用，验证 prompt构造和 DB 保存
 - `alembic/versions/<id>_add_code_reviews_table.py` — 创建 `code_reviews` 表（含 `tenant_id` 索引）

### 2.3 缺什么

- [ ] `CodeReviewModel` ORM 模型 — 无 DB 表存储审查记录- [ ] `CodeReviewService` 业务逻辑 — 无 service 方法提供 `create_review` / `list_history`
- [ ] LLM 调用与响应解析 — prompt构造逻辑和 LLM JSON 结构化输出解析
- [ ] 多租户 DB持久化 — 审查记录必须按 `tenant_id` 隔离

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/code_review.py` | `CodeReviewModel` ORM，含 code/language/review_type/tenant_id/result_json 字段 |
| `src/services/code_review_service.py` | `CodeReviewService`，`create_review` 和 `list_history` |
| `tests/unit/test_code_review_service.py` | 单元测试，mock LLM gateway，验证 prompt构造和 DB 保存 |
| `alembic/versions/<id>_add_code_reviews_table.py` | 创建 `code_reviews` 表，含 `tenant_id`索引 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | import 新增的 `CodeReviewModel` 以便 autogen |

### 3.3 新增能力

- **ORM model**：`CodeReviewModel` in `src/db/models/code_review.py`
- **Service method**：`CodeReviewService.create_review(code, language, review_type, tenant_id) -> CodeReviewModel`
- **Service method**：`CodeReviewService.list_history(tenant_id, page, page_size) -> tuple[list[CodeReviewModel], int]`
- **Migration**：`alembic upgrade head` 创建 `code_reviews` 表（含 `tenant_id`索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 JSON 结构化解析，不选 embed-chain / tool-use**：大多数 LLM 接入（stub / MiniMax / OpenAI）均支持 JSON 输出，使用 `re` 或 `json.loads()` 从 LLM reply 文本中提取结构化字段最通用；不引入 LangChain 等额外依赖。
- **选 `AIChatGateway`（issue #41），不重造 LLM 调用层**：`AIChatGateway` 是现有 AI agent框架的核心组件，`CodeReviewService`复用其一致的 chat 接口；若 #41 尚未完成则依赖 `LLMService`（#627）。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/model 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- Session注入：`__init__(self, session: AsyncSession)` — 不接受默认值为 `None`

### 4.4 已知坑

1. **LLM 返回非 JSON 格式文本** → 规避：`create_review` 对 `json.loads()` 做 try/except，解析失败时抛 `ValidationException("LLM response could not be parsed")`，不静默丢弃或写脏数据。
2. **LLM 返回字段缺失或类型错误（如 score 为字符串）** → 规避：解析后用 `.get()` + `isinstance()` 做防御式读取，提供默认值（如 `score = float(parsed.get("score", 0))`），避免因 LLM 幻觉字段导致 500。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 CodeReviewModel ORM 模型

在 `src/db/models/code_review.py` 新建文件。字段设计：id（auto-increment pk）、tenant_id（int，index）、code（text）、language（varchar(50)）、review_type（varchar(50)）、score（float）、issues（jsonb）、summary（text）、created_at（datetime）。

```python
"""CodeReview ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CodeReviewModel(Base):
    """Code review record, mapped to the ``code_reviews`` table."""

    __tablename__ = "code_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    issues: Mapped[dict] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_code_reviews_tenant_id", "tenant_id"),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code": self.code,
            "language": self.language,
            "review_type": self.review_type,
            "score": self.score,
            "issues": self.issues,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`ruff check src/db/models/code_review.py` → 0 errors

---

### Step 2: 生成 Alembic migration

启动 `test-db`（docker compose），在专用 `alembic_dev` 数据库上运行：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "add code_reviews table"
#人工审查 alembic/versions/<新id>_add_code_reviews_table.py，确认：
#   - JSONB 而非 JSON（手动改回）
#   - tenant_id 索引存在
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

确认 migration 文件存在且 `alembic upgrade head` exit 0。

**完成判定**：`alembic upgrade head` exit 0；`alembic downgrade -1` exit 0

---

### Step 3: 实现 CodeReviewService — prompt构造和 LLM 调用

在 `src/services/code_review_service.py` 新建文件。`__init__` 接收 `session: AsyncSession` 和可选 `gateway: AIChatGateway`；`create_review` 方法：

1. 根据 `code + language + review_type` 构造 system prompt（可按 review_type 分支，如 `security` / `style` / `performance`）。
2. 调用 `gateway.chat([{"role": "user", "content": prompt}])`（注：若 #627 `LLMService` 已完成则使用之，否则跌回 `AIChatGateway`）。
3. 对 LLM reply 做 JSON 解析得 `score`（float）、`issues`（list）、`summary`（str）。
4. 构造 `CodeReviewModel` 实例，`session.add` + `await session.flush()`。
5. `await session.refresh(review)` 返回 ORM 对象。

```python
"""Code review service — AI-powered code review via LLM."""

import json
import re
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.code_review import CodeReviewModel
from internal.ai_gateway import AIChatGateway, AIResponse
from pkg.errors.app_exceptions import ValidationException


REVIEW_TYPE_PROMPTS = {
    "security": (
        "You are a security expert. Review the following {language} code and "
        "return JSON: {{\"score\": float 0-100, \"issues\": [{{\"severity\": \"high\"|\"medium\"|\"low\", "
        "\"line\": int, \"description\": str, \"suggestion\": str}}], \"summary\": str}}"
    ),
    "style": (
        "You are a code style expert. Review the following {language} code and "
        "return JSON: {{\"score\": float0-100, \"issues\": [{{\"severity\": \"info\"|\"warning\", "
        "\"line\": int, \"description\": str, \"suggestion\": str}}], \"summary\": str}}"
    ),
    "performance": (
        "You are a performance expert. Review the following {language} code and "
        "return JSON: {{\"score\": float 0-100, \"issues\": [{{\"severity\": \"critical\"|\"info\", "
        "\"line\": int, \"description\": str, \"suggestion\": str}}], \"summary\": str}}"
    ),
}


class CodeReviewService:
    """Code review service backed by AI gateway."""

    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        self.session = session
        self.gateway = gateway or AIChatGateway()

    def _build_prompt(self, code: str, language: str, review_type: str) -> str:
        template = REVIEW_TYPE_PROMPTS.get(review_type, REVIEW_TYPE_PROMPTS["security"])
        return f"{template.format(language=language)}\n\nCode:\n```{language}\n{code}\n```"

    def _parse_llm_response(self, reply: str) -> dict:
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if not match:
            raise ValidationException("LLM response could not be parsed as JSON")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ValidationException("LLM response could not be parsed as JSON") from exc

    async def create_review(
        self,
        code: str,
        language: str,
        review_type: str,
        tenant_id: int,
    ) -> CodeReviewModel:
        prompt = self._build_prompt(code, language, review_type)
        response: AIResponse = await self.gateway.chat([{"role": "user", "content": prompt}])
        parsed = self._parse_llm_response(response.reply)

        now = datetime.now(UTC)
        review = CodeReviewModel(
            tenant_id=tenant_id,
            code=code,
            language=language,
            review_type=review_type,
            score=float(parsed.get("score", 0)),
            issues=parsed.get("issues", []),
            summary=parsed.get("summary", ""),
            created_at=now,
        )
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def list_history(
        self, tenant_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[CodeReviewModel], int]:
        conditions = [CodeReviewModel.tenant_id == tenant_id]
        count_result = await self.session.execute(
            select(func.count(CodeReviewModel.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(CodeReviewModel)
            .where(and_(*conditions))
            .order_by(CodeReviewModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total)
```

**完成判定**：`ruff check src/services/code_review_service.py` → 0 errors

---

### Step 4:编写单元测试

在 `tests/unit/test_code_review_service.py` 新建文件。`mock_db_session` fixture 仅 mock `add`/`flush`/`refresh`/`execute`（实际不需要 handler，因为 `CodeReviewModel` 是新表，测试用 `MagicMock`模拟 session）。测试用例：

1. `test_create_review_calls_llm_with_correct_prompt`：mock `gateway.chat`，调用 `create_review`，断言 `gateway.chat` 被调用 1 次、prompt 含 language、review_type、code。
2. `test_create_review_saves_result_to_db`：mock `session.add/flush/refresh`，断言 `CodeReviewModel` 被 `session.add`。
3. `test_create_review_parsing_failure_raises`：mock `gateway.chat` 返回非 JSON reply，断言抛 `ValidationException`。
4. `test_list_history_returns_paginated_results`：mock `session.execute` 返回 fixture 数据，断言返回列表长度 = page_size。

```python
"""Unit tests for src/services/code_review_service.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMockimport pytest

from internal.ai_gateway import AIResponse
from pkg.errors.app_exceptions import ValidationException
from services.code_review_service import CodeReviewService


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    gateway.chat = AsyncMock(
        return_value=AIResponse(
            reply='{"score": 85.0, "issues": [{"severity": "high", "line": 3, '
            '"description": "SQL injection risk", "suggestion": "Use parameterized query"}], '
            '"summary": "Good overall structure"}',
        )
    )
    return gateway


@pytest.fixture
def service(mock_session, mock_gateway):
    return CodeReviewService(mock_session, mock_gateway)


class TestCreateReview:
    async def test_calls_llm_with_prompt(self, service, mock_gateway):
        result = await service.create_review(
            code='x = input()',
            language="Python",
            review_type="security",
            tenant_id=1,
        )
        mock_gateway.chat.assert_called_once()
        call_arg = mock_gateway.chat.call_args[0][0]
        assert call_arg[0]["role"] == "user"
        assert "Python" in call_arg[0]["content"]
        assert "security" in call_arg[0]["content"]
        assert 'x = input()' in call_arg[0]["content"]

    async def test_saves_result_to_db(self, service, mock_session):
        review = MagicMock()
        mock_session.refresh = AsyncMock(side_effect=lambda r: setattr(r, "id", 1))
        await service.create_review("code", "Python", "security", tenant_id=1)
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.tenant_id == 1
        assert added.language == "Python"

    async def test_parse_failure_raises(self, mock_session, mock_gateway):
        mock_gateway.chat = AsyncMock(return_value=AIResponse(reply="not json at all"))
        svc = CodeReviewService(mock_session, mock_gateway)
        with pytest.raises(ValidationException):
            await svc.create_review("code", "Python", "security", tenant_id=1)


class TestListHistory:
    async def test_returns_paginated_results(self, service, mock_session):
        mock_row = MagicMock()
        mock_row.scalars.return_value.all.return_value = [MagicMock(id=1), MagicMock(id=2)]
        mock_count = MagicMock()
        mock_count.scalar.return_value = 5
        mock_session.execute = AsyncMock(side_effect=[mock_count, mock_row])
        items, total = await service.list_history(tenant_id=1, page=1, page_size=2)
        assert total == 5
        assert len(items) == 2
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_code_review_service.py -v` → `≥ 4 passed`

---

## 6. 验收

- [ ] `ruff check src/services/code_review_service.py src/db/models/code_review.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_code_review_service.py -v` → ≥ 4 passed
- [ ] `PYTHONPATH=src mypy src/services/code_review_service.py src/db/models/code_review.py` → 0 errors
- [ ] `alembic upgrade head` → exit 0（如已经完成 Step 2 则通过；首次运行时执行）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| LLM 响应格式不稳定，导致解析失败率 > 10% | 中 | 高 | `ValidationException` 暴露给 router 层，API 返回 422；用户可重试 |
| `AIChatGateway` 接口在 #41 完成前与本板块预期不符 | 中 | 中 | 降级为 `LLMService`（#627，跌回 JSON parse逻辑不变） |
| `CodeReviewModel` migration 与已有模型列名冲突 | 低 | 高 | 删除 migration，用 `create_all` 在 dev 环境验证后重建 |

---

## 8. 完成后必做

```bash
git add src/db/models/code_review.py src/services/code_review_service.py tests/unit/test_code_review_service.py alembic/versions/*.py
git commit -m "feat(code-review): add CodeReviewService with AI prompt logicCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#610): implement CodeReviewService with AI prompt logic" --body "Closes #610"
```

---

## 9. 参考

- 同类参考实现：[`src/services/ai_service.py`](../../src/services/ai_service.py) — AI service复用 `AIChatGateway` 的模式- 第三方文档：[AIChatGateway stub](https://github.com/anthropics/claude-code/blob/main/README.md) — 仅作 LLM 调用接口参考
- 父 issue /关联：#44（父 issue）；#609（依赖的 Model 建表）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
