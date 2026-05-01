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
