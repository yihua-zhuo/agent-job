"""
用户服务单元测试
"""
import pytest
from src.services.user_service import UserService, ValidationError
from src.models.user import User, UserRole, UserStatus
from src.models.response import ResponseStatus


class TestUserService:
    """用户服务测试"""
    
    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return UserService()
    
    @pytest.fixture
    def existing_user(self, service):
        """创建已有用户"""
        resp = service.create_user("existing", "existing@test.com", "Password123")
        return resp.data
    
    def test_create_user_success(self, service):
        resp = service.create_user("newuser", "new@test.com", "Password123")
        assert bool(resp) is True
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.data.username == "newuser"
        assert resp.data.email == "new@test.com"
        assert resp.data.id == 1
    
    def test_create_user_invalid_username(self, service):
        resp = service.create_user("ab", "test@test.com", "Password123")
        assert bool(resp) is False
        assert resp.status == ResponseStatus.VALIDATION_ERROR
        assert "username" in str(resp.errors[0])
    
    def test_create_user_invalid_email(self, service):
        resp = service.create_user("validname", "invalid-email", "Password123")
        assert bool(resp) is False
        assert resp.status == ResponseStatus.VALIDATION_ERROR
    
    def test_create_user_weak_password(self, service):
        resp = service.create_user("newuser", "new@test.com", "weak")
        assert bool(resp) is False
        assert resp.status == ResponseStatus.VALIDATION_ERROR
    
    def test_create_user_duplicate_username(self, service, existing_user):
        resp = service.create_user("existing", "another@test.com", "Password123")
        assert bool(resp) is False
        assert resp.errors[0].code == 2002
    
    def test_create_user_duplicate_email(self, service, existing_user):
        resp = service.create_user("another", "existing@test.com", "Password123")
        assert bool(resp) is False
        assert resp.errors[0].code == 2005
    
    def test_get_user_by_id(self, service, existing_user):
        user = service.get_user_by_id(1)
        assert user is not None
        assert user.username == "existing"
    
    def test_get_user_by_id_not_found(self, service):
        user = service.get_user_by_id(999)
        assert user is None
    
    def test_get_user_by_username(self, service, existing_user):
        user = service.get_user_by_username("existing")
        assert user is not None
        assert user.email == "existing@test.com"
    
    def test_get_user_by_email(self, service, existing_user):
        user = service.get_user_by_email("existing@test.com")
        assert user is not None
        assert user.username == "existing"
    
    def test_list_users(self, service, existing_user):
        resp = service.list_users()
        assert bool(resp) is True
        assert resp.data.total >= 1
        assert len(resp.data.items) >= 1
    
    def test_list_users_pagination(self, service):
        # 创建多个用户
        for i in range(25):
            service.create_user(f"user{i}", f"user{i}@test.com", "Password123")
        
        resp = service.list_users(page=1, page_size=10)
        assert len(resp.data.items) == 10
        assert resp.data.total == 25
        assert resp.data.total_pages == 3
        assert resp.data.has_next is True
        assert resp.data.has_prev is False
    
    def test_list_users_filter_by_role(self, service):
        service.create_user("admin", "admin@test.com", "Password123", role=UserRole.ADMIN)
        service.create_user("user1", "user1@test.com", "Password123", role=UserRole.USER)
        
        resp = service.list_users(role=UserRole.ADMIN)
        assert all(u.role == UserRole.ADMIN for u in resp.data.items)
    
    def test_update_user(self, service, existing_user):
        resp = service.update_user(1, bio="New bio", email="new@test.com")
        assert bool(resp) is True
        assert resp.data.bio == "New bio"
        assert resp.data.email == "new@test.com"
    
    def test_update_user_not_found(self, service):
        resp = service.update_user(999, bio="New bio")
        assert bool(resp) is False
        assert resp.errors[0].code == 2001
    
    def test_delete_user(self, service, existing_user):
        resp = service.delete_user(1)
        assert bool(resp) is True
        assert service.get_user_by_id(1) is None
    
    def test_delete_user_not_found(self, service):
        resp = service.delete_user(999)
        assert bool(resp) is False
    
    def test_search_users(self, service):
        service.create_user("john_doe", "john@test.com", "Password123")
        service.create_user("jane_doe", "jane@test.com", "Password123")
        service.create_user("alice", "alice@test.com", "Password123")
        
        resp = service.search_users("doe")
        assert resp.data.total == 2
    
    def test_change_password(self, service, existing_user):
        resp = service.change_password(1, "Password123", "NewPassword456")
        assert bool(resp) is True
    
    def test_change_password_weak_new(self, service, existing_user):
        resp = service.change_password(1, "Password123", "weak")
        assert bool(resp) is False
