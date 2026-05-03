from flask import Blueprint, request, jsonify
from src.services.sales_service import SalesService

sales_bp = Blueprint('sales', __name__, url_prefix='/api/v1')
service = SalesService()


@sales_bp.route('/pipelines', methods=['POST'])
def create_pipeline():
    data = request.get_json()
    response = service.create_pipeline(data)
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines', methods=['GET'])
def list_pipelines():
    response = service.list_pipelines()
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines/<int:pipeline_id>', methods=['GET'])
def get_pipeline(pipeline_id):
    response = service.get_pipeline(pipeline_id)
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines/<int:pipeline_id>/stats', methods=['GET'])
def get_pipeline_stats(pipeline_id):
    response = service.get_pipeline_stats(pipeline_id)
    return jsonify(response.to_dict())


@sales_bp.route('/pipelines/<int:pipeline_id>/funnel', methods=['GET'])
def get_pipeline_funnel(pipeline_id):
    response = service.get_pipeline_funnel(pipeline_id)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities', methods=['POST'])
def create_opportunity():
    data = request.get_json()
    response = service.create_opportunity(data)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities', methods=['GET'])
def list_opportunities():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    pipeline_id = request.args.get('pipeline_id', type=int)
    stage = request.args.get('stage')
    owner_id = request.args.get('owner_id', type=int)
    response = service.list_opportunities(page=page, page_size=page_size, pipeline_id=pipeline_id, stage=stage, owner_id=owner_id)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>', methods=['GET'])
def get_opportunity(opp_id):
    response = service.get_opportunity(opp_id)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>', methods=['PUT'])
def update_opportunity(opp_id):
    data = request.get_json()
    response = service.update_opportunity(opp_id, data)
    return jsonify(response.to_dict())


@sales_bp.route('/opportunities/<int:opp_id>/stage', methods=['PUT'])
def change_stage(opp_id):
    data = request.get_json()
    stage = data.get('stage')
    response = service.change_stage(opp_id, stage)
    return jsonify(response.to_dict())


@sales_bp.route('/forecast', methods=['GET'])
def get_forecast():
    owner_id = request.args.get('owner_id', type=int)
    response = service.get_forecast(owner_id=owner_id)
    return jsonify(response.to_dict())
