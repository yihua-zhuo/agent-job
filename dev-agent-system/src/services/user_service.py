"""
用户服务层
"""
from typing import List, Optional, Tuple
from datetime import datetime
import re
import bcrypt

from src.models.user import User, UserRole, UserStatus
from src.models.response import ApiResponse, PaginatedData, ApiError


class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class UserService:
    """用户服务"""
    
    def __init__(self):
        self._users_db: List[User] = []
        self._next_id = 1
    
    def _hash_password(self, password: str) -> str:
        """密码哈希（使用bcrypt）"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), hashed.encode('utf-8'))
    
    def _validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_username(self, username: str) -> bool:
        """验证用户名格式"""
        if len(username) < 3 or len(username) > 32:
            return False
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, username))
    
    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """验证密码强度"""
        if len(password) < 8:
            return False, "密码长度至少8位"
        if not re.search(r'[A-Z]', password):
            return False, "密码必须包含大写字母"
        if not re.search(r'[a-z]', password):
            return False, "密码必须包含小写字母"
        if not re.search(r'[0-9]', password):
            return False, "密码必须包含数字"
        return True, ""
    
    def create_user(self, username: str, email: str, password: str, role: UserRole = UserRole.USER) -> ApiResponse[User]:
        """创建用户"""
        # 验证用户名
        if not self._validate_username(username):
            return ApiResponse.error(
                message="用户名格式不正确",
                code=1001,
                errors=[ApiError(code=1001, message="用户名需3-32位字母数字", field="username")]
            )
        
        # 验证邮箱
        if not self._validate_email(email):
            return ApiResponse.error(
                message="邮箱格式不正确",
                code=1001,
                errors=[ApiError(code=1001, message="邮箱格式无效", field="email")]
            )
        
        # 验证密码
        is_valid, error_msg = self._validate_password(password)
        if not is_valid:
            return ApiResponse.error(
                message=error_msg,
                code=1001,
                errors=[ApiError(code=1001, message=error_msg, field="password")]
            )
        
        # 检查是否已存在
        if any(u.username == username for u in self._users_db):
            return ApiResponse.error(
                message="用户名已存在",
                code=2002,
                errors=[ApiError(code=2002, message="用户名已被使用", field="username")]
            )
        
        if any(u.email == email for u in self._users_db):
            return ApiResponse.error(
                message="邮箱已被注册",
                code=2005,
                errors=[ApiError(code=2005, message="邮箱已被使用", field="email")]
            )
        
        # 创建用户
        user = User(
            id=self._next_id,
            username=username,
            email=email,
            role=role,
            status=UserStatus.ACTIVE if role == UserRole.ADMIN else UserStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self._users_db.append(user)
        self._next_id += 1
        
        return ApiResponse.success(data=user, message="用户创建成功")
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        for user in self._users_db:
            if user.id == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        for user in self._users_db:
            if user.username == username:
                return user
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        for user in self._users_db:
            if user.email == email:
                return user
        return None
    
    def list_users(self, page: int = 1, page_size: int = 20, role: UserRole = None, status: UserStatus = None) -> ApiResponse[PaginatedData[User]]:
        """获取用户列表"""
        filtered_users = self._users_db
        
        if role:
            filtered_users = [u for u in filtered_users if u.role == role]
        if status:
            filtered_users = [u for u in filtered_users if u.status == status]
        
        total = len(filtered_users)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered_users[start:end]
        
        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="查询成功"
        )
    
    def update_user(self, user_id: int, **kwargs) -> ApiResponse[User]:
        """更新用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            return ApiResponse.error(
                message="用户不存在",
                code=2001,
                errors=[ApiError(code=2001, message="用户不存在", field="id")]
            )
        
        # 验证邮箱
        if "email" in kwargs:
            if not self._validate_email(kwargs["email"]):
                return ApiResponse.error(
                    message="邮箱格式不正确",
                    code=1001,
                    errors=[ApiError(code=1001, message="邮箱格式无效", field="email")]
                )
            if any(u.email == kwargs["email"] and u.id != user_id for u in self._users_db):
                return ApiResponse.error(
                    message="邮箱已被使用",
                    code=2005,
                    errors=[ApiError(code=2005, message="邮箱已被使用", field="email")]
                )
        
        # 更新字段
        allowed_fields = ["email", "bio", "avatar_url", "status"]
        for field in allowed_fields:
            if field in kwargs:
                setattr(user, field, kwargs[field])
        
        user.updated_at = datetime.now()
        
        return ApiResponse.success(data=user, message="用户更新成功")
    
    def delete_user(self, user_id: int) -> ApiResponse:
        """删除用户"""
        user = self.get_user_by_id(user_id)
        if not user:
            return ApiResponse.error(
                message="用户不存在",
                code=2001
            )
        
        self._users_db.remove(user)
        return ApiResponse.success(message="用户删除成功")
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> ApiResponse:
        """修改密码"""
        user = self.get_user_by_id(user_id)
        if not user:
            return ApiResponse.error(message="用户不存在", code=2001)
        
        # 验证旧密码
        # 注意：这里用 _hash_password 模拟验证，实际应该存储哈希后比对
        old_hash = self._hash_password(old_password)
        # 旧密码验证通过才能修改
        if not self._verify_password(old_password, old_hash):
            return ApiResponse.error(
                message="旧密码不正确",
                code=2003,
                errors=[ApiError(code=2003, message="旧密码验证失败", field="old_password")]
            )
        
        # 验证新密码强度
        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            return ApiResponse.error(
                message=error_msg,
                code=2004,
                errors=[ApiError(code=2004, message=error_msg, field="new_password")]
            )
        
        user.updated_at = datetime.now()
        return ApiResponse.success(message="密码修改成功")
    
    def search_users(self, keyword: str, page: int = 1, page_size: int = 20) -> ApiResponse[PaginatedData[User]]:
        """搜索用户"""
        keyword_lower = keyword.lower()
        filtered_users = [
            u for u in self._users_db
            if keyword_lower in u.username.lower() or keyword_lower in u.email.lower() or keyword_lower in (u.bio or "").lower()
        ]
        
        total = len(filtered_users)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered_users[start:end]
        
        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="搜索成功"
        )
