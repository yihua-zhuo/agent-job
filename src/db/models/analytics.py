"""Analytics ORM models (dashboards, reports, and chart data)."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

ReportType = Enum(
    "sales_revenue",
    "sales_conversion",
    "customer_growth",
    "customer_churn",
    "pipeline_forecast",
    "team_performance",
    name="report_type_enum",
)
ChartType = Enum(
    "line",
    "bar",
    "pie",
    "funnel",
    "table",
    name="chart_type_enum",
)


class DashboardModel(Base):
    """Dashboard entity mapped to the `dashboards` table."""

    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    widgets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "widgets": self.widgets or [],
            "owner_id": self.owner_id,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReportModel(Base):
    """Report entity mapped to the `reports` table."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    date_range: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chart_data: Mapped[list["ChartDataModel"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "type": self.type,
            "config": self.config or {},
            "date_range": self.date_range or {},
            "created_by": self.created_by,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChartDataModel(Base):
    """Chart data entity mapped to the `chart_data` table."""

    __tablename__ = "chart_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), nullable=False, index=True)
    chart_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report: Mapped["ReportModel"] = relationship(back_populates="chart_data")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "chart_type": self.chart_type,
            "data": self.data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
