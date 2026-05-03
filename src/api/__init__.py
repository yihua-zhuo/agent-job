from flask import Flask
from src.api.customers import customer_bp
from src.api.sales import sales_bp


def register_routes(app: Flask):
    app.register_blueprint(customer_bp)
    app.register_blueprint(sales_bp)
