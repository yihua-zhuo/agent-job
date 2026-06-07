# [推荐端点] · Add GET recommendations by opportunity ID

| 元数据 | 值 |
|---|---|
| Issue | #813 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | #812 — board 路径待验证（预期 `../20-sales/0812-*.md`） |
| 启用后赋能 | TBD - 待验证：下游 LLM 推荐流测试/集成板块（候选 #0814） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The recommendation feature (parent #600) is being built incrementally. #812 delivers the service-layer capability (`RecommendationService.get_recommendations(...)`) and the LLM-backed recommendation generation. To make those recommendations consumable by API clients (frontend, mobile, internal services), a thin read endpoint is required. Without it, the service output is unreachable over HTTP and downstream integrations cannot proceed. This board wires up the last mile — a single route that composes the two services and returns the standard success envelope.

### 1.2 做完后

- **用户视角**：An authenticated CRM user (sales rep / manager) with access to an opportunity can call `GET /recommendations/{opportunity_id}` to retrieve the list of AI-generated recommendations produced for that opportunity. The response is the standard envelope `{"success": true, "data": {...}}`. No new UI is introduced in this board — this is the API surface that a future UI will call.
- **开发者视角**：A new router module `src/api/routers/recommendation_router.py` is available, registered in `src/main.py`. The endpoint composes `AIAgentService` and `RecommendationService` (both derived from the injected session), enforces multi-tenant isolation via `AuthContext.tenant_id`, and serializes the service result via `.to_dict()`. Other services can call this route as a stable read interface; tests can mount it with a real test client.

### 1.3 不做什么（剔除）

- [ ] LLM prompt construction, tool wiring, or recommendation generation logic — owned by #812.
- [ ] Authentication/authorization beyond `Depends(require_auth)` — no role checks, no opportunity-level ownership checks; tenant scoping via `tenant_id` is the only access boundary.
- [ ] Response caching, pagination, or filtering of recommendations — out of scope; return whatever the service produces.
- [ ] Frontend/UI integration — no new pages, no JS changes.
- [ ] New ORM models or Alembic migrations — the recommendation storage layer is owned upstream.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_recommendation_router.py -v` → ≥ 3 passed (happy path, 404 on missing opportunity, tenant isolation)
- `ruff check src/api/routers/recommendation_router.py src/main.py` → 0 errors
- Router is registered in `src/main.py` and appears in the FastAPI `/openapi.json` schema under the `recommendations` tag

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。TBD - 待验证：grep `recommendation_router` in `src/api/routers/` and `src/main.py` to confirm whether `src/api/routers/recommendation_router.py` already exists with any partial routes, and verify the exact `RecommendationService` constructor signature (issue body says `(session, ai_agent)`) against the actual class in #812's deliverable.

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../../src/main.py) — import `recommendation_router` and call `app.include_router(recommendation_router.router)` in the app bootstrap block
- 要建：
  - `src/api/routers/recommendation_router.py` — FastAPI `APIRouter` exposing `GET /recommendations/{opportunity_id}`
  - `tests/unit/test_recommendation_router.py` — unit tests for the new route (mocked session, no real DB)

### 2.3 缺什么

- [ ] No HTTP-accessible read endpoint for recommendations — service output is unreachable from outside the Python process.
- [ ] No router-level composition of `AIAgentService` and `RecommendationService` for the recommendation domain.
- [ ] No test coverage for the recommendation GET path (happy path + error cases).
- [ ] No registration of the recommendation router in the FastAPI app — even if the router file existed, it would not be mounted.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/recommendation_router.py` | FastAPI router exposing `GET /recommendations/{opportunity_id}`; instantiates `AIAgentService` and `RecommendationService` from the injected session |
| `tests/unit/test_recommendation_router.py` | Unit tests covering happy path, 404 on missing opportunity, and tenant isolation |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../../src/main.py) | Add `from src.api.routers import recommendation_router` and `app.include_router(recommendation_router.router)` next to the other router registrations |

### 3.3 新增能力

- **API endpoint**：`GET /recommendations/{opportunity_id}` → `{"success": True, "data": <recommendation>.to_dict()}` (200 on success, 404 on missing opportunity or cross-tenant, 401 on missing auth, 422 on non-integer `opportunity_id`)
- **Router module**：`recommendation_router` (FastAPI `APIRouter`) registered in `src/main.py`
- **Service composition**：Route handler composes `AIAgentService(session)` + `RecommendationService(session, ai_agent)` per request

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Compose `AIAgentService` inside the route, not in `get_db`** — the route handler is the only place both services are needed together. Keeping the composition in the handler avoids polluting the DI graph with a one-off dependency and matches the existing CRM pattern of "router instantiates services from session" (see CLAUDE.md §Service Pattern).
- **Single `GET` route, no query params** — the issue body specifies the route shape exactly. No `?limit=`, `?status=`, etc. Pagination/filtering is explicitly out of scope (§1.3).
- **`Depends(require_auth)` for `AuthContext`, `Depends(get_db)` for `AsyncSession`** — matches the canonical router pattern in CLAUDE.md §Router Pattern. No `async with get_db()` in the route.
- **`opportunity_id: int` as a typed path param** — FastAPI returns 422 on non-integer input before the service is called, keeping input validation at the framework boundary.

### 4.2 版本约束

No new runtime dependencies introduced by this board.

### 4.3 兼容性约束

- Multi-tenant: `RecommendationService.get_recommendations` must be called with `tenant_id=ctx.tenant_id` — never read tenant from path or body (CLAUDE.md §Multi-Tenancy).
- Service returns ORM/domain objects; the route calls `.to_dict()` for serialization (CLAUDE.md §Rules #1, #3).
- Service errors are `AppException` subclasses — route does NOT wrap in `try/except`; the global exception handler in `src/main.py` converts to JSON (CLAUDE.md §Rules #4).
- Session injection: `session: AsyncSession = Depends(get_db)` — never `async with get_db() as session:` (CLAUDE.md §Rules #4).
- No new ORM models, no Alembic migration — the recommendation storage schema is owned upstream by #812.

### 4.4 已知坑

1. **`AIAgentService` import path is not verified** → 规避：TBD - 待验证：grep `class AIAgentService` in `src/services/` to find the exact module path before writing the import. If defined in a submodule (e.g. `src/services/ai/agent_service.py`), use the full dotted path; if in `src/services/ai_agent_service.py`, the import above is correct.
2. **`RecommendationService` constructor takes `(session, ai_agent)` per the issue body — confirm this matches the actual signature in #812** → 规避：TBD - 待验证：cross-check against the `RecommendationService` class in #812's deliverable. If the constructor differs (e.g. requires keyword args, or takes a pre-built `ai_agent` from DI), adjust the route handler accordingly.
3. **`get_recommendations` may return `None` when no recommendations exist for the opportunity** — behavior not specified by the issue. → 规避：default to `raise NotFoundException` from the service (preferred — keeps the route thin and the 404 semantics consistent with the rest of the CRM). If the service returns `None`, the route must convert to 404 explicitly. Confirm with #812 owner before merge.
4. **`rec.to_dict()` will fail if `get_recommendations` returns a `list[RecommendationModel]` instead of a single object** → 规避：TBD - 待验证：confirm the return type of `get_recommendations` against #812. If it's a list, the response shape becomes `{"success": true, "data": [r.to_dict() for r in rec]}` — the issue body's `rec.to_dict()` literal only works for a single object.

---

## 5. 实现步骤（按顺序）

### Step 1: Create recommendation_router.py with GET route

Create a new FastAPI router module exposing the recommendation GET endpoint. The route composes `AIAgentService` and `RecommendationService` from the injected session, calls `get_recommendations` with the tenant from `AuthContext`, and returns the standard success envelope.

操作：
- a) Create `src/api/routers/recommendation_router.py` (empty file first).
- b) Add imports: `from fastapi import APIRouter, Depends`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from db.connection import get_db`, `from internal.middleware.fastapi_auth import AuthContext, require_auth`, and the two service imports per §4.4 #1 / #2 verification.
- c) Define `router = APIRouter(prefix="/recommendations", tags=["Recommendations"])`.
- d) Implement the handler per the example below.
- e) Run `ruff check src/api/routers/recommendation_router.py` — must exit 0.

示例代码：

```python
@router.get("/{opportunity_id}")
async def get_recommendations(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    ai_agent = AIAgentService(session)
    svc = RecommendationService(session, ai_agent)
    rec = await svc.get_recommendations(opportunity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rec.to_dict()}
```

**完成判定**：`src/api/routers/recommendation_router.py` 文件存在 / `ruff check src/api/routers/recommendation_router.py` exit 0

### Step 2: Register router in src/main.py

Mount the new router in the FastAPI app so the route becomes reachable.

操作：
- a) Open [`src/main.py`](../../../src/main.py) and locate the block where other routers are `include_router`'d.
- b) Add `from src.api.routers import recommendation_router` at the top with the other router imports (matching the existing import style — verify whether other imports use the `src.` prefix or not per CLAUDE.md §PYTHONPATH=src convention).
- c) Add `app.include_router(recommendation_router.router)` next to the other `include_router` calls.
- d) Run `ruff check src/main.py` — must exit 0.
- e) Run `PYTHONPATH=src python -c "from src.main import app; print([r.path for r in app.routes if 'recommendation' in r.path])"` — must print a list containing `/recommendations/{opportunity_id}`.

**完成判定**：`grep -n "recommendation_router" src/main.py` 输出至少两行（import + include_router）/ `ruff check src/main.py` exit 0 / the route appears in the FastAPI app's route list

### Step 3: Write unit test for the new endpoint

Add unit tests covering happy path, missing opportunity (404), and tenant isolation.

操作：
- a) Create `tests/unit/test_recommendation_router.py`.
- b) Define a `mock_db_session` fixture using `tests/unit/conftest.py` helpers — required handlers depend on what `AIAgentService` and `RecommendationService` touch. Minimum: a handler that returns a recommendation-shaped ORM object on `get_recommendations`. If no existing handler covers recommendations, add a minimal `make_recommendation_handler(state)` to `tests/unit/conftest.py` first (or build a `MockResult` inline in the test file).
- c) Write at least 3 tests:
   - `test_get_recommendations_happy_path` — returns 200 with `{"success": True, "data": {...}}`
   - `test_get_recommendations_not_found` — service raises `NotFoundException`, route returns 404
   - `test_get_recommendations_tenant_isolation` — caller's `tenant_id` is forwarded to the service (assert via mock inspection)
- d) All tests must run without a real DB (mock session only).
- e) Run `PYTHONPATH=src pytest tests/unit/test_recommendation_router.py -v` — must show ≥ 3 passed.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_router.py -v` → ≥ 3 passed

### Step 4: Run lint + full unit suite + integration smoke

Final verification: lint the changed files, run the full unit test suite, and run integration tests if any exist for the recommendation domain.

操作：
- a) `ruff check src/api/routers/recommendation_router.py src/main.py tests/unit/test_recommendation_router.py` → 0 errors.
- b) `PYTHONPATH=src pytest tests/unit/ -v` → all unit tests pass (no regressions from the new router registration or new tests).
- c) `PYTHONPATH=src pytest tests/integration/ -v -k recommendation` → pass if integration tests exist for this domain. Use `pytest tests/integration/ --co -q` first to confirm presence; skip this sub-step if no recommendation-tagged integration tests exist.

**完成判定**：ruff exit 0 / unit suite green / integration suite green for the `recommendation` keyword (or confirmed absent)

---

## 6. 验收

- [ ] `ruff check src/api/routers/recommendation_router.py src/main.py tests/unit/test_recommendation_router.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_router.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → all unit tests pass (no regressions)
- [ ] `PYTHONPATH=src pytest tests/integration/ -v -k recommendation` → 全 passed（如涉及 DB）
- [ ] 端到端：启动 app 后 `curl -X GET http://localhost:8000/recommendations/{valid_opportunity_id} -H "Authorization: Bearer <token>"` 返回 `{"success": true, "data": {...}}`（如涉及 router）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `RecommendationService` constructor signature in #812 differs from the `(session, ai_agent)` shape assumed in this board | 中 | 高 | Adjust the route handler to match the actual signature; if #812 is not yet merged, gate this PR behind #812's merge and mark as draft |
| `AIAgentService` import path or module location differs from assumptions in §4.4 #1 | 中 | 中 | TBD - 待验证：after #812 lands, grep `class AIAgentService` in `src/services/` and fix the import; this is a one-line change in the router file |
| `get_recommendations` returns a `list` (not a single object), making `rec.to_dict()` fail | 中 | 中 | Change the route to return `{"success": True, "data": [r.to_dict() for r in rec]}`; or add a wrapper that picks the first/relevant item — confirm the intended return type with #812 owner before merge |
| Existing recommendation tests (if any) break due to router registration order or import side effects in `src/main.py` | 低 | 中 | Run full suite before merge; revert the `app.include_router` line if it breaks unrelated routes — the board's changes are isolated to one router module and two lines in `main.py`, so the revert blast radius is small |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/recommendation_router.py tests/unit/test_recommendation_router.py src/main.py
git commit -m "feat(recommendations): add GET /recommendations/{opportunity_id} endpoint"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(recommendations): add GET /recommendations/{opportunity_id} endpoint" --body "Closes #813"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
