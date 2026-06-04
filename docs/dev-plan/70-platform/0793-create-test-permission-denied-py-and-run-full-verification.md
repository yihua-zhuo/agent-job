# Test Permission Denied · Cover all 14 routers

| 元数据 | 值 |
|---|---|
| Issue | #793 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 1-2 工作日 |
| 依赖 | #792 |
| 启用后赋能 | #643 (parent epic) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM has 14 routers enforcing role-based access control (RBAC) via `Depends(require_auth)` (or equivalent), but there is no dedicated test file that systematically verifies the permission-denied path across all of them. The only existing RBAC coverage is implicit — individual unit tests may or may not exercise the `ForbiddenException` path, and none of them do so consistently. Without explicit permission-denied tests, a refactor of `require_auth`, a change to a router's role check, or a new endpoint added without a role guard can silently weaken the authorization contract and go unnoticed until production. Issue #793 (subtask of #643) closes this gap by adding a single, comprehensive test file that locks in the 403 contract for every router.

### 1.2 做完后

- **用户视角**：No user-visible change — this is a test-only addition that strengthens the safety net for RBAC enforcement. End users see no difference in API behavior.
- **开发者视角**：A new `tests/unit/test_permission_denied.py` with ≥ 30 test cases covering all 14 routers (≥ 2 per router: one permission-denied with `roles=["viewer"]` expecting `ForbiddenException`, one happy-path with `roles=["admin"]` expecting success). A reusable `make_auth_ctx()` helper in `tests/unit/conftest.py` that any future RBAC test can import. CI's `pytest tests/unit/ -v` step now has explicit, named coverage of the 403 path for every router.

### 1.3 不做什么（剔除）

- [ ] Not adding new RBAC logic, new roles, or changing permission rules — only testing what already exists
- [ ] Not testing HTTP-level auth (token validation, session expiry, login flow) — only role-based `ForbiddenException` paths
- [ ] Not writing integration tests — only unit tests with mocked sessions (per CLAUDE.md §Unit Test SQL Mocks)
- [ ] Not adding shorthand helpers like `make_admin_ctx()` / `make_viewer_ctx()` — keep a single flexible `make_auth_ctx(roles=...)` helper per the issue spec
- [ ] Not modifying any production code under `src/` — this is a tests-only change
- [ ] Not adding new SQL mock handlers to `tests/unit/conftest.py` — the new tests reuse existing handlers

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` → ≥ 30 passed, 0 failed
- `PYTHONPATH=src pytest tests/unit/ -v` → all passed, 0 failed (no regressions in the full unit suite)
- `ruff check src/api/routers/` → 0 errors
- `ruff check tests/unit/test_permission_denied.py tests/unit/conftest.py` → 0 errors
- Each of the 14 routers has ≥ 2 test methods in the new file (1 permission-denied + 1 happy-path)

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建测试文件。本节描述现有 RBAC 触点供实现参考（路径未在 CLAUDE.md 中显式给出，标 TBD）。

The permission check is enforced via `Depends(require_auth)` in each router under [`src/api/routers/`](../../../src/api/routers/) (14 router modules — exact list TBD - 待验证：`ls src/api/routers/`). `require_auth` resolves to an `AuthContext` defined in TBD - 待验证：`internal/middleware/fastapi_auth.py` — the `AuthContext` class location and `__init__` signature are not documented in `CLAUDE.md`. On insufficient roles, the relevant code path raises `ForbiddenException` from TBD - 待验证：`pkg/errors/app_exceptions.py` — `CLAUDE.md` §Error Handling references `ForbiddenException(detail)` with HTTP 403, and the import path is `pkg.errors.app_exceptions`.

The existing unit test infrastructure lives in [`tests/unit/conftest.py`](../../../tests/unit/conftest.py), which provides `MockState`, `MockRow`, `MockResult`, `make_mock_session(handlers)`, and domain handlers (`make_customer_handler`, `make_user_handler`, `make_count_handler`, `tenant_handler`, `pipeline_handler`, `opportunity_handler`, `ticket_sql_handler`, `campaign_handler`). The new test file will reuse these composable building blocks but does NOT require new SQL handlers — each test mocks only the service method the router calls.

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — append `make_auth_ctx(roles=None, tenant_id=1, user_id=1, **kwargs) -> AuthContext` helper (do not remove or rename existing fixtures)
- 要建：
  - `tests/unit/test_permission_denied.py` — ≥ 30 test methods across 14 routers (≥ 2 per router)

### 2.3 缺什么

- [ ] No `tests/unit/test_permission_denied.py` exists — the permission-denied path is untested at the unit level for any router
- [ ] No `make_auth_ctx()` helper in `tests/unit/conftest.py` — every test that needs an `AuthContext` currently constructs one inline or via a per-test fixture
- [ ] No systematic coverage of all 14 routers' RBAC contracts — silent auth regressions are possible
- [ ] No shared pattern for "call endpoint with `roles=['viewer']` and expect `ForbiddenException`" — each future test would reinvent the setup

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_permission_denied.py` | ≥ 30 test methods: 1 permission-denied + 1 happy-path per router × 14 routers |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | Add `make_auth_ctx(roles, tenant_id, user_id, **kwargs) -> AuthContext` helper function; export it for import by test files |

### 3.3 新增能力

- **Test helper**：`make_auth_ctx(roles: list[str] | None = None, tenant_id: int = 1, user_id: int = 1, **kwargs) -> AuthContext` in `tests/unit/conftest.py`
- **Test file**：`tests/unit/test_permission_denied.py` with ≥ 30 `async def test_` methods, organized as 14 per-router groups (class or grouped functions)
- **Test pattern (per router)**：one test calls the endpoint/service with `make_auth_ctx(roles=["viewer"])` and asserts `pytest.raises(ForbiddenException)`; one test calls it with `make_auth_ctx(roles=["admin"])` and asserts success (return value or expected side effect)
- **No new service methods, no new API endpoints, no new ORM models, no new Alembic migrations** — this board is tests-only

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Test at the service/router level, not the HTTP level** — unit tests with mocked sessions (per CLAUDE.md §Unit Test SQL Mocks). No `httpx.AsyncClient`, no `TestClient`, no ASGI transport. Rationale: matches the existing unit-test pattern in the repo, runs in < 5s, and the RBAC check happens at the `require_auth` boundary (or inside the service call), so HTTP-level testing adds complexity without coverage gain.
- **Single flexible `make_auth_ctx(roles=...)` helper, not multiple shorthand helpers** — the issue spec says "add a `make_auth_ctx()` helper" (singular). Avoid premature abstraction (no `make_admin_ctx()`, `make_viewer_ctx()`, `make_manager_ctx()`). The caller passes `roles=` explicitly so each test reads self-documenting: `make_auth_ctx(roles=["viewer"])` vs `make_auth_ctx(roles=["admin"])`.
- **Reuse existing mock-session fixtures, do not add new SQL handlers** — the new tests don't introduce new SQL patterns; they call service/router methods that internally use already-mocked handlers (e.g. `make_customer_handler`, `make_count_handler`). No changes to `tests/unit/conftest.py` beyond appending `make_auth_ctx()`.
- **Per-router test groups, not one flat list of 30+ tests** — organize as 14 classes (or 14 grouped function blocks) so a failure points immediately at the offending router. This also makes it trivial to skip a router that turns out to have no RBAC-protected endpoint.

### 4.2 版本约束

No new dependencies — this board adds only test code. No `pyproject.toml` changes. No `requirements.txt` changes.

### 4.3 兼容性约束

- Must not change any production code under `src/` — this is a tests-only change
- Must not break the existing `pytest tests/unit/ -v` suite — zero regressions allowed
- Must follow the per-test-file `mock_db_session` fixture pattern (CLAUDE.md §Unit Test SQL Mocks) — no global autouse patching
- `make_auth_ctx()` must return a valid `AuthContext` that passes through `Depends(require_auth)` without raising — it must set whatever fields `require_auth` reads (likely `tenant_id`, `user_id`, and `roles`)
- Each test must instantiate a fresh `AuthContext` — no shared mutable state across tests (no module-level `ctx` variable)
- Imports must follow `from tests.unit.conftest import make_auth_ctx` and `from pkg.errors...` style — never `from src....` (CLAUDE.md §Conventions: `PYTHONPATH=src`)

### 4.4 已知坑

1. **`AuthContext` constructor signature is not documented in CLAUDE.md** → 规避：TBD - 待验证：read `internal/middleware/fastapi_auth.py` to find the `AuthContext` class and replicate its `__init__` signature in `make_auth_ctx()`. If the class is a Pydantic model, the helper constructs it with the right kwargs; if it's a dataclass, same approach. Use `**kwargs` pass-through for forward-compat with fields the implementer might miss.

2. **The exact list of 14 routers is not in CLAUDE.md** → 规避：TBD - 待验证：`ls src/api/routers/` to enumerate the 14 files. Cross-check with the domain handlers in `tests/unit/conftest.py` (`customer_handler`, `user_handler`, `tenant_handler`, `pipeline_handler`, `opportunity_handler`, `ticket_sql_handler`, `campaign_handler` — 7 visible) to find the other 7. Record the list in a comment block at the top of the new test file.

3. **Which roles trigger `ForbiddenException` per router is not visible from CLAUDE.md** → 规避：TBD - 待验证：for each of the 14 routers, read the router module and the `require_auth` (or equivalent role-check dependency) to determine the allowed-role set. The issue spec assumes `viewer` is denied and `admin` is allowed for every router — verify this assumption holds for all 14 before writing tests. If a router has a different role hierarchy (e.g. `manager` instead of `admin`, or a list of allowed roles), adjust the test pair accordingly and document the actual hierarchy in the test file's comment block.

4. **The phrase "calls the underlying service method" in the issue is ambiguous** — it could mean (a) the service method called by the router, (b) the router endpoint itself, or (c) a thin wrapper that checks roles before the service call. → 规避：TBD - 待验证：inspect one representative router end-to-end to determine the exact call site of the RBAC check. Write the test against that call site. If the service method itself checks roles, the test calls the service directly; if the router checks, the test calls the router endpoint. The pattern must be consistent across all 14 routers — if it's not, document the deviation per router.

5. **Some routers may have endpoints that don't go through `require_auth`** (public health checks, login, etc.) → 规避：TBD - 待验证：during Step 1, confirm each of the 14 routers has at least one RBAC-protected endpoint to test. If a router has no protected endpoint, skip it and add a comment in the test file explaining why. The ≥ 30 test count must still be met from the remaining routers — if 12 routers have protected endpoints, write 3 test pairs on routers with multiple protected endpoints to reach 24+, or add a 3rd test (e.g. `roles=[]` anonymous denied) per router to push the count above 30.

6. **Pre-push hook blocks on `ruff` + `mypy`** (CLAUDE.md §Gotchas) → 规避：run `ruff check tests/unit/test_permission_denied.py tests/unit/conftest.py` and `mypy tests/unit/` before pushing. If the hook blocks, fix the root cause; do NOT use `git push --no-verify` as a permanent bypass.

7. **Mock sessions do not enforce RBAC at the session level** — RBAC is enforced by `require_auth` or the service/router code, not by the mocked SQL. → 规避：tests must exercise the code path that invokes the role check (e.g. call the router function with a mocked `Depends(require_auth)` returning `make_auth_ctx(roles=["viewer"])`). If a test calls a service method with only `tenant_id`, it bypasses the RBAC check and the test is meaningless.

---

## 5. 实现步骤（按顺序）

### Step 1: Enumerate the 14 routers and their RBAC contracts

Read each of the 14 router modules under `src/api/routers/` and record in a comment block at the top of `tests/unit/test_permission_denied.py`:
- Router module name (and the test class/function name that will cover it)
- The role(s) each endpoint accepts
- The endpoint(s) chosen for the permission-denied + happy-path pair (pick the most representative one per router)

操作：
- a) `ls src/api/routers/` to enumerate the 14 router files (TBD - 待验证：exact list)
- b) For each router, `grep -n "require_auth\|ForbiddenException\|roles" src/api/routers/<router>.py` to find the RBAC touchpoints
- c) Note the allowed-role set per endpoint in the comment block

**完成判定**：The comment block in `tests/unit/test_permission_denied.py` lists all 14 routers with their target endpoint and allowed-role set; no TBD entries remain in the list.

### Step 2: Inspect `AuthContext` to design `make_auth_ctx()`

Open TBD - 待验证：`internal/middleware/fastapi_auth.py` and find the `AuthContext` class definition. Record:
- Required fields (likely `tenant_id: int`, `user_id: int`)
- Optional fields (likely `roles: list[str]`)
- Any other kwargs the `require_auth` dependency reads

操作：
- a) `grep -n "class AuthContext" internal/middleware/fastapi_auth.py` (TBD - 待验证：path)
- b) Note the `__init__` signature
- c) Design `make_auth_ctx(roles=None, tenant_id=1, user_id=1, **kwargs)` to match — pass through `**kwargs` for forward-compat

**完成判定**：The Step 2 design note is recorded (mentally or in a scratch comment); the implementer can write `make_auth_ctx()` in Step 3 without re-reading the source.

### Step 3: Add `make_auth_ctx()` helper to `tests/unit/conftest.py`

In [`tests/unit/conftest.py`](../../../tests/unit/conftest.py), append (do not replace or rename existing fixtures):

```python
# TBD - 待验证：adjust the import path to match the actual AuthContext location
from internal.middleware.fastapi_auth import AuthContext  # TBD - 待验证：import path

def make_auth_ctx(
    roles: list[str] | None = None,
    tenant_id: int = 1,
    user_id: int = 1,
    **kwargs,
) -> AuthContext:
    """Build an AuthContext for unit tests.

    Pass roles=["viewer"] for permission-denied tests, roles=["admin"] for
    happy-path tests. Extra kwargs are forwarded to AuthContext for
    forward-compat with fields added later (e.g. permissions, scopes).
    """
    return AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles or [],
        **kwargs,
    )
```

操作：
- a) Append the helper after the existing fixtures in `tests/unit/conftest.py`
- b) Verify the import path matches the actual `AuthContext` location (TBD - 待验证)
- c) Run `PYTHONPATH=src python -c "from tests.unit.conftest import make_auth_ctx; print(make_auth_ctx(roles=['admin']))"` to smoke-test — must exit 0 and print an AuthContext-shaped object

**完成判定**：`PYTHONPATH=src python -c "from tests.unit.conftest import make_auth_ctx; print(make_auth_ctx(roles=['admin']))"` exits 0 and prints a non-error representation.

### Step 4: Create `tests/unit/test_permission_denied.py` with the test scaffold

Create the new file with:
- Module docstring explaining the test pattern and the assumed role pair (`viewer` denied, `admin` allowed) with a pointer to the comment block from Step 1 for per-router deviations
- Imports: `pytest`, `ForbiddenException`, `make_auth_ctx`, `make_mock_session`, relevant domain handlers
- 14 per-router test groups (classes or grouped functions) — ≥ 2 tests each

Scaffold for one router (others follow the same pattern; adjust module paths and endpoint names per the Step 1 comment block):

```python
import pytest
# TBD - 待验证：adjust imports to match actual module paths
from pkg.errors.app_exceptions import ForbiddenException  # TBD - 待验证
from tests.unit.conftest import make_auth_ctx, make_mock_session

# Per-router: import the service or router function under test.
# Example for one router (others follow the same pattern):
# from src.services.customer_service import CustomerService
# from src.api.routers.customer import list_customers


class TestCustomerRouter:
    async def test_viewer_denied(self):
        ctx = make_auth_ctx(roles=["viewer"])
        # TBD - 待验证：call the actual endpoint / service method that
        # triggers the RBAC check for this router
        with pytest.raises(ForbiddenException):
            ...

    async def test_admin_allowed(self):
        ctx = make_auth_ctx(roles=["admin"])
        # TBD - 待验证：assert success (return value or expected side effect)
        ...
```

操作：
- a) Write the file with all 14 router groups, ≥ 2 tests each
- b) Use `make_auth_ctx(roles=["viewer"])` for permission-denied and `make_auth_ctx(roles=["admin"])` for happy-path
- c) Use `pytest.raises(ForbiddenException)` for denied cases; plain `assert` for success cases
- d) Each test (or each test class) defines its own `mock_db_session` fixture locally using the existing handlers from `tests/unit/conftest.py` (per CLAUDE.md §Unit Test SQL Mocks)
- e) Verify the file parses: `PYTHONPATH=src python -c "import tests.unit.test_permission_denied"` exits 0

**完成判定**：File exists, has ≥ 30 `async def test_` methods, parses without syntax errors.

### Step 5: Run the new test file and iterate to green

操作：
- a) `PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` — fix any failures (most likely: import path mismatches, `AuthContext` shape mismatches, or wrong role assumptions)
- b) Confirm ≥ 30 passed, 0 failed
- c) If any test fails because the assumed role (`viewer` denied, `admin` allowed) is wrong for a given router, adjust the test to use the correct denied/allowed role pair and update the Step 1 comment block accordingly (TBD - 待验证：which roles per router)
- d) If any test fails because the call site is wrong (e.g. the RBAC check is in the router, not the service), adjust the test to call the right function

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` → `30 passed` (or more) and 0 failed.

### Step 6: Run full unit suite and ruff to confirm no regressions

操作：
- a) `PYTHONPATH=src pytest tests/unit/ -v` — must show 0 failures (existing tests + new tests all pass)
- b) `ruff check src/api/routers/` — must show 0 errors
- c) `ruff check tests/unit/test_permission_denied.py tests/unit/conftest.py` — must show 0 errors
- d) If any regression appears, fix the root cause before proceeding — do not disable tests or add `xfail` markers to mask failures

**完成判定**：`PYTHONPATH=src pytest tests/unit/ -v` → 0 failed; `ruff check src/api/routers/` exit 0; `ruff check tests/unit/test_permission_denied.py tests/unit/conftest.py` exit 0.

### Step 7: Commit, push, open PR

操作：
- a) `git add tests/unit/test_permission_denied.py tests/unit/conftest.py`
- b) `git commit -m "test: add permission-denied coverage for all 14 routers (#793)"`
- c) `git push -u origin "$(git branch --show-current)"`
- d) `gh pr create --base master --title "test: permission-denied coverage for all routers (#793)" --body "Closes #793"`

**完成判定**：PR exists on GitHub, CI passes, branch is ready for review.

---

## 6. 验收

- [ ] `PYTHONPATH=src pytest tests/unit/test_permission_denied.py -v` → `30 passed` (or more) and 0 failed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → all passed, 0 failed (no regressions in the full unit suite)
- [ ] `ruff check src/api/routers/` → 0 errors
- [ ] `ruff check tests/unit/test_permission_denied.py tests/unit/conftest.py` → 0 errors
- [ ] Each of the 14 routers has ≥ 2 test methods in `tests/unit/test_permission_denied.py` (1 permission-denied with `roles=["viewer"]` + 1 happy-path with `roles=["admin"]`)
- [ ] `make_auth_ctx()` is importable from `tests.unit.conftest` and returns a valid `AuthContext` that does not raise when constructed
- [ ] No production code under `src/` is modified — this is a tests-only change
- [ ] The comment block at the top of `tests/unit/test_permission_denied.py` documents the 14 routers, their target endpoints, and their allowed-role sets (no TBD entries remain)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `AuthContext` constructor signature differs from assumption — `make_auth_ctx()` raises `TypeError` at import time, taking down all 30 tests | 中 | 高 | TBD - 待验证：read `internal/middleware/fastapi_auth.py` and adjust the helper signature; this is exactly why Step 2 exists before Step 3. If the class has a non-obvious required field, add it as a keyword arg with a sensible default |
| Role assumption (`viewer` denied, `admin` allowed) is wrong for one or more routers | 中 | 中 | Adjust the test to use the correct denied/allowed role pair per router; document the actual role hierarchy in the test file's comment block. The tests stay green; the comment block becomes the source of truth for the role map |
| Some routers have no RBAC-protected endpoint (e.g. public health check, login) | 低 | 低 | Skip those routers in the test file; add a 3rd test case to routers with multiple protected endpoints to maintain ≥ 30 total. Document skipped routers in the comment block |
| `require_auth` is not the only RBAC mechanism — some routers check roles inline in the handler body | 低 | 中 | Add a second test per affected router that exercises the inline-check path with the same role pattern; or read the router code in Step 1 and design tests around the actual check locations |
| The phrase "calls the underlying service method" maps to different call sites for different routers (service vs router vs wrapper) | 中 | 中 | Step 4 writes each test against the actual call site discovered in Step 1's router read. If patterns diverge, group tests by pattern (e.g. `TestRouterLevelRBAC`, `TestServiceLevelRBAC`) and document the split |
| Pre-push hook blocks on `ruff` / `mypy` | 中 | 低 | Fix the lint/type error in the new files; do NOT use `git push --no-verify` as a permanent bypass (CLAUDE.md §Gotchas) |
| The new test file accidentally exercises a real DB path (e.g. a test forgets to mock the session) and integration-test infrastructure kicks in | 低 | 高 | Each test defines its own `mock_db_session` fixture per CLAUDE.md §Unit Test SQL Mocks; no global autouse patching. If a test hits the real DB, it will fail fast in CI (no `DATABASE_URL` in unit-test environment) and the implementer fixes the fixture |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_permission_denied.py tests/unit/conftest.py
git commit -m "test: add permission-denied coverage for all 14 routers (#793)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: permission-denied coverage for all routers (#793)" --body "Closes #793"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`grep -rn "AuthContext" tests/unit/` 找现有使用 AuthContext 的测试文件作为 `make_auth_ctx()` 的调用范例；`grep -rn "ForbiddenException" tests/unit/` 找现有 `pytest.raises(ForbiddenException)` 的测试作为每个 router 测试对儿的模板
- 第三方文档：N/A（FastAPI `Depends` 与 SQLAlchemy mock 模式已在 CLAUDE.md §Conventions 覆盖）
- 父 issue / 关联：#643 (parent epic), #792 (depends on)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-04 | 创建 | TBD |
