"""src/api - FastAPI routes (customers + sales)."""
from src.api.routes import customers_router, sales_router

__all__ = ['customers_router', 'sales_router']