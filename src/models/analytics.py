from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReportType(Enum):
    SALES_REVENUE = "sales_revenue"
    SALES_CONVERSION = "sales_conversion"
    CUSTOMER_GROWTH = "customer_growth"
    CUSTOMER_CHURN = "customer_churn"
    PIPELINE_FORECAST = "pipeline_forecast"
    TEAM_PERFORMANCE = "team_performance"


class ChartType(Enum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    FUNNEL = "funnel"
    TABLE = "table"


@dataclass
class Dashboard:
    id: int | None
    name: str
    description: str | None
    widgets: list[dict]  # [{type, config, position}]
    owner_id: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class Report:
    id: int | None
    name: str
    type: ReportType
    config: dict  # 报表配置
    date_range: dict  # {start, end}
    created_by: int
    created_at: datetime
    last_run_at: datetime | None


@dataclass
class ChartData:
    """图表数据"""

    labels: list[str]
    datasets: list[dict]  # [{label, data, color}]
    chart_type: ChartType
