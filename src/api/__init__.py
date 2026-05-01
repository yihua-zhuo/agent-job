"""src/api - FastAPI routes (customers + sales)."""
from api.routes import customers_router, sales_router

__all__ = ['customers_router', 'sales_router']