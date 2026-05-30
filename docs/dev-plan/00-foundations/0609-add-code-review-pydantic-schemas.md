# Code Review Pydantic Schemas · Add Pydantic schemas for review endpoint

---

## 1. 目标与背景

### 1.1 为什么做

Issue #609 requires adding typed Pydantic request/response schemas for a code review endpoint. Without these schemas, the endpoint lacks runtime input validation, Swagger documentation is absent or incorrect, and callers have no type-safe DTOs to work against. The project already has a clear Pydantic schema convention in `src/pkg/response/schemas.py` and `src/models/ai.py` — this board formalises that same pattern for the review domain.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 定义，仅影响 API 类型安全性与 OpenAPI 文档质量。
- **开发者视角**：`CodeReviewRequest`、`CodeReviewIssue`、`CodeReviewResponse` 三个 schema 即可导入使用；路由层和测试层均可引用这些类型，消除裸 `dict` 和无校验的 JSON 解析。

### 1.3 不做什么（剔除）

- [ ] 路由 handler 实现（属于下游板块，由 #608 路由端点完成后引用 schema）
- [ ] ORM model 或数据库迁移（schema 为纯内存/序列化层，无持久化需求）
- [ ] AI/LLM 调用逻辑或规则执行引擎

### 1.4 关键 KPI

- [指标 1：`ruff check src/models/code_review.py` → 0 errors]
- [指标 2：`PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → ≥ 5 passed]
- [指标 3：`python -c "from src.models.code_review import CodeReviewRequest, CodeReviewIssue, CodeReviewResponse; print('import ok')"` → exit 0]

---

## 2. 当前现状（起点）

### 2.1 现有实现

同类参考实现（schema 模式）：[`src/models/ai.py`](../../../src/models/ai.py) L{1}-L{20}

```python
"""Pydantic request / response schemas for the AI Chat Assistant API."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for ``POST /api/v1/ai/chat``."""

    message: str = Field(..., min_length=1, max_length=4000)
    context: dict[str, Any] | None = Field(default=None)
    conversation_id: int | None = Field(default=None)
```

同类参考实现（response envelope）：[`src/pkg/response/schemas.py`](../../../src/pkg/response/schemas.py) L{1}-L{30}

```python
from pydantic import BaseModel, Field


class SuccessEnvelope(BaseModel):
    """Shared envelope fields — all API responses inherit these."""

    success: bool = True
    message: str = "OK"


class ErrorEnvelope(BaseModel):
    """SuccessEnvelope / ErrorEnvelope base + APIResponse[T] generic envelope."""
```

### 2.2 涉及文件清单

- 要改：无
- 要建：
  - `src/models/code_review.py` — Pydantic schema 定义（request / issue / response）
  - `tests/unit/test_code_review.py` — schema 单元测试

### 2.3 缺什么

- [ ] 缺失 `CodeReviewRequest` Pydantic schema（无 request DTO → 路由层无法做类型安全参数校验）
- [ ] 缺失 `CodeReviewIssue` Pydantic schema（issue 列表项无类型）
- [ ] 缺失 `CodeReviewResponse` Pydantic schema（响应结构不完整，Swagger 无文档）
- [ ] 无单元测试覆盖 schema 验证逻辑（无测试 → 重构时无法回归保护）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/code_review.py` | Pydantic schema：`CodeReviewRequest`、`CodeReviewIssue`、`CodeReviewResponse` |
| `tests/unit/test_code_review.py` | schema 单元测试（字段验证、序列化、边界值） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | — |

### 3.3 新增能力

- **Pydantic schema**：`CodeReviewRequest(code: str, language: str, review_type: str)` — 请求体验证
- **Pydantic schema**：`CodeReviewIssue(type: str, severity: str, line: int, message: str, suggestion: str | None)` — 单条 issue 表示
- **Pydantic schema**：`CodeReviewResponse(issues: list[CodeReviewIssue], score: int, summary: str)` — 响应体

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 Pydantic `BaseModel` 而非 `@dataclass`**：项目 API 层已统一使用 Pydantic（见 `src/models/ai.py`、`src/pkg/response/schemas.py`），与现有约定保持一致，同时获得自动 Swagger/OpenAPI schema 生成。
- **不包装 `SuccessEnvelope`**：与 `ai.py` 中的 `ChatResponse` 模式一致（直接继承 `BaseModel`），避免过深的继承链。若后续路由需要统一 envelope，再包装为 `APIResponse[CodeReviewResponse]`。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pydantic` | 已有约束（见 `pyproject.toml`） | 项目已引入，不引入新依赖 |

### 4.3 兼容性约束

- 多租户：schema 字段中不含 `tenant_id`（request 由调用方/路由层在上下文中注入，schema 本身无需承载）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- Import 路径：`from src.models.code_review import ...`（PYTHONPATH=src 时）

### 4.4 已知坑

1. **Pydantic v2 `model_dump()` vs `dict()`** → 规避：使用 `model_dump()` 替代已废弃的 `.dict()`，与 `src/models/ai.py` 保持一致
2. **字段名 `metadata` 与 SQLAlchemy Base.metadata 冲突** → 规避：schema 不涉及 ORM 层，此问题不适用；如后续扩展到 ORM，请避免 `metadata` 列名

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/models/code_review.py`

创建新文件，定义三个 Pydantic schema 类。

操作：

在 `src/models/` 下新建 `code_review.py`，内容如下：

```python
"""Pydantic request / response schemas for the code review endpoint."""

from enum import StrEnum

from pydantic import BaseModel, Field


class IssueType(StrEnum):
    """Categorisation of a code review issue."""

    BUG = "bug"
    VULNERABILITY = "vulnerability"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class IssueSeverity(StrEnum):
    """Severity level of a code review issue."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewType(StrEnum):
    """Type of code review to perform."""

    SECURITY = "security"
    STYLE = "style"
    CORRECTNESS = "correctness"
    FULL = "full"


class CodeReviewRequest(BaseModel):
    """Request body for ``POST /review``."""

    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = Field(..., min_length=1, max_length=64)
    review_type: ReviewType = Field(..., description="Type of review to perform")

    model_config = {"str_strip_whitespace": True}


class CodeReviewIssue(BaseModel):
    """A single issue found during code review."""

    type: IssueType = Field(..., description="Category of the issue")
    severity: IssueSeverity = Field(..., description="How severe the issue is")
    line: int = Field(..., ge=1, description="1-based line number in the submitted code")
    message: str = Field(..., min_length=1, max_length=1000)
    suggestion: str | None = Field(None, max_length=500)

    model_config = {"str_strip_whitespace": True}


class CodeReviewResponse(BaseModel):
    """Response body for ``POST /review``."""

    issues: list[CodeReviewIssue] = Field(default_factory=list)
    score: int = Field(..., ge=0, le=100, description="Overall code quality score 0-100")
    summary: str = Field(..., min_length=1, max_length=2000)

    model_config = {"str_strip_whitespace": True}

    def to_dict(self) -> dict:
        return self.model_dump()
```

**完成判定**：`ruff check src/models/code_review.py` → 0 errors

---

### Step 2: 创建 `tests/unit/test_code_review.py`

操作：

创建 `tests/unit/test_code_review.py`，包含 happy path、boundary、error 三类测试：

```python
"""Unit tests for src/models/code_review.py."""

import pytest
from pydantic import ValidationError

from src.models.code_review import (
    CodeReviewRequest,
    CodeReviewIssue,
    CodeReviewResponse,
    IssueType,
    IssueSeverity,
    ReviewType,
)


class TestCodeReviewRequest:
    def test_valid_request(self):
        req = CodeReviewRequest(
            code="def foo():\n    pass",
            language="python",
            review_type=ReviewType.FULL,
        )
        assert req.language == "python"
        assert req.review_type == ReviewType.FULL

    def test_all_review_types(self):
        for rt in ReviewType:
            req = CodeReviewRequest(code="x = 1", language="py", review_type=rt)
            assert req.review_type == rt

    def test_code_required_raises(self):
        with pytest.raises(ValidationError):
            CodeReviewRequest(code="", language="py", review_type=ReviewType.SECURITY)

    def test_language_required_raises(self):
        with pytest.raises(ValidationError):
            CodeReviewRequest(code="x = 1", language="", review_type=ReviewType.STYLE)

    def test_code_strips_whitespace(self):
        req = CodeReviewRequest(code="  x = 1  ", language="py", review_type=ReviewType.FULL)
        assert req.code == "x = 1"


class TestCodeReviewIssue:
    def test_valid_issue(self):
        issue = CodeReviewIssue(
            type=IssueType.BUG,
            severity=IssueSeverity.HIGH,
            line=10,
            message="Undefined variable",
            suggestion="Did you mean 'x'?",
        )
        assert issue.line == 10
        assert issue.suggestion == "Did you mean 'x'?"

    def test_issue_optional_suggestion(self):
        issue = CodeReviewIssue(type=IssueType.STYLE, severity=IssueSeverity.LOW, line=1, message="Msg")
        assert issue.suggestion is None

    def test_line_must_be_positive(self):
        with pytest.raises(ValidationError):
            CodeReviewIssue(type=IssueType.BUG, severity=IssueSeverity.HIGH, line=0, message="x")

    def test_all_issue_types(self):
        for it in IssueType:
            issue = CodeReviewIssue(type=it, severity=IssueSeverity.INFO, line=1, message="msg")
            assert issue.type == it

    def test_all_severities(self):
        for sev in IssueSeverity:
            issue = CodeReviewIssue(type=IssueType.OTHER, severity=sev, line=1, message="msg")
            assert issue.severity == sev


class TestCodeReviewResponse:
    def test_valid_response(self):
        issue = CodeReviewIssue(
            type=IssueType.BUG, severity=IssueSeverity.CRITICAL, line=5, message="Null deref"
        )
        resp = CodeReviewResponse(issues=[issue], score=72, summary="Found 1 critical issue")
        assert len(resp.issues) == 1
        assert resp.score == 72

    def test_empty_issues(self):
        resp = CodeReviewResponse(issues=[], score=100, summary="Clean code")
        assert resp.issues == []

    def test_score_clamped_to_100(self):
        with pytest.raises(ValidationError):
            CodeReviewResponse(issues=[], score=101, summary="x")

    def test_score_clamped_to_0(self):
        with pytest.raises(ValidationError):
            CodeReviewResponse(issues=[], score=-1, summary="x")

    def test_to_dict(self):
        resp = CodeReviewResponse(issues=[], score=85, summary="OK")
        d = resp.to_dict()
        assert isinstance(d, dict)
        assert d["score"] == 85
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → 15 passed

---

## 6. 验收

- [ ] `ruff check src/models/code_review.py` → 0 errors
- [ ] `ruff check tests/unit/test_code_review.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_code_review.py -v` → 15 passed
- [ ] `python -c "from src.models.code_review import CodeReviewRequest, CodeReviewIssue, CodeReviewResponse, IssueType, IssueSeverity, ReviewType; print('all schemas import ok')"` → exit 0
- [ ] `python -c "from src.models.code_review import CodeReviewResponse; r = CodeReviewResponse(issues=[], score=100, summary='clean'); print(r.model_dump())"` → `{'issues': [], 'score': 100, 'summary': 'clean'}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Schema 字段设计与下游路由需求不匹配（字段名/类型遗漏） | 低 | 中 | 已在 §2.3 列出缺什么，按 issue #609 需求字段清单实现；若后续发现遗漏，新增字段无需破坏性变更 |
| Pydantic 版本不一致导致 `model_dump()` API 差异 | 低 | 低 | 项目已有 `pyproject.toml` 依赖约束；本板块仅使用标准 v2 API |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/code_review.py tests/unit/test_code_review.py
git commit -m "feat(schemas): add Pydantic schemas for code review endpoint (closes #609)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(schemas): add code review Pydantic schemas (#609)" --body "Closes #609

## Summary
- Add CodeReviewRequest / CodeReviewIssue / CodeReviewResponse Pydantic schemas
- Add unit tests with happy-path, boundary, and error cases
- Follow existing schema conventions (src/models/ai.py, src/pkg/response/schemas.py)

## Test plan
- [x] ruff check src/models/code_review.py → 0 errors
- [x] pytest tests/unit/test_code_review.py -v → 15 passed
"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/models/ai.py`](../../../src/models/ai.py) — `ChatRequest` / `ChatResponse` Pydantic 模式
- 同类参考实现：[`src/pkg/response/schemas.py`](../../../src/pkg/response/schemas.py) — `SuccessEnvelope` / `APIResponse[T]` 模式
- 同类参考实现：[`src/models/routing.py`](../../../src/models/routing.py) — `StrEnum` + `Field` 验证模式
- 单元测试参考：[`tests/unit/test_schemas.py`](../../../tests/unit/test_schemas.py) — schema 验证测试模式
- 父 issue / 关联：#44
- 依赖 issue：#608

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

---

All 6 links now use `../../../` (up 3 levels from `docs/dev-plan/00-foundations/` → repo root) and all target files are confirmed to exist at those paths.
