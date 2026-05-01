"""Services package for CRM system — lazy loading to avoid SQLAlchemy duplicate table registration."""
import sys
from types import ModuleType
from typing import TYPE_CHECKING

_lazy_map = {
    "ActivityService": "src.services.activity_service",
    "AnalyticsService": "src.services.analytics_service",
    "AuthService": "src.services.auth_service",
    "AutomationRules": "src.services.automation_rules",
    "ChurnPredictionService": "src.services.churn_prediction",
    "CustomerService": "src.services.customer_service",
    "DataIsolationError": "src.services.data_isolation",
    "DataIsolationService": "src.services.data_isolation",
    "ImportExportService": "src.services.import_export_service",
    "is_valid_email": "src.services.auth_service",
    "is_cross_tenant_safe": "src.services.data_isolation",
    "MarketingService": "src.services.marketing_service",
    "NotificationService": "src.services.notification_service",
    "Permission": "src.services.rbac_service",
    "RBACService": "src.services.rbac_service",
    "ReportService": "src.services.report_service",
    "require_tenant_id": "src.services.data_isolation",
    "sanitize_string": "src.services.auth_service",
    "sanitize_tenant_write": "src.services.data_isolation",
    "SalesRecommendationService": "src.services.sales_recommendation",
    "SalesService": "src.services.sales_service",
    "SmartCategorizationService": "src.services.smart_categorization",
    "SLAService": "src.services.sla_service",
    "get_cross_tenant_fields": "src.services.data_isolation",
    "TaskService": "src.services.task_service",
    "TenantScope": "src.services.data_isolation",
    "TenantService": "src.services.tenant_service",
    "TriggerService": "src.services.trigger_service",
    "UserService": "src.services.user_service",
    "validate_id": "src.services.auth_service",
    "WorkflowService": "src.services.workflow_service",
}


def __getattr__(name: str):
    if name in _lazy_map:
        module_path = _lazy_map[name]
        module = __import__(module_path, fromlist=[name])
        val = getattr(module, name)
        # Cache it
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(__all__)


__all__ = list(_lazy_map.keys())