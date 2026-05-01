"""Activity service for CRM system — async SQLAlchemy implementation."""
from datetime import datetime, UTC
from typing import List, Dict, Optional

from models.activity import Activity, ActivityType
from models.response import ApiResponse, PaginatedData
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.activity import ActivityModel
from sqlalchemy import text


class ActivityService:
    """活动记录服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _scope(self, tenant_id: int) -> str:
        """Return a SQL WHERE clause snippet scoped to tenant_id."""
        if tenant_id and tenant_id > 0:
            return "tenant_id = :tenant_id"
        return "1=1"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_activity(self, row) -> Activity:
        """Convert a DB row (or dict from fetchone/fetchall) to an Activity."""
        if hasattr(row, "_mapping"):
            d = dict(row._mapping)
        else:
            d = dict(row)
        return Activity.from_dict(d)

    def _row_to_dict(self, row) -> dict:
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        return dict(row)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def create_activity(
        self,
        customer_id: int,
        activity_type: str,
        content: str,
        created_by: int,
        tenant_id: int = 0,
        **kwargs,
    ) -> ApiResponse[Activity]:
        """创建活动记录"""
        try:
            activity_type_enum = ActivityType(activity_type)
        except (ValueError, TypeError) as e:
            return ApiResponse.error(message=f"创建活动记录失败: {str(e)}", code=1001)

        opportunity_id = kwargs.get("opportunity_id")
        now = datetime.now(UTC)

        sql = text(
            """
            INSERT INTO activities
                (tenant_id, customer_id, opportunity_id, type, content, created_by, created_at)
            VALUES
                (:tenant_id, :customer_id, :opportunity_id, :type, :content, :created_by, :created_at)
            RETURNING id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            """
        )
        params = {
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "opportunity_id": opportunity_id,
            "type": activity_type_enum.value,
            "content": content,
            "created_by": created_by,
            "created_at": now,
        }

        try:
            async with self.session:
                result = await self.session.execute(sql, params)
                row = result.fetchone()
                activity = self._row_to_activity(row)
                return ApiResponse.success(data=activity, message="活动记录创建成功")
        except Exception as e:
            return ApiResponse.error(message=f"创建活动记录失败: {str(e)}", code=1001)

    async def get_activity(self, activity_id: int, tenant_id: int = 0) -> ApiResponse[Activity]:
        """获取活动详情"""
        scope = await self._scope(tenant_id)
        sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE id = :activity_id AND {scope}
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, {"activity_id": activity_id, "tenant_id": tenant_id})
                row = result.fetchone()
                if not row:
                    return ApiResponse.error(message="活动记录不存在", code=1404)
                activity = self._row_to_activity(row)
                return ApiResponse.success(data=activity, message="")
        except Exception as e:
            return ApiResponse.error(message=f"获取活动记录失败: {str(e)}", code=1001)

    async def update_activity(
        self, activity_id: int, tenant_id: int = 0, **kwargs
    ) -> ApiResponse[Activity]:
        """更新活动"""
        scope = await self._scope(tenant_id)

        # First verify the record exists
        check_sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE id = :activity_id AND {scope}
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(check_sql, {"activity_id": activity_id, "tenant_id": tenant_id})
                row = result.fetchone()
                if not row:
                    return ApiResponse.error(message="活动记录不存在", code=1404)

                # Build dynamic UPDATE
                sets: List[str] = []
                params: dict = {"activity_id": activity_id}

                if "content" in kwargs:
                    sets.append("content = :content")
                    params["content"] = kwargs["content"]
                if "activity_type" in kwargs:
                    try:
                        ActivityType(kwargs["activity_type"])
                    except (ValueError, TypeError) as e:
                        return ApiResponse.error(message=f"更新活动记录失败: {str(e)}", code=1001)
                    sets.append("type = :activity_type")
                    params["activity_type"] = kwargs["activity_type"]
                if "opportunity_id" in kwargs:
                    sets.append("opportunity_id = :opportunity_id")
                    params["opportunity_id"] = kwargs["opportunity_id"]

                if not sets:
                    activity = self._row_to_activity(row)
                    return ApiResponse.success(data=activity, message="活动记录更新成功")

                update_sql = text(
                    f"""
                    UPDATE activities
                    SET {', '.join(sets)}
                    WHERE id = :activity_id
                    RETURNING id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
                    """
                )
                result = await self.session.execute(update_sql, params)
                updated_row = result.fetchone()
                activity = self._row_to_activity(updated_row)
                return ApiResponse.success(data=activity, message="活动记录更新成功")
        except Exception as e:
            return ApiResponse.error(message=f"更新活动记录失败: {str(e)}", code=1001)

    async def delete_activity(self, activity_id: int, tenant_id: int = 0) -> ApiResponse[Dict]:
        """删除活动"""
        scope = await self._scope(tenant_id)
        sql = text(
            f"""
            DELETE FROM activities
            WHERE id = :activity_id AND {scope}
            RETURNING id
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, {"activity_id": activity_id, "tenant_id": tenant_id})
                row = result.fetchone()
                if not row:
                    return ApiResponse.error(message="活动记录不存在", code=1404)
                return ApiResponse.success(data={"id": activity_id}, message="活动记录删除成功")
        except Exception as e:
            return ApiResponse.error(message=f"删除活动记录失败: {str(e)}", code=1001)

    async def list_activities(
        self,
        customer_id: Optional[int] = None,
        activity_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        tenant_id: int = 0,
    ) -> ApiResponse[PaginatedData[Activity]]:
        """活动列表"""
        scope = await self._scope(tenant_id)
        conditions = [scope]
        params: dict = {"tenant_id": tenant_id}

        if customer_id is not None:
            conditions.append("customer_id = :customer_id")
            params["customer_id"] = customer_id
        if activity_type:
            conditions.append("type = :activity_type")
            params["activity_type"] = activity_type

        where_clause = " AND ".join(conditions)

        count_sql = text(f"SELECT COUNT(*) as total FROM activities WHERE {where_clause}")
        offset_val = (page - 1) * page_size

        try:
            async with self.session:
                # Total count
                count_result = await self.session.execute(count_sql, params)
                count_row = count_result.fetchone()
                total = int(count_row[0]) if count_row else 0

                # Paginated rows
                list_sql = text(
                    f"""
                    SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
                    FROM activities
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :page_size OFFSET :offset
                    """
                )
                params["page_size"] = page_size
                params["offset"] = offset_val
                rows_result = await self.session.execute(list_sql, params)
                rows = rows_result.fetchall()

                items = [self._row_to_activity(row) for row in rows]
                return ApiResponse.paginated(
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    message="",
                )
        except Exception as e:
            return ApiResponse.error(message=f"查询活动列表失败: {str(e)}", code=1001)

    async def get_customer_activities(
        self, customer_id: int, limit: int = 50, tenant_id: int = 0
    ) -> ApiResponse[List[Dict]]:
        """获取客户的所有活动"""
        scope = await self._scope(tenant_id)
        sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE customer_id = :customer_id AND {scope}
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, {"customer_id": customer_id, "limit": limit, "tenant_id": tenant_id})
                rows = result.fetchall()
                return ApiResponse.success(data=[self._row_to_activity(row).to_dict() for row in rows], message="")
        except Exception as e:
            return ApiResponse.error(message=f"获取客户活动失败: {str(e)}", code=1001)

    async def get_opportunity_activities(
        self, opportunity_id: int, tenant_id: int = 0
    ) -> ApiResponse[List[Dict]]:
        """获取商机的所有活动"""
        scope = await self._scope(tenant_id)
        sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE opportunity_id = :opportunity_id AND {scope}
            ORDER BY created_at DESC
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, {"opportunity_id": opportunity_id, "tenant_id": tenant_id})
                rows = result.fetchall()
                return ApiResponse.success(data=[self._row_to_activity(row).to_dict() for row in rows], message="")
        except Exception as e:
            return ApiResponse.error(message=f"获取商机活动失败: {str(e)}", code=1001)

    async def search_activities(
        self, keyword: str, filters: Optional[Dict] = None, tenant_id: int = 0
    ) -> ApiResponse[List[Dict]]:
        """搜索活动"""
        scope = await self._scope(tenant_id)
        conditions = [scope, "LOWER(content) LIKE LOWER(:keyword)"]
        params: dict = {"keyword": f"%{keyword}%", "tenant_id": tenant_id}

        if filters:
            if "customer_id" in filters:
                conditions.append("customer_id = :customer_id")
                params["customer_id"] = filters["customer_id"]
            if "activity_type" in filters:
                conditions.append("type = :activity_type")
                params["activity_type"] = filters["activity_type"]
            if "start_date" in filters:
                conditions.append("created_at >= :start_date")
                params["start_date"] = filters["start_date"]
            if "end_date" in filters:
                conditions.append("created_at <= :end_date")
                params["end_date"] = filters["end_date"]

        where_clause = " AND ".join(conditions)
        sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE {where_clause}
            ORDER BY created_at DESC
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, params)
                rows = result.fetchall()
                return ApiResponse.success(data=[self._row_to_activity(row).to_dict() for row in rows], message="")
        except Exception as e:
            return ApiResponse.error(message=f"搜索活动失败: {str(e)}", code=1001)

    async def get_activity_summary(
        self,
        customer_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: int = 0,
    ) -> ApiResponse[Dict]:
        """获取活动摘要"""
        scope = await self._scope(tenant_id)
        conditions = [scope, "customer_id = :customer_id"]
        params: dict = {"customer_id": customer_id, "tenant_id": tenant_id}

        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date

        where_clause = " AND ".join(conditions)
        sql = text(
            f"""
            SELECT id, tenant_id, customer_id, opportunity_id, type, content, created_by, created_at
            FROM activities
            WHERE {where_clause}
            ORDER BY created_at DESC
            """
        )
        try:
            async with self.session:
                result = await self.session.execute(sql, params)
                rows = result.fetchall()

                activities = [self._row_to_activity(row) for row in rows]
                by_type: Dict[str, int] = {}
                for a in activities:
                    type_val = a.type.value if isinstance(a.type, ActivityType) else str(a.type)
                    by_type[type_val] = by_type.get(type_val, 0) + 1

                summary: dict = {
                    "total": len(activities),
                    "by_type": by_type,
                    "recent_activities": [a.to_dict() for a in activities[:5]],
                }
                return ApiResponse.success(data=summary, message="")
        except Exception as e:
            return ApiResponse.error(message=f"获取活动摘要失败: {str(e)}", code=1001)