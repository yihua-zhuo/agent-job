"""Services package for CRM system."""
from services.activity_service import ActivityService
from services.analytics_service import AnalyticsService
from services.auth_service import AuthService, is_valid_email, sanitize_string, validate_id
from services.automation_rules import AutomationRules
from services.churn_prediction import ChurnPredictionService
from services.customer_service import CustomerService
from services.data_isolation import (
    DataIsolationError,
    TenantScope,
    is_cross_tenant_safe,
    require_tenant_id,
    sanitize_tenant_write,
    get_cross_tenant_fields,
)
from services.import_export_service import ImportExportService
from services.marketing_service import MarketingService
from services.notification_service import NotificationService
from services.report_service import ReportService
from services.rbac_service import RBACService, Permission
from services.sales_recommendation import SalesRecommendationService
from services.sales_service import SalesService
from services.smart_categorization import SmartCategorizationService
from services.sla_service import SLAService
from services.task_service import TaskService
from services.tenant_service import TenantService
from services.trigger_service import TriggerService
from services.user_service import UserService
from services.workflow_service import WorkflowService

__all__ = [
    "ActivityService",
    "AnalyticsService",
    "AuthService",
    "AutomationRules",
    "ChurnPredictionService",
    "CustomerService",
    "DataIsolationError",
    "ImportExportService",
    "is_valid_email",
    "is_cross_tenant_safe",
    "MarketingService",
    "NotificationService",
    "Permission",
    "RBACService",
    "ReportService",
    "require_tenant_id",
    "sanitize_string",
    "sanitize_tenant_write",
    "SalesRecommendationService",
    "SalesService",
    "SmartCategorizationService",
    "SLAService",
    "get_cross_tenant_fields",
    "TaskService",
    "TenantScope",
    "TenantService",
    "TriggerService",
    "UserService",
    "validate_id",
    "WorkflowService",
]
