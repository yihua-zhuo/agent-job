"""Central API router — aggregates all feature routers (requirement 5)."""
from api.routers.customers import customers_router
from api.routers.sales import sales_router

__all__ = ["customers_router", "sales_router"]