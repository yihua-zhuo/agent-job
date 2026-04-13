from flask import Blueprint, request, jsonify, g
from src.services.customer_service import CustomerService
from src.middleware.auth import AuthMiddleware
import os

customer_bp = Blueprint('customers', __name__, url_prefix='/api/v1/customers')
service = CustomerService()

# Initialize auth middleware with JWT_SECRET from environment
_auth = AuthMiddleware(secret_key=os.environ.get('JWT_SECRET_KEY'))


class _MissingTenantError(Exception):
    """Raised when authenticated user has no valid tenant_id in the token."""


def _get_tenant_id() -> int:
    """Extract tenant_id from the current request context.

    A missing or non-positive tenant_id means the token is not scoped to a
    tenant; treating it as 0 would silently bypass tenant isolation in the
    service layer, so we raise instead.
    """
    if not hasattr(g, 'current_user'):
        raise _MissingTenantError("No authenticated user in request context")
    tenant_id = g.current_user.get('tenant_id')
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise _MissingTenantError("Token is missing a valid tenant_id")
    return tenant_id


@customer_bp.errorhandler(_MissingTenantError)
def _handle_missing_tenant(e):
    return jsonify({"code": 401, "message": "Tenant context required"}), 401


def _validate_pagination(page, page_size):
    """Validate pagination parameters"""
    if page < 1:
        return False, {"code": 1001, "message": "page must be >= 1"}
    if page_size < 1 or page_size > 100:
        return False, {"code": 1001, "message": "page_size must be between 1 and 100"}
    return True, None


@customer_bp.route('', methods=['POST'])
@_auth.require_auth
def create_customer():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    
    # Basic input validation
    if not data.get('name') or not data.get('name').strip():
        return jsonify({"code": 1001, "message": "客户名称不能为空"}), 400
    if data.get('email') and not _is_valid_email(data.get('email')):
        return jsonify({"code": 1001, "message": "邮箱格式不正确"}), 400
    
    response = service.create_customer(data, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('', methods=['GET'])
@_auth.require_auth
def list_customers():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    
    valid, error = _validate_pagination(page, page_size)
    if not valid:
        return jsonify(error), 400
    
    status = request.args.get('status')
    owner_id = request.args.get('owner_id', type=int)
    tags = request.args.get('tags')
    response = service.list_customers(
        page=page, page_size=page_size, status=status, owner_id=owner_id, tags=tags,
        tenant_id=_get_tenant_id()
    )
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['GET'])
@_auth.require_auth
def get_customer(customer_id):
    response = service.get_customer(customer_id, tenant_id=_get_tenant_id())
    status_code = 200 if response.status.value == "success" else 404
    return jsonify(response.to_dict()), status_code


@customer_bp.route('/<int:customer_id>', methods=['PUT'])
@_auth.require_auth
def update_customer(customer_id):
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    response = service.update_customer(customer_id, data, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
@_auth.require_auth
def delete_customer(customer_id):
    response = service.delete_customer(customer_id, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/search', methods=['GET'])
@_auth.require_auth
def search_customers():
    keyword = request.args.get('keyword', '')
    # Sanitize keyword to prevent XSS
    keyword = _sanitize_string(keyword)
    response = service.search_customers(keyword, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/tags', methods=['POST'])
@_auth.require_auth
def add_tag(customer_id):
    data = request.get_json()
    tag = data.get('tag')
    if not tag or not tag.strip():
        return jsonify({"code": 1001, "message": "Tag cannot be empty"}), 400
    # Sanitize tag
    tag = _sanitize_string(tag)
    response = service.add_tag(customer_id, tag, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/tags/<tag>', methods=['DELETE'])
@_auth.require_auth
def remove_tag(customer_id, tag):
    # Sanitize tag
    tag = _sanitize_string(tag)
    response = service.remove_tag(customer_id, tag, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/status', methods=['PUT'])
@_auth.require_auth
def change_status(customer_id):
    data = request.get_json()
    status = data.get('status')
    valid_statuses = ['active', 'inactive', 'blocked']
    if status not in valid_statuses:
        return jsonify({"code": 1001, "message": f"status must be one of: {valid_statuses}"}), 400
    response = service.change_status(customer_id, status, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/<int:customer_id>/owner', methods=['PUT'])
@_auth.require_auth
def assign_owner(customer_id):
    data = request.get_json()
    owner_id = data.get('owner_id')
    if not owner_id or not isinstance(owner_id, int):
        return jsonify({"code": 1001, "message": "owner_id must be a valid integer"}), 400
    response = service.assign_owner(customer_id, owner_id, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


@customer_bp.route('/import', methods=['POST'])
@_auth.require_auth
def bulk_import():
    data = request.get_json()
    customers = data.get('customers', [])
    if not isinstance(customers, list):
        return jsonify({"code": 1001, "message": "customers must be an array"}), 400
    if len(customers) > 1000:
        return jsonify({"code": 1001, "message": "Maximum 1000 customers per import"}), 400
    response = service.bulk_import(customers, tenant_id=_get_tenant_id())
    return jsonify(response.to_dict())


def _is_valid_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _sanitize_string(s: str) -> str:
    """Basic string sanitization to prevent XSS"""
    if not s:
        return s
    # Remove HTML tags and control characters
    import re
    s = re.sub(r'<[^>]*>', '', s)
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()