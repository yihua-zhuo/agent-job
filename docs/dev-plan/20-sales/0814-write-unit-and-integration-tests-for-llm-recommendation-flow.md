# LLM 推荐 · 单元与集成测试覆盖

| 元数据 | 值 |
|---|---|
| Issue | #814 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：#813 的 dev-plan 板块路径（issue body 仅写「Depends on #813」，未给出板块文件名） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The LLM recommendation flow was implemented in #813 but shipped without automated test coverage. Without tests, any refactor of the LLM response parsing logic or the recommendation persistence path can silently break in production. More critically, the flow consumes an external LLM endpoint — if the provider changes its response schema, a missing test means a 500 in prod rather than a CI failure. This board closes that gap with both fast unit tests (mocked AI agent) and an integration test (respx-mocked HTTP, real DB) that together lock down the valid and invalid response branches.

### 1.2 做完后

- **User perspective**: No user-visible change — this is a test-coverage board. The recommendation feature behaves identically; the difference is that regressions are now caught before merge.
- **Developer perspective**: Developers can refactor `RecommendationService`, change the LLM JSON schema, or swap LLM providers with confidence. CI gates any change that breaks the valid-response parsing, the invalid-response error path, or the DB persistence step. The `AsyncMock` + `respx` pattern established here becomes the template for future AI-feature test coverage.

### 1.3 不做什么（剔除）

- [ ] Implementing the recommendation flow itself (owned by #813)
- [ ] Configuring the LLM provider credentials or endpoint URL
- [ ] Adding metrics/observability for the LLM call
- [ ] Performance/load testing of the LLM call
- [ ] Snapshot/golden-file testing of LLM outputs

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → ≥ 2 passed (valid + invalid response cases)
- `PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` → ≥ 1 passed
- `ruff check tests/unit/test_recommendation_service.py tests/integration/test_recommendation_llm_integration.py` → 0 errors
- Both unit and integration test files exit 0 in CI on the PR branch
- Integration test asserts the `RecommendationModel` row in Postgres matches the mocked LLM response field-for-field

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块（本板块只新增测试文件；被测的 `RecommendationService` / `RecommendationModel` / AI agent 抽象层均由 #813 提供）。

TBD - 待验证：`src/services/recommendation_service.py` 中 `RecommendationService` 的方法签名 — issue body 未给出具体方法名，推测为 `generate_recommendation(opportunity_id: int, tenant_id: int) -> RecommendationModel`

TBD - 待验证：`src/db/models/recommendation.py`（或类似路径）中 `RecommendationModel` 的字段定义 — issue body 未列出具体字段，需在 Step 1 从 #813 的实现中确认

TBD - 待验证：服务调用 LLM 的路径 — 是 `httpx.AsyncClient.post(...)` 直连，还是通过 `await ai_agent.generate(...)` 抽象层；前者会让 `AsyncMock` 单元测试策略失效（见 §4.4 风险 3）

### 2.2 涉及文件清单

- 要改：
  - [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) — 如 `_seed_opportunity` 不存在则新增（遵循已有 `_seed_customer` / `_seed_user` 模式）
- 要建：
  - `tests/unit/test_recommendation_service.py` — 单元测试，覆盖 valid + invalid LLM 响应
  - `tests/integration/test_recommendation_llm_integration.py` — 集成测试，respx mock LLM HTTP 端点，断言 DB 持久化

### 2.3 缺什么

- [ ] No unit test coverage for the LLM response parsing branch (valid JSON → model)
- [ ] No unit test coverage for the invalid-response error path (`ValidationException`)
- [ ] No integration test confirming the recommendation is actually persisted with correct field values end-to-end
- [ ] No `AsyncMock` pattern documented for the AI agent abstraction (this board will establish it)
- [ ] No CI gate preventing LLM-schema regressions from reaching production
- [ ] No `_seed_opportunity` integration helper — cross-service seed for the recommendation flow

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_recommendation_service.py` | Unit tests for `RecommendationService`: `mock_ai_agent` (AsyncMock) + `mock_db_session` (make_mock_session + opportunity_handler); covers valid-LLM-response and invalid-LLM-response cases |
| `tests/integration/test_recommendation_llm_integration.py` | Integration test using `respx` to mock the LLM HTTP endpoint, real Postgres via `async_session` fixture, asserts the `RecommendationModel` row is persisted with correct field values |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) | Add `_seed_opportunity(async_session, tenant_id, **overrides)` helper if not already present — mirrors the existing `_seed_customer` / `_seed_user` pattern, returns the inserted model or its id |

### 3.3 新增能力

- **Unit test fixtures**: `mock_ai_agent` (AsyncMock whose `.generate()` or equivalent returns a valid LLM JSON dict) + `mock_db_session` (built via `make_mock_session([opportunity_handler, ...])` from `tests/unit/conftest.py`)
- **Unit test case 1**: Valid LLM JSON payload → service returns a `RecommendationModel` instance with all fields correctly mapped from the JSON
- **Unit test case 2**: Invalid LLM JSON payload (missing field / wrong type / non-dict) → service raises `ValidationException`
- **Integration test**: Seed opportunity via `_seed_opportunity` → `respx.mock` intercepts the LLM HTTP call and returns a valid JSON response → call service → query DB and assert the `RecommendationModel` row exists with `tenant_id` matching and all fields equal to the mocked response
- **CI gate**: Both files run in `pytest tests/unit/ -v` and `pytest tests/integration/ -v` jobs; failure blocks merge

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **`AsyncMock` for unit tests, `respx` for integration tests**: `AsyncMock` is simpler and faster for unit tests because it bypasses the HTTP layer entirely and keeps the test focused on the service's parsing and persistence logic. `respx` is required for integration tests because we need to verify the real HTTP call path works end-to-end — URL routing, request body shape, response parsing from raw HTTP body — and mocking at the `AsyncMock` level would test less than the real path. Splitting the two layers means a unit-test failure points to service logic, while an integration-test failure points to HTTP/serialization/transport issues.
- **Mock the AI agent abstraction in unit tests, not httpx directly**: The service depends on an AI agent abstraction (per issue body). Mocking at the agent level (`mock_ai_agent.generate.return_value = {...}`) keeps the unit test decoupled from the underlying HTTP client; if the service later swaps httpx for aiohttp, the unit test still passes without changes.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `respx` | TBD - 待验证：检查 `pyproject.toml` 中是否已声明 respx 及版本 | Issue requires `respx` for the integration test; if absent, add to dev-dependencies |

### 4.3 兼容性约束

- Multi-tenant: every DB query in the test path must include `WHERE tenant_id = :tenant_id` — the `_seed_opportunity` helper and the integration test must use the same `tenant_id` fixture value
- Async session in integration test: use the `async_session` fixture from `tests/integration/conftest.py`, never `async with get_db()`
- Test isolation: `db_schema` fixture truncates CASCADE between tests — do not rely on data persisting across test functions
- Ruff format: all new test files must pass `ruff check` and `ruff format --check`
- Service contract (from #813): service `__init__` takes `session: AsyncSession` with no default; returns ORM objects; raises `AppException` subclasses — tests must not assert on `.to_dict()` output from the service

### 4.4 已知坑

1. **`AsyncMock` vs `MagicMock` for async AI agent methods** → 规避: use `unittest.mock.AsyncMock` (not `MagicMock`) for any coroutine on the AI agent; otherwise `await mock_ai_agent()` raises `TypeError: object MagicMock can't be used in 'await' expression`
2. **`respx` must bind to the test's event loop** → 规避: use `respx` as a context manager (`async with respx.mock:`) or via a fixture, not as a module-level decorator, to ensure it binds to the running loop; otherwise the mock never intercepts and the test hangs on a real network call
3. **`RecommendationService` may call httpx directly (no AI agent abstraction)** → 规避: TBD - 待验证：Step 1 must confirm the call path; if httpx is used directly, the unit-test strategy shifts to mocking the httpx client (or fall back to using `respx` in the unit test as well) — this is the highest-risk assumption in the board
4. **LLM JSON response may be wrapped in markdown fences (` ```json ... ``` `)** → 规避: TBD - 待验证：check whether #813's `RecommendationService` strips markdown fences before parsing; if not, the invalid-response test should include a fenced payload as one of the failure cases
5. **`make_count_handler` may be required if the service does a COUNT** → 规避: TBD - 待验证：if `RecommendationService.<method>` calls `.count()` on a query, add `make_count_handler(state)` to the handler list in Step 2; otherwise omit it
6. **Integration test `tenant_id` mismatch causes silent empty-result assertion** → 规避: pull `tenant_id` from the fixture once, pass it explicitly to both `_seed_opportunity` and the service call; assert the queried row's `tenant_id` equals the fixture value, not just that a row exists

---

## 5. 实现步骤（按顺序）

### Step 1: 验证 #813 提供的实现

Before writing any test code, confirm the exact shape of the system under test. This step exists because the issue body leaves several method/field names unspecified, and guessing wrong wastes Steps 2-6.

操作：
- a) Open #813's dev-plan board (path TBD) and read the implementation summary
- b) Read [`src/services/recommendation_service.py`](../../../src/services/recommendation_service.py) — note the `__init__` signature and the method used to generate a recommendation
- c) Read the `RecommendationModel` ORM class — note field names, types, and whether any field is `nullable=False` (these are the fields the valid-JSON test must populate)
- d) Trace the LLM call: is it `httpx.AsyncClient.post(...)` or `await ai_agent.generate(...)`? If both, which path does `generate_recommendation` use?
- e) Grep [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) for `_seed_opportunity`; if absent, Step 5 will add it

**完成判定**：All five items checked; method signature, model fields, LLM call path, and conftest state written down in a scratch note for use in Steps 2-6.

### Step 2: 搭建单元测试 fixture

Create the skeleton of `tests/unit/test_recommendation_service.py` with the `mock_ai_agent` and `mock_db_session` fixtures, plus a `recommendation_service` fixture that wires them together.

操作：
- a) Create `tests/unit/test_recommendation_service.py` with imports: `from unittest.mock import AsyncMock`, `import pytest`, `from tests.unit.conftest import make_mock_session, opportunity_handler, make_count_handler, MockState`, plus `RecommendationService` and `RecommendationModel` (paths TBD)
- b) Define `mock_ai_agent` fixture returning `AsyncMock()` whose `.<method_name>` is configured with a `.return_value` (the exact method name comes from Step 1)
- c) Define `mock_db_session` fixture: `state = MockState(); return make_mock_session([opportunity_handler, make_count_handler(state)])` — include `make_count_handler` only if Step 1 confirmed a COUNT call
- d) Define `recommendation_service` fixture that instantiates `RecommendationService(mock_db_session, ai_agent=mock_ai_agent)` (or however the agent is injected — TBD from Step 1)
- e) Add two empty test stubs: `test_valid_llm_response` and `test_invalid_llm_response`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py --collect-only` shows both test IDs without import error.

### Step 3: 编写 valid-LLM-response 单元测试

Fill in `test_valid_llm_response` so that a valid LLM JSON payload produces a `RecommendationModel` with the correct field values.

操作：
- a) Construct a valid LLM JSON payload dict (TBD: exact field names from Step 1; should include opportunity context + recommended action + any score/confidence field)
- b) Configure `mock_ai_agent.<method>.return_value = payload` (or `AsyncMock(return_value=payload)`)
- c) Call `result = await recommendation_service.<method>(opportunity_id=<seeded_id>, tenant_id=1)`
- d) Assert `isinstance(result, RecommendationModel)`
- e) Assert each field of `result` matches the corresponding key in `payload` (field-by-field comparison, not just `result.to_dict() == payload`)

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py::test_valid_llm_response -v` → `1 passed`.

### Step 4: 编写 invalid-LLM-response 单元测试

Fill in `test_invalid_llm_response` so that a malformed LLM response raises `ValidationException`.

操作：
- a) Configure `mock_ai_agent.<method>.return_value` to a malformed payload (e.g. `{"missing_required_field": True}` or `"not a dict"` or `None`)
- b) Wrap the service call in `with pytest.raises(ValidationException):`
- c) Optional: parametrize over 2-3 failure shapes (missing field, wrong type, non-dict) using `@pytest.mark.parametrize` to cover the type-coercion error path

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py::test_invalid_llm_response -v` → `1 passed` (or `N passed` if parametrized).

### Step 5: 在 integration conftest 中新增 `_seed_opportunity`

If `_seed_opportunity` is absent from `tests/integration/conftest.py`, add it following the existing `_seed_customer` / `_seed_user` pattern.

操作：
- a) Read [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) to confirm the exact pattern used by `_seed_customer` and `_seed_user` (signature, return type, whether they `.commit()` or rely on the fixture)
- b) Define `_seed_opportunity(async_session, tenant_id: int, **overrides) -> <OpportunityModel>` that inserts one row into the `opportunities` table
- c) Accept `**overrides` for fields like `stage`, `value`, `name` so future tests can vary the seed
- d) Return the inserted model (or its `id`) so the test can use it directly

**完成判定**：`PYTHONPATH=src pytest tests/integration/ --collect-only` runs without import error; the helper is importable as `from tests.integration.conftest import _seed_opportunity`.

### Step 6: 编写集成测试（respx + 真实 DB）

Create `tests/integration/test_recommendation_llm_integration.py` using `respx` to mock the LLM HTTP endpoint and assert the recommendation row is persisted in Postgres with correct field values.

操作：
- a) Create the file with imports: `import respx`, `import httpx` (if needed for the URL pattern), `import pytest`, `RecommendationModel`, `RecommendationService`, `_seed_opportunity`
- b) Mark the test class with `@pytest.mark.integration`
- c) Use fixtures: `db_schema`, `tenant_id`, `async_session`
- d) Seed an opportunity: `opportunity = await _seed_opportunity(async_session, tenant_id)`
- e) Set up `respx.mock` (as context manager or fixture) to intercept the LLM HTTP call and return a valid JSON `Response` (status 200, `json=` payload)
- f) Call `result = await RecommendationService(async_session).<method>(opportunity_id=opportunity.id, tenant_id=tenant_id)`
- g) Assert: query the DB via `async_session.execute(select(RecommendationModel).where(RecommendationModel.tenant_id == tenant_id, RecommendationModel.opportunity_id == opportunity.id))` and assert the returned row's fields equal the mocked LLM response

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` → `1 passed`.

### Step 7: 运行全量验证

Run the full unit and integration suites plus ruff to confirm nothing regressed and the new files are clean.

操作：
- a) `PYTHONPATH=src ruff check tests/unit/test_recommendation_service.py tests/integration/test_recommendation_llm_integration.py tests/integration/conftest.py`
- b) `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v`
- c) `PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` (requires `DATABASE_URL` pointing at the docker-compose test DB)
- d) `PYTHONPATH=src pytest tests/ -m "not integration" -v` (full unit suite, to catch unrelated breakage)

**完成判定**：All four commands exit 0; no new ruff warnings.

---

## 6. 验收

- [ ] `ruff check tests/unit/test_recommendation_service.py tests/integration/test_recommendation_llm_integration.py tests/integration/conftest.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → `2 passed` (valid + invalid cases; or `N passed` if invalid case is parametrized)
- [ ] `PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/ -m "not integration" -v` → 全 passed（无回归）
- [ ] CI green: both unit and integration jobs pass on the PR branch
- [ ] Integration test asserts the `RecommendationModel` row in Postgres has `tenant_id` equal to the fixture and field values equal to the mocked LLM response

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `RecommendationService` calls httpx directly (no AI agent abstraction), breaking the `AsyncMock` unit-test strategy | 中 | 高 | Fall back to mocking the httpx client in the unit test (or use `respx` in both unit and integration tests); if widespread, escalate to #813 to refactor the service to inject an AI agent client. Does not block merge of the integration test. |
| `respx` not yet in `pyproject.toml` dev dependencies | 中 | 低 | Add `respx` to `[tool.uv.dev-dependencies]` (or the equivalent dev-deps section) in `pyproject.toml`; dev-only dep, no runtime impact |
| LLM JSON schema changes during #813 development, making the test payload stale | 中 | 中 | Pin the test payload to a documented example response; treat schema changes as breaking changes that update both the service and the test in the same PR |
| `_seed_opportunity` duplicates an existing helper under a different name | 低 | 低 | Reuse the existing helper and remove the duplicate; if semantics differ, keep the new one and mark the old as deprecated |
| Integration test flakes because `respx` intercepts the wrong URL pattern | 低 | 中 | Pin the exact URL/method in `respx.post(...)` / `respx.get(...)`; add `assert respx.calls.call_count == 1` to the test to catch double-calls early; if the LLM URL is built dynamically, mock the full base URL with a regex pattern |
| `make_count_handler` omitted but the service does a COUNT, causing unit test to raise on `.count()` | 低 | 低 | Add `make_count_handler(state)` to the handler list in Step 2; unit test fails fast with a clear error if the handler is missing |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_recommendation_service.py \
        tests/integration/test_recommendation_llm_integration.py \
        tests/integration/conftest.py
git commit -m "test(recommendation): add unit + integration coverage for LLM flow (#814)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(recommendation): LLM flow unit + integration tests" --body "Closes #814"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
