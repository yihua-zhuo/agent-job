"""
用户服务层 — async PostgreSQL implementation via SQLAlchemy.
"""
from __future__ import annotations

import re
from datetime import datetime, UTC
from typing import Optional, Tuple

import bcrypt
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import UserModel
from models.user import User, UserRole, UserStatus
from models.response import ApiResponse, PaginatedData, ApiError


class ValidationError(Exception):
    """验证错误异常"""

    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


def _row_to_user(row: UserModel) -> User:
    """Convert a UserModel ORM row to the domain User dataclass."""
    return User(
        id=row.id,
        tenant_id=row.tenant_id,
        username=row.username,
        email=row.email,
        role=UserRole(row.role),
        status=UserStatus(row.status),
        full_name=row.full_name,
        bio=row.bio,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class UserService:
    """用户服务 — async PostgreSQL backend."""

    def __init__(self, session: AsyncSession = None):
        self.session = session
        if session is not None:
            self._require_session()

    def _require_session(self):
        if self.session is None:
            raise TypeError(
                f"{self.__class__.__name__} requires an injected AsyncSession; "
                "construct with XxxService(async_session)."
            )

    # ------------------------------------------------------------------
    # Validation helpers (unchanged from original)
    # ------------------------------------------------------------------

    def _hash_password(self, password: str) -> str:
        """密码哈希(使用bcrypt)"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), hashed.encode("utf-8"))

    def _validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _validate_username(self, username: str) -> bool:
        """验证用户名格式"""
        if len(username) < 3 or len(username) > 32:
            return False
        pattern = r"^[a-zA-Z0-9_-]+$"
        return bool(re.match(pattern, username))

    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """验证密码强度"""
        if len(password) < 8:
            return False, "密码长度至少8位"
        if not re.search(r"[A-Z]", password):
            return False, "密码必须包含大写字母"
        if not re.search(r"[a-z]", password):
            return False, "密码必须包含小写字母"
        if not re.search(r"[0-9]", password):
            return False, "密码必须包含数字"
        return True, ""

    # ------------------------------------------------------------------
    # Service methods — all async
    # ------------------------------------------------------------------

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
        tenant_id: int = 0,
        full_name: Optional[str] = None,
        **kwargs,
    ) -> ApiResponse[User]:
        """创建用户"""

        # Validate username
        if not self._validate_username(username):
            return ApiResponse.error(
                message="用户名格式不正确",
                code=1001,
                errors=[ApiError(code=1001, message="用户名需3-32位字母数字", field="username")],
            )

        # Validate email
        if not self._validate_email(email):
            return ApiResponse.error(
                message="邮箱格式不正确",
                code=1001,
                errors=[ApiError(code=1001, message="邮箱格式无效", field="email")],
            )

        # Validate password strength
        is_valid, error_msg = self._validate_password(password)
        if not is_valid:
            return ApiResponse.error(
                message=error_msg,
                code=1001,
                errors=[ApiError(code=1001, message=error_msg, field="password")],
            )

        # Check duplicate username
        existing_username = await self.session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        if existing_username.scalar_one_or_none() is not None:
            return ApiResponse.error(
                message="用户名已存在",
                code=2002,
                errors=[ApiError(code=2002, message="用户名已被使用", field="username")],
            )

        # Check duplicate email
        existing_email = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        if existing_email.scalar_one_or_none() is not None:
            return ApiResponse.error(
                message="邮箱已被注册",
                code=2005,
                errors=[ApiError(code=2005, message="邮箱已被使用", field="email")],
            )

        # Determine initial status
        initial_status = (
            UserStatus.ACTIVE if role == UserRole.ADMIN else UserStatus.PENDING
        )

        now = datetime.now(UTC)
        row = UserModel(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role=role.value if hasattr(role, "value") else role,
            status=initial_status.value,
            full_name=full_name,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()  # Populate row.id before commit
        user = _row_to_user(row)

        return ApiResponse.success(data=user, message="用户创建成功")

    async def get_user_by_id(self, user_id: int, tenant_id: Optional[int] = None) -> Optional[User]:
        """根据ID获取用户"""

        result = await self.session.execute(
            select(UserModel).where(
                UserModel.id == user_id,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )
        row = result.scalar_one_or_none()
        return _row_to_user(row) if row is not None else None

    async def get_user_by_username(self, username: str, tenant_id: Optional[int] = None) -> Optional[User]:
        """根据用户名获取用户"""

        result = await self.session.execute(
            select(UserModel).where(
                UserModel.username == username,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )
        row = result.scalar_one_or_none()
        return _row_to_user(row) if row is not None else None

    async def get_user_by_email(self, email: str, tenant_id: Optional[int] = None) -> Optional[User]:
        """根据邮箱获取用户"""

        result = await self.session.execute(
            select(UserModel).where(
                UserModel.email == email,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )
        row = result.scalar_one_or_none()
        return _row_to_user(row) if row is not None else None

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        tenant_id: Optional[int] = None,
    ) -> ApiResponse[PaginatedData[User]]:
        """获取用户列表"""

        base_query = select(UserModel)
        if tenant_id is not None:
            base_query = base_query.where(UserModel.tenant_id == tenant_id)
        count_query = select(func.count()).select_from(UserModel)
        if tenant_id is not None:
            count_query = count_query.where(UserModel.tenant_id == tenant_id)

        if role is not None:
            base_query = base_query.where(UserModel.role == role.value)
            count_query = count_query.where(UserModel.role == role.value)
        if status is not None:
            base_query = base_query.where(UserModel.status == status.value)
            count_query = count_query.where(UserModel.status == status.value)

        # Total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Paginated rows
        offset = (page - 1) * page_size
        rows_result = await self.session.execute(
            base_query.offset(offset).limit(page_size)
        )
        items = [_row_to_user(r) for r in rows_result.scalars().all()]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="查询成功",
        )

    async def update_user(self, user_id: int, tenant_id: Optional[int] = None, **kwargs) -> ApiResponse[User]:
        """更新用户"""

        # Fetch existing record
        result = await self.session.execute(
            select(UserModel).where(
                UserModel.id == user_id,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(
                message="用户不存在",
                code=2001,
                errors=[ApiError(code=2001, message="用户不存在", field="id")],
            )

        # Validate and check duplicate email
        if "email" in kwargs:
            if not self._validate_email(kwargs["email"]):
                return ApiResponse.error(
                    message="邮箱格式不正确",
                    code=1001,
                    errors=[ApiError(code=1001, message="邮箱格式无效", field="email")],
                )
            dup_result = await self.session.execute(
                select(UserModel).where(
                    UserModel.email == kwargs["email"],
                    UserModel.id != user_id,
                )
            )
            if dup_result.scalar_one_or_none() is not None:
                return ApiResponse.error(
                    message="邮箱已被使用",
                    code=2005,
                    errors=[ApiError(code=2005, message="邮箱已被使用", field="email")],
                )

        # Apply allowed field updates
        allowed_fields = ["email", "bio", "full_name", "status"]
        values: dict = {}
        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                # Coerce enum to its string value for storage
                if hasattr(value, "value"):
                    value = value.value
                values[field] = value

        values["updated_at"] = datetime.now(UTC)

        await self.session.execute(
            update(UserModel).where(
                UserModel.id == user_id,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            ).values(**values)
        )
        await self.session.flush()

        # Re-fetch updated row
        refreshed = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        updated_row = refreshed.scalar_one()
        user = _row_to_user(updated_row)

        return ApiResponse.success(data=user, message="用户更新成功")

    async def delete_user(self, user_id: int, tenant_id: Optional[int] = None) -> ApiResponse:
        """删除用户"""

        result = await self.session.execute(
            select(UserModel).where(
                UserModel.id == user_id,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )
        if result.scalar_one_or_none() is None:
            return ApiResponse.error(message="用户不存在", code=2001)

        await self.session.execute(
            delete(UserModel).where(
                UserModel.id == user_id,
                *([] if tenant_id is None else [UserModel.tenant_id == tenant_id]),
            )
        )

        return ApiResponse.success(message="用户删除成功")

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> ApiResponse:
        """修改密码"""
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return ApiResponse.error(message="用户不存在", code=2001)

        # Verify old password against the stored hash
        if row.password_hash:
            if not self._verify_password(old_password, row.password_hash):
                return ApiResponse.error(
                    message="旧密码不正确",
                    code=2003,
                    errors=[
                        ApiError(code=2003, message="旧密码验证失败", field="old_password")
                    ],
                )

        # Validate new password strength
        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            return ApiResponse.error(
                message=error_msg,
                code=2004,
                errors=[ApiError(code=2004, message=error_msg, field="new_password")],
            )

        new_hash = self._hash_password(new_password)
        await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=new_hash, updated_at=datetime.now(UTC))
        )

        return ApiResponse.success(message="密码修改成功")

    async def search_users(
        self, keyword: str, page: int = 1, page_size: int = 20, tenant_id: Optional[int] = None
    ) -> ApiResponse[PaginatedData[User]]:
        """搜索用户"""

        pattern = f"%{keyword}%"

        from sqlalchemy import or_, and_

        conditions = []
        if tenant_id is not None:
            conditions.append(UserModel.tenant_id == tenant_id)
        conditions.append(
            or_(
                UserModel.username.ilike(pattern),
                UserModel.email.ilike(pattern),
                UserModel.bio.ilike(pattern),
            )
        )

        count_result = await self.session.execute(
            select(func.count()).select_from(UserModel).where(*conditions)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        rows_result = await self.session.execute(
            select(UserModel).where(*conditions).offset(offset).limit(page_size)
        )
        items = [_row_to_user(r) for r in rows_result.scalars().all()]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="搜索成功",
        )
