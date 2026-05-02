<<<<<<< HEAD
"""Central API router — aggregates all feature routers (requirement 5)."""
from api.routers.customers import customers_router
from api.routers.sales import sales_router
from api.routers.users import users_router
from api.routers.tenants import tenants_router
from api.routers.tickets import tickets_router
from api.routers.activities import activities_router

__all__ = [
    "customers_router",
    "sales_router",
    "users_router",
    "tenants_router",
    "tickets_router",
    "activities_router",
]
=======
from flask import Flask
from api.auth import auth_bp
from api.customers import customer_bp
from api.sales import sales_bp
from api.tickets import ticket_bp


def register_routes(app: Flask):
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(ticket_bp)
>>>>>>> 1ae2cf3fd4773d03d9d142fde28d8b3427259dfb
