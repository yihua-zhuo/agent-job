"""Central API router — aggregates all feature routers (requirement 5)."""
from api.routers.customers import customers_router
from api.routers.sales import sales_router
from api.routers.users import users_router
from api.routers.tenants import tenants_router
from api.routers.tickets import tickets_router
from api.routers.activities import activities_router
from api.routers.automation import automation_router
from api.routers.notifications import notifications_router

__all__ = [
    "customers_router",
    "sales_router",
    "users_router",
    "tenants_router",
    "tickets_router",
    "activities_router",
    "notifications_router",
    "automation_router",
]