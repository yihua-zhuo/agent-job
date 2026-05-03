"""Task service for CRM system."""
from typing import List, Dict, Optional
from datetime import datetime


class TaskService:
    """任务服务"""

    def __init__(self):
        self._tasks_db: List[Dict] = []
        self._next_id = 1

    def create_task(self, title: str, description: str, assigned_to: int, due_date: datetime = None, **kwargs) -> Dict:
        """创建任务"""
        task = {
            'id': self._next_id,
            'title': title,
            'description': description,
            'assigned_to': assigned_to,
            'due_date': due_date.isoformat() if due_date else None,
            'status': 'pending',
            'created_by': kwargs.get('created_by'),
            'priority': kwargs.get('priority', 'normal'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'completed_at': None,
        }
        self._tasks_db.append(task)
        self._next_id += 1
        return {'success': True, 'data': task, 'message': '任务创建成功'}

    def get_task(self, task_id: int) -> Dict:
        """获取任务详情"""
        for task in self._tasks_db:
            if task['id'] == task_id:
                return {'success': True, 'data': task, 'message': ''}
        return {'success': False, 'data': None, 'message': '任务不存在'}

    def update_task(self, task_id: int, **kwargs) -> Dict:
        """更新任务"""
        for task in self._tasks_db:
            if task['id'] == task_id:
                if 'title' in kwargs:
                    task['title'] = kwargs['title']
                if 'description' in kwargs:
                    task['description'] = kwargs['description']
                if 'assigned_to' in kwargs:
                    task['assigned_to'] = kwargs['assigned_to']
                if 'due_date' in kwargs:
                    task['due_date'] = kwargs['due_date'].isoformat() if kwargs['due_date'] else None
                if 'status' in kwargs:
                    task['status'] = kwargs['status']
                if 'priority' in kwargs:
                    task['priority'] = kwargs['priority']
                task['updated_at'] = datetime.utcnow().isoformat()
                return {'success': True, 'data': task, 'message': '任务更新成功'}
        return {'success': False, 'data': None, 'message': '任务不存在'}

    def complete_task(self, task_id: int):
        """完成任务"""
        for task in self._tasks_db:
            if task['id'] == task_id:
                task['status'] = 'completed'
                task['completed_at'] = datetime.utcnow().isoformat()
                task['updated_at'] = datetime.utcnow().isoformat()
                return {'success': True, 'data': task, 'message': '任务已完成'}
        return {'success': False, 'data': None, 'message': '任务不存在'}

    def delete_task(self, task_id: int):
        """删除任务"""
        for i, task in enumerate(self._tasks_db):
            if task['id'] == task_id:
                self._tasks_db.pop(i)
                return {'success': True, 'data': {'id': task_id}, 'message': '任务删除成功'}
        return {'success': False, 'data': None, 'message': '任务不存在'}

    def list_tasks(self, assigned_to: int = None, status: str = None, page: int = 1, page_size: int = 20) -> Dict:
        """任务列表"""
        filtered = self._tasks_db
        if assigned_to is not None:
            filtered = [t for t in filtered if t['assigned_to'] == assigned_to]
        if status:
            filtered = [t for t in filtered if t['status'] == status]

        filtered.sort(key=lambda x: x['created_at'], reverse=True)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = filtered[start:end]

        return {'success': True, 'data': {'page': page, 'page_size': page_size, 'total': total, 'items': items}, 'message': ''}

    def get_my_tasks(self, user_id: int, status: str = None) -> List[Dict]:
        """获取我的任务"""
        tasks = [t for t in self._tasks_db if t['assigned_to'] == user_id]
        if status:
            tasks = [t for t in tasks if t['status'] == status]

        tasks.sort(key=lambda x: x['due_date'] or '9999-12-31')
        return tasks
