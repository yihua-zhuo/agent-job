"""Task service for CRM system - async PostgreSQL via SQLAlchemy."""
from typing import List, Dict, Optional
from datetime import datetime, UTC

from sqlalchemy import text, func, and_, or_

from db.connection import get_db_session


class TaskService:
    """任务服务"""

    async def create_task(
        self,
        title: str,
        description: str,
        assigned_to: int,
        due_date: datetime = None,
        **kwargs,
    ) -> Dict:
        """创建任务"""
        async with get_db_session() as session:
            tenant_id = kwargs.get("tenant_id", 0)
            created_by = kwargs.get("created_by")
            priority = kwargs.get("priority", "normal")
            now = datetime.now(UTC)
            result = await session.execute(
                text(
                    """
                    INSERT INTO tasks
                        (tenant_id, title, description, assigned_to, due_date, status,
                         priority, created_by, completed_at, created_at, updated_at)
                    VALUES
                        (:tenant_id, :title, :description, :assigned_to, :due_date, 'pending',
                         :priority, :created_by, NULL, :now, :now)
                    RETURNING id, tenant_id, title, description, assigned_to, due_date,
                              status, priority, created_by, completed_at, created_at, updated_at
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "title": title,
                    "description": description,
                    "assigned_to": assigned_to,
                    "due_date": due_date,
                    "priority": priority,
                    "created_by": created_by,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            task = self._row_to_dict(row)
            return {"success": True, "data": task, "message": "任务创建成功"}

    async def get_task(self, task_id: int) -> Dict:
        """获取任务详情"""
        async with get_db_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, tenant_id, title, description, assigned_to, due_date,
                           status, priority, created_by, completed_at, created_at, updated_at
                    FROM tasks
                    WHERE id = :task_id
                    """
                ),
                {"task_id": task_id},
            )
            row = result.fetchone()
            if row is None:
                return {"success": False, "data": None, "message": "任务不存在"}
            return {"success": True, "data": self._row_to_dict(row), "message": ""}

    async def update_task(self, task_id: int, **kwargs) -> Dict:
        """更新任务"""
        async with get_db_session() as session:
            # Build dynamic SET clause
            set_clauses = []
            params: Dict = {"task_id": task_id}
            if "title" in kwargs:
                set_clauses.append("title = :title")
                params["title"] = kwargs["title"]
            if "description" in kwargs:
                set_clauses.append("description = :description")
                params["description"] = kwargs["description"]
            if "assigned_to" in kwargs:
                set_clauses.append("assigned_to = :assigned_to")
                params["assigned_to"] = kwargs["assigned_to"]
            if "due_date" in kwargs:
                set_clauses.append("due_date = :due_date")
                params["due_date"] = kwargs["due_date"]
            if "status" in kwargs:
                set_clauses.append("status = :status")
                params["status"] = kwargs["status"]
            if "priority" in kwargs:
                set_clauses.append("priority = :priority")
                params["priority"] = kwargs["priority"]

            if not set_clauses:
                return {"success": False, "data": None, "message": "任务不存在"}

            set_clauses.append("updated_at = :now")
            params["now"] = datetime.now(UTC)

            sql = text(
                f"UPDATE tasks SET {', '.join(set_clauses)} "
                f"WHERE id = :task_id "
                f"RETURNING id, tenant_id, title, description, assigned_to, due_date, "
                f"status, priority, created_by, completed_at, created_at, updated_at"
            )
            result = await session.execute(sql, params)
            await session.commit()
            row = result.fetchone()
            if row is None:
                return {"success": False, "data": None, "message": "任务不存在"}
            return {"success": True, "data": self._row_to_dict(row), "message": "任务更新成功"}

    async def complete_task(self, task_id: int):
        """完成任务"""
        async with get_db_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                text(
                    """
                    UPDATE tasks
                    SET status = 'completed', completed_at = :now, updated_at = :now
                    WHERE id = :task_id
                    RETURNING id, tenant_id, title, description, assigned_to, due_date,
                              status, priority, created_by, completed_at, created_at, updated_at
                    """
                ),
                {"task_id": task_id, "now": now},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return {"success": False, "data": None, "message": "任务不存在"}
            return {"success": True, "data": self._row_to_dict(row), "message": "任务已完成"}

    async def delete_task(self, task_id: int):
        """删除任务"""
        async with get_db_session() as session:
            result = await session.execute(
                text("DELETE FROM tasks WHERE id = :task_id RETURNING id"),
                {"task_id": task_id},
            )
            await session.commit()
            row = result.fetchone()
            if row is None:
                return {"success": False, "data": None, "message": "任务不存在"}
            return {"success": True, "data": {"id": task_id}, "message": "任务删除成功"}

    async def list_tasks(
        self,
        assigned_to: int = None,
        status: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """任务列表"""
        async with get_db_session() as session:
            # Count
            count_params: Dict = {}
            where_clauses = []
            if assigned_to is not None:
                where_clauses.append("assigned_to = :assigned_to")
                count_params["assigned_to"] = assigned_to
            if status:
                where_clauses.append("status = :status")
                count_params["status"] = status
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM tasks {where_sql}"),
                count_params,
            )
            total = count_result.fetchone()[0]

            # Fetch page
            offset = (page - 1) * page_size
            fetch_sql = text(
                f"""
                SELECT id, tenant_id, title, description, assigned_to, due_date,
                       status, priority, created_by, completed_at, created_at, updated_at
                FROM tasks
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            )
            fetch_params = dict(count_params, limit=page_size, offset=offset)
            rows = await session.execute(fetch_sql, fetch_params)
            items = [self._row_to_dict(r) for r in rows.fetchall()]
            return {
                "success": True,
                "data": {"page": page, "page_size": page_size, "total": total, "items": items},
                "message": "",
            }

    async def get_my_tasks(self, user_id: int, status: str = None) -> List[Dict]:
        """获取我的任务"""
        async with get_db_session() as session:
            params: Dict = {"user_id": user_id}
            where_clauses = ["assigned_to = :user_id"]
            if status:
                where_clauses.append("status = :status")
                params["status"] = status
            where_sql = "WHERE " + " AND ".join(where_clauses)

            sql = text(
                f"""
                SELECT id, tenant_id, title, description, assigned_to, due_date,
                       status, priority, created_by, completed_at, created_at, updated_at
                FROM tasks
                {where_sql}
                ORDER BY due_date ASC NULLS LAST
                """
            )
            rows = await session.execute(sql, params)
            return [self._row_to_dict(r) for r in rows.fetchall()]

    def _row_to_dict(self, row) -> Dict:
        """Map a tasks row to a dict matching the original shape."""
        return {
            "id": row[0],
            "tenant_id": row[1],
            "title": row[2],
            "description": row[3],
            "assigned_to": row[4],
            "due_date": row[5].isoformat() if row[5] else None,
            "status": row[6],
            "priority": row[7],
            "created_by": row[8],
            "completed_at": row[9].isoformat() if row[9] else None,
            "created_at": row[10].isoformat() if row[10] else None,
            "updated_at": row[11].isoformat() if row[11] else None,
        }
