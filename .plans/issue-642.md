I now have full context. Let me write the implementation plan.

# Implementation Plan — Issue #642

## Goal

Create a `RoleService` and a 6-endpoint HTTP API for role and permission management under `/api/v1/rbac/`, enabling tenant administrators to list/create custom roles, manage role-to-permission assignments, assign roles to users, and enumerate all available system permissions. The endpoints in the dev-plan overlap significantly with the existing `RBACService` / `rbac_router` (introduced by #641) — the existing code already covers most endpoints. The new `RoleService` will be a thin facade that re-uses the existing DB-backed models (`RoleModel`, `PermissionModel`, `RolePermissionModel`, `UserRoleModel`) rather than introducing a new JSONB column design, and a new `RoleManagementRouter` in `src/api/routers/rbac.py` will expose the six endpoints described in the issue body, aligning with the path/method shape the issue requires.

## Source Contract

Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0642-add-role-and-permission-management-api-endpoints.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/70-platform/0642-add-role-and-permission-management-api-endpoints.md`

## Affected Files

- `src/services/role_service.py` — **new**: `RoleService` class providing six methods (`list_roles`, `create_custom_role`, `get_role_permissions`, `update_role_permissions`, `assign_role_to_user`, `list_all_permissions`). Delegates the heavy lifting to existing `RBACService` or to direct ORM queries on `RoleModel` / `PermissionModel` / `RolePermissionModel` / `UserRoleModel`.
- `src/api/routers/rbac.py` — **modify**: add a `RoleManagementRouter` (`APIRouter` with prefix `/api/v1/rbac`, tags `["rbac-roles"]`) containing the six endpoints the issue specifies. The existing `rbac_router` stays untouched (it was created by #641 and serves a different granularity of endpoints).
- `src/dependencies/rbac.py` — **read only**: `require_permission(resource, action)` already exists and is used to gate admin+ endpoints.
- `tests/unit/test_role_service.py` — **new**: unit tests for all six `RoleService` methods.
- `tests/integration/test_rbac_integration.py` — **new**: end-to-end HTTP tests against the real Postgres-backed FastAPI app.

## Implementation Steps

1. **Create `src/services/role_service.py`** with `RoleService`:
   - `__init__(self, session: AsyncSession)` — no default, per CLAUDE.md §Service Pattern.
   - `list_roles(tenant_id: int) -> list[RoleModel]` — returns roles where `tenant_id == tenant_id OR tenant_id == 0` (system roles visible to all tenants), ordered by `priority DESC, id ASC`.
   - `create_custom_role(tenant_id: int, name: str, permissions: list[str]) -> RoleModel` — creates a non-system role (`is_system=False`) and assigns the given permission names via `RolePermissionModel` rows. Raises `ValidationException` if any permission name does not exist in `PermissionModel`. Raises `ConflictException` if a role with the same `name` already exists for the tenant.
   - `get_role_permissions(role_id: int, tenant_id: int) -> list[str]` — returns permission name strings (not ORM objects) for the given role, scoped to the tenant or system (`tenant_id == 0`).
   - `update_role_permissions(role_id: int, tenant_id: int, permissions: list[str]) -> RoleModel` — replaces `RolePermissionModel` rows for the role. Raises `ForbiddenException` if `role.is_system == True`. Raises `ValidationException` if any permission name is unknown.
   - `assign_role_to_user(user_id: int, role_id: int, tenant_id: int, granted_by: int) -> dict` — validates the user exists in the tenant, validates the role exists for the tenant or system, then inserts a `UserRoleModel` row (idempotent: if already assigned, returns `{"already_assigned": True}`).
   - `list_all_permissions() -> list[dict[str, str]]` — returns the static `DEFAULT_PERMISSIONS` list from `services.rbac_service` as `[{"resource": ..., "action": ...}, ...]` pairs derived from the permission name `resource:action` format.
   - Internal helpers: `_permission_pairs()` to derive `[{resource, action}]` from the permission name string by splitting on `:`.

2. **Modify `src/api/routers/rbac.py`** to add a `RoleManagementRouter`:
   - Define `role_management_router = APIRouter(prefix="/api/v1/rbac", tags=["rbac-roles"])`.
   - `GET /roles` — calls `RoleService.list_roles(ctx.tenant_id)`, returns `{"success": True, "data": {"items": [r.to_dict() for r in roles], "total": len(roles)}}`.
   - `POST /roles` — Pydantic body `CreateRoleRequest { name: str, permissions: list[str] }`. Gated with `Depends(require_permission("admin", "all"))` (admin+ only). Calls `RoleService.create_custom_role`.
   - `GET /roles/{role_id}/permissions` — returns `{"success": True, "data": {"role_id": role_id, "permissions": [...]}}`.
   - `PUT /roles/{role_id}/permissions` — body `UpdatePermissionsRequest { permissions: list[str] }`. Gated with `Depends(require_permission("admin", "all"))`. Calls `RoleService.update_role_permissions`.
   - `POST /users/{user_id}/role` — body `AssignRoleRequest { role_id: int }`. Gated with `Depends(require_permission("admin", "all"))`. Calls `RoleService.assign_role_to_user`.
   - `GET /permissions` — returns `{"success": True, "data": [{"resource": ..., "action": ...}, ...]}`.
   - All routes inject `ctx: AuthContext = Depends(require_auth)` and `session: AsyncSession = Depends(get_db)`.
   - Discovery note: `src/api/__init__.py::iter_routers()` yields all `APIRouter` instances whose attribute name is `router` or ends with `_router`. Since `rbac_router` (existing) and `role_management_router` (new) both use the prefix `/api/v1/rbac`, FastAPI will route them independently by the unique path/method pairs. No changes to `src/main.py` are required — the auto-discovery picks up both routers.

3. **Add `tests/unit/test_role_service.py`** with `mock_db_session` fixture using `RBACMockState` and the auto-discovered handlers:
   - `test_list_roles_returns_tenant_and_system_roles` — seed tenant-specific role + system role, verify both appear.
   - `test_create_custom_role_persists_role_and_permission_links` — call `create_custom_role`, verify `state.roles` and `state.role_permissions` updated.
   - `test_create_custom_role_raises_conflict_on_duplicate_name` — second call with same name raises `ConflictException`.
   - `test_create_custom_role_raises_validation_on_unknown_permission` — pass `["nonexistent:perm"]`, expect `ValidationException`.
   - `test_get_role_permissions_returns_name_list` — verify return type is `list[str]`, not ORM objects.
   - `test_update_role_permissions_blocks_system_role` — call on `is_system=True` role, expect `ForbiddenException`.
   - `test_update_role_permissions_replaces_existing_links` — verify old `role_permissions` rows for the role are deleted before new ones inserted.
   - `test_assign_role_to_user_checks_tenant_membership` — seed user in a different tenant, expect `NotFoundException("用户")`.
   - `test_assign_role_to_user_is_idempotent` — call twice, second returns `{"already_assigned": True}`.
   - `test_list_all_permissions_returns_resource_action_pairs` — verify every entry is `{"resource": str, "action": str}` with non-empty values.

4. **Add `tests/integration/test_rbac_integration.py`** using the real `api_client` fixture (which includes `auth_headers_web` for a seeded admin user):
   - `test_list_roles_returns_empty_initially` — `GET /api/v1/rbac/roles` → `data.items == []`.
   - `test_create_role_then_list_includes_it` — `POST /api/v1/rbac/roles` with `{"name": "custom_support", "permissions": ["customer:read"]}` → 201, then `GET` shows it.
   - `test_create_role_with_unknown_permission_returns_422` — body includes `["fake:perm"]` → 422.
   - `test_update_role_permissions_replaces_existing` — `PUT` new list, `GET` confirms replacement.
   - `test_update_system_role_permissions_returns_403` — try to update `admin` (system role) → 403.
   - `test_assign_role_to_user_persists_binding` — `POST /api/v1/rbac/users/{uid}/role` with `{"role_id": 2}` → 200; then `GET /api/v1/rbac/users/{uid}/roles` (existing endpoint) shows the binding.
   - `test_list_permissions_returns_all_system_pairs` — `GET /api/v1/rbac/permissions` → ≥ 6 pairs, all `resource`/`action` non-empty.
   - `test_tenant_isolation_roles` — create role in tenant 1, switch to `api_client_tenant_2`, verify `GET /roles` does not show tenant 1's custom role (only system roles shared via `tenant_id == 0`).

## Test Plan

- Unit tests in `tests/unit/test_role_service.py`: mock DB via `make_mock_session` + `RBACMockState` (auto-loaded from `tests/unit/domain_handlers/rbac.py`). Covers all six service methods across success, tenant-isolation, conflict, validation, and forbidden paths. Expected: `PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → ≥ 10 passed.
- Integration tests in `tests/integration/test_rbac_integration.py`: uses `api_client`, `auth_headers_web`, `api_client_tenant_2`, `db_schema`, `async_session` fixtures from `tests/integration/conftest.py`. Verifies HTTP round-trip including 201/200/403/422 status codes, envelope shape, and cross-tenant data isolation. Expected: `PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → ≥ 8 passed.
- Dev-plan verification (§6): the target board lists these checks:
  - `ruff check src/services/role_service.py src/api/routers/rbac.py` → 0 errors.
  - `PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → 6+ passed.
  - `PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → 6+ passed.
  - `PYTHONPATH=src mypy src/services/role_service.py src/api/routers/rbac.py` → 0 errors.
  - `curl http://localhost:8000/api/v1/rbac/permissions` → `{"success": true, "data": [...]}`.

## Acceptance Criteria

- `ruff check src/services/role_service.py src/api/routers/rbac.py` → 0 errors.
- `PYTHONPATH=src pytest tests/unit/test_role_service.py -v` → all tests passed.
- `PYTHONPATH=src pytest tests/integration/test_rbac_integration.py -v` → all tests passed.
- `GET /api/v1/rbac/roles` returns 200 with `{"success": true, "data": {"items": [...], "total": N}}` envelope.
- `POST /api/v1/rbac/roles` with admin auth returns 201; without admin role returns 403.
- `GET /api/v1/rbac/roles/{id}/permissions` returns `{"success": true, "data": {"role_id": id, "permissions": [string...]}}`.
- `PUT /api/v1/rbac/roles/{id}/permissions` on a system role returns 403; on a custom role returns 200.
- `POST /api/v1/rbac/users/{id}/role` returns 200 with `{"success": true, "data": {"user_id": id, "role_id": id}}`.
- `GET /api/v1/rbac/permissions` returns 200 with `{"success": true, "data": [{"resource": ..., "action": ...}, ...]}` containing all 15 permissions from `DEFAULT_PERMISSIONS`.
- All SQL queries filter by `tenant_id`; cross-tenant roles are not visible in `GET /roles`.

## Risks / Open Questions

- **Path collision with existing `rbac_router`**: Both `rbac_router` (from #641, prefix `/api/v1/rbac`) and the new `role_management_router` use the same prefix. FastAPI handles this by matching the first registered router that owns a given path+method pair. The existing `rbac_router` registers paths like `POST /roles`, `GET /roles/{role_id}`, `PUT /roles/{role_id}` — the new router must not duplicate these. The six endpoints in the issue body map to paths that are already covered by the existing router (`GET /roles`, `POST /roles`, `GET /roles/{id}/permissions`, `PUT /roles/{id}/permissions`, `POST /users/{id}/roles` vs issue's `POST /users/{id}/role`, `GET /permissions`). This raises a real risk: the new endpoints will conflict with existing ones, causing FastAPI to raise `AssertionError: route conflict` at startup. **Mitigation**: Register `role_management_router` with the same prefix only if path/method pairs are genuinely new; otherwise, the existing `rbac_router` already satisfies the issue. If a separate `RoleManagementRouter` is mandated by the issue contract, paths must be differentiated (e.g., add a `/v2/` or distinct prefix), or the new router should only add genuinely new routes not covered by `rbac_router` (e.g., `GET /permissions` is the only one not present in `rbac_router` since it lists `PermissionModel` paginated, not resource/action pairs).
- **`@require_permission` gate semantics**: The existing `require_permission(resource, action)` dependency checks `ctx.roles` (a list of role names like `"admin"`, `"viewer"`) against `ROLE_PERMISSIONS` from `permission_service.py`. It does not consult the DB-backed `UserRoleModel` assignments. So a user assigned a custom role at runtime via the new `POST /users/{id}/role` endpoint will not be granted `admin:all` permission through the `require_permission` guard. This is a pre-existing limitation in the auth flow (not caused by this issue) but the dev-plan's claim that admin+ endpoints are protected by `@require_permission` is only true for users whose JWT contains `"admin"` in `roles` — not for users who get admin via the DB-backed custom-role mechanism.
