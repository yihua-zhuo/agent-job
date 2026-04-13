"""Services package for CRM system."""
from src.services.activity_service import ActivityService
from src.services.analytics_service import AnalyticsService
from src.services.auth_service import AuthService, is_valid_email, sanitize_string, validate_id
from src.services.automation_rules import AutomationRules
from src.services.churn_prediction import ChurnPredictionService
from src.services.customer_service import CustomerService
from src.services.data_isolation import (
    DataIsolationError,
    TenantScope,
    is_cross_tenant_safe,
    require_tenant_id,
    sanitize_tenant_write,
    get_cross_tenant_fields,
)
from src.services.import_export_service import ImportExportService
from src.services.marketing_service import MarketingService
from src.services.notification_service import NotificationService
from src.services.report_service import ReportService
from src.services.rbac_service import RBACService, Permission
from src.services.sales_recommendation import SalesRecommendationService
from src.services.sales_service import SalesService
from src.services.smart_categorization import SmartCategorizationService
from src.services.sla_service import SLAService
from src.services.task_service import TaskService
from src.services.tenant_service import TenantService
from src.services.trigger_service import TriggerService
from src.services.user_service import UserService
from src.services.workflow_service import WorkflowService

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
    "PaginatedData",
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
