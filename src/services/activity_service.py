"""Activity service for CRM system."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models.activity import Activity, ActivityType
from pkg.errors.app_exceptions import NotFoundException, ValidationException

# Module-level state for placeholder service (shared across instances per-process)
_activities_db: list[Activity] = []
_next_id = 1


class ActivityService:
    """活动记录服务"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_activity(self, customer_id: int, activity_type: str, content: str, created_by: int, tenant_id: int = 0, **kwargs) -> Activity:
        """创建活动记录"""
        global _next_id
        try:
            activity_type_enum = ActivityType(activity_type)
        except ValueError:
            raise ValidationException(f"无效的活动类型: {activity_type}")
        activity = Activity(
            id=_next_id,
            customer_id=customer_id,
            type=activity_type_enum,
            content=content,
            created_by=created_by,
            opportunity_id=kwargs.get('opportunity_id'),
            created_at=datetime.utcnow()
        )
        _activities_db.append(activity)
        _next_id += 1
        return activity

    async def get_activity(self, activity_id: int, tenant_id: int = 0) -> Activity:
        """获取活动详情"""
        for activity in _activities_db:
            if activity.id == activity_id:
                return activity
        raise NotFoundException("活动记录")

    async def update_activity(self, activity_id: int, tenant_id: int = 0, **kwargs) -> Activity:
        """更新活动"""
        for activity in _activities_db:
            if activity.id == activity_id:
                if 'content' in kwargs:
                    activity.content = kwargs['content']
                if 'activity_type' in kwargs:
                    activity.type = ActivityType(kwargs['activity_type'])
                if 'opportunity_id' in kwargs:
                    activity.opportunity_id = kwargs['opportunity_id']
                return activity
        raise NotFoundException("活动记录")

    async def delete_activity(self, activity_id: int, tenant_id: int = 0) -> dict:
        """删除活动"""
        for i, activity in enumerate(_activities_db):
            if activity.id == activity_id:
                _activities_db.pop(i)
                return {'id': activity_id}
        raise NotFoundException("活动记录")

    async def list_activities(self, customer_id: int = None, activity_type: str = None, page: int = 1, page_size: int = 20, tenant_id: int = 0) -> tuple[list[Activity], int]:
        """活动列表"""
        filtered = _activities_db
        if customer_id is not None:
            filtered = [a for a in filtered if a.customer_id == customer_id]
        if activity_type:
            filtered = [a for a in filtered if a.type.value == activity_type]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered[start:end]

        return items, total

    async def get_customer_activities(self, customer_id: int, tenant_id: int = 0) -> list[Activity]:
        """获取客户的所有活动"""
        activities = [a for a in _activities_db if a.customer_id == customer_id]
        activities.sort(key=lambda x: x.created_at, reverse=True)
        return activities

    async def get_opportunity_activities(self, opportunity_id: int, tenant_id: int = 0) -> list[Activity]:
        """获取商机的所有活动"""
        activities = [a for a in _activities_db if a.opportunity_id == opportunity_id]
        activities.sort(key=lambda x: x.created_at, reverse=True)
        return activities

    async def search_activities(self, keyword: str, tenant_id: int = 0, filters: dict = None) -> list[Activity]:
        """搜索活动"""
        keyword_lower = keyword.lower()
        results = [a for a in _activities_db if keyword_lower in a.content.lower()]

        if filters:
            if 'customer_id' in filters:
                results = [a for a in results if a.customer_id == filters['customer_id']]
            if 'activity_type' in filters:
                results = [a for a in results if a.type.value == filters['activity_type']]
            if 'start_date' in filters:
                results = [a for a in results if a.created_at >= filters['start_date']]
            if 'end_date' in filters:
                results = [a for a in results if a.created_at <= filters['end_date']]

        return results

    async def get_activity_summary(self, customer_id: int, tenant_id: int = 0, start_date: datetime = None, end_date: datetime = None) -> dict:
        """获取活动摘要"""
        activities = [a for a in _activities_db if a.customer_id == customer_id]

        if start_date:
            activities = [a for a in activities if a.created_at >= start_date]
        if end_date:
            activities = [a for a in activities if a.created_at <= end_date]

        summary = {
            'total': len(activities),
            'by_type': {},
            'recent_activities': [a.to_dict() for a in sorted(activities, key=lambda x: x.created_at, reverse=True)[:5]]
        }

        for activity in activities:
            type_val = activity.type.value
            summary['by_type'][type_val] = summary['by_type'].get(type_val, 0) + 1

        return summary
