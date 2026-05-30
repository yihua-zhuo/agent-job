# LLMService 板块 · Multi-provider LLM interface| 元数据 | 值 |
|---|---|
| Issue | #627 |
| 分类 | [00-foundations](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0626](0626-add-llms-full-prompt-pipeline.md)（需要 LLMService 作为 provider 底座） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The existing [`AIChatGateway`](../../src/internal/ai_gateway.py) in this repo is a single-provider stub hardcoded to a fictional MiniMax-like backend. The CRM needs to call different LLM providers (OpenAI, Anthropic, MiniMax, etc.) across tenants and use-cases, with unified `.chat()` and `.embed()` semantics, built-in retry/backoff, and per-tenant cost tracking. No such abstraction exists today.

### 1.2 做完后

- **用户视角**：无用户可见变化 — this is a pure backend service layer.
- **开发者视角**：`LLMService` provides `chat(messages, model?) -> str`, `embed(text) -> list[float]`, and per-tenant cost counters. All providers share one interface; adding a new provider requires only a config dict, not a new class.

### 1.3 不做什么（剔除）

- [ ] FastAPI router integration (this is service-only; deps wiring is a future issue).
- [ ] LLM log persistence / conversation history (covered by existing `AIService`).
- [ ] Token estimating utility (not part of the API surface).
- [ ] Streaming chat responses.

### 1.4 关键 KPI

- `ruff check src/services/llm_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_llm_service.py -v` → ≥ 8 passed
- `PYTHONPATH=src mypy src/services/llm_service.py` → 0 errors---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：无- 要建：
  - `src/services/llm_service.py` — `LLMService` 类，chat / embed / cost-tracking 方法
  - `tests/unit/test_llm_service.py` — 单元测试，mock HTTP底层调用
  - `docs/dev-plan/99-misc/0627-add-llmservice-with-multi-provider-support.md` — 本文档

### 2.3 缺什么

- [ ] No unified LLM service — each caller (or future callers) would re-implement provider selection and retry logic.
- [ ] No retry with backoff on transient HTTP failures.
- [ ] No per-tenant LLM cost tracking.
- [ ] No embedding (`embed(text) -> list[float]`) capability.
- [ ] Provider configuration is hardcoded in `AIChatGateway`; no runtime model selection via `model?` param.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/llm_service.py` | `LLMService`：统一 chat / embed 接口，provider 路由，retry/backoff，per-tenant cost counter |
| `tests/unit/test_llm_service.py` | 单元测试：用 `AsyncMock` patch 底层 HTTP 调用，覆盖 happy path、retry、error、model-select cases |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| 无 | — |

### 3.3 新增能力

- **Service method**：`LLMService.chat(self, messages: list[dict], tenant_id: int, model: str?) -> str`
- **Service method**：`LLMService.embed(self, text: str, tenant_id: int, model: str?) -> list[float]`
- **Service method**：`LLMService.get_cost(self, tenant_id: int) -> float`
- **Error**：provider errors raise `ValidationException("LLM provider error: ...")`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选每个 provider独立一个 async 函数（`_openai_chat`, `_anthropic_chat`, …）**，不先抽 provider interface/abstraction protocol — 避免过度工程。Provider 数 ≤ 3 时函数派发（if/elif）足够可读；抽象 later when needed.
- **选 `tenacity`/`asyncio.sleep` exponential backoff** 而不选 Celery task — this is an ORM-free service layer, synchronous retry is sufficient, no external queue dependency.
- **选 `httpx.AsyncClient` 而不选 `aiohttp`** — `httpx` supports both HTTP/1.1 and HTTP/2, has simpler sync/async API, and is already unrlocked in this repo's CI.

### 4.2 版本约束

无新外部依赖引入。已使用 `httpx` (via existing `internal/ai_gateway.py` pattern); retry via stdlib `asyncio.sleep` backoff — no new package required.

### 4.3 兼容性约束

- Service Constructor：`__init__(self, session: AsyncSession)` — session is required, no default.
- Service错误抛 `ValidationException`（按 issue 明确要求 on provider errors），**不**返回 `ApiResponse.error()`。
- Service **不**调用 `.to_dict()`，不返回 envelope dict — caller handles.
- Multi-tenant：cost tracking state is keyed by `tenant_id` dict in memory for this iteration (no new ORM model required).

### 4.4 已知坑

1. **Provider API may return non-200 for transient reasons (429 rate-limit, 503 overload) with valid JSON body** →规避：`retry`逻辑只对 HTTP 4xx/5xx status触发，`chat()` 返回 `ValidationException` only after all retries exhausted.
2. **`httpx.AsyncClient` must be closed or used as async context manager** → 规避：实例化为 `self._client = httpx.AsyncClient(timeout=...)` 在 service `__init__` 中，不在每次 call 时创建/销毁。

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold LLMService class skeleton

Create `src/services/llm_service.py` with:
- Import block: `httpx`, `asyncio`, `ValidationException` from `pkg.errors.app_exceptions`, `dataclasses` for config.
- `LLMService` class: `__init__(self, session: AsyncSession)` storing `self.session`, `self._client = httpx.AsyncClient(timeout=30.0)`, `self._cost_by_tenant: dict[int, float] = {}`.
- Placeholder methods: `chat`, `embed`, `get_cost` (async def, body = `raise NotImplementedError`).
- Provider dispatch constants: `OPENAI_API_URL`, `ANTHROPIC_API_URL`, `DEFAULT_MODEL`.

操作：
- 在 `src/services/llm_service.py` 写入以上骨架。

**完成判定**：文件 `src/services/llm_service.py` 存在，`ruff check src/services/llm_service.py` exit 0。

### Step 2: Implement `_call_openai` private method with retry + backoff

Add `async def _call_openai(self, payload: dict, tenant_id: int) -> dict` using `self._client.post` and 3 retry attempts with `asyncio.sleep(2**attempt)` backoff on any non-200 status. Increment `self._cost_by_tenant[tenant_id]` by estimated cost pulled from response `usage` field after success. On final failure raise `ValidationException(f"LLM provider error: {status} after3 retries")`.

操作：
- 在 `LLMService` 类中加入 `_call_openai` 方法。
- 在 `_call_openai` 中对 `self._client.post` 调用加上 try/except；用 `for attempt in range(3)` + `asyncio.sleep(2**attempt)`。

示例代码：

```python
async def _call_openai(self, payload: dict, tenant_id: int) -> dict:
    for attempt in range(3):
        resp = await self._client.post(OPENAI_API_URL, json=payload, headers={
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        })
        if resp.status_code == 200:
            data = resp.json()
            tokens = data.get("usage", {}).get("total_tokens", 0)
            cost_per_m_token = 0.002  # GPT-4o input cost $/1M tokens
            self._cost_by_tenant[tenant_id] = self._cost_by_tenant.get(tenant_id, 0.0) + (tokens / 1_000_000) * cost_per_m_token
            return data
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)
    raise ValidationException(f"LLM provider error: OpenAI returned {resp.status_code} after 3 retries")
```

**完成判定**：`ruff check src/services/llm_service.py` exit 0；`PYTHONPATH=src mypy src/services/llm_service.py` exit 0。

### Step 3: Implement `_call_anthropic` private method

Add `async def _call_anthropic(self, payload: dict, tenant_id: int) -> dict` similarly to `_call_openai` but targeting `ANTHROPIC_API_URL` with appropriate headers (`x-api-key`). Anthropic uses `-Claude-3-5` family and a different response shape (`content[0].text`). Raise `ValidationException` on exhausted retries.

操作：
- 在 `LLMService` 类中加入 `_call_anthropic` 方法（与 Step2 平级的 elif 分支）。

**完成判定**：`ruff check src/services/llm_service.py` exit 0。

### Step 4: Implement public `chat` method with provider routing

Add:

```python
async def chat(
    self,
    messages: list[dict[str, str]],
    tenant_id: int,
    model: str | None = None,
) -> str:
    """Return the assistant's text reply. Raise ValidationException on provider error."""
    resolved_model = model or DEFAULT_MODEL
    payload = {"model": resolved_model, "messages": messages}

    if resolved_model.startswith("gpt-") or resolved_model.startswith("o1"):
        data = await self._call_openai(payload, tenant_id)
        return data["choices"][0]["message"]["content"]
    elif resolved_model.startswith("claude-") or resolved_model in ("claude-3-5-sonnet",):
        data = await self._call_anthropic(payload, tenant_id)
        return data["content"][0]["text"]
    else:
        raise ValidationException(f"Unknown model: {resolved_model}")
```

操作：
- 将以上代码追加到 `src/services/llm_service.py` `LLMService` 类中。

**完成判定**：`ruff check src/services/llm_service.py` exit 0；文件编译通过。

### Step 5: Implement public `embed` method

```python
async def embed(
    self,
    text: str,
    tenant_id: int,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """Return embedding vector for the given text. Raise ValidationException on provider error."""
    payload = {"model": model, "input": text}
    for attempt in range(3):
        resp = await self._client.post(
            f"{OPENAI_API_URL.rsplit('/', 1)[0]}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}", "Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)
    raise ValidationException(f"LLM provider error: OpenAI embeddings returned {resp.status_code} after 3 retries")
```

操作：
- 将以上 `embed` 方法追加到 `LLMService` 类中。

**完成判定**：`ruff check src/services/llm_service.py` exit 0。

### Step 6: Implement `get_cost` and `__aenter__` / `__aexit__`

Add:

```python
async def get_cost(self, tenant_id: int) -> float:
    """Return accumulated LLM cost for this tenant in USD."""
    return self._cost_by_tenant.get(tenant_id, 0.0)

async def __aenter__(self) -> "LLMService":
    return self

async def __aexit__(self, *args) -> None:
    await self._client.aclose()
```

操作：
- 将 `get_cost` 方法和 `__aenter__` / `__aexit__` 追加到 `LLMService` 类中。

**完成判定**：`ruff check src/services/llm_service.py` exit 0。

### Step 7: Write unit tests

In `tests/unit/test_llm_service.py`:
- Happy path: mock `httpx.AsyncClient.post` to return 200 with valid OpenAI-compatible JSON → `chat()` returns the reply string.
- Happy path: mock embedding response → `embed()` returns a `list[float]`.
- Model routing: `claude-*` model → `_call_anthropic` path.
- Retry path: first2 calls return 429, third returns 200 → `chat()` succeeds.
- Error path: all 3 calls fail → `ValidationException` raised with expected message.
- `get_cost`: after one successful call cost counter reads correctly.
- Tenant isolation: two different `tenant_id` values accumulate separate cost counters.

操作：
- 创建 `tests/unit/test_llm_service.py`，使用 `unittest.mock.AsyncMock` patch `httpx.AsyncClient` 方法，覆盖以上 6 个场景。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_llm_service.py -v` → 6 passed。

---

## 6. 验收

- [ ] `ruff check src/services/llm_service.py` →0 errors
- [ ] `PYTHONPATH=src mypy src/services/llm_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_llm_service.py -v` →6 passed

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Provider API key not set in environment → `ValidationException` at runtime | 低 | 中 | Service 使用 `os.environ.get()`，未设置 key 时 HTTP 401 由 retry exhaustion转为 `ValidationException("LLM provider error: 401 after3 retries")` — callers 收到422，最小化 blast radius |
| OpenAI/Anthropic API response schema changes (e.g. new `refusal` field breaking `choices[0].message.content`) | 中 | 中 | 立即在 `_call_openai`/`_call_anthropic` 中加 `data.get("choices", [{}])[0].get("message", {}).get("content", "")` safe-access；有 unit test 覆盖即可在 CI阶段 catch |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/llm_service.py tests/unit/test_llm_service.py
git commit -m "feat(foundations): add LLMService with multi-provider chat/embed and cost tracking"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "#627 feat: LLMService with multi-provider support" --body "Closes #627"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/ai_service.py`](../../src/services/ai_service.py) — follows the same service pattern (`__init__(session)`, raises `AppException` subclasses)
- 同类参考实现：[`src/internal/ai_gateway.py`](../../src/internal/ai_gateway.py) — the current stub LLM adapter; `LLMService` replaces its role for non-conversation use-cases
- 父 issue：#41
- 关联 issue：#626（LLMService 是 #626 的依赖）, #627（本 issue 本身）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
