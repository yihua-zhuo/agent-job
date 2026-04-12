from flask import Blueprint, request, jsonify
from src.services.customer_service import CustomerService

customer_bp = Blueprint('customers', __name__, url_prefix='/api/v1/customers')
service = CustomerService()


@customer_bp.route('', methods=['POST'])
def create_customer():
    data = request.get_json()
    response = service.create_customer(data)
    return jsonify(response.to_dict())


@customer_bp.route('', methods=['GET'])
def list_customers():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    status = request.args.get('status')
    owner_id = request.args.get('owner_id', type=int)
    tags = request.args.get('tags')
    response = service.list_customers(page=page, page_size=page_size, status=status, owner_id=owner_id, tags=tags)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    response = service.get_customer(customer_id)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    data = request.get_json()
    response = service.update_customer(customer_id, data)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    response = service.delete_customer(customer_id)
    return jsonify(response.to_dict())


@customer_bp.route('/search', methods=['GET'])
def search_customers():
    keyword = request.args.get('keyword', '')
    response = service.search_customers(keyword)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/tags', methods=['POST'])
def add_tag(customer_id):
    data = request.get_json()
    tag = data.get('tag')
    response = service.add_tag(customer_id, tag)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/tags/<tag>', methods=['DELETE'])
def remove_tag(customer_id, tag):
    response = service.remove_tag(customer_id, tag)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/status', methods=['PUT'])
def change_status(customer_id):
    data = request.get_json()
    status = data.get('status')
    response = service.change_status(customer_id, status)
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/owner', methods=['PUT'])
def assign_owner(customer_id):
    data = request.get_json()
    owner_id = data.get('owner_id')
    response = service.assign_owner(customer_id, owner_id)
    return jsonify(response.to_dict())


@customer_bp.route('/import', methods=['POST'])
def bulk_import():
    data = request.get_json()
    customers = data.get('customers', [])
    response = service.bulk_import(customers)
    return jsonify(response.to_dict())
