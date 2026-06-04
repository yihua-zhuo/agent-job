# 权限装饰器接入7路由 · 为7个router补上权限校验

| 元数据 | 值 |
|---|---|
| Issue | #792 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | #791（`require_permission` 装饰器所在板块） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

This CRM currently has a RBAC decorator (`require_permission`) available in `src/dependencies/rbac.py` (delivered via #791), but the seven domain routers — activities, notifications, automation, marketing, ai, tasks, lead_routing — do not yet call it on their endpoints. Without it, any authenticated user (regardless of role) can hit any of those ~46 endpoints and mutate tenant data they were never authorized to touch. This is a cross-tenant / cross-role authorization gap and must be closed before any of these surfaces can be considered production-safe.

### 1.2 做完后

- **User perspective**：No user-visible change. All endpoints continue to work for users who already have the appropriate role/permission; users lacking the required permission now receive a 403 instead of silently succeeding.
- **Developer perspective**：Every endpoint in the seven listed routers declares its required permission via a single decorator. New contributors can read the decorator on a route to learn what permission it needs, and the global `AppException` → JSON handler in `main.py` already converts `ForbiddenException` into a 403 response — no router-side try/catch needed.

### 1.3 不做什么（剔除）

- [ ] Do NOT change the existing admin/manager role checks in `lead_routing.py` — the new `automation:manage` / `automation:read` permission checks are *additive*, layered on top.
- [ ] Do NOT redesign the permission catalog or the role → permission mapping. Reuse the string keys already established in #791.
- [ ] Do NOT add permission decorators to routers other than the seven listed in the issue body (e.g. customers, sales, tickets are out of scope for this board).
- [ ] Do NOT introduce a new dependency or refactor existing `require_auth` / `require_role` usage.

### 1.4 关键 KPI

- All 46 endpoints across the 7 routers carry an `@require_permission(...)` decorator (or, for `lead_routing.py` writes, an additional permission check on top of the existing role check).
- `PYTHONPATH=src ruff check src/api/routers/activities.py src/api/routers/notifications.py src/api/routers/automation.py src/api/routers/marketing.py src/api/routers/ai.py src/api/routers/tasks.py src/api/routers/lead_routing.py` → `All checks passed!`
- `PYTHONPATH=src pytest tests/unit/ -v` → no new failures attributable to this change.
- At least 1 unit test per router asserts that calling an endpoint without the required permission raises `ForbiddenException` (or returns 403 via the global handler in a FastAPI `TestClient`).

---

## 2. 当前现状（起点）

### 2.1 现有实现

`require_permission` is defined in [`src/dependencies/rbac.py`](../../../src/dependencies/rbac.py). The exact signature and accepted argument shape (single string, list of strings, AND vs OR semantics) must be confirmed against the file before use — see "TBD" below.

```{x}:{y}:src/dependencies/rbac.py
TBD - 待验证：grep `def require_permission` in `src/dependencies/rbac.py` — need the signature, the
permission-key type (str vs list[str]), and the exception it raises on denial.
```

The seven target routers exist at the paths named in the issue body. Each currently uses `Depends(require_auth)` to establish the `AuthContext` but does not further authorize the request by permission.

```{x}:{y}:src/api/routers/activities.py
TBD - 待验证：each endpoint in `src/api/routers/activities.py` uses `ctx: AuthContext = Depends(require_auth)` —
verify whether a `from src.dependencies.rbac import require_permission` is already present, and list the 8
endpoint function names + HTTP methods (TBD — 待验证 by reading the file).
```

For `src/api/routers/lead_routing.py` specifically, the issue notes that write endpoints already enforce admin/manager roles. The existing role guard must be located before adding the permission layer on top.

```{x}:{y}:src/api/routers/lead_routing.py
TBD - 待验证：identify which of the 7 endpoints in `lead_routing.py` are writes (already role-guarded) vs
reads (no guard today). Need this to know which 4 read endpoints need `automation:read` added and which
3 write endpoints need `automation:manage` added.
```

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/activities.py`](../../../src/api/routers/activities.py) — add `@require_permission("activity:*")` to all 8 endpoints; add `from src.dependencies.rbac import require_permission` import.
  - [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) — add `@require_permission("notification:read", ...)` for read endpoints and `@require_permission("notification:send", ...)` for send endpoints; import.
  - [`src/api/routers/automation.py`](../../../src/api/routers/automation.py) — add `@require_permission("automation:read", ...)` for reads, `@require_permission("automation:manage", ...)` for writes; import.
  - [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) — add `@require_permission("campaign:*")` to all 6 endpoints; import.
  - [`src/api/routers/ai.py`](../../../src/api/routers/ai.py) — add `@require_permission("ai:access")` to all 3 endpoints; import.
  - [`src/api/routers/tasks.py`](../../../src/api/routers/tasks.py) — add `@require_permission("task:*")` to all 5 endpoints; import.
  - [`src/api/routers/lead_routing.py`](../../../src/api/routers/lead_routing.py) — add `@require_permission("automation:read")` to the read endpoints and `@require_permission("automation:manage")` to the write endpoints *on top of* the existing role checks; import.
- 要建：
  - `tests/unit/test_rbac_router_coverage.py` (or one new test per router — TBD per §3.1) — verify that at least one endpoint per router raises `ForbiddenException` when called without the required permission.

### 2.3 缺什么

- [ ] `require_permission` is not yet imported into any of the 7 routers (TBD - 待验证 — confirm by grep).
- [ ] No per-endpoint authorization: any authenticated user in the tenant can invoke any of the 46 endpoints.
- [ ] No regression test asserts that a missing permission produces a 403 for any of these routes.
- [ ] Permission keys are not yet consistently named across the catalog (e.g. is it `automation.read` or `automation:read`? — TBD - 待验证 against `rbac.py` and the catalog from #791).
- [ ] For `lead_routing.py` reads, there is currently *no* authorization at all (only writes have the role check) — the 4 read endpoints are the most exposed surface in this set.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_rbac_router_coverage.py` | Single test module that hits one representative endpoint from each of the 7 routers without the required permission and asserts a `ForbiddenException` (or 403 via the global handler). TBD - 待验证：confirm whether a single consolidated file is preferred over 7 per-router files — pick whichever matches the existing test layout in `tests/unit/`. |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/activities.py`](../../../src/api/routers/activities.py) | Import `require_permission`; decorate all 8 endpoints with `activity:*`. |
| [`src/api/routers/notifications.py`](../../../src/api/routers/notifications.py) | Import `require_permission`; decorate reads with `notification:read`, writes (send) with `notification:send`. |
| [`src/api/routers/automation.py`](../../../src/api/routers/automation.py) | Import `require_permission`; reads → `automation:read`, writes → `automation:manage`. |
| [`src/api/routers/marketing.py`](../../../src/api/routers/marketing.py) | Import `require_permission`; decorate all 6 endpoints with `campaign:*`. |
| [`src/api/routers/ai.py`](../../../src/api/routers/ai.py) | Import `require_permission`; decorate all 3 endpoints with `ai:access`. |
| [`src/api/routers/tasks.py`](../../../src/api/routers/tasks.py) | Import `require_permission`; decorate all 5 endpoints with `task:*`. |
| [`src/api/routers/lead_routing.py`](../../../src/api/routers/lead_routing.py) | Import `require_permission`; reads → `automation:read` added, writes → `automation:manage` added on top of the existing admin/manager role checks (do NOT remove the role checks). |

### 3.3 新增能力

- **Decorator coverage**：`@require_permission(...)` applied to 46 endpoints across 7 routers; `lead_routing.py` write endpoints stack the new permission check on top of their existing role check.
- **Permission catalog (in use)**：`activity:*`, `notification:read`, `notification:send`, `automation:read`, `automation:manage`, `campaign:*`, `ai:access`, `task:*` — the eight permission keys surfaced by this change.
- **Test coverage**：`tests/unit/test_rbac_router_coverage.py` proves that missing permission ⇒ 403 for a representative endpoint in each of the 7 routers.

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Decorate per-endpoint, not per-router.** A single module-level guard would be too coarse: e.g. `notifications.py` mixes reads (anyone in the tenant) and sends (restricted). The decorator must be on the individual route function.
- **Stack on top of existing role checks in `lead_routing.py`** rather than replacing them. The current `admin/manager` role gate is a different axis from the new `automation:manage` permission gate; removing the role check would be a behavior change outside this board's scope.
- **Reuse the global `AppException` handler** in `main.py` for 403 responses. Do not add per-router try/except around the decorator — `ForbiddenException` (or whatever `require_permission` raises — TBD - 待验证) is converted to JSON centrally.
- **No new permission keys.** All eight keys used here are presumed to already exist in the catalog from #791. If a key is missing, the decorator will fail at request time; the test in §3.1 is the safety net.

### 4.2 版本约束

No new dependencies introduced by this board.

### 4.3 兼容性约束

- Multi-tenant: every endpoint remains tenant-scoped via the existing `tenant_id=ctx.tenant_id` argument; the new decorator does not change tenancy.
- Session injection: routers continue to use `session: AsyncSession = Depends(get_db)` — do not switch to `async with get_db()` (see CLAUDE.md "Gotchas & Tips").
- `require_auth` stays — `require_permission` is layered on top of authentication, not a replacement.
- Do not remove or weaken any existing role check in `lead_routing.py`.
- Public API surface (path, method, request/response shape) is unchanged; only the authorization gate is added.

### 4.4 已知坑

1. **`require_permission` argument shape is unverified** → 规避：before editing any router, run `PYTHONPATH=src python -c "from src.dependencies.rbac import require_permission; import inspect; print(inspect.signature(require_permission))"` to confirm whether it takes a single string, a list of strings, or a variadic. If the signature is `(*perms)`, wrap multi-permission endpoints in a list; if it takes a single string, add multiple decorators stacked.
2. **Permission key delimiter mismatch** (e.g. `automation:read` vs `automation.read` vs `automation_read`) → 规避：grep the existing role → permission mapping in the catalog from #791 to confirm the exact string format before writing decorators. A wrong key silently degrades to "permission always denied" at runtime.
3. **`lead_routing.py` order of guards matters** → 规避：put the new permission decorator *between* `Depends(require_auth)` and the function body (i.e. as the outermost decorator on the route function), so it runs after authentication but before the existing role check inside the function — or, if the role check is itself a decorator, stack it as `@require_role("admin", "manager")` outermost with `@require_permission("automation:manage")` directly under it. Confirm by reading the file (TBD).
4. **Import path is `src.dependencies.rbac`, not `dependencies.rbac`** — the issue body explicitly says to import from `src/dependencies/rbac.py`. Because `PYTHONPATH=src` is exported at runtime, `from dependencies.rbac import require_permission` *also* works, but to match the issue spec exactly use the `src.` prefix. → 规避：use `from src.dependencies.rbac import require_permission` in all 7 files.
5. **`@require_permission` may resolve `ctx` via `Depends` itself** — if it inspects the route's existing `Depends(require_auth)` to read `AuthContext`, the existing `ctx: AuthContext = Depends(require_auth)` parameter must remain on every decorated route. Do not remove it.
6. **Alembic autogen quirks are NOT relevant here** — this board changes only router Python files, no ORM models, no migrations. Do not run `alembic revision --autogenerate`.

---

## 5. 实现步骤（按顺序）

### Step 1: Confirm `require_permission` signature and key format

Read the decorator to lock down the argument shape and the permission-key string format used in the catalog.

操作：
- a) `PYTHONPATH=src python -c "from src.dependencies.rbac import require_permission; import inspect; print(inspect.signature(require_permission))"` — record the signature.
- b) `grep -rn 'permission' src/dependencies/rbac.py` — list the permission keys referenced.
- c) `grep -rn 'permission' tests/` — find any existing test that uses the decorator to confirm the call pattern.
- d) Record the answer as a code comment at the top of `tests/unit/test_rbac_router_coverage.py` so the next person sees it.

**完成判定**：the four commands above all exit 0 and the output is pasted into a comment block in the test file.

### Step 2: Wire `@require_permission` into `src/api/routers/activities.py`

8 endpoints, all get `activity:*`.

操作：
- a) Add `from src.dependencies.rbac import require_permission` after the existing imports.
- b) For each of the 8 endpoint functions, insert `@require_permission("activity:*")` as the outermost decorator on the route function.
- c) `PYTHONPATH=src ruff check src/api/routers/activities.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/activities.py` returns `8`.

### Step 3: Wire `@require_permission` into `src/api/routers/notifications.py`

10 endpoints: reads → `notification:read`, sends → `notification:send`.

操作：
- a) Add the import.
- b) Tag each endpoint with the appropriate key. TBD - 待验证 — list each endpoint and its method from the file to decide read vs send.
- c) `PYTHONPATH=src ruff check src/api/routers/notifications.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/notifications.py` returns `10`; the split between `notification:read` and `notification:send` is documented in a 1-line comment above the import.

### Step 4: Wire `@require_permission` into `src/api/routers/automation.py`

7 endpoints: reads → `automation:read`, writes → `automation:manage`.

操作：
- a) Add the import.
- b) Decorate each endpoint per the read/write split (TBD - 待验证 — confirm by reading the file).
- c) `PYTHONPATH=src ruff check src/api/routers/automation.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/automation.py` returns `7`.

### Step 5: Wire `@require_permission` into `src/api/routers/marketing.py`

6 endpoints, all `campaign:*`.

操作：
- a) Add the import.
- b) Decorate all 6 endpoints with `@require_permission("campaign:*")`.
- c) `PYTHONPATH=src ruff check src/api/routers/marketing.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/marketing.py` returns `6`.

### Step 6: Wire `@require_permission` into `src/api/routers/ai.py`

3 endpoints, all `ai:access`.

操作：
- a) Add the import.
- b) Decorate all 3 endpoints with `@require_permission("ai:access")`.
- c) `PYTHONPATH=src ruff check src/api/routers/ai.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/ai.py` returns `3`.

### Step 7: Wire `@require_permission` into `src/api/routers/tasks.py`

5 endpoints, all `task:*`.

操作：
- a) Add the import.
- b) Decorate all 5 endpoints with `@require_permission("task:*")`.
- c) `PYTHONPATH=src ruff check src/api/routers/tasks.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/tasks.py` returns `5`.

### Step 8: Wire `@require_permission` into `src/api/routers/lead_routing.py` (additive on top of role checks)

7 endpoints: reads → `automation:read` added, writes → `automation:manage` added on top of the existing `admin/manager` role check.

操作：
- a) Add the import.
- b) For each of the 4 read endpoints (TBD - 待验证 — confirm by reading the file), add `@require_permission("automation:read")`. Do NOT touch the function body.
- c) For each of the 3 write endpoints, add `@require_permission("automation:manage")` *in addition to* the existing role check. The role check stays.
- d) `PYTHONPATH=src ruff check src/api/routers/lead_routing.py` → `All checks passed!`

**完成判定**：`grep -c '@require_permission' src/api/routers/lead_routing.py` returns `7`; `grep -c 'admin\|manager' src/api/routers/lead_routing.py` is unchanged from `master` (the role check is preserved).

### Step 9: Add regression test and run full check pipeline

操作：
- a) Create `tests/unit/test_rbac_router_coverage.py`. For each of the 7 routers, call one representative endpoint without the required permission and assert `ForbiddenException` (or 403 via `TestClient`).
- b) `PYTHONPATH=src ruff check src/api/routers/activities.py src/api/routers/notifications.py src/api/routers/automation.py src/api/routers/marketing.py src/api/routers/ai.py src/api/routers/tasks.py src/api/routers/lead_routing.py tests/unit/test_rbac_router_coverage.py` → `All checks passed!`
- c) `PYTHONPATH=src pytest tests/unit/test_rbac_router_coverage.py -v` → all assertions pass.
- d) `PYTHONPATH=src pytest tests/unit/ -v` → no previously-passing test now fails.

**完成判定**：commands (b), (c), (d) all exit 0; the new test file covers all 7 routers.

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/api/routers/activities.py src/api/routers/notifications.py src/api/routers/automation.py src/api/routers/marketing.py src/api/routers/ai.py src/api/routers/tasks.py src/api/routers/lead_routing.py` → `All checks passed!`
- [ ] `grep -c '@require_permission' src/api/routers/activities.py` → `8`
- [ ] `grep -c '@require_permission' src/api/routers/notifications.py` → `10`
- [ ] `grep -c '@require_permission' src/api/routers/automation.py` → `7`
- [ ] `grep -c '@require_permission' src/api/routers/marketing.py` → `6`
- [ ] `grep -c '@require_permission' src/api/routers/ai.py` → `3`
- [ ] `grep -c '@require_permission' src/api/routers/tasks.py` → `5`
- [ ] `grep -c '@require_permission' src/api/routers/lead_routing.py` → `7` AND `git diff master -- src/api/routers/lead_routing.py | grep -c '^-.*admin\|^-.*manager'` → `0` (existing role check lines are not deleted)
- [ ] `PYTHONPATH=src pytest tests/unit/test_rbac_router_coverage.py -v` → all 7 router-coverage cases pass
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → no new failures (pre-existing failures unrelated to this change are acceptable; new failures are not)
- [ ] `PYTHONPATH=src python -c "from src.api.routers.activities import router; from src.api.routers.notifications import router; from src.api.routers.automation import router; from src.api.routers.marketing import router; from src.api.routers.ai import router; from src.api.routers.tasks import router; from src.api.routers.lead_routing import router; print('imports ok')"` → prints `imports ok` (no circular import or missing-symbol errors from the new import line)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| A permission key string (e.g. `automation:read`) is misspelled or not registered in the catalog from #791, causing all calls to that endpoint to 403 for legitimate users | 中 | 高 | Add a one-off integration test that hits one decorated endpoint with a known-good role and asserts 200. If a key is missing, add it to the catalog and re-run. The PR is still mergeable behind a feature flag if #791's catalog is incomplete. |
| Stacking `@require_permission` on top of the existing role check in `lead_routing.py` changes the order of evaluation, causing role-gated writes to fail for users who previously passed | 低 | 中 | Re-read the decorator stack after editing; if order is wrong, swap decorator order. The test in Step 9 covers this. |
| `require_permission` resolves `AuthContext` via a different mechanism than `Depends(require_auth)` (e.g. it reads a request header instead), and the existing `ctx: AuthContext` parameter must be added to a route that does not have it | 低 | 中 | For any 403 returned to a user who *should* have the permission, check the test logs for `AuthContext` resolution errors. Add `ctx: AuthContext = Depends(require_auth)` to any route that lacks it. |
| Some of the 46 endpoints are intentionally public (no auth required); adding `@require_permission` would break them | 低 | 中 | TBD - 待验证：spot-check each router for any endpoint that does NOT have `Depends(require_auth)` already; skip those. The issue body implies all 46 are auth'd, but confirm by reading. |
| Ruff flags the new import as unused (e.g. because `@require_permission` is interpreted as a non-exported symbol) | 低 | 低 | `ruff check --fix` to auto-remove the import if unused, OR add a `# noqa: F401` with a comment explaining why. |

---

## 8. 完成后必做

```bash
# 1. Verify the seven files are clean
PYTHONPATH=src ruff check \
  src/api/routers/activities.py \
  src/api/routers/notifications.py \
  src/api/routers/automation.py \
  src/api/routers/marketing.py \
  src/api/routers/ai.py \
  src/api/routers/tasks.py \
  src/api/routers/lead_routing.py \
  tests/unit/test_rbac_router_coverage.py
# expected: "All checks passed!"

# 2. Run the targeted test
PYTHONPATH=src pytest tests/unit/test_rbac_router_coverage.py -v
# expected: 7+ passed

# 3. Run the full unit suite to catch regressions
PYTHONPATH=src pytest tests/unit/ -v
# expected: no new failures

# 4. commit + PR
git add \
  src/api/routers/activities.py \
  src/api/routers/notifications.py \
  src/api/routers/automation.py \
  src/api/routers/marketing.py \
  src/api/routers/ai.py \
  src/api/routers/tasks.py \
  src/api/routers/lead_routing.py \
  tests/unit/test_rbac_router_coverage.py
git commit -m "feat(rbac): wire @require_permission into 7 routers (Closes #792)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master \
  --title "Wire @require_permission into activities, notifications, automation, marketing, ai, tasks, lead_routing" \
  --body "Closes #792

- Adds @require_permission decorator to 46 endpoints across 7 routers.
- Imports require_permission from src/dependencies.rbac.py.
- lead_routing.py: stacks automation:manage / automation:read on top of the existing admin/manager role checks (additive, not replacement).
- New test: tests/unit/test_rbac_router_coverage.py asserts 403 when permission is missing for one representative endpoint per router.

Subtask of #643. Depends on #791."

# 5. Update progress
# - In this board's §Changelog table, add a row with the merge date and PR number.
# - After PR merge, docs/dev-plan/README.md §1.1 AUTO-INDEX block updates automatically.
```

---

## 9. 参考

- Parent issue: #643
- Dependency (provides `require_permission`): #791
- Decorator source: [`src/dependencies/rbac.py`](../../../src/dependencies/rbac.py) (TBD - 待验证 — confirm signature before editing routers)
- Test helpers (mock session, MockState, FastAPI TestClient patterns): [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) (TBD - 待验证 — pick the right fixture per router)
- Error → HTTP mapping (how `ForbiddenException` becomes 403): `src/main.py` global exception handler (TBD - 待验证 — find the handler registration)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-04 | 创建 | TBD |
