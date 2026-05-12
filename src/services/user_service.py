"""User service — CRUD + auth + password management via SQLAlchemy ORM."""

import re
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import UserModel
from pkg.errors.app_exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class ValidationError(Exception):
    """验证错误异常"""

    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class UserService:
    """User service — backed by PostgreSQL via SQLAlchemy async ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Password & validation helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def _validate_email(email: str) -> bool:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def _validate_username(username: str) -> bool:
        if len(username) < 3 or len(username) > 32:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", username))

    @staticmethod
    def _validate_password(password: str) -> tuple[bool, str]:
        if len(password) < 8:
            return False, "密码长度至少8位"
        if not re.search(r"[A-Z]", password):
            return False, "密码必须包含大写字母"
        if not re.search(r"[a-z]", password):
            return False, "密码必须包含小写字母"
        if not re.search(r"[0-9]", password):
            return False, "密码必须包含数字"
        return True, ""

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        tenant_id: int = 0,
        role: str = "user",
        full_name: str | None = None,
    ) -> UserModel:
        """Create a user, validating inputs and hashing the password."""
        if not self._validate_username(username):
            raise ValidationException("用户名格式不正确")
        if not self._validate_email(email):
            raise ValidationException("邮箱格式不正确")
        is_valid, error_msg = self._validate_password(password)
        if not is_valid:
            raise ValidationException(error_msg)

        now = datetime.now(UTC)
        user = UserModel(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role=role,
            status="pending",
            full_name=full_name,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        try:
            # flush surfaces unique-constraint errors here so we can translate
            # them; the router-bound get_db dependency owns commit/rollback.
            await self.session.flush()
            await self.session.refresh(user)
            return user
        except IntegrityError as e:
            err = str(e).lower()
            if "username" in err:
                raise ConflictException("用户名已存在") from e
            if "email" in err:
                raise ConflictException("邮箱已被注册") from e
            raise

    async def get_user_by_id(self, user_id: int, tenant_id: int = 0) -> UserModel:
        """Fetch a user by id (tenant-scoped)."""
        result = await self.session.execute(
            select(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundException("用户")
        return user

    async def get_user_by_username(self, tenant_id: int, username: str) -> UserModel | None:
        """Fetch a user by username within a tenant."""
        result = await self.session.execute(
            select(UserModel).where(and_(UserModel.tenant_id == tenant_id, UserModel.username == username))
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, tenant_id: int, email: str) -> UserModel | None:
        """Fetch a user by email within a tenant."""
        result = await self.session.execute(
            select(UserModel).where(and_(UserModel.tenant_id == tenant_id, UserModel.email == email))
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        role: str | None = None,
        status: str | None = None,
        q: str | None = None,
        tenant_id: int = 0,
    ) -> tuple[list[UserModel], int]:
        """List users for tenant with optional filters."""
        conditions = [UserModel.tenant_id == tenant_id]
        if role:
            conditions.append(UserModel.role == role)
        if status:
            conditions.append(UserModel.status == status)
        if q:
            kw = f"%{q}%"
            conditions.append(
                or_(
                    UserModel.username.ilike(kw),
                    UserModel.email.ilike(kw),
                    UserModel.full_name.ilike(kw),
                )
            )

        count_result = await self.session.execute(select(func.count(UserModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(UserModel)
            .where(and_(*conditions))
            .order_by(UserModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def search_users(
        self,
        keyword: str,
        tenant_id: int = 0,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UserModel], int]:
        """Search users by username/email/full_name."""
        return await self.list_users(
            page=page,
            page_size=page_size,
            q=keyword,
            tenant_id=tenant_id,
        )

    async def update_user(self, user_id: int, **kwargs) -> UserModel | None:
        """Update a user's allowed fields."""
        tenant_id = kwargs.get("tenant_id", 0)
        user = await self.get_user_by_id(user_id, tenant_id)

        if "email" in kwargs and not self._validate_email(kwargs["email"]):
            raise ValidationException("邮箱格式不正确")

        allowed = {"email", "bio", "full_name", "status", "role"}
        any_changes = False
        for key, value in kwargs.items():
            if key in allowed:
                setattr(user, key, value)
                any_changes = True
        if not any_changes:
            return None

        user.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int, tenant_id: int = 0) -> None:
        """Delete a user (tenant-scoped)."""
        result = await self.session.execute(
            delete(UserModel).where(and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id))
        )
        if (result.rowcount or 0) == 0:
            raise NotFoundException("用户")
        await self.session.flush()

    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str,
        tenant_id: int = 0,
    ) -> None:
        """Verify old password then update to new password hash."""
        user = await self.get_user_by_id(user_id, tenant_id)

        if not self._verify_password(old_password, user.password_hash or ""):
            raise ValidationException("旧密码不正确")

        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            raise ValidationException(error_msg)

        user.password_hash = self._hash_password(new_password)
        user.updated_at = datetime.now(UTC)
        await self.session.flush()
