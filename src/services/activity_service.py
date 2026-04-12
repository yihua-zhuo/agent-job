"""Activity service for CRM system."""
from typing import List, Dict, Optional
from datetime import datetime

from src.models.activity import Activity, ActivityType
from src.models.response import ApiResponse, PaginatedData


class ActivityService:
    """活动记录服务"""

    def __init__(self):
        self._activities_db: List[Activity] = []
        self._next_id = 1

    def create_activity(self, customer_id: int, activity_type: str, content: str, created_by: int, **kwargs) -> Dict:
        """创建活动记录"""
        activity = Activity(
            id=self._next_id,
            customer_id=customer_id,
            type=ActivityType(activity_type),
            content=content,
            created_by=created_by,
            opportunity_id=kwargs.get('opportunity_id'),
            created_at=datetime.utcnow()
        )
        self._activities_db.append(activity)
        self._next_id += 1
        return {'success': True, 'data': activity.to_dict(), 'message': '活动记录创建成功'}

    def get_activity(self, activity_id: int) -> Dict:
        """获取活动详情"""
        for activity in self._activities_db:
            if activity.id == activity_id:
                return {'success': True, 'data': activity.to_dict(), 'message': ''}
        return {'success': False, 'data': None, 'message': '活动记录不存在'}

    def update_activity(self, activity_id: int, **kwargs) -> Dict:
        """更新活动"""
        for activity in self._activities_db:
            if activity.id == activity_id:
                if 'content' in kwargs:
                    activity.content = kwargs['content']
                if 'activity_type' in kwargs:
                    activity.type = ActivityType(kwargs['activity_type'])
                if 'opportunity_id' in kwargs:
                    activity.opportunity_id = kwargs['opportunity_id']
                return {'success': True, 'data': activity.to_dict(), 'message': '活动记录更新成功'}
        return {'success': False, 'data': None, 'message': '活动记录不存在'}

    def delete_activity(self, activity_id: int):
        """删除活动"""
        for i, activity in enumerate(self._activities_db):
            if activity.id == activity_id:
                self._activities_db.pop(i)
                return {'success': True, 'data': {'id': activity_id}, 'message': '活动记录删除成功'}
        return {'success': False, 'data': None, 'message': '活动记录不存在'}

    def list_activities(self, customer_id: int = None, activity_type: str = None, page: int = 1, page_size: int = 20) -> Dict:
        """活动列表"""
        filtered = self._activities_db
        if customer_id is not None:
            filtered = [a for a in filtered if a.customer_id == customer_id]
        if activity_type:
            filtered = [a for a in filtered if a.type.value == activity_type]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = [a.to_dict() for a in filtered[start:end]]

        return {'success': True, 'data': {'page': page, 'page_size': page_size, 'total': total, 'items': items}, 'message': ''}

    def get_customer_activities(self, customer_id: int, limit: int = 50) -> List[Dict]:
        """获取客户的所有活动"""
        activities = [a for a in self._activities_db if a.customer_id == customer_id]
        activities.sort(key=lambda x: x.created_at, reverse=True)
        return [a.to_dict() for a in activities[:limit]]

    def get_opportunity_activities(self, opportunity_id: int) -> List[Dict]:
        """获取商机的所有活动"""
        activities = [a for a in self._activities_db if a.opportunity_id == opportunity_id]
        activities.sort(key=lambda x: x.created_at, reverse=True)
        return [a.to_dict() for a in activities]

    def search_activities(self, keyword: str, filters: Dict = None) -> List[Dict]:
        """搜索活动"""
        keyword_lower = keyword.lower()
        results = [a for a in self._activities_db if keyword_lower in a.content.lower()]

        if filters:
            if 'customer_id' in filters:
                results = [a for a in results if a.customer_id == filters['customer_id']]
            if 'activity_type' in filters:
                results = [a for a in results if a.type.value == filters['activity_type']]
            if 'start_date' in filters:
                results = [a for a in results if a.created_at >= filters['start_date']]
            if 'end_date' in filters:
                results = [a for a in results if a.created_at <= filters['end_date']]

        return [a.to_dict() for a in results]

    def get_activity_summary(self, customer_id: int, start_date: datetime = None, end_date: datetime = None) -> Dict:
        """获取活动摘要"""
        activities = [a for a in self._activities_db if a.customer_id == customer_id]

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

        return {'success': True, 'data': summary, 'message': ''}
