from flask import Flask
from api.customers import customer_bp
from api.sales import sales_bp


def register_routes(app: Flask):
    app.register_blueprint(customer_bp)
    app.register_blueprint(sales_bp)
