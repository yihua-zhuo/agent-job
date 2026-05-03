"""
用户模型单元测试
"""
import pytest
from datetime import datetime
from src.models.user import User, UserRole, UserStatus, Role


class TestUserModel:
    """用户模型测试"""

    def test_create_user_with_defaults(self):
        user = User(username="testuser", email="test@example.com")
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == Role.USER
        assert user.status == UserStatus.PENDING
        assert user.id is None
        assert user.tags == []
        assert user.created_at is not None

    def test_create_user_with_all_fields(self):
        user = User(
            id=1,
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            bio="Test bio"
        )
        assert user.id == 1
        assert user.username == "admin"
        assert user.role == UserRole.ADMIN
        assert user.status == UserStatus.ACTIVE
        assert user.bio == "Test bio"

    def test_is_active(self):
        active_user = User(username="user1", email="u1@example.com", status=UserStatus.ACTIVE)
        pending_user = User(username="user2", email="u2@example.com", status=UserStatus.PENDING)
        banned_user = User(username="user3", email="u3@example.com", status=UserStatus.BANNED)

        assert active_user.is_active_user() is True
        assert pending_user.is_active_user() is False
        assert banned_user.is_active_user() is False

    def test_has_permission(self):
        admin = User(username="admin", email="a@example.com", role=UserRole.ADMIN)
        user = User(username="user", email="u@example.com", role=UserRole.USER)

        assert admin.has_permission(UserRole.USER) is True
        assert admin.has_permission(UserRole.ADMIN) is True
        assert user.has_permission(UserRole.USER) is True
        assert user.has_permission(UserRole.ADMIN) is False

    def test_to_dict(self):
        user = User(id=1, username="test", email="test@example.com", role=UserRole.USER)
        user_dict = user.to_dict()

        assert user_dict["id"] == 1
        assert user_dict["username"] == "test"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["role"] == "user"
        assert user_dict["status"] == "pending"

    def test_from_dict(self):
        data = {
            "id": 1,
            "username": "test",
            "email": "test@example.com",
            "role": "admin",
            "status": "active"
        }
        user = User.from_dict(data)

        assert user.id == 1
        assert user.username == "test"
        assert user.role == UserRole.ADMIN
        assert user.status == UserStatus.ACTIVE

    def test_user_tags(self):
        user = User(username="test", email="test@example.com", tags=["python", "ai"])
        assert len(user.tags) == 2
        assert "python" in user.tags


class TestUserRole:
    """用户角色测试"""

    def test_role_values(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.GUEST.value == "guest"


class TestUserStatus:
    """用户状态测试"""

    def test_status_values(self):
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.INACTIVE.value == "inactive"
        assert UserStatus.BANNED.value == "banned"
        assert UserStatus.PENDING.value == "pending"
