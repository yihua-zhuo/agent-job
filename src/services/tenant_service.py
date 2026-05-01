"""租户管理服务 - async PostgreSQL via SQLAlchemy."""
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import json

from sqlalchemy import text, func

from src.db.connection import get_db_session
from src.models.response import ApiResponse, PaginatedData


class TenantService:
    """租户管理服务"""

    async def create_tenant(self, name: str, plan: str, admin_email: str = None, **kwargs) -> ApiResponse[Dict]:
        """创建租户（公司）"""
        async with get_db_session() as session:
            now = datetime.now(UTC)
            settings = kwargs.get("settings", {})
            settings_json = json.dumps(settings) if isinstance(settings, dict) else settings
            result = await session.execute(
                text(
                    """
                    INSERT INTO tenants (name, plan, status, settings, created_at, updated_at)
                    VALUES (:name, :plan, 'active', :settings, :now, :now)
                    RETURNING id, name, plan, status, settings, created_at, updated_at
                    """
                ),
                {
                    "name": name,
                    "plan": plan,
                    "settings": settings_json,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            tenant = self._row_to_dict(row)
            return ApiResponse.success(data=tenant, message="租户创建成功")

    async def get_tenant(self, tenant_id: int) -> ApiResponse[Dict]:
        """获取租户详情"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, name, plan, status, settings, created_at, updated_at
                    FROM tenants
                    WHERE id = :tenant_id
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id},
            )
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message=f"Tenant {tenant_id} not found", code=1404)
            return ApiResponse.success(data=self._row_to_dict(row))

    async def update_tenant(self, tenant_id: int, **kwargs) -> ApiResponse[Dict]:
        """更新租户信息"""
        async with get_db_session() as session:
            set_clauses = []
            params: Dict = {"tenant_id": tenant_id}
            allowed_fields = {"name", "plan", "status"}
            for key, value in kwargs.items():
                if key in allowed_fields:
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = value
            if "settings" in kwargs:
                settings_val = kwargs["settings"]
                settings_json = json.dumps(settings_val) if isinstance(settings_val, dict) else settings_val
                set_clauses.append("settings = :settings")
                params["settings"] = settings_json

            if not set_clauses:
                return ApiResponse.error(message=f"Tenant {tenant_id} not found", code=1404)

            set_clauses.append("updated_at = :now")
            params["now"] = datetime.now(UTC)

            sql = text(
                f"UPDATE tenants SET {', '.join(set_clauses)} "
                f"WHERE id = :tenant_id "
                f"RETURNING id, name, plan, status, settings, created_at, updated_at"
            )
            result = await session.execute(sql, params)
            await session.commit()
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message=f"Tenant {tenant_id} not found", code=1404)
            return ApiResponse.success(data=self._row_to_dict(row), message="租户信息更新成功")

    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> ApiResponse[PaginatedData[Dict]]:
        """租户列表"""
        async with get_db_session() as session:
            # Count total
            count_sql = text("SELECT COUNT(*) FROM tenants")
            count_params: Dict = {}
            if status:
                count_sql = text("SELECT COUNT(*) FROM tenants WHERE status = :status")
                count_params = {"status": status}
            total_result = await session.execute(count_sql, count_params)
            total = total_result.fetchone()[0]

            # Fetch page
            offset = (page - 1) * page_size
            fetch_sql = text(
                """
                SELECT id, name, plan, status, settings, created_at, updated_at
                FROM tenants
                """
                + ("WHERE status = :status" if status else "")
                + """
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            )
            fetch_params: Dict = {}
            if status:
                fetch_params["status"] = status
            fetch_params["limit"] = page_size
            fetch_params["offset"] = offset
            rows = await session.execute(fetch_sql, fetch_params)
            items = [self._row_to_dict(r) for r in rows.fetchall()]
            return ApiResponse.paginated(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                message="查询成功",
            )

    async def delete_tenant(self, tenant_id: int) -> ApiResponse[Dict]:
        """删除租户（软删除）"""
        async with get_db_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                text(
                    """
                    UPDATE tenants
                    SET status = 'deleted', updated_at = :now
                    WHERE id = :tenant_id AND status != 'deleted'
                    RETURNING id, name, plan, status, settings, created_at, updated_at
                    """
                ),
                {"tenant_id": tenant_id, "now": now},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message=f"Tenant {tenant_id} not found", code=1404)
            return ApiResponse.success(data={"tenant_id": tenant_id}, message="租户已删除")

    async def get_tenant_stats(self, tenant_id: int) -> ApiResponse[Dict]:
        """获取租户统计信息"""
        return await self.get_tenant_usage(tenant_id)

    async def get_tenant_usage(self, tenant_id: int) -> ApiResponse[Dict]:
        """获取租户使用量统计（用户数、存储量、API调用量）"""
        async with get_db_session() as session:
            # Check tenant exists
            tenant_result = await session.execute(
                text("SELECT id FROM tenants WHERE id = :tenant_id LIMIT 1"),
                {"tenant_id": tenant_id},
            )
            if tenant_result.fetchone() is None:
                return ApiResponse.error(message=f"Tenant {tenant_id} not found", code=1404)

            # Count users under this tenant
            user_count_result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
            user_count = user_count_result.fetchone()[0]

            usage = {
                "tenant_id": tenant_id,
                "user_count": user_count,
                "storage_used": 0,
                "api_calls": 0,
            }
            return ApiResponse.success(data=usage)

    def _row_to_dict(self, row) -> Dict:
        """Map a tenants row to a dict."""
        settings_val = row[4]
        if isinstance(settings_val, str):
            try:
                settings_val = json.loads(settings_val)
            except (json.JSONDecodeError, TypeError):
                settings_val = {}
        return {
            "id": row[0],
            "name": row[1],
            "plan": row[2],
            "status": row[3],
            "settings": settings_val or {},
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None,
        }
