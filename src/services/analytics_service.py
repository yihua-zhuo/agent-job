from datetime import datetime, timedelta
from typing import Optional, List, Dict


class AnalyticsService:
    def __init__(self, session=None):
        self._session = session
        self._dashboards = {}
        self._reports = {}
        self._next_id = 1

    # Dashboard methods
    def create_dashboard(self, name: str, owner_id: int, description: Optional[str] = None) -> Dict:
        """创建仪表板"""
        now = datetime.utcnow()
        dashboard = {
            "id": self._next_id,
            "name": name,
            "description": description,
            "widgets": [],
            "owner_id": owner_id,
            "is_default": False,
            "created_at": now,
            "updated_at": now,
        }
        self._dashboards[self._next_id] = dashboard
        self._next_id += 1
        return dashboard

    def get_dashboard(self, dashboard_id: int) -> Optional[Dict]:
        """获取仪表板"""
        return self._dashboards.get(dashboard_id)

    def update_dashboard(self, dashboard_id: int, **kwargs) -> Optional[Dict]:
        """更新仪表板"""
        if dashboard_id not in self._dashboards:
            return None
        dashboard = self._dashboards[dashboard_id]
        for key, value in kwargs.items():
            if key in ["name", "description", "widgets", "is_default"]:
                dashboard[key] = value
        dashboard["updated_at"] = datetime.utcnow()
        return dashboard

    def list_dashboards(self, owner_id: Optional[int] = None) -> List[Dict]:
        """仪表板列表"""
        if owner_id is None:
            return list(self._dashboards.values())
        return [d for d in self._dashboards.values() if d["owner_id"] == owner_id]

    def add_widget(self, dashboard_id: int, widget_config: Dict) -> Optional[Dict]:
        """添加组件"""
        if dashboard_id not in self._dashboards:
            return None
        dashboard = self._dashboards[dashboard_id]
        widget = {"id": len(dashboard["widgets"]) + 1, **widget_config}
        dashboard["widgets"].append(widget)
        dashboard["updated_at"] = datetime.utcnow()
        return widget

    def remove_widget(self, dashboard_id: int, widget_id: int) -> bool:
        """移除组件"""
        if dashboard_id not in self._dashboards:
            return False
        dashboard = self._dashboards[dashboard_id]
        dashboard["widgets"] = [w for w in dashboard["widgets"] if w["id"] != widget_id]
        dashboard["updated_at"] = datetime.utcnow()
        return True

    # Report methods
    def create_report(
        self,
        name: str,
        report_type: str,
        config: Dict,
        created_by: int,
    ) -> Dict:
        """创建报表"""
        now = datetime.utcnow()
        report = {
            "id": self._next_id,
            "name": name,
            "type": report_type,
            "config": config,
            "date_range": {"start": None, "end": None},
            "created_by": created_by,
            "created_at": now,
            "last_run_at": None,
        }
        self._reports[self._next_id] = report
        self._next_id += 1
        return report

    def run_report(self, report_id: int, date_range: Dict) -> Optional[Dict]:
        """运行报表"""
        if report_id not in self._reports:
            return None
        report = self._reports[report_id]
        report["date_range"] = date_range
        report["last_run_at"] = datetime.utcnow()

        report_type = report["type"]
        start = date_range.get("start")
        end = date_range.get("end")

        if report_type == "sales_revenue":
            return self.get_sales_revenue_report(start, end)
        elif report_type == "sales_conversion":
            return self.get_sales_conversion_report(start, end)
        elif report_type == "customer_growth":
            return self.get_customer_growth_report(start, end)
        elif report_type == "pipeline_forecast":
            return self.get_pipeline_forecast(date_range.get("pipeline_id"))
        elif report_type == "team_performance":
            return self.get_team_performance(start, end)
        else:
            return {"error": "Unknown report type"}

    def get_sales_revenue_report(self, start_date, end_date, group_by: str = "day") -> Dict:
        """销售营收报表"""
        # 返回：每日/周/月销售额
        labels = []
        data = []
        if start_date and end_date:
            start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
            end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
            delta = end - start
            periods = []
            current = start
            while current <= end:
                periods.append(current)
                if group_by == "day":
                    current += timedelta(days=1)
                elif group_by == "week":
                    current += timedelta(weeks=1)
                elif group_by == "month":
                    # approximate month advance
                    month = current.month + 1
                    year = current.year + (month // 13)
                    month = month % 13 or 12
                    current = current.replace(year=year, month=month)
            labels = [p.strftime("%Y-%m-%d") for p in periods]
            data = [0.0] * len(periods)  # placeholder data
        return {
            "labels": labels,
            "datasets": [{"label": "Sales Revenue", "data": data, "color": "#4F46E5"}],
            "chart_type": "line",
        }

    def get_sales_conversion_report(self, start_date, end_date) -> Dict:
        """销售转化报表"""
        # 返回：各阶段转化率
        return {
            "labels": ["Leads", "Qualified", "Proposal", "Negotiation", "Closed Won"],
            "datasets": [
                {
                    "label": "Conversion Rate",
                    "data": [100, 65, 40, 25, 15],
                    "color": "#10B981",
                }
            ],
            "chart_type": "funnel",
        }

    def get_customer_growth_report(self, start_date, end_date) -> Dict:
        """客户增长报表"""
        # 返回：新增客户数、流失数、净增长
        return {
            "labels": ["New Customers", "Churned", "Net Growth"],
            "datasets": [
                {"label": "Customer Growth", "data": [120, 30, 90], "color": "#F59E0B"}
            ],
            "chart_type": "bar",
        }

    def get_pipeline_forecast(self, pipeline_id) -> Dict:
        """管道预测"""
        # 按概率计算预期收入
        if pipeline_id is None:
            pipeline_id = "default"
        return {
            "pipeline_id": pipeline_id,
            "labels": ["Stage 1", "Stage 2", "Stage 3", "Closed"],
            "datasets": [
                {
                    "label": "Expected Revenue",
                    "data": [500000, 350000, 200000, 150000],
                    "color": "#8B5CF6",
                }
            ],
            "chart_type": "bar",
        }

    def get_team_performance(self, start_date, end_date) -> Dict:
        """团队绩效"""
        # 各销售的任务完成数、成交数、金额
        return {
            "labels": ["Alice", "Bob", "Charlie", "Diana"],
            "datasets": [
                {"label": "Deals Closed", "data": [15, 12, 18, 10], "color": "#EC4899"},
                {"label": "Revenue", "data": [150000, 120000, 180000, 100000], "color": "#3B82F6"},
            ],
            "chart_type": "bar",
        }

    # Chart data methods
    def get_chart_data(self, chart_type: str, data: List, labels: List[str]) -> Dict:
        """格式化图表数据"""
        return {
            "labels": labels,
            "datasets": [{"label": "Data", "data": data, "color": "#6366F1"}],
            "chart_type": chart_type,
        }
