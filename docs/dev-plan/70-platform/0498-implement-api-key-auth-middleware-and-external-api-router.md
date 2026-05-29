# API Key 鉴权中间件与外部 API 路由 · 为外部系统提供 API Key 认证的受控接口

| 元数据 | 值 |
|---|---|
| Issue | #498 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [API Key 数据模型](../50-automation/0497-add-api-key-data-model.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

External systems (webhooks, partner integrations, data pipelines) cannot use the existing JWT-based authentication which requires an interactive user session. A dedicated API Key auth path is needed so non-interactive services can authenticate against this CRM without embedding user credentials. Additionally, the existing router layer has no isolation between internal-user traffic and external-party traffic — an ExternalApiRouter is needed to expose a versioned, API-Key-protected surface.

### 1.2 做完后

- **用户视角**: External integrators receive an API Key from the admin panel (future work, out of scope here) and use it to call `GET/POST /external/v1/customers` and `GET/POST /external/v1/opportunities`. Each key is rate-limited to 100 req/min so a misbehaving integration cannot overload the system.
- **开发者视角**: New `ApiKeyAuthMiddleware` registers with FastAPI and validates `X-API-Key` on every request to `/external/*`. New `src/api/routers/external.py` provides the versioned external endpoints. A sliding-window in-memory rate limiter guards all external calls. Unit tests cover key validation and rate-limit enforcement.

### 1.3 不做什么（剔除）

- [ ] Admin UI for generating / revoking API Keys — handled in a future issue
- [ ] Redis-backed rate limiter — in-process in-memory is the only implementation; Redis is noted as a possible future optimisation but not built here
- [ ] OAuth / token-exchange flows
- [ ] Changes to existing JWT authentication paths (`/api/v*/*`)

### 1.4 关键 KPI

- [KPI 1: `PYTHONPATH=src pytest tests/unit/test_api_key_auth.py -v` → ≥ 6 passed (≥ 3 key-validation tests + ≥ 3 rate-limit tests)]
- [KPI 2: `ruff check src/middleware/api_key_auth.py src/api/routers/external.py src/db/models/api_key.py tests/unit/test_api_key_auth.py` → 0 errors]
- [KPI 3: `PYTHONPATH=src mypy src/middleware/api_key_auth.py src/api/routers/external.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

`src/main.py` is the FastAPI app bootstrap. TBD — 待验证：`src/main.py` 中是否有现有中间件注册模式（如 `app.add_middleware(...)` 或 `app.include_router(...)`），以及 `src/middleware/` 目录结构。

新模块，不存在现有实现。外部 API 路由将挂载于已有 router 之下，参考 `src/api/routers/` 下的现有 router 写法。

### 2.2 涉及文件清单

- 要改：
  - `src/main.py` — 注册 ApiKeyAuthMiddleware 并挂载 ExternalApiRouter
- 要建：
  - `src/db/models/api_key.py` — ApiKey ORM model（id, tenant_id, name, key_hash, expires_at, created_at）
  - `src/middleware/api_key_auth.py` — ApiKeyAuthMiddleware 或 `get_api_key_auth` dependency，X-API-Key 校验
  - `src/api/routers/external.py` — ExternalApiRouter: GET/POST /external/v1/customers, GET/POST /external/v1/opportunities
  - `alembic/versions/<id>_add_api_keys_table.py` — migration 创建 api_keys 表（含 tenant_id 索引）
  - `tests/unit/test_api_key_auth.py` — API Key 校验 + 滑动窗口 rate-limit 单元测试

### 2.3 缺什么

- [ ] No `api_keys` table in the database schema
- [ ] No middleware or FastAPI dependency to validate an `X-API-Key` header
- [ ] No rate-limiting mechanism (in-memory or otherwise) for API-key-gated endpoints
- [ ] No `/external/v1/...` router for customer and opportunity proxy endpoints
- [ ] No unit tests for API Key validation logic
- [ ] No unit tests for rate limiting logic

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/api_key.py` | ORM model for api_keys table |
| `src/middleware/api_key_auth.py` | ApiKeyAuthMiddleware + get_api_key_auth dependency |
| `src/api/routers/external.py` | ExternalApiRouter with /external/v1/customers and /external/v1/opportunities |
| `alembic/versions/<id>_add_api_keys_table.py` | Migration: creates api_keys table with tenant_id index |
| `tests/unit/test_api_key_auth.py` | Unit tests: API Key validation + rate limiting |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/main.py` | Import and register ApiKeyAuthMiddleware; include ExternalApiRouter |

### 3.3 新增能力

- **ORM model**: `ApiKey` in `src/db/models/api_key.py` (id, tenant_id, name, key_hash, expires_at, created_at)
- **Middleware**: `ApiKeyAuthMiddleware` — Starlette middleware, validates X-API-Key on `/external/*` routes
- **Dependency**: `get_api_key_auth` — FastAPI `Security` dependency for per-route key checking
- **Rate limiter**: In-memory sliding window, 100 req/min per API key, auto-evicts stale entries
- **API router**: `ExternalApiRouter` — `GET/POST /external/v1/customers`, `GET/POST /external/v1/opportunities`
- **Migration**: `alembic/versions/<id>_add_api_keys_table.py` — creates `api_keys` table with `tenant_id` index

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **In-memory sliding window rate limiter over Redis**: The issue explicitly allows "in-memory sliding window (or Redis if available)" — in-memory is the default. Redis is a future optimisation; no Redis client is added in this board.
- **Middleware + FastAPI dependency dual approach**: `ApiKeyAuthMiddleware` as a Starlette-level middleware for blanket coverage of `/external/*` and `get_api_key_auth` as an optional FastAPI `Security` dependency for fine-grained per-route enforcement. Both coexist without conflict.
- **SHA-256 key hashing over storing plaintext or HMAC**: SHA-256 is fast, widely available, and prevents plaintext key exposure if the DB is leaked. The key sent by the client is hashed server-side before comparison.

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `passlib[bcrypt]` | `>=1.7.4` | For `passlib.context.CryptContext` used to hash/verify API keys (reuse the same pattern as password hashing already present in this repo if applicable) |

No new Alembic-independent dependencies are introduced. All other dependencies (FastAPI, Starlette, SQLAlchemy) are already constrained by `pyproject.toml`.

### 4.3 兼容性约束

- Multi-tenancy: every SQL query on `api_keys` must include `WHERE tenant_id = :tenant_id`
- ORM models must not define a column named `metadata` (conflicts with `Base.metadata`) — use `event_metadata`, `key_metadata`, or `attrs` if needed
- Service returns ORM/dataclass objects, does NOT call `.to_dict()`; serialization is router responsibility
- Service errors raise `AppException` subclasses; router never catches or returns `ApiResponse.error()`
- `X-API-Key` header must NOT be logged or included in error responses (key confidentiality)

### 4.4 已知坑

1. **In-memory rate-limiter state is per-process** → Symptom: with uvicorn workers > 1, each process maintains its own counter and the 100 req/min limit is multiplied by the number of workers. → Mitigation: document this limitation; recommend `workers=1` for now; Redis backend is the future upgrade path.
2. **Alembic autogenerate writes `sa.JSON()` instead of `sa.JSONB()`** → Symptom: JSON columns are created as JSONB-capable in Postgres but the ORM type annotation may not reflect the right comparator. → Mitigation: after autogenerate, manually edit the migration to use `sa.JSONB()` for any JSONB columns.
3. **Alembic autogenerate drops `timezone=True` on DateTime columns** → Symptom: `DateTime` columns lack timezone info and comparing `created_at` with `datetime.now(timezone.utc)` raises a warning. → Mitigation: inspect the migration file and add `timezone=True` to any naive-tz datetime columns.
4. **Stale rate-limiter entries cause unbounded memory growth** → Symptom: keys that are used once then never again leave their timestamp lists in the dict forever. → Mitigation: the sliding-window cleanup pass removes all entries with no timestamps within the window on every call — no explicit TTL needed.

---

## 5. 实现步骤（按顺序）

### Step 1: Create ApiKey ORM model and database migration

Create `src/db/models/api_key.py` with the SQLAlchemy model for the `api_keys` table.

Columns: `id` (PK, auto-increment), `tenant_id` (Integer, indexed), `name` (String(255)), `key_hash` (String(64), stores SHA-256 hex digest), `expires_at` (DateTime, nullable — null means never expires), `created_at` (DateTime with timezone).

Import the new model in `alembic/env.py` so autogenerate picks it up.

Run alembic autogenerate against a clean `alembic_dev` database (see CLAUDE.md §Alembic Migrations for the exact `docker compose` + `alembic revision --autogenerate` commands).

Review the generated migration: fix `sa.JSON()` → `sa.JSONB()` and add `timezone=True` to DateTime columns.

**完成判定**: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exits with exit code 0; `ruff check src/db/models/api_key.py` → 0 errors

---

### Step 2: Implement API Key hash utility and validation helper

In `src/middleware/api_key_auth.py`, add a `hash_api_key(key: str) -> str` function using `hashlib.sha256(key.encode()).hexdigest()`.

Add a `verify_api_key(plain_key: str, stored_hash: str) -> bool` function.

Add an async `get_validated_tenant_id(api_key: str, session: AsyncSession) -> int | None` helper:
- Hash the incoming key, query `api_keys` for a row matching `key_hash`, checking `tenant_id` from the result.
- Return `None` if not found or if `expires_at` is set and in the past.

**完成判定**: `ruff check src/middleware/api_key_auth.py` → 0 errors; unit test for `hash_api_key` (deterministic, correct length) and `verify_api_key` (correct + incorrect keys) pass

---

### Step 3: Implement in-memory sliding-window rate limiter

In `src/middleware/api_key_auth.py`, add a module-level `_rate_limit_store: dict[str, list[float]] = {}`.

Implement `check_rate_limit(key_hash: str, limit: int = 100, window_seconds: int = 60) -> bool`:
- `now = time.time()`
- Remove all timestamps from `store[key_hash]` older than `now - window_seconds` (sliding window cleanup).
- If the remaining list length >= limit, return `False` (rate limited).
- Otherwise append `now` and return `True`.

The cleanup-on-read approach avoids a background thread and prevents unbounded growth.

**完成判定**: unit test for rate limiter — fill 99 slots (passes), 100th slot returns False, waiting 61s then making a new request passes again

---

### Step 4: Add get_api_key_auth FastAPI dependency and ApiKeyAuthMiddleware

In `src/middleware/api_key_auth.py`, add `get_api_key_auth` as a FastAPI `Security` dependency:
- Extract `X-API-Key` header via `Header(...)`.
- Call `get_validated_tenant_id(api_key, session)`.
- If validation fails, raise `UnauthorizedException("Invalid or expired API Key")`.
- Return an `AuthContext` (or a new `ApiKeyAuthContext`) with `tenant_id`.

Add `ApiKeyAuthMiddleware` as a Starlette `MiddlewareMixin` subclass:
- Only activates on routes starting with `/external/`.
- For non-`/external/*` routes, calls `await self.app(scope, receive, send)` immediately (pass-through).
- On `/external/*` routes: reads `X-API-Key`, validates, checks rate limit.
- On rate-limit failure: returns HTTP 429 with `Retry-After` header.
- On auth failure: returns HTTP 401.

**完成判定**: `ruff check src/middleware/api_key_auth.py` → 0 errors; `mypy src/middleware/api_key_auth.py` → 0 errors

---

### Step 5: Build ExternalApiRouter with /external/v1/customers and /external/v1/opportunities

Create `src/api/routers/external.py`.

Router prefix = `/external/v1`, tags = `["External"]`.

Endpoints:

| Method | Path | Service | Notes |
|--------|------|---------|-------|
| GET | `/customers` | CustomerService.list_customers | ?page=1&page_size=20 |
| POST | `/customers` | CustomerService.create_customer | body = customer data |
| GET | `/opportunities` | OpportunityService.list_opportunities | ?page=1&page_size=20 |
| POST | `/opportunities` | OpportunityService.create_opportunity | body = opportunity data |

Each endpoint uses `get_api_key_auth` dependency for auth and injects the resulting `tenant_id` into the service call.

Return the standard CRM envelope: `{"success": True, "data": {...}}`.

**完成判定**: `ruff check src/api/routers/external.py` → 0 errors; `mypy src/api/routers/external.py` → 0 errors

---

### Step 6: Wire middleware and router into src/main.py

In `src/main.py`:
- Import `ApiKeyAuthMiddleware` from `src.middleware.api_key_auth`.
- Import `ExternalApiRouter` from `src.api.routers.external`.
- Register middleware: `app.add_middleware(ApiKeyAuthMiddleware)` — placement relative to other middleware matters; add it after any session/CORS middleware.
- Include router: `app.include_router(ExternalApiRouter)`.

Ensure the import does not break existing tests or other routers.

**完成判定**: `ruff check src/main.py` → 0 errors; existing unit tests still pass (`PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → baseline still passes)

---

### Step 7: Write unit tests for API Key auth and rate limiting

Create `tests/unit/test_api_key_auth.py`.

Mock the DB session using the pattern from `tests/unit/conftest.py` (MockRow, MockResult, make_mock_session). Do NOT use a real database.

Tests to cover:

**API Key validation (≥ 3 tests)**:
- Valid key → returns correct tenant_id
- Invalid/expired key → raises UnauthorizedException
- Missing X-API-Key header → raises UnauthorizedException

**Rate limiting (≥ 3 tests)**:
- Up to 100 requests within 60 s window → all pass
- 101st request within 60 s window → HTTP 429 / False from rate limiter
- Request after 61 s (sliding window expires) → succeeds again
- Multiple keys are rate-limited independently

Use `freezegun` or `monkeypatch` to mock `time.time()` for deterministic sliding-window testing.

**完成判定**: `PYTHONPATH=src pytest tests/unit/test_api_key_auth.py -v` → ≥ 6 passed; `ruff check tests/unit/test_api_key_auth.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check src/db/models/api_key.py src/middleware/api_key_auth.py src/api/routers/external.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/middleware/api_key_auth.py src/api/routers/external.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_api_key_auth.py -v` → ≥ 6 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → three exits with exit code 0
- [ ] Existing unit test baseline unchanged: `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → all previously passing tests still pass

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| In-memory rate-limiter multiplies limit with uvicorn workers > 1 (each process has independent counter) | 中 | 中 | Document the `workers=1` constraint in the deployment notes; future upgrade to Redis-backed store |
| Migration typo causes api_keys table creation to fail on existing production DB with data | 低 | 高 | Review migration manually before applying; if failed, `alembic downgrade -1` reverts cleanly; new table has no foreign keys so rollback is safe |
| ApiKeyAuthMiddleware blocks /external/* requests but the dependency `get_api_key_auth` is also applied to individual routes, causing double auth check | 低 | 低 | Middleware is the single auth enforcement point; do NOT add `get_api_key_auth` dependency on top of routes already protected by middleware — use it only for routes that need explicit tenant_id injection without the middleware blanket coverage |
| SHA-256 hash collision (theoretical) | 极低 | 中 | Unmitigated in-scope; upgrade to HMAC-SHA256 key derivation if ever needed |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/api_key.py src/middleware/api_key_auth.py src/api/routers/external.py src/main.py alembic/versions/*_add_api_keys_table.py tests/unit/test_api_key_auth.py
git commit -m "feat(external-api): add API Key auth middleware, rate limiter, and ExternalApiRouter"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(external-api): API Key auth + external v1 router (closes #498)" --body "Closes #498"

# 2. Update progress
# - In this board document §Changelog table add a row for today
# - PR merge triggers the AUTO-INDEX generator; no manual README edit needed
```

---

## 9. 参考

- Parent issue: #78
- Depends on: #497
- FastAPI Middleware pattern: TBD — 待验证：`src/middleware/` 目录下现有中间件实现，用于参考 Starlette middleware 注册方式
- SQLAlchemy async session injection: `from db.connection import get_db` pattern from existing routers in `src/api/routers/`
- Rate limiter sliding-window pattern: `time.time()`-based list cleanup on read (no background thread needed)
- Unit test mocking: `tests/unit/conftest.py` — MockState, MockRow, make_mock_session helpers

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
