"""Customer API - Synchronous wrapper for async customer service."""
from flask import Blueprint, request, jsonify
from services.customer_service import CustomerService
from internal.middleware.auth import require_auth, get_current_tenant_id
from api._sync_helper import run_async

customer_bp = Blueprint('customers', __name__, url_prefix='/api/v1/customers')


def _get_tenant_id():
    tenant_id = get_current_tenant_id()
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise Exception("Token is missing a valid tenant_id")
    return tenant_id


@customer_bp.errorhandler(Exception)
def _handle_error(e):
    msg = str(e)
    if "tenant" in msg.lower():
        return jsonify({"code": 401, "message": "Tenant context required"}), 401
    return jsonify({"code": 500, "message": msg}), 500


def _validate_pagination(page, page_size):
    if page < 1:
        return False, {"code": 1001, "message": "page must be >= 1"}
    if page_size < 1 or page_size > 100:
        return False, {"code": 1001, "message": "page_size must be between 1 and 100"}
    return True, None


@customer_bp.route('', methods=['POST'])
@require_auth
def create_customer():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    if not data.get('name') or not data.get('name').strip():
        return jsonify({"code": 1001, "message": "客户名称不能为空"}), 400

    svc = CustomerService()
    result = run_async(svc.create_customer, data, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('', methods=['GET'])
@require_auth
def list_customers():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    valid, error = _validate_pagination(page, page_size)
    if not valid:
        return jsonify(error), 400
    status = request.args.get('status')
    owner_id = request.args.get('owner_id', type=int)
    tags = request.args.get('tags')

    svc = CustomerService()
    result = run_async(
        svc.list_customers,
        page=page, page_size=page_size, status=status, owner_id=owner_id, tags=tags,
        tenant_id=_get_tenant_id()
    )
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['GET'])
@require_auth
def get_customer(customer_id):
    svc = CustomerService()
    result = run_async(svc.get_customer, customer_id, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['PUT'])
@require_auth
def update_customer(customer_id):
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    svc = CustomerService()
    result = run_async(svc.update_customer, customer_id, data, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
@require_auth
def delete_customer(customer_id):
    svc = CustomerService()
    result = run_async(svc.delete_customer, customer_id, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/search', methods=['GET'])
@require_auth
def search_customers():
    keyword = request.args.get('keyword', '')
    import re
    keyword = re.sub(r'<[^>]*>', '', keyword)
    keyword = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', keyword).strip()

    svc = CustomerService()
    result = run_async(svc.search_customers, keyword, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>/tags', methods=['POST'])
@require_auth
def add_tag(customer_id):
    data = request.get_json()
    tag = data.get('tag') if data else None
    if not tag:
        return jsonify({"code": 1001, "message": "tag is required"}), 400

    svc = CustomerService()
    result = run_async(svc.add_tag, customer_id, tag, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>/tags/<tag>', methods=['DELETE'])
@require_auth
def remove_tag(customer_id, tag):
    svc = CustomerService()
    result = run_async(svc.remove_tag, customer_id, tag, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>/status', methods=['PUT'])
@require_auth
def change_status(customer_id):
    data = request.get_json()
    status = data.get('status') if data else None
    if not status:
        return jsonify({"code": 1001, "message": "status is required"}), 400

    svc = CustomerService()
    result = run_async(svc.change_status, customer_id, status, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/<int:customer_id>/owner', methods=['PUT'])
@require_auth
def assign_owner(customer_id):
    data = request.get_json()
    owner_id = data.get('owner_id') if data else None
    if not owner_id:
        return jsonify({"code": 1001, "message": "owner_id is required"}), 400

    svc = CustomerService()
    result = run_async(svc.assign_owner, customer_id, owner_id, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())


@customer_bp.route('/import', methods=['POST'])
@require_auth
def bulk_import():
    data = request.get_json()
    customers = data.get('customers', []) if data else []
    if not customers:
        return jsonify({"code": 1001, "message": "customers list is required"}), 400

    svc = CustomerService()
    result = run_async(svc.bulk_import, customers, tenant_id=_get_tenant_id())
    return jsonify(result.to_dict())