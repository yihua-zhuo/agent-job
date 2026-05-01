"""Services package for CRM system — lazy loading to avoid SQLAlchemy duplicate table registration."""
from types import ModuleType
from typing import TYPE_CHECKING

_lazy_map = {
    "ActivityService": "services.activity_service",
    "AnalyticsService": "services.analytics_service",
    "AuthService": "services.auth_service",
    "AutomationRules": "services.automation_rules",
    "ChurnPredictionService": "services.churn_prediction",
    "CustomerService": "services.customer_service",
    "DataIsolationError": "services.data_isolation",
    "DataIsolationService": "services.data_isolation",
    "ImportExportService": "services.import_export_service",
    "is_valid_email": "services.auth_service",
    "is_cross_tenant_safe": "services.data_isolation",
    "MarketingService": "services.marketing_service",
    "NotificationService": "services.notification_service",
    "Permission": "services.rbac_service",
    "RBACService": "services.rbac_service",
    "ReportService": "services.report_service",
    "require_tenant_id": "services.data_isolation",
    "sanitize_string": "services.auth_service",
    "sanitize_tenant_write": "services.data_isolation",
    "SalesRecommendationService": "services.sales_recommendation",
    "SalesService": "services.sales_service",
    "SmartCategorizationService": "services.smart_categorization",
    "SLAService": "services.sla_service",
    "get_cross_tenant_fields": "services.data_isolation",
    "TaskService": "services.task_service",
    "TenantScope": "services.data_isolation",
    "TenantService": "services.tenant_service",
    "TriggerService": "services.trigger_service",
    "UserService": "services.user_service",
    "validate_id": "services.auth_service",
    "WorkflowService": "services.workflow_service",
}


def __getattr__(name: str):
    if name in _lazy_map:
        module_path = _lazy_map[name]
        module = __import__(module_path, fromlist=[name])
        val = getattr(module, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(__all__)


__all__ = list(_lazy_map.keys())