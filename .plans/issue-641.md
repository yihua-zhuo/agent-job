I now have a full picture of the codebase. Let me write the implementation plan.

---

# Implementation Plan — Issue #641

## Goal

Create a static, in-memory permission service (`src/services/permission_service.py`) with glob-aware `has_permission` and `check_permission`, plus a new FastAPI `Depends` decorator `@require_permission` in `src/dependencies/rbac.py` that gates router endpoints by `resource:action` permissions using the user's `AuthContext.roles`.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0641-build-permission-service-and-require-permission-decorator.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md` §2 (global constraints enforced)
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0641-build-permission-service-and-require-permission-decorator.md`

## Affected Files

- `src/services/permission_service.py` — **new** — `ROLE_PERMISSIONS` constant, `has_permission()`, `check_permission()`
- `src/dependencies/rbac.py` — **new** — `@require_permission(resource, action)` FastAPI `Depends` factory
- `src/dependencies/__init__.py` — **new** — `__init__` so `src/dependencies/` is a Python package (referenced in issue body; no `__init__.py` exists today)
- `tests/unit/test_permission_service.py` — **new** — unit tests for `ROLE_PERMISSIONS`, glob matching, boundary cases
- `tests/unit/test_require_permission.py` — **new** — unit tests for `@require_permission` decorator scenarios

## Implementation Steps

1. **Create `src/dependencies/__init__.py`** (empty package marker):
   ```python
   """RBAC + auth FastAPI dependencies."""
   ```
   No other changes needed.

2. **Create `src/services/permission_service.py`**:
   - Define `ROLE_PERMISSIONS: dict[str, list[str]]` covering the five roles from `RBACService.DEFAULT_ROLE_PERMISSIONS` plus an explicit `'owner': ['*']` entry (the issue body calls for `'owner': ['*']`; the existing `RBACService` does not include one, so this is additive):
     ```python
     ROLE_PERMISSIONS: dict[str, list[str]] = {
         "owner": ["*"],
         "admin": [p[0] for p in DEFAULT_PERMISSIONS],   # from rbac_service
         "manager": [...same as RBACService.DEFAULT_ROLE_PERMISSIONS["manager"]...],
         "sales": [...],
         "support": [...],
         "member": ["customer:read", "customer:create", "opportunity:read"],
         "viewer": ["customer:read", "opportunity:read", "ticket:read"],
     }
     ```
   - `has_permission(role: str, resource: str, action: str) -> bool`:
     - Return `False` immediately for unknown roles (no KeyError)
     - Check exact `"resource:action"` match first
     - If `'*'` is in the role's permission list → return `True` (super-admin wildcard)
     - If `'<resource>:*'` is in the role's permission list → return `True` (resource-level wildcard)
     - Use `fnmatch` for any remaining `'<resource>:*'` patterns as fallback
   - `check_permission(user_id: int, tenant_id: int, resource: str, action: str) -> bool`:
     - Accept `(user_id, tenant_id, resource, action)` as specified in the issue body; skip DB lookup (no session available in the static context) and return `False` until a future DB-backed version is wired in

3. **Create `src/dependencies/rbac.py`**:
   - Import `require_auth` from `internal.middleware.fastapi_auth`, `ForbiddenException` from `pkg.errors.app_exceptions`, and `has_permission` from `services.permission_service`
   - Define `require_permission(resource: str, action: str)` returning a `Callable` compatible with `FastAPI.Depends`:
     - Inside the guard: read `AuthContext` via `require_auth`; if `ctx.roles` is empty or `None` → raise `ForbiddenException("权限不足")` with debug log
     - Iterate `ctx.roles` (a list of role names from the JWT payload); call `has_permission(role, resource, action)` on each; if any returns `True` → return `ctx`; if all return `False` → raise `ForbiddenException(f"权限不足: {resource}:{action}")`
   - Pattern follows the same `Callable` factory pattern used by `require_role` in [`src/dependencies/auth.py`](src/dependencies/auth.py) L57–L73

4. **Create `tests/unit/test_permission_service.py`**:
   - Test cases (≥ 9, matching dev-plan §6 acceptance criterion):
     1. `test_owner_star_allows_any` → `has_permission("owner", "anyresource", "anyaction") is True`
     2. `test_admin_exact_match` → `has_permission("admin", "customer", "read") is True`
     3. `test_admin_no_delete_for_viewer` → `has_permission("viewer", "customer", "delete") is False`
     4. `test_resource_wildcard` → `has_permission("support", "ticket", "delete")` with a `ticket:*` entry in support role → `True` (if role includes `ticket:*`)
     5. `test_unknown_role_returns_false` → `has_permission("nonexistent", "customer", "read") is False`
     6. `test_member_read_write` → `has_permission("member", "customer", "read") is True`
     7. `test_sales_opportunity_crud` → `has_permission("sales", "opportunity", "update") is True`
     8. `test_manager_no_delete` → `has_permission("manager", "customer", "delete") is False`
     9. `test_check_permission_static` → `check_permission(1, 1, "customer", "read")` returns `False` (static stub; covers the signature)
   - No database required; pure function tests only

5. **Create `tests/unit/test_require_permission.py`**:
   - Test cases (≥ 6):
     1. `test_permission_allowed_returns_ctx` — mock `require_auth` to return `AuthContext(user_id=1, tenant_id=1, roles=["admin"])`; decorator resolves to `ctx`
     2. `test_permission_denied_raises_forbidden` — same ctx with `roles=["viewer"]`; `has_permission("viewer", "customer", "delete")` is `False`; `ForbiddenException` raised
     3. `test_no_roles_raises_forbidden` — ctx with `roles=[]`; `ForbiddenException` raised
     4. `test_multiple_roles_one_has_permission` — ctx with `roles=["viewer", "admin"]`; `has_permission("admin", ...)` is `True`; returns ctx
     5. `test_tenant_id_none_raises_forbidden` — ctx with `tenant_id=None`; `ForbiddenException` raised
     6. `test_require_permission_returns_callable` — `require_permission("customer", "read")` returns a callable
   - Use `unittest.mock.patch` to patch `dependencies.rbac.require_auth`

## Test Plan

- Unit tests in `tests/unit/`: `test_permission_service.py` (9+ cases) + `test_require_permission.py` (6+ cases); both fully mock-free for the permission service layer; decorator tests use `unittest.mock.patch`
- Integration tests in `tests/integration/`: none (this is a pure-static service with no DB involvement)
- Dev-plan verification commands:
  - `ruff check src/services/permission_service.py src/dependencies/rbac.py` → 0 errors
  - `PYTHONPATH=src pytest tests/unit/test_permission_service.py -v` → ≥ 9 passed
  - `PYTHONPATH=src pytest tests/unit/test_require_permission.py -v` → ≥ 6 passed
  - `PYTHONPATH=src python -c "from services.permission_service import has_permission; print(has_permission('owner', 'foo', 'bar'))"` → `True`
  - `PYTHONPATH=src python -c "from services.permission_service import has_permission; print(has_permission('viewer', 'customer', 'delete'))"` → `False`
  - `PYTHONPATH=src python -c "from dependencies.rbac import require_permission; print('OK')"` → `OK`

## Acceptance Criteria

- `src/services/permission_service.py` exists with `ROLE_PERMISSIONS`, `has_permission()` (glob-aware), and `check_permission()` — the module imports without error
- `has_permission("owner", "anyresource", "anyaction")` returns `True`
- `has_permission("viewer", "customer", "delete")` returns `False`
- `has_permission("admin", "customer", "read")` returns `True`
- `has_permission("nonexistent", "customer", "read")` returns `False`
- `src/dependencies/rbac.py` exists; `require_permission("customer", "read")` returns a callable; calling it with a mocked `AuthContext(roles=["admin"])` returns that ctx without raising
- Calling it with `AuthContext(roles=["viewer"])` raises `ForbiddenException`
- `ruff check src/services/permission_service.py src/dependencies/rbac.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_permission_service.py tests/unit/test_require_permission.py -v` → ≥ 15 passed
