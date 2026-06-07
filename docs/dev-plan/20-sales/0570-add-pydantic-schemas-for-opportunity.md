# 销售 · 添加 Opportunity Pydantic Schema

| 元数据 | 值 |
|---|---|
| Issue | #570 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [069-搭建 Opportunity Service 与 Router](0569-add-opportunity-api-router-with-crud-endpoints.md) |
| 启用后赋能 | 30-tickets (工单可能关联 Opportunity) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #569 adds OpportunityService and the Opportunity router, but request bodies and response payloads are currently unvalidated (raw dicts or missing schemas). Without Pydantic schemas, FastAPI cannot enforce field types, requiredness, or default values at the API boundary — increasing the risk of bad data reaching the service layer. This board adds the missing schema layer to close the validation gap.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema / API validation layer.
- **开发者视角**：`src/models/opportunity.py` exposes `OpportunityCreate`, `OpportunityUpdate`, `OpportunityResponse`. The router uses these for request validation and response serialisation. IDE autocompletion is available on all schema fields.

### 1.3 不做什么（剔除）

- [ ] Do not add new router endpoints — only add schemas for endpoints introduced by #569.
- [ ] Do not modify `OpportunityModel` or add database migrations — schema field names must match the existing ORM model.
- [ ] Do not add `OpportunityListResponse` pagination schema — out of scope; add later in a separate board if needed.

### 1.4 关键 KPI

- `ruff check src/models/opportunity.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → all passed
- Router handlers in `#569` accept `OpportunityCreate` / `OpportunityUpdate` as request models with zero runtime `ValidationError` on valid input

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/opportunity.py` — Opportunity router from #569 (endpoints exist but lack Pydantic request/response models)

TBD - 待验证：`src/db/models/opportunity.py` L? — `OpportunityModel` ORM class; schema field names and types must match this model exactly

TBD - 待验证：`src/models/` — existing Pydantic schemas (e.g. `customer.py`, `pipeline.py`) to use as reference pattern

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/opportunity.py` — add `OpportunityCreate` / `OpportunityUpdate` to endpoint request models
  - `tests/unit/test_opportunity.py` — add schema unit tests
- 要建：
  - `src/models/opportunity.py` — Pydantic schemas for Opportunity
  - `tests/unit/test_opportunity_schema.py` — schema validation tests (new file)

### 2.3 缺什么

- [ ] `src/models/opportunity.py` does not exist — no `OpportunityCreate`, `OpportunityUpdate`, or `OpportunityResponse` schemas
- [ ] Router endpoints in #569 receive raw Pydantic `Body()` or no validator — no field-level type enforcement
- [ ] No unit tests for schema serialisation / deserialisation round-trips

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/opportunity.py` | Pydantic `BaseModel` schemas: `OpportunityCreate`, `OpportunityUpdate`, `OpportunityResponse` |
| `tests/unit/test_opportunity_schema.py` | Round-trip validation tests for all three schemas |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/api/routers/opportunity.py` | Add `OpportunityCreate` / `OpportunityUpdate` as request models on POST/PATCH handlers |
| `tests/unit/test_opportunity.py` | Add schema smoke tests; update existing router test fixtures if needed |

### 3.3 新增能力

- **Pydantic schemas**：`OpportunityCreate`, `OpportunityUpdate`, `OpportunityResponse` in `src/models/opportunity.py`
- **Validation**：Router endpoints validate request bodies via FastAPI/Pydantic automatically
- **ORM alignment**：All schema fields have the same name and type as `OpportunityModel` attributes (verified by round-trip test)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Pydantic v2 `BaseModel`** (not v1 `ORMMode`) — this repo uses Pydantic v2 (from `pyproject.toml`); use `model_validate` / `model_dump` rather than `.dict()`.
- **Flat response schema** (not nested `data` wrapper) — matches existing pattern in `src/models/response.py`'s `ApiResponse` envelope; router handles wrapping.
- **Optional fields on `OpportunityUpdate` only** — `OpportunityCreate` requires all fields the service needs to create a record; `OpportunityUpdate` uses `Optional[T] = None` on every field.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pydantic` | `^2.0` | Repo-wide; this board uses v2 API (`model_validate`, `model_dump`) |

### 4.3 兼容性约束

- Schema field names and types must match `OpportunityModel` attributes exactly — if `OpportunityModel` from #569 uses `amount: Mapped[Decimal | None]`, the schema must use `amount: Decimal | None`, not `float`.
- Multi-tenancy: schemas do NOT include `tenant_id` as an input field — tenant is derived from `AuthContext` at the router layer.
- Service methods called by the router continue to receive raw ORM objects; router serialises with `.to_dict()` — schemas are purely at the API boundary.

### 4.4 已知坑

1. **Alembic autogenerate emits `sa.JSON()` instead of `sa.JSONB()`** → N/A — this board does not create migrations.
2. **Pydantic v2 `BaseModel` is not compatible with v1 `ORMMode`** — do not mix `from_attributes = True` with `class Config: orm_mode = True`; use the former only.
3. **`Decimal` fields must be coerced from `float` JSON values** → FastAPI decodes query params as `float` by default; use `StrictFloat = False` or parse explicitly; schema `Decimal` field accepts string `"123.45"` via Pydantic coercion.

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/models/opportunity.py` 基础结构

Create the new file with three schemas. Inspect `OpportunityModel` attributes first (via grep or Read if available) to align field names and types. Use existing schema files (e.g. `src/models/customer.py`) as a structural reference.

操作：
- a) Create `src/models/opportunity.py`.
- b) Define `OpportunityCreate(BaseModel)` — all required fields from `OpportunityModel` (minus `id`, `created_at`, `updated_at`, `tenant_id`).
- c) Define `OpportunityUpdate(BaseModel)` — same fields as `OpportunityCreate` but all `Optional[T] = None`.
- d) Define `OpportunityResponse(BaseModel)` — all fields including `id`, `created_at`, `updated_at`; use `model_config = ConfigDict(from_attributes=True)`.

```python
# src/models/opportunity.py
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OpportunityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    pipeline_id: int
    stage: str = Field(..., max_length=50)
    amount: Optional[Decimal] = None
    # ... match all non-id/non-tenant OpportunityModel fields
    model_config = ConfigDict(from_attributes=True)


class OpportunityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    pipeline_id: Optional[int] = None
    stage: Optional[str] = Field(None, max_length=50)
    amount: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)


class OpportunityResponse(BaseModel):
    id: int
    name: str
    pipeline_id: int
    stage: str
    amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**完成判定**：`ruff check src/models/opportunity.py` → 0 errors

---

### Step 2: 更新 `src/api/routers/opportunity.py` 使用 Schema

Locate the POST and PATCH endpoint handlers added in #569. Replace `Body()` or bare parameter declarations with `OpportunityCreate` / `OpportunityUpdate` body models.

操作：
- a) Add import: `from models.opportunity import OpportunityCreate, OpportunityUpdate, OpportunityResponse`
- b) On the POST handler (create), change `request_body: dict` to `schema: OpportunityCreate = Body(...)`.
- c) On the PATCH handler (update), change to `schema: OpportunityUpdate = Body(...)`.
- d) On GET handler (detail), change return type annotation to `OpportunityResponse`.
- e) Ensure router still calls service methods with `**schema.model_dump()` (Pydantic v2 serialisation) or equivalent.

**完成判定**：`ruff check src/api/routers/opportunity.py` → 0 errors

---

### Step 3: 创建 `tests/unit/test_opportunity_schema.py`

Add a new test file that validates schema round-trips: construct an `OpportunityModel`-like dict, parse through each schema, serialise back, and assert fields match.

操作：
- a) Create `tests/unit/test_opportunity_schema.py`.
- b) Define fixture `opportunity_model_dict` — sample dict with all required fields + optional fields, matching `OpportunityModel` attribute names and types.
- c) Write `test_opportunity_create_valid` — parse `opportunity_model_dict` through `OpportunityCreate`; assert no `ValidationError`.
- d) Write `test_opportunity_create_missing_required` — assert `ValidationError` when required field is omitted.
- e) Write `test_opportunity_update_partial` — parse dict with only one field through `OpportunityUpdate`; assert rest are `None`.
- f) Write `test_opportunity_response_roundtrip` — parse via `OpportunityResponse.model_validate(opportunity_model_dict)`; assert `model_dump()` matches original.

```python
# tests/unit/test_opportunity_schema.py (excerpt)
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import ValidationError
from models.opportunity import OpportunityCreate, OpportunityUpdate, OpportunityResponse


@pytest.fixture
def sample_opportunity_data():
    return {
        "name": "Enterprise Deal",
        "pipeline_id": 1,
        "stage": "Negotiation",
        "amount": Decimal("50000.00"),
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }


def test_opportunity_create_valid(sample_opportunity_data):
    schema = OpportunityCreate(**sample_opportunity_data)
    assert schema.name == "Enterprise Deal"
    assert schema.amount == Decimal("50000.00")


def test_opportunity_create_missing_required():
    with pytest.raises(ValidationError):
        OpportunityCreate(pipeline_id=1, stage="Lead")  # missing `name`


def test_opportunity_update_partial():
    schema = OpportunityUpdate(name="Updated Name")
    assert schema.name == "Updated Name"
    assert schema.pipeline_id is None
    assert schema.stage is None


def test_opportunity_response_roundtrip(sample_opportunity_data):
    resp = OpportunityResponse.model_validate(sample_opportunity_data)
    dump = resp.model_dump()
    assert dump["name"] == "Enterprise Deal"
    assert dump["amount"] == "50000.00"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_schema.py -v` → 4 passed

---

### Step 4: 更新 `tests/unit/test_opportunity.py` 中的 Router 测试

If `#569`'s router tests pass raw dicts as request bodies, update them to use the new schemas so they benefit from validation.

操作：
- a) Read `tests/unit/test_opportunity.py` — locate any `client.post("/opportunities", json={...})` calls.
- b) Ensure request bodies are valid against `OpportunityCreate` / `OpportunityUpdate` (use `OpportunityCreate.model_validate(...)` to pre-validate test data).

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → all passed

---

### Step 5: 运行全量检查

Run lint, type-check, and all unit tests to confirm nothing regressed.

操作：
- a) `ruff check src/models/opportunity.py src/api/routers/opportunity.py`
- b) `PYTHONPATH=src pytest tests/unit/ -v` (or scoped to `test_opportunity`)
- c) `ruff format --check src/models/opportunity.py`

**完成判定**：
- `ruff check src/models/opportunity.py src/api/routers/opportunity.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_opportunity.py tests/unit/test_opportunity_schema.py -v` → all passed
- `ruff format --check src/models/opportunity.py` → unchanged

---

## 6. 验收

- [ ] `ruff check src/models/opportunity.py src/api/routers/opportunity.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_schema.py -v` → 4 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity.py -v` → all passed
- [ ] `ruff format --check src/models/opportunity.py` → unchanged (no formatting差异)
- [ ] `mypy src/models/opportunity.py` → 0 errors (if mypy is configured for this path)
- [ ] Router endpoints in `#569` accept valid `OpportunityCreate` / `OpportunityUpdate` payloads with HTTP 200/201 and reject invalid payloads with HTTP 422

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Schema field names don't match `OpportunityModel` from #569 at merge time | 中 | 高 | Re-run Step 1 with correct field list; update tests; no DB migration needed |
| `OpportunityModel` in #569 uses a type (e.g. `UUID`, `List[str]`) not yet handled in schema | 低 | 中 | Add field with appropriate Pydantic type (`UUID`, `list[str]`); update test fixture; no service change |
| Routing test fixtures break because they use raw dicts not matching schema | 低 | 中 | Wrap test dicts with `OpportunityCreate.model_validate(...)` in the test file before passing to client; no revert of schemas needed |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/opportunity.py src/api/routers/opportunity.py tests/unit/test_opportunity_schema.py tests/unit/test_opportunity.py
git commit -m "feat(sales): add Pydantic schemas for Opportunity (#570)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): add Pydantic schemas for Opportunity (#570)" --body "Closes #570"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/models/customer.py` — existing Pydantic schema pattern (use as structural reference before writing)
- 父 issue / 关联：#570 (this issue), #569 (Opportunity Service + Router), #552 (parent epic)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
