"""Unit tests for UserService."""
import pytest
from services.user_service import UserService


@pytest.fixture
def service():
    return UserService()


@pytest.mark.asyncio
class TestUserService:
    async def test_create_user_success(self, service):
        result = await service.create_user({
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "role": "agent",
        })
        assert bool(result) is True
        assert result.data["username"] == "testuser"

    async def test_create_user_invalid_username(self, service):
        result = await service.create_user({
            "username": "ab",  # too short
            "email": "test@example.com",
            "password": "SecurePass123!",
        })
        assert bool(result) is False

    async def test_create_user_invalid_email(self, service):
        result = await service.create_user({
            "username": "validuser",
            "email": "not-an-email",
            "password": "SecurePass123!",
        })
        assert bool(result) is False

    async def test_create_user_weak_password(self, service):
        result = await service.create_user({
            "username": "validuser",
            "email": "test@example.com",
            "password": "weak",
        })
        assert bool(result) is False

    async def test_create_user_duplicate_username(self, service):
        await service.create_user({
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "SecurePass123!",
        })
        dup = await service.create_user({
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "SecurePass123!",
        })
        assert bool(dup) is False

    async def test_create_user_duplicate_email(self, service):
        await service.create_user({
            "username": "user1",
            "email": "dup@example.com",
            "password": "SecurePass123!",
        })
        dup = await service.create_user({
            "username": "user2",
            "email": "dup@example.com",
            "password": "SecurePass123!",
        })
        assert bool(dup) is False

    async def test_get_user_by_id(self, service):
        create = await service.create_user({
            "username": "gettest",
            "email": "gettest@example.com",
            "password": "SecurePass123!",
        })
        uid = create.data["id"]
        result = await service.get_user_by_id(uid)
        assert bool(result) is True
        assert result.data["username"] == "gettest"

    async def test_get_user_by_id_not_found(self, service):
        result = await service.get_user_by_id(99999)
        assert bool(result) is False

    async def test_get_user_by_username(self, service):
        await service.create_user({
            "username": "findme",
            "email": "findme@example.com",
            "password": "SecurePass123!",
        })
        result = await service.get_user_by_username("findme")
        assert bool(result) is True
        assert result.data["username"] == "findme"

    async def test_get_user_by_email(self, service):
        await service.create_user({
            "username": "emailtest",
            "email": "emailtest@example.com",
            "password": "SecurePass123!",
        })
        result = await service.get_user_by_email("emailtest@example.com")
        assert bool(result) is True
        assert result.data["email"] == "emailtest@example.com"

    async def test_list_users(self, service):
        result = await service.list_users()
        assert bool(result) is True
        assert result.data.total >= 0

    async def test_list_users_pagination(self, service):
        for i in range(3):
            await service.create_user({
                "username": f"pageuser{i}",
                "email": f"page{i}@example.com",
                "password": "SecurePass123!",
            })
        result = await service.list_users(page=1, page_size=2)
        assert bool(result) is True
        assert len(result.data.items) == 2
        assert result.data.total >= 3

    async def test_list_users_filter_by_role(self, service):
        await service.create_user({
            "username": "adminuser",
            "email": "admin@example.com",
            "password": "SecurePass123!",
            "role": "admin",
        })
        result = await service.list_users(role="admin")
        assert bool(result) is True
        assert all(u["role"] == "admin" for u in result.data.items)

    async def test_update_user(self, service):
        create = await service.create_user({
            "username": "updateme",
            "email": "update@example.com",
            "password": "SecurePass123!",
        })
        uid = create.data["id"]
        result = await service.update_user(uid, {"display_name": "Updated Name"})
        assert bool(result) is True
        assert result.data["display_name"] == "Updated Name"

    async def test_update_user_not_found(self, service):
        result = await service.update_user(99999, {"display_name": "X"})
        assert bool(result) is False

    async def test_delete_user(self, service):
        create = await service.create_user({
            "username": "deleteme",
            "email": "delete@example.com",
            "password": "SecurePass123!",
        })
        uid = create.data["id"]
        result = await service.delete_user(uid)
        assert bool(result) is True
        gone = await service.get_user_by_id(uid)
        assert bool(gone) is False

    async def test_delete_user_not_found(self, service):
        result = await service.delete_user(99999)
        assert bool(result) is False

    async def test_search_users(self, service):
        await service.create_user({
            "username": "searchtarget",
            "email": "search@example.com",
            "password": "SecurePass123!",
        })
        result = await service.search_users("search")
        assert bool(result) is True

    async def test_change_password(self, service):
        create = await service.create_user({
            "username": "pwchange",
            "email": "pwchange@example.com",
            "password": "OldPass123!",
        })
        uid = create.data["id"]
        result = await service.change_password(
            uid, old_password="OldPass123!", new_password="NewPass456!"
        )
        assert bool(result) is True

    async def test_change_password_weak_new(self, service):
        create = await service.create_user({
            "username": "pwweak",
            "email": "pwweak@example.com",
            "password": "OldPass123!",
        })
        uid = create.data["id"]
        result = await service.change_password(uid, old_password="OldPass123!", new_password="x")
        assert bool(result) is False
