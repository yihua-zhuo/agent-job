"""Sales API - 同步封装 async 服务层"""
from flask import Blueprint, request, jsonify
from services.sales_service import SalesService
from internal.middleware.auth import require_auth, get_current_tenant_id
from api._sync_helper import run_async

sales_bp = Blueprint('sales', __name__, url_prefix='/api/v1')
service = None  # created per request


def _get_tenant_id():
    tenant_id = get_current_tenant_id()
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise Exception("Token is missing a valid tenant_id")
    return tenant_id


@sales_bp.errorhandler(Exception)
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


@sales_bp.route('/pipelines', methods=['POST'])
@require_auth
def create_pipeline():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    if not data.get('name') or not data.get('name').strip():
        return jsonify({"code": 1001, "message": "管道名称不能为空"}), 400

    svc = SalesService()
    result = run_async(svc.create_pipeline, _get_tenant_id(), data)
    return jsonify(result.to_dict())


@sales_bp.route('/pipelines', methods=['GET'])
@require_auth
def list_pipelines():
    svc = SalesService()
    result = run_async(svc.list_pipelines, _get_tenant_id())
    return jsonify(result.to_dict())


@sales_bp.route('/pipelines/<int:pipeline_id>', methods=['GET'])
@require_auth
def get_pipeline(pipeline_id):
    svc = SalesService()
    result = run_async(svc.get_pipeline, _get_tenant_id(), pipeline_id)
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@sales_bp.route('/pipelines/<int:pipeline_id>/stats', methods=['GET'])
@require_auth
def get_pipeline_stats(pipeline_id):
    svc = SalesService()
    result = run_async(svc.get_pipeline_stats, _get_tenant_id(), pipeline_id)
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@sales_bp.route('/pipelines/<int:pipeline_id>/funnel', methods=['GET'])
@require_auth
def get_pipeline_funnel(pipeline_id):
    svc = SalesService()
    result = run_async(svc.get_pipeline_funnel, _get_tenant_id(), pipeline_id)
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@sales_bp.route('/opportunities', methods=['POST'])
@require_auth
def create_opportunity():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    required_fields = ['name', 'customer_id', 'pipeline_id', 'stage', 'amount', 'owner_id']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"code": 1002, "message": f"缺少必填字段: {', '.join(missing)}"}), 400

    svc = SalesService()
    result = run_async(svc.create_opportunity, _get_tenant_id(), data)
    return jsonify(result.to_dict())


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

    svc = SalesService()
    result = run_async(
        svc.list_opportunities, _get_tenant_id(),
        page=page, page_size=page_size, pipeline_id=pipeline_id, stage=stage, owner_id=owner_id
    )
    return jsonify(result.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>', methods=['GET'])
@require_auth
def get_opportunity(opp_id):
    svc = SalesService()
    result = run_async(svc.get_opportunity, _get_tenant_id(), opp_id)
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@sales_bp.route('/opportunities/<int:opp_id>', methods=['PUT'])
@require_auth
def update_opportunity(opp_id):
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    svc = SalesService()
    result = run_async(svc.update_opportunity, _get_tenant_id(), opp_id, data)
    return jsonify(result.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>/stage', methods=['PUT'])
@require_auth
def change_stage(opp_id):
    data = request.get_json()
    stage = data.get('stage')
    if not stage:
        return jsonify({"code": 1001, "message": "stage is required"}), 400

    svc = SalesService()
    result = run_async(svc.change_stage, _get_tenant_id(), opp_id, stage)
    return jsonify(result.to_dict())


@sales_bp.route('/forecast', methods=['GET'])
@require_auth
def get_forecast():
    owner_id = request.args.get('owner_id', type=int)
    svc = SalesService()
    result = run_async(svc.get_forecast, _get_tenant_id(), owner_id=owner_id)
    return jsonify(result.to_dict())