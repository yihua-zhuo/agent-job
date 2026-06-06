"""Unit tests for RoleService.

Uses RBACMockState (auto-discovered by tests/unit/conftest._load_domain_handler_modules)
plus the user handler so the tenant-membership check in assign_role_to_user
can query ``from users`` and filter by tenant_id.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pkg.errors.app_exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from services.rbac_service import DEFAULT_PERMISSIONS
from services.role_service import RoleService
from tests.unit.conftest import make_mock_session
from tests.unit.domain_handlers.rbac import RBACMockState, get_handlers
from tests.unit.domain_handlers.users import make_user_handler


def _now() -> datetime:
    return datetime.now(UTC)


def _seed_role(
    state: RBACMockState,
    role_id: int,
    *,
    tenant_id: int,
    name: str,
    display_name: str | None = None,
    is_system: bool = False,
    priority: int = 0,
) -> None:
    state.roles[role_id] = {
        "id": role_id,
        "tenant_id": tenant_id,
        "name": name,
        "display_name": display_name or name,
        "description": "",
        "is_system": is_system,
        "priority": priority,
        "created_at": _now(),
    }


@pytest.fixture
def state() -> RBACMockState:
    return RBACMockState()


@pytest.fixture
def mock_db_session(state: RBACMockState):
    return make_mock_session(
        [*get_handlers(state), make_user_handler(state)],
        state=state,
    )


@pytest.fixture
def role_service(mock_db_session):
    return RoleService(mock_db_session)


class TestListRoles:
    async def test_list_roles_returns_tenant_and_system_roles(self, role_service, state):
        _seed_role(
            state,
            900,
            tenant_id=1,
            name="custom_tenant_role",
            display_name="Custom Tenant Role",
        )
        roles = await role_service.list_roles(tenant_id=1)
        names = {r.name for r in roles}
        assert "admin" in names
        assert "custom_tenant_role" in names

    async def test_list_roles_excludes_other_tenant_roles(self, role_service, state):
        _seed_role(
            state,
            901,
            tenant_id=2,
            name="tenant2_only",
            display_name="Tenant 2 Only",
        )
        roles = await role_service.list_roles(tenant_id=1)
        names = {r.name for r in roles}
        assert "tenant2_only" not in names


class TestCreateCustomRole:
    async def test_create_custom_role_persists_role_and_permission_links(
        self, role_service, state
    ):
        role = await role_service.create_custom_role(
            tenant_id=1,
            name="custom_support",
            permissions=["customer:read", "opportunity:read"],
        )
        assert role.name == "custom_support"
        assert role.is_system is False
        assert role.tenant_id == 1
        assert any(r["name"] == "custom_support" for r in state.roles.values())
        perm_names_for_role = {
            state.permissions[rp["permission_id"]]["name"]
            for rp in state.role_permissions
            if rp["role_id"] == role.id
        }
        assert "customer:read" in perm_names_for_role
        assert "opportunity:read" in perm_names_for_role

    async def test_create_custom_role_raises_conflict_on_duplicate_name(self, role_service):
        await role_service.create_custom_role(
            tenant_id=1, name="dup_role", permissions=["customer:read"]
        )
        with pytest.raises(ConflictException):
            await role_service.create_custom_role(
                tenant_id=1, name="dup_role", permissions=["customer:read"]
            )

    async def test_create_custom_role_raises_validation_on_unknown_permission(self, role_service):
        with pytest.raises(ValidationException):
            await role_service.create_custom_role(
                tenant_id=1,
                name="bad_perms_role",
                permissions=["customer:read", "nonexistent:perm"],
            )

    async def test_create_custom_role_allows_duplicate_name_in_different_tenants(
        self, role_service
    ):
        await role_service.create_custom_role(
            tenant_id=1, name="shared_name", permissions=["customer:read"]
        )
        role2 = await role_service.create_custom_role(
            tenant_id=2, name="shared_name", permissions=["customer:read"]
        )
        assert role2.tenant_id == 2


class TestGetRolePermissions:
    async def test_get_role_permissions_returns_name_list(self, role_service, state):
        custom_id = 960
        _seed_role(
            state,
            custom_id,
            tenant_id=1,
            name="perms_test",
            display_name="Perms Test",
        )
        state.role_permissions.append(
            {"id": 9001, "role_id": custom_id, "permission_id": 2}
        )
        state.role_permissions.append(
            {"id": 9002, "role_id": custom_id, "permission_id": 6}
        )
        perms = await role_service.get_role_permissions(role_id=custom_id, tenant_id=1)
        assert isinstance(perms, list)
        assert all(isinstance(p, str) for p in perms)
        assert "customer:read" in perms
        assert "opportunity:read" in perms

    async def test_get_role_permissions_raises_not_found_for_unknown_role(self, role_service):
        with pytest.raises(NotFoundException):
            await role_service.get_role_permissions(role_id=99999, tenant_id=1)


class TestUpdateRolePermissions:
    async def test_update_role_permissions_blocks_system_role(self, role_service):
        with pytest.raises(ForbiddenException):
            await role_service.update_role_permissions(
                role_id=1,
                tenant_id=1,
                permissions=["customer:read"],
            )

    async def test_update_role_permissions_replaces_existing_links(self, role_service, state):
        custom_id = 950
        _seed_role(
            state,
            custom_id,
            tenant_id=1,
            name="replaceable",
            display_name="Replaceable",
        )
        # Use reserved id range (>=9000) to avoid colliding with
        # state.role_permissions_next_id auto-increment.
        state.role_permissions.append(
            {"id": 9003, "role_id": custom_id, "permission_id": 1}
        )
        state.role_permissions.append(
            {"id": 9004, "role_id": custom_id, "permission_id": 2}
        )
        before = [rp for rp in state.role_permissions if rp["role_id"] == custom_id]
        assert len(before) == 2

        await role_service.update_role_permissions(
            role_id=custom_id,
            tenant_id=1,
            permissions=["customer:read"],
        )
        remaining = {rp["permission_id"] for rp in state.role_permissions if rp["role_id"] == custom_id}
        assert remaining == {2}
        assert len([rp for rp in state.role_permissions if rp["role_id"] == custom_id]) == 1

    async def test_update_role_permissions_raises_validation_on_unknown_permission(
        self, role_service, state
    ):
        custom_id = 951
        _seed_role(
            state,
            custom_id,
            tenant_id=1,
            name="custom_for_val",
            display_name="Custom For Val",
        )
        with pytest.raises(ValidationException):
            await role_service.update_role_permissions(
                role_id=custom_id,
                tenant_id=1,
                permissions=["fake:perm"],
            )


class TestAssignRoleToUser:
    async def test_assign_role_to_user_checks_tenant_membership(
        self, role_service, state
    ):
        state.users[42] = {
            "id": 42,
            "tenant_id": 99,
            "username": "other_tenant_user",
            "email": "x@x.com",
            "password_hash": None,
            "role": "user",
            "status": "active",
            "full_name": None,
            "bio": None,
            "created_at": None,
            "updated_at": None,
        }
        with pytest.raises(NotFoundException):
            await role_service.assign_role_to_user(
                user_id=42, role_id=1, tenant_id=1, granted_by=0
            )

    async def test_assign_role_to_user_is_idempotent(self, role_service, state):
        state.users[10] = {
            "id": 10,
            "tenant_id": 1,
            "username": "tenant1_user",
            "email": "t@t.com",
            "password_hash": None,
            "role": "user",
            "status": "active",
            "full_name": None,
            "bio": None,
            "created_at": None,
            "updated_at": None,
        }
        first = await role_service.assign_role_to_user(
            user_id=10, role_id=2, tenant_id=1, granted_by=0
        )
        assert first.get("already_assigned") is not True
        second = await role_service.assign_role_to_user(
            user_id=10, role_id=2, tenant_id=1, granted_by=0
        )
        assert second.get("already_assigned") is True

    async def test_assign_role_to_user_raises_not_found_for_unknown_role(
        self, role_service, state
    ):
        state.users[11] = {
            "id": 11,
            "tenant_id": 1,
            "username": "u11",
            "email": "u@t.com",
            "password_hash": None,
            "role": "user",
            "status": "active",
            "full_name": None,
            "bio": None,
            "created_at": None,
            "updated_at": None,
        }
        with pytest.raises(NotFoundException):
            await role_service.assign_role_to_user(
                user_id=11, role_id=99999, tenant_id=1, granted_by=0
            )


class TestListAllPermissions:
    async def test_list_all_permissions_returns_resource_action_pairs(self, role_service):
        perms = await role_service.list_all_permissions()
        assert len(perms) == len(DEFAULT_PERMISSIONS)
        for entry in perms:
            assert set(entry.keys()) == {"resource", "action"}
            assert isinstance(entry["resource"], str)
            assert isinstance(entry["action"], str)
            assert entry["resource"] != ""
            assert entry["action"] != ""

    async def test_list_all_permissions_matches_default_permissions(self, role_service):
        perms = await role_service.list_all_permissions()
        expected_names = {p[0] for p in DEFAULT_PERMISSIONS}
        actual_names = {f"{p['resource']}:{p['action']}" for p in perms}
        assert actual_names == expected_names
