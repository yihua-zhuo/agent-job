# AIAgentService · 新增 call_recommendation_llm 方法

| 元数据 | 值 |
|---|---|
| Issue | #811 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | #810 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The AI Agent Service needs the ability to call the external LLM backend for generating sales recommendations. This is a prerequisite for the broader sales recommendation flow defined in #600. Without this method, downstream services (such as the recommendation service) cannot generate LLM-powered suggestions for opportunities. The issue is a well-scoped subtask of #600 and depends on #810 for the LLM endpoint contract.

### 1.2 做完后

- **User perspective**: No direct user-visible change — this is a backend service method that enables LLM-powered recommendations in a later board.
- **Developer perspective**: `AIAgentService.call_recommendation_llm(prompt: str) -> dict` becomes available. The service constructor accepts `llm_base_url` so tests and different environments can point at different LLM backends.

### 1.3 不做什么（剔除）

- [ ] Wiring `call_recommendation_llm` into `RecommendationService.get_recommendations` (separate board)
- [ ] Adding the `GET /opportunities/{id}/recommendations` endpoint (separate board)
- [ ] LLM response parsing, validation, retry, or circuit-breaking logic — this method is a thin pass-through
- [ ] Unit/integration tests for the full LLM recommendation flow (separate board)

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ai_agent_service.py -v` → ≥ 3 passed
- `ruff check src/services/ai_agent_service.py` → 0 errors
- Method signature exactly matches: `async def call_recommendation_llm(self, prompt: str) -> dict`
- Constructor signature: `AIAgentService(session: AsyncSession, llm_base_url: str)` — `session` has no default

---

## 2. 当前现状（起点）

### 2.1 现有实现

The issue body names `src/services/ai_agent_service.py` as the target file but does not describe its current contents. Before implementation, verify the existing state.

Reference: TBD - 待验证：grep for `class AIAgentService` and `__init__` to confirm current constructor shape and existing methods (link to `src/services/ai_agent_service.py` not yet resolvable).

Pre-implementation checks:
- Does `AIAgentService` already exist? If so, what is its current constructor?
- Is `llm_base_url` already stored on the service instance?
- Is `httpx` already a project dependency in `pyproject.toml`?

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：确认服务文件实际路径 — add `llm_base_url: str` to `__init__`, add `call_recommendation_llm` method (link to `src/services/ai_agent_service.py` not yet resolvable)
  - TBD - 待验证：确认单元测试文件实际路径 — add unit tests for the new method (link to `tests/unit/test_ai_agent_service.py` not yet resolvable)
  - Any existing call site of `AIAgentService(...)` — add `llm_base_url` argument (breaking constructor change)
- 要建：
  - 无

### 2.3 缺什么

- [ ] `AIAgentService` cannot currently call the LLM backend
- [ ] No way to pass `llm_base_url` to the service for testability / multi-environment support
- [ ] No test coverage for the LLM HTTP call behavior (happy path, HTTP error, timeout)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无 | — |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：确认服务文件实际路径 (link to `src/services/ai_agent_service.py` not yet resolvable) | Add `llm_base_url: str` to `__init__` (no default for `session`); add `call_recommendation_llm` method per issue spec |
| TBD - 待验证：确认单元测试文件实际路径 (link to `tests/unit/test_ai_agent_service.py` not yet resolvable) | Add unit tests covering happy path, HTTP error, and request-body shape |
| All existing `AIAgentService(...)` call sites | Pass `llm_base_url` argument (constructor is a breaking change) |

### 3.3 新增能力

- **Service method**: `AIAgentService.call_recommendation_llm(self, prompt: str) -> dict` — async, POSTs to `{llm_base_url}/recommend`, returns parsed JSON
- **Constructor change**: `AIAgentService(session: AsyncSession, llm_base_url: str)` — `session` has no default (per CLAUDE.md §Service Pattern)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use `httpx.AsyncClient` rather than `requests`**: async-native; the project already uses async SQLAlchemy, so the rest of the request path stays non-blocking.
- **Hardcode `timeout=30.0`**: matches the issue spec exactly; no retry or circuit-breaker in this board to keep scope minimal.
- **`resp.raise_for_status()` for error handling**: idiomatic `httpx` pattern; surfaces non-2xx as `httpx.HTTPStatusError` which the caller can catch. No wrapping in `AppException` here — this method is a thin HTTP wrapper.
- **`llm_base_url` stored with trailing `/` stripped**: prevents `//recommend` double-slash if a caller passes `https://llm.example.com/`.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | TBD - 待验证：check `pyproject.toml` | Required for the new method. If not already present, add the latest stable version. |

### 4.3 兼容性约束

- Constructor must follow project convention: `session: AsyncSession` with no default (per CLAUDE.md §Service Pattern)
- Multi-tenancy: this method does not query the DB, but any future DB calls added to this service must filter by `tenant_id`
- Service raises `AppException` subclasses on errors — this method lets `httpx.HTTPStatusError` / `httpx.TimeoutException` propagate unchanged
- Do NOT call `.to_dict()` in service — not applicable here; the method returns a `dict` from the LLM response
- Constructor change is breaking: every existing `AIAgentService(...)` call site must be updated to pass `llm_base_url`

### 4.4 已知坑

1. **`llm_base_url` trailing slash** → POST URL becomes `//recommend`. Mitigation: strip trailing `/` in `__init__` before storing.
2. **Distinct httpx exception types** → `httpx.TimeoutException`, `httpx.ConnectError`, and `httpx.HTTPStatusError` are separate. Tests should cover at least the HTTP error case using `respx` or `httpx.MockTransport`.
3. **Constructor is a breaking change** → any existing instantiation of `AIAgentService` will fail at import/test time. Mitigation: grep for `AIAgentService(` before merging and update each call site.
4. **Dependency on #810** → the LLM endpoint URL and prompt structure are expected to be finalized in #810. If #810 changes the payload schema, this method must be updated to match.

---

## 5. 实现步骤（按顺序）

### Step 1: 验证现有代码与依赖

Verify the current state of `src/services/ai_agent_service.py` and confirm `httpx` is available.

操作：
- a) Read `src/services/ai_agent_service.py` to confirm the current constructor signature and existing methods
- b) Check `pyproject.toml` for `httpx` — if missing, add it
- c) Check `tests/unit/test_ai_agent_service.py` for existing fixtures and patterns
- d) Grep the repo for existing `AIAgentService(` call sites to know what will break

**完成判定**：`PYTHONPATH=src python -c "import httpx; print(httpx.__version__)"` prints a version; `pyproject.toml` contains an `httpx` entry; list of existing call sites is known.

### Step 2: 修改 `AIAgentService` 构造函数并新增 `call_recommendation_llm` 方法

Modify `src/services/ai_agent_service.py`:

操作：
- a) Add `llm_base_url: str` as the second parameter to `AIAgentService.__init__` (no default for `session`)
- b) Strip trailing `/` from `llm_base_url` when storing as `self.llm_base_url`
- c) Add the `call_recommendation_llm` method per the issue spec

示例代码：

```python
import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class AIAgentService:
    def __init__(self, session: AsyncSession, llm_base_url: str):
        self.session = session
        self.llm_base_url = llm_base_url.rstrip("/")

    async def call_recommendation_llm(self, prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.llm_base_url}/recommend",
                json={
                    "prompt": prompt,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            return resp.json()
```

**完成判定**：`ruff check src/services/ai_agent_service.py` exit 0; method exists with exact signature `async def call_recommendation_llm(self, prompt: str) -> dict`; constructor is `def __init__(self, session: AsyncSession, llm_base_url: str)`.

### Step 3: 编写单元测试

Add unit tests in `tests/unit/test_ai_agent_service.py`:

操作：
- a) Mock the POST to `{llm_base_url}/recommend` using `respx` (preferred) or `httpx.MockTransport`
- b) Test happy path: mock returns 200 with a JSON body, method returns parsed dict
- c) Test HTTP error: mock returns 500, method raises `httpx.HTTPStatusError`
- d) Test that the request body contains `"prompt": <value>` and `"response_format": {"type": "json_object"}`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_agent_service.py -v` → ≥ 3 passed, 0 failed.

### Step 4: 更新所有现有 `AIAgentService(...)` 调用点

The constructor change is breaking. Update every existing call site.

操作：
- a) Grep for `AIAgentService(` across the repo (exclude `src/services/ai_agent_service.py` itself)
- b) For each call site, add a `llm_base_url` argument (use a test/staging URL in test files, real URL in production code)
- c) Re-run the full unit test suite to confirm no regressions

**完成判定**：`PYTHONPATH=src pytest tests/unit/ -v` → all previously-passing tests still pass; no import errors related to `AIAgentService`.

### Step 5: 运行完整检查流水线

操作：
- a) `ruff check src/`
- b) `ruff format --check src/`
- c) `PYTHONPATH=src pytest tests/unit/test_ai_agent_service.py -v`

**完成判定**：all three commands exit 0.

---

## 6. 验收

- [ ] `ruff check src/services/ai_agent_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_agent_service.py -v` → ≥ 3 passed
- [ ] `ruff format --check src/services/ai_agent_service.py` → 0 formatting issues
- [ ] Method signature: `async def call_recommendation_llm(self, prompt: str) -> dict` exists in `AIAgentService`
- [ ] Constructor: `def __init__(self, session: AsyncSession, llm_base_url: str)` — `session` has no default
- [ ] POST URL: `f"{self.llm_base_url}/recommend"` (trailing `/` stripped)
- [ ] Request body: `{"prompt": prompt, "response_format": {"type": "json_object"}}`
- [ ] `resp.raise_for_status()` called before `resp.json()`
- [ ] Timeout: `httpx.AsyncClient(timeout=30.0)`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `httpx` not yet a dependency | Low | Low | Add to `pyproject.toml`; no breaking change to other code |
| #810 changes the LLM payload schema | Medium | Medium | This method is a thin pass-through; payload alignment is the downstream wiring board's responsibility |
| Constructor change breaks existing call sites | Medium | Medium | Step 4 updates all call sites; if a site is missed, the test suite will fail loudly at import/test time |
| LLM endpoint unreachable in test env | Low | Low | Tests use mocked transport; no live HTTP required |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/ai_agent_service.py tests/unit/test_ai_agent_service.py
git commit -m "feat(sales): add call_recommendation_llm method to AIAgentService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "Add call_recommendation_llm method to AIAgentService" --body "Closes #811"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
