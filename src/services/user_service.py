"""User service — CRUD + auth + password management via real DB."""
import re

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.response import ApiResponse


class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class UserService:
    """User service — all methods are async."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _hash_password(self, password: str) -> str:
        """密码哈希（使用bcrypt）"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode('utf-8'))
        except Exception:
            return False

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

    def _validate_password(self, password: str) -> tuple[bool, str]:
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

    async def create_user(self, username: str, email: str, password: str,
                         tenant_id: int = 0, role: str = "user",
                         full_name: str = None) -> ApiResponse:
        """INSERT INTO users ... ON CONFLICT DO NOTHING."""
        # Validate
        if not self._validate_username(username):
            return ApiResponse.error(
                message="用户名格式不正确",
                code=1001,
                errors=[],
            )
        if not self._validate_email(email):
            return ApiResponse.error(
                message="邮箱格式不正确",
                code=1001,
                errors=[],
            )
        is_valid, error_msg = self._validate_password(password)
        if not is_valid:
            return ApiResponse.error(message=error_msg, code=1001, errors=[])

        password_hash = self._hash_password(password)

        sql = text("""
            INSERT INTO users (tenant_id, username, email, password_hash, role, status, full_name)
            VALUES (:tenant_id, :username, :email, :password_hash, :role,
                    'pending', :full_name)
            RETURNING id, tenant_id, username, email, role, status, full_name, bio,
                      created_at, updated_at
        """)
        try:
            row = await self._session.execute(sql, {
                "tenant_id": tenant_id,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "role": role,
                "full_name": full_name,
            })
            await self._session.commit()
            result = row.fetchone()
            return ApiResponse.success(
                data={c: getattr(result, c) for c in result._fields},
                message="用户创建成功",
            )
        except Exception as e:
            await self._session.rollback()
            err_str = str(e).lower()
            if "unique" in err_str or "duplicate" in err_str:
                if "username" in err_str:
                    return ApiResponse.error(message="用户名已存在", code=2002, errors=[])
                if "email" in err_str:
                    return ApiResponse.error(message="邮箱已被注册", code=2005, errors=[])
            return ApiResponse.error(message="用户创建失败", code=500, errors=[])

    async def get_user_by_id(self, user_id: int, tenant_id: int = 0) -> dict | None:
        """SELECT FROM users WHERE id = :id AND tenant_id = :tid."""
        sql = text("""
            SELECT id, tenant_id, username, email, role, status, full_name, bio,
                   created_at, updated_at
            FROM users
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        row = await self._session.execute(sql, {"id": user_id, "tenant_id": tenant_id})
        result = row.fetchone()
        if result is None:
            return None
        return {c: getattr(result, c) for c in result._fields}

    async def get_user_by_username(self, username: str) -> dict | None:
        """SELECT FROM users WHERE username = :username."""
        sql = text("""
            SELECT id, tenant_id, username, email, password_hash, role, status,
                   full_name, bio, created_at, updated_at
            FROM users
            WHERE username = :username
        """)
        row = await self._session.execute(sql, {"username": username})
        result = row.fetchone()
        if result is None:
            return None
        return {c: getattr(result, c) for c in result._fields}

    async def get_user_by_email(self, email: str) -> dict | None:
        """SELECT FROM users WHERE email = :email."""
        sql = text("""
            SELECT id, tenant_id, username, email, password_hash, role, status,
                   full_name, bio, created_at, updated_at
            FROM users
            WHERE email = :email
        """)
        row = await self._session.execute(sql, {"email": email})
        result = row.fetchone()
        if result is None:
            return None
        return {c: getattr(result, c) for c in result._fields}

    async def list_users(
        self, page: int = 1, page_size: int = 20,
        role: str = None, status: str = None, q: str = None,
        tenant_id: int = 0,
    ) -> ApiResponse:
        """SELECT FROM users WHERE tenant_id = :tid [+ optional filters]."""
        conditions = ["tenant_id = :tenant_id"]
        params: dict = {"tenant_id": tenant_id, "page": page, "page_size": page_size}

        if role:
            conditions.append("role = :role")
            params["role"] = role
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if q:
            conditions.append("(username ILIKE :q OR email ILIKE :q OR full_name ILIKE :q)")
            params["q"] = f"%{q}%"

        where_clause = " AND ".join(conditions)

        count_sql = text(f"SELECT COUNT(*) as total FROM users WHERE {where_clause}")
        count_row = await self._session.execute(count_sql, params)
        total = count_row.scalar() or 0

        offset = (page - 1) * page_size
        params["offset"] = offset

        list_sql = text(f"""
            SELECT id, tenant_id, username, email, role, status, full_name, bio,
                   created_at, updated_at
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :page_size OFFSET :offset
        """)
        rows = await self._session.execute(list_sql, params)
        items = [{c: getattr(r, c) for c in r._fields} for r in rows.fetchall()]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="查询成功",
        )

    async def search_users(
        self, keyword: str, tenant_id: int = 0,
        page: int = 1, page_size: int = 20,
    ) -> ApiResponse:
        """SELECT FROM users WHERE tenant_id = :tid AND (username ILIKE ...)."""
        sql = text("""
            SELECT id, tenant_id, username, email, role, status, full_name, bio,
                   created_at, updated_at
            FROM users
            WHERE tenant_id = :tenant_id
              AND (username ILIKE :kw OR email ILIKE :kw OR full_name ILIKE :kw)
            ORDER BY created_at DESC
            LIMIT :page_size OFFSET :offset
        """)
        offset = (page - 1) * page_size
        rows = await self._session.execute(sql, {
            "tenant_id": tenant_id,
            "kw": f"%{keyword}%",
            "offset": offset,
            "page_size": page_size,
        })
        items = [{c: getattr(r, c) for c in r._fields} for r in rows.fetchall()]

        count_sql = text("""
            SELECT COUNT(*) as total
            FROM users
            WHERE tenant_id = :tenant_id
              AND (username ILIKE :kw OR email ILIKE :kw OR full_name ILIKE :kw)
        """)
        count_row = await self._session.execute(count_sql, {
            "tenant_id": tenant_id, "kw": f"%{keyword}%"
        })
        total = count_row.scalar() or 0

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="搜索成功",
        )

    async def update_user(self, user_id: int, **kwargs) -> ApiResponse:
        """UPDATE users SET ... WHERE id = :id AND tenant_id = :tid."""
        # Check existence
        check_sql = text("SELECT id FROM users WHERE id = :id AND tenant_id = :tenant_id")
        row = await self._session.execute(check_sql, {
            "id": user_id,
            "tenant_id": kwargs.get("tenant_id", 0),
        })
        if row.fetchone() is None:
            return ApiResponse.error(message="用户不存在", code=2001, errors=[])

        # Validate email if provided
        if "email" in kwargs:
            if not self._validate_email(kwargs["email"]):
                return ApiResponse.error(message="邮箱格式不正确", code=1001, errors=[])

        allowed_fields = {"email", "bio", "full_name", "status"}
        set_clauses = []
        params: dict = {"id": user_id}
        for field in allowed_fields:
            if field in kwargs:
                set_clauses.append(f"{field} = :{field}")
                params[field] = kwargs[field]

        if not set_clauses:
            return ApiResponse.success(data=None, message="没有需要更新的字段")

        params["tenant_id"] = kwargs.get("tenant_id", 0)
        sql = text(f"""
            UPDATE users
            SET {", ".join(set_clauses)}, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, username, email, role, status, full_name, bio,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, params)
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse.error(message="用户不存在", code=2001, errors=[])
        return ApiResponse.success(
            data={c: getattr(result, c) for c in result._fields},
            message="用户更新成功",
        )

    async def delete_user(self, user_id: int, tenant_id: int = 0) -> ApiResponse:
        """DELETE FROM users WHERE id = :id AND tenant_id = :tid."""
        sql = text("""
            DELETE FROM users
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id
        """)
        row = await self._session.execute(sql, {"id": user_id, "tenant_id": tenant_id})
        await self._session.commit()
        deleted = row.fetchone()
        if deleted is None:
            return ApiResponse.error(message="用户不存在", code=2001)
        return ApiResponse.success(message="用户删除成功")

    async def change_password(
        self, user_id: int, old_password: str, new_password: str,
        tenant_id: int = 0,
    ) -> ApiResponse:
        """Verify old password then update to new password hash."""
        # Fetch current user with password hash
        sql = text("""
            SELECT id, password_hash FROM users
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        row = await self._session.execute(sql, {"id": user_id, "tenant_id": tenant_id})
        user = row.fetchone()
        if user is None:
            return ApiResponse.error(message="用户不存在", code=2001)

        user_dict = {c: getattr(user, c) for c in user._fields}
        stored_hash = user_dict.get("password_hash", "")

        # Verify old password
        if not self._verify_password(old_password, stored_hash):
            return ApiResponse.error(
                message="旧密码不正确",
                code=2003,
                errors=[],
            )

        # Validate new password strength
        is_valid, error_msg = self._validate_password(new_password)
        if not is_valid:
            return ApiResponse.error(message=error_msg, code=2004, errors=[])

        # Update password hash
        new_hash = self._hash_password(new_password)
        update_sql = text("""
            UPDATE users
            SET password_hash = :password_hash, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        await self._session.execute(update_sql, {
            "id": user_id,
            "tenant_id": tenant_id,
            "password_hash": new_hash,
        })
        await self._session.commit()
        return ApiResponse.success(message="密码修改成功")
