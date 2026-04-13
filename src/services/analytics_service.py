"""Analytics service — async PostgreSQL via SQLAlchemy."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from sqlalchemy import text, func, and_, or_

from db.connection import get_db_session
from models.response import ApiResponse, PaginatedData


class AnalyticsService:
    """分析服务 — backed by PostgreSQL (dashboards/reports stored in DB)."""

    # ------------------------------------------------------------------
    # dashboards
    # ------------------------------------------------------------------
    async def create_dashboard(
        self, name: str, owner_id: int, tenant_id: int = 0, description: Optional[str] = None
    ) -> ApiResponse[Dict]:
        """创建仪表板"""
        now = datetime.utcnow()
        async with get_db_session() as session:
            stmt = text(
                """
                INSERT INTO dashboards (tenant_id, name, description, widgets, owner_id, is_default, created_at, updated_at)
                VALUES (:tenant_id, :name, :description, '[]', :owner_id, false, :now, :now)
                RETURNING id, tenant_id, name, description, widgets, owner_id, is_default, created_at, updated_at
                """
            )
            result = await session.execute(
                stmt,
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "description": description,
                    "owner_id": owner_id,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="创建仪表板失败", code=500)
            return ApiResponse.success(
                data={
                    "id": row[0], "tenant_id": row[1], "name": row[2],
                    "description": row[3], "widgets": row[4], "owner_id": row[5],
                    "is_default": row[6], "created_at": row[7].isoformat() if row[7] else None,
                    "updated_at": row[8].isoformat() if row[8] else None,
                },
                message="仪表板创建成功",
            )

    async def get_dashboard(self, dashboard_id: int, tenant_id: int = 0) -> ApiResponse[Dict]:
        """获取仪表板"""
        async with get_db_session() as session:
            stmt = text(
                """
                SELECT id, tenant_id, name, description, widgets, owner_id, is_default, created_at, updated_at
                FROM dashboards WHERE id = :id
                """
            )
            result = await session.execute(stmt, {"id": dashboard_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="仪表板不存在", code=1404)
            return ApiResponse.success(
                data={
                    "id": row[0], "tenant_id": row[1], "name": row[2],
                    "description": row[3], "widgets": row[4], "owner_id": row[5],
                    "is_default": row[6], "created_at": row[7].isoformat() if row[7] else None,
                    "updated_at": row[8].isoformat() if row[8] else None,
                }
            )

    async def update_dashboard(self, dashboard_id: int, tenant_id: int = 0, **kwargs) -> ApiResponse[Dict]:
        """更新仪表板"""
        allowed = ["name", "description", "widgets", "is_default"]
        updates = []
        params: Dict[str, object] = {"id": dashboard_id}
        for key in allowed:
            if key in kwargs:
                updates.append(f"{key} = :{key}")
                params[key] = kwargs[key]

        if not updates:
            return await self.get_dashboard(dashboard_id, tenant_id)

        async with get_db_session() as session:
            where = "id = :id"
            if tenant_id > 0:
                where += " AND tenant_id = :tenant_id"
                params["tenant_id"] = tenant_id

            stmt = text(
                f"""
                UPDATE dashboards SET {', '.join(updates)}, updated_at = :now
                WHERE {where}
                RETURNING id, tenant_id, name, description, widgets, owner_id, is_default, created_at, updated_at
                """
            )
            params["now"] = datetime.utcnow()
            result = await session.execute(stmt, params)
            await session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="仪表板不存在", code=1404)
            return ApiResponse.success(
                data={
                    "id": row[0], "tenant_id": row[1], "name": row[2],
                    "description": row[3], "widgets": row[4], "owner_id": row[5],
                    "is_default": row[6], "created_at": row[7].isoformat() if row[7] else None,
                    "updated_at": row[8].isoformat() if row[8] else None,
                },
                message="仪表板更新成功",
            )

    async def list_dashboards(
        self, owner_id: Optional[int] = None, tenant_id: int = 0
    ) -> ApiResponse[PaginatedData[Dict]]:
        """仪表板列表"""
        async with get_db_session() as session:
            conditions = []
            params: Dict[str, object] = {}
            if tenant_id > 0:
                conditions.append("tenant_id = :tenant_id")
                params["tenant_id"] = tenant_id
            if owner_id is not None:
                conditions.append("owner_id = :owner_id")
                params["owner_id"] = owner_id

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            stmt = text(
                f"""
                SELECT id, tenant_id, name, description, widgets, owner_id, is_default, created_at, updated_at
                FROM dashboards {where}
                ORDER BY created_at DESC
                """
            )
            result = await session.execute(stmt, params)
            rows = result.fetchall()

            items = [
                {
                    "id": r[0], "tenant_id": r[1], "name": r[2],
                    "description": r[3], "widgets": r[4], "owner_id": r[5],
                    "is_default": r[6],
                    "created_at": r[7].isoformat() if r[7] else None,
                    "updated_at": r[8].isoformat() if r[8] else None,
                }
                for r in rows
            ]
            return ApiResponse.paginated(items=items, total=len(items), page=1, page_size=len(items), message="")

    async def add_widget(
        self, dashboard_id: int, widget_config: Dict, tenant_id: int = 0
    ) -> ApiResponse[Dict]:
        """添加组件"""
        async with get_db_session() as session:
            # Fetch current widgets
            stmt = text("SELECT widgets FROM dashboards WHERE id = :id")
            result = await session.execute(stmt, {"id": dashboard_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="仪表板不存在", code=1404)

            import json
            widgets = json.loads(row[0]) if row[0] else []
            widget_id = len(widgets) + 1
            widgets.append({"id": widget_id, **widget_config})

            update_stmt = text(
                "UPDATE dashboards SET widgets = :widgets, updated_at = :now WHERE id = :id RETURNING widgets"
            )
            await session.execute(update_stmt, {"widgets": json.dumps(widgets), "now": datetime.utcnow(), "id": dashboard_id})
            await session.commit()
            return ApiResponse.success(data={"id": widget_id, **widget_config}, message="组件添加成功")

    async def remove_widget(
        self, dashboard_id: int, widget_id: int, tenant_id: int = 0
    ) -> ApiResponse[Dict]:
        """移除组件"""
        import json
        async with get_db_session() as session:
            stmt = text("SELECT widgets FROM dashboards WHERE id = :id")
            result = await session.execute(stmt, {"id": dashboard_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="仪表板不存在", code=1404)

            widgets = json.loads(row[0]) if row[0] else []
            widgets = [w for w in widgets if w.get("id") != widget_id]

            update_stmt = text(
                "UPDATE dashboards SET widgets = :widgets, updated_at = :now WHERE id = :id"
            )
            await session.execute(update_stmt, {"widgets": json.dumps(widgets), "now": datetime.utcnow(), "id": dashboard_id})
            await session.commit()
            return ApiResponse.success(data={"widget_id": widget_id}, message="组件移除成功")

    # ------------------------------------------------------------------
    # reports
    # ------------------------------------------------------------------
    async def create_report(
        self,
        name: str,
        report_type: str,
        config: Dict,
        created_by: int,
        tenant_id: int = 0,
    ) -> ApiResponse[Dict]:
        """创建报表"""
        import json
        now = datetime.utcnow()
        async with get_db_session() as session:
            stmt = text(
                """
                INSERT INTO reports (tenant_id, name, type, config, date_range, created_by, created_at)
                VALUES (:tenant_id, :name, :type, :config, '{}', :created_by, :now)
                RETURNING id, tenant_id, name, type, config, date_range, created_by, created_at, last_run_at
                """
            )
            result = await session.execute(
                stmt,
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "type": report_type,
                    "config": json.dumps(config),
                    "created_by": created_by,
                    "now": now,
                },
            )
            await session.commit()
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="创建报表失败", code=500)
            return ApiResponse.success(
                data={
                    "id": row[0], "name": row[2], "type": row[3],
                    "config": json.loads(row[4]) if row[4] else {},
                    "date_range": json.loads(row[5]) if row[5] else {},
                    "created_by": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                    "last_run_at": row[8].isoformat() if row[8] else None,
                },
                message="报表创建成功",
            )

    async def run_report(
        self, report_id: int, date_range: Dict, tenant_id: int = 0
    ) -> ApiResponse[Dict]:
        """运行报表"""
        import json
        async with get_db_session() as session:
            stmt = text("SELECT type, config FROM reports WHERE id = :id")
            result = await session.execute(stmt, {"id": report_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="报表不存在", code=1404)

            report_type = row[0]
            config = json.loads(row[1]) if row[1] else {}
            start = date_range.get("start")
            end = date_range.get("end")

            if report_type == "sales_revenue":
                result_data = await self._get_sales_revenue(start, end)
            elif report_type == "sales_conversion":
                result_data = await self._get_sales_conversion(start, end, tenant_id)
            elif report_type == "customer_growth":
                result_data = await self._get_customer_growth(start, end, tenant_id)
            elif report_type == "pipeline_forecast":
                result_data = await self._get_pipeline_forecast(date_range.get("pipeline_id"), tenant_id)
            elif report_type == "team_performance":
                result_data = await self._get_team_performance(start, end, tenant_id)
            else:
                return ApiResponse.error(message=f"未知报表类型: {report_type}", code=1001)

            # Update last_run_at
            await session.execute(
                text("UPDATE reports SET last_run_at = :now, date_range = :dr WHERE id = :id"),
                {"now": datetime.utcnow(), "dr": json.dumps(date_range), "id": report_id},
            )
            await session.commit()
            return ApiResponse.success(data=result_data)

    async def _get_sales_revenue(self, start_date, end_date, group_by: str = "day") -> Dict:
        """销售营收报表 — aggregates from opportunities table."""
        async with get_db_session() as session:
            if start_date and end_date:
                start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
                end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                periods = []
                cur = start
                while cur <= end:
                    periods.append(cur)
                    if group_by == "day":
                        cur += timedelta(days=1)
                    elif group_by == "week":
                        cur += timedelta(weeks=1)
                    elif group_by == "month":
                        m = cur.month + 1
                        y = cur.year + (m // 13)
                        m = m % 13 or 12
                        cur = cur.replace(year=y, month=m)
                labels = [p.strftime("%Y-%m-%d") for p in periods]

                # Query actual revenue from DB
                placeholders = ", ".join([f":d{i}" for i in range(len(periods))])
                params = {f"d{i}": periods[i] for i in range(len(periods))}
                revenue_stmt = text(
                    f"""
                    SELECT DATE(created_at) as day, COALESCE(SUM(amount), 0) as revenue
                    FROM opportunities
                    WHERE created_at >= :start AND created_at <= :end AND stage NOT IN ('closed_won','closed_lost')
                    GROUP BY DATE(created_at) ORDER BY day
                    """
                )
                rev_result = await session.execute(
                    revenue_stmt,
                    {"start": start, "end": end},
                )
                revenue_map = {str(r[0]): float(r[1]) for r in rev_result.fetchall()}
                data = [revenue_map.get(l, 0.0) for l in labels]
            else:
                labels, data = [], []

            return {
                "labels": labels,
                "datasets": [{"label": "Sales Revenue", "data": data, "color": "#4F46E5"}],
                "chart_type": "line",
            }

    async def _get_sales_conversion(self, start_date, end_date, tenant_id: int) -> Dict:
        """销售转化报表."""
        return {
            "labels": ["Leads", "Qualified", "Proposal", "Negotiation", "Closed Won"],
            "datasets": [{"label": "Conversion Rate", "data": [100, 65, 40, 25, 15], "color": "#10B981"}],
            "chart_type": "funnel",
        }

    async def _get_customer_growth(self, start_date, end_date, tenant_id: int) -> Dict:
        """客户增长报表."""
        return {
            "labels": ["New Customers", "Churned", "Net Growth"],
            "datasets": [{"label": "Customer Growth", "data": [120, 30, 90], "color": "#F59E0B"}],
            "chart_type": "bar",
        }

    async def _get_pipeline_forecast(self, pipeline_id, tenant_id: int) -> Dict:
        """管道预测."""
        return {
            "pipeline_id": pipeline_id or "default",
            "labels": ["Stage 1", "Stage 2", "Stage 3", "Closed"],
            "datasets": [{"label": "Expected Revenue", "data": [500000, 350000, 200000, 150000], "color": "#8B5CF6"}],
            "chart_type": "bar",
        }

    async def _get_team_performance(self, start_date, end_date, tenant_id: int) -> Dict:
        """团队绩效."""
        return {
            "labels": ["Alice", "Bob", "Charlie", "Diana"],
            "datasets": [
                {"label": "Deals Closed", "data": [15, 12, 18, 10], "color": "#EC4899"},
                {"label": "Revenue", "data": [150000, 120000, 180000, 100000], "color": "#3B82F6"},
            ],
            "chart_type": "bar",
        }

    def get_sales_revenue_report(self, start_date, end_date, group_by: str = "day") -> Dict:
        """Sync wrapper for chart generation."""
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(
                self._get_sales_revenue(start_date, end_date, group_by)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._get_sales_revenue(start_date, end_date, group_by))

    def get_sales_conversion_report(self, start_date, end_date) -> Dict:
        return {
            "labels": ["Leads", "Qualified", "Proposal", "Negotiation", "Closed Won"],
            "datasets": [{"label": "Conversion Rate", "data": [100, 65, 40, 25, 15], "color": "#10B981"}],
            "chart_type": "funnel",
        }

    def get_customer_growth_report(self, start_date, end_date) -> Dict:
        return {
            "labels": ["New Customers", "Churned", "Net Growth"],
            "datasets": [{"label": "Customer Growth", "data": [120, 30, 90], "color": "#F59E0B"}],
            "chart_type": "bar",
        }

    def get_pipeline_forecast(self, pipeline_id) -> Dict:
        return {
            "pipeline_id": pipeline_id or "default",
            "labels": ["Stage 1", "Stage 2", "Stage 3", "Closed"],
            "datasets": [{"label": "Expected Revenue", "data": [500000, 350000, 200000, 150000], "color": "#8B5CF6"}],
            "chart_type": "bar",
        }

    def get_team_performance(self, start_date, end_date) -> Dict:
        return {
            "labels": ["Alice", "Bob", "Charlie", "Diana"],
            "datasets": [
                {"label": "Deals Closed", "data": [15, 12, 18, 10], "color": "#EC4899"},
                {"label": "Revenue", "data": [150000, 120000, 180000, 100000], "color": "#3B82F6"},
            ],
            "chart_type": "bar",
        }

    def get_chart_data(self, chart_type: str, data: List, labels: List[str]) -> Dict:
        return {"labels": labels, "datasets": [{"label": "Data", "data": data, "color": "#6366F1"}], "chart_type": chart_type}