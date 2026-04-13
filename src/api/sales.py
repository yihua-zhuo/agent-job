from flask import Blueprint, request, jsonify, g
from services.sales_service import SalesService
from internal.middleware.auth import require_auth, get_current_tenant_id
from pkg.errors import AppError

sales_bp = Blueprint('sales', __name__, url_prefix='/api/v1')
service = SalesService()


class _MissingTenantError(Exception):
    """Raised when authenticated user has no valid tenant_id in the token."""


def _get_tenant_id() -> int:
    """Extract tenant_id from the current request context.

    A missing or non-positive tenant_id means the token is not scoped to a
    tenant; treating it as 0 would silently bypass tenant isolation in the
    service layer, so we raise instead.
    """
    tenant_id = get_current_tenant_id()
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise _MissingTenantError("Token is missing a valid tenant_id")
    return tenant_id


@sales_bp.errorhandler(_MissingTenantError)
def _handle_missing_tenant(e):
    return jsonify({"code": 401, "message": "Tenant context required"}), 401


def _validate_pagination(page, page_size):
    """Validate pagination parameters"""
    if page < 1:
        return False, {"code": 1001, "message": "page must be >= 1"}
    if page_size < 1 or page_size > 100:
        return False, {"code": 1001, "message": "page_size must be between 1 and 100"}
    return True, None


@sales_bp.route('/pipelines', methods=['POST'])
@require_auth
def create_pipeline():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    if not data.get('name') or not data.get('name').strip():
        return jsonify({"code": 1001, "message": "管道名称不能为空"}), 400
    response = service.create_pipeline(_get_tenant_id(), data)
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines', methods=['GET'])
@require_auth
def list_pipelines():
    response = service.list_pipelines(_get_tenant_id())
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines/<int:pipeline_id>', methods=['GET'])
@require_auth
def get_pipeline(pipeline_id):
    response = service.get_pipeline(_get_tenant_id(), pipeline_id)
    status_code = 200 if response.status.value == "success" else 404
    return jsonify(response.to_dict()), status_code


@sales_bp.route('/pipelines/<int:pipeline_id>/stats', methods=['GET'])
@require_auth
def get_pipeline_stats(pipeline_id):
    response = service.get_pipeline_stats(_get_tenant_id(), pipeline_id)
    status_code = 200 if response.status.value == "success" else 404
    return jsonify(response.to_dict()), status_code


@sales_bp.route('/pipelines/<int:pipeline_id>/funnel', methods=['GET'])
@require_auth
def get_pipeline_funnel(pipeline_id):
    response = service.get_pipeline_funnel(_get_tenant_id(), pipeline_id)
    status_code = 200 if response.status.value == "success" else 404
    return jsonify(response.to_dict()), status_code


@sales_bp.route('/opportunities', methods=['POST'])
@require_auth
def create_opportunity():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    # Validate required fields
    required_fields = ['name', 'customer_id', 'pipeline_id', 'stage', 'amount', 'owner_id']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"code": 1002, "message": f"缺少必填字段: {', '.join(missing)}"}), 400

    response = service.create_opportunity(_get_tenant_id(), data)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities', methods=['GET'])
@require_auth
def list_opportunities():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)

    valid, error = _validate_pagination(page, page_size)
    if not valid:
        return jsonify(error), 400

    pipeline_id = request.args.get('pipeline_id', type=int)
    stage = request.args.get('stage')
    owner_id = request.args.get('owner_id', type=int)
    response = service.list_opportunities(_get_tenant_id(), page=page, page_size=page_size, pipeline_id=pipeline_id, stage=stage, owner_id=owner_id)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>', methods=['GET'])
@require_auth
def get_opportunity(opp_id):
    response = service.get_opportunity(_get_tenant_id(), opp_id)
    status_code = 200 if response.status.value == "success" else 404
    return jsonify(response.to_dict()), status_code


@sales_bp.route('/opportunities/<int:opp_id>', methods=['PUT'])
@require_auth
def update_opportunity(opp_id):
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    response = service.update_opportunity(_get_tenant_id(), opp_id, data)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>/stage', methods=['PUT'])
@require_auth
def change_stage(opp_id):
    data = request.get_json()
    stage = data.get('stage')
    if not stage:
        return jsonify({"code": 1001, "message": "stage is required"}), 400
    response = service.change_stage(_get_tenant_id(), opp_id, stage)
    return jsonify(response.to_dict())


@sales_bp.route('/forecast', methods=['GET'])
@require_auth
def get_forecast():
    owner_id = request.args.get('owner_id', type=int)
    response = service.get_forecast(_get_tenant_id(), owner_id=owner_id)
    return jsonify(response.to_dict())
