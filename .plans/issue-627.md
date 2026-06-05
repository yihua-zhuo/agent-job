# Implementation Plan — Issue #627

## Goal
Create `src/services/llm_service.py` — a unified `LLMService` that abstracts multi-provider LLM access behind `chat(messages, model?) -> str` and `embed(text) -> list[float]`, with provider dispatch by model prefix, 3-attempt exponential-backoff retry on transient HTTP errors, and in-memory per-tenant cost tracking. All provider errors raise `ValidationException`. This module is service-layer only — no FastAPI router or dependency wiring. The goal is to replace the role of the single-provider stub `AIChatGateway` for non-conversation use-cases (embedding, batch generation, programmatic chat) that #626 will build on.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0627-add-llmservice-with-multi-provider-support.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/99-misc/0627-add-llmservice-with-multi-provider-support.md`

## Affected Files
- `src/services/llm_service.py` — new file; `LLMService` class with `__init__(session)`, `chat`, `embed`, `get_cost`, private `_call_openai` / `_call_anthropic`, module-level `OPENAI_API_URL` / `ANTHROPIC_API_URL` / `DEFAULT_MODEL` constants
- `tests/unit/test_llm_service.py` — new file; unit tests mocking `httpx.AsyncClient.post` via `unittest.mock.AsyncMock`

## Implementation Steps

1. **Create `src/services/llm_service.py` with the class skeleton and module constants.**
   - Imports: `os`, `asyncio`, `httpx`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from pkg.errors.app_exceptions import ValidationException`.
   - Module constants: `OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"`, `ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"`, `DEFAULT_MODEL = "gpt-4o"`, `MAX_RETRIES = 3`.
   - `class LLMService: __init__(self, session: AsyncSession)` stores `self.session`, instantiates `self._client = httpx.AsyncClient(timeout=30.0)`, and initializes `self._cost_by_tenant: dict[int, float] = {}`.

2. **Implement `_call_openai(self, payload: dict, tenant_id: int) -> dict` and `_call_anthropic(self, payload: dict, tenant_id: int) -> dict`.**
   - Each runs a `for attempt in range(MAX_RETRIES)` loop calling `self._client.post(url, json=payload, headers=...)` (OpenAI: `Authorization: Bearer OPENAI_API_KEY`; Anthropic: `x-api-key` + `anthropic-version` header).
   - On `status_code == 200`, parse JSON; pull `usage.total_tokens` from OpenAI / `usage.input_tokens + output_tokens` from Anthropic; increment `self._cost_by_tenant[tenant_id]` by `(tokens / 1_000_000) * cost_per_m_token` (use a hardcoded per-model rate constant, e.g. `OPENAI_COST_PER_M_TOKEN = 0.002`); return the parsed dict.
   - On non-200, `await asyncio.sleep(2 ** attempt)` if `attempt < MAX_RETRIES - 1`; after the loop exits without success, raise `ValidationException(f"LLM provider error: {provider_name} returned {status_code} after {MAX_RETRIES} retries")`.

3. **Implement `chat(self, messages: list[dict[str, str]], tenant_id: int, model: str | None = None) -> str`.**
   - Resolve `resolved_model = model or DEFAULT_MODEL`.
   - Build payload `{"model": resolved_model, "messages": messages}`.
   - Dispatch: if `resolved_model.startswith("gpt-")` or `resolved_model.startswith("o1")` → call `_call_openai` and return `data["choices"][0]["message"]["content"]`; if `resolved_model.startswith("claude-")` → call `_call_anthropic` and return `data["content"][0]["text"]`; else raise `ValidationException(f"Unknown model: {resolved_model}")`.

4. **Implement `embed(self, text: str, tenant_id: int, model: str = "text-embedding-3-small") -> list[float]`.**
   - POST to `f"{OPENAI_API_URL.rsplit('/', 1)[0]}/embeddings"` with `{"model": model, "input": text}` and the same retry/backoff pattern as the chat helpers.
   - On success, return `resp.json()["data"][0]["embedding"]`; on exhaustion, raise `ValidationException(f"LLM provider error: OpenAI embeddings returned {status_code} after {MAX_RETRIES} retries")`.
   - Update `self._cost_by_tenant[tenant_id]` by the token count from `usage.total_tokens` using the OpenAI embedding rate.

5. **Implement `get_cost(self, tenant_id: int) -> float` returning `self._cost_by_tenant.get(tenant_id, 0.0)`.**

6. **Add `__aenter__` and `__aexit__` to the class** so the service can be used as `async with LLMService(session) as svc:` — `__aenter__` returns `self`, `__aexit__` calls `await self._client.aclose()`. This prevents the `httpx.AsyncClient` leak noted in the dev-plan §4.4 known-pitfall #2.

7. **Create `tests/unit/test_llm_service.py` with 8 unit tests covering:**
   - `test_chat_openai_happy_path` — mock `httpx.AsyncClient.post` to return 200 + OpenAI-shaped JSON (`{"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 100}}`); assert `chat()` returns `"hi"` and `get_cost(tenant_id)` reflects the token charge.
   - `test_chat_anthropic_routing` — pass `model="claude-3-5-sonnet"`, mock the Anthropic response shape (`{"content": [{"text": "reply"}], ...}`); assert correct dispatch and returned string.
   - `test_embed_returns_vector` — mock embeddings response with `"data": [{"embedding": [0.1, 0.2, 0.3]}]`; assert return type is `list[float]` of the expected length.
   - `test_chat_retry_on_429` — first 2 `post` calls return 429, third returns 200; assert success and that exactly 3 calls were made.
   - `test_chat_retry_exhausted` — all 3 calls return 500; assert `pytest.raises(ValidationException)` with `"LLM provider error"` in the message.
   - `test_unknown_model_raises` — pass `model="some-unknown-model"`, assert `ValidationException("Unknown model: ...")`.
   - `test_get_cost_tenant_isolation` — call `chat()` twice with different `tenant_id` values; assert `get_cost(tenant_a)` and `get_cost(tenant_b)` accumulate independently.
   - `test_embed_retry_exhausted` — embeddings endpoint returns 500 three times; assert `ValidationException` raised.

   Tests should use `unittest.mock.AsyncMock` and `unittest.mock.patch` on `httpx.AsyncClient.post` at the module level (or patch the client instance created in `__init__`). Use the existing `tests/unit/conftest.py` patterns — no DB mock session is needed (the service is DB-free per dev-plan §4.3: cost is in-memory only).

## Test Plan
- Unit tests in `tests/unit/`: new `test_llm_service.py` with 8 tests (listed in Step 7) covering happy path, provider routing, retry success, retry exhaustion, unknown model, embed success/failure, cost accumulation, and tenant isolation. `LLMService` is constructed with a plain `AsyncMock()` for its `session` argument (no DB calls are made). Mock `httpx.AsyncClient` via `unittest.mock.patch` targeting the module-level client.
- Integration tests in `tests/integration/`: none required — the dev-plan §1.3 explicitly excludes FastAPI integration and the service is DB-free; cost tracking is in-memory and intentionally not persisted in this iteration.
- Dev-plan verification (target-board §6):
  - `ruff check src/services/llm_service.py` → 0 errors
  - `PYTHONPATH=src mypy src/services/llm_service.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_llm_service.py -v` → 8 passed

## Acceptance Criteria
- `src/services/llm_service.py` exists and defines `LLMService` with `__init__(self, session: AsyncSession)` typed as `AsyncSession` with no default, conforming to CLAUDE.md §Service Pattern.
- `LLMService.chat(messages, tenant_id, model=None)` dispatches to OpenAI or Anthropic based on model prefix and returns the assistant text string.
- `LLMService.embed(text, tenant_id, model="text-embedding-3-small")` returns a `list[float]`.
- On non-200 HTTP responses the service retries up to 3 times with `asyncio.sleep(2 ** attempt)` backoff; on exhaustion it raises `ValidationException` (per dev-plan §1.3 + §3.3).
- `LLMService.get_cost(tenant_id)` returns the accumulated USD cost keyed by tenant, starting at 0.0 for unseen tenants.
- `LLMService` is usable as an async context manager (`async with LLMService(session) as svc:`) and closes its `httpx.AsyncClient` on exit.
- `ruff check src/services/llm_service.py` exits 0.
- `PYTHONPATH=src mypy src/services/llm_service.py` exits 0.
- `PYTHONPATH=src pytest tests/unit/test_llm_service.py -v` shows 8 passed.
- No files outside `src/services/llm_service.py` and `tests/unit/test_llm_service.py` are modified (per the issue's explicit scope constraint).
