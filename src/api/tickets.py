"""Tickets API - Synchronous wrapper for async ticket service."""
from flask import Blueprint, request, jsonify
from services.ticket_service import TicketService
from internal.middleware.auth import require_auth, get_current_tenant_id
from api._sync_helper import run_async

ticket_bp = Blueprint('tickets', __name__, url_prefix='/api/v1/tickets')


def _get_tenant_id():
    tenant_id = get_current_tenant_id()
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise Exception("Tenant context required")
    return tenant_id


@ticket_bp.errorhandler(Exception)
def _handle_error(e):
    msg = str(e)
    if "tenant" in msg.lower():
        return jsonify({"code": 401, "message": "Tenant context required"}), 401
    return jsonify({"code": 500, "message": msg}), 500


@ticket_bp.route('', methods=['POST'])
@require_auth
def create_ticket():
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400
    if not data.get('subject', '').strip():
        return jsonify({"code": 1001, "message": "工单标题不能为空"}), 400

    svc = TicketService()
    result = run_async(svc.create_ticket, _get_tenant_id(), data)
    return jsonify(result.to_dict())


@ticket_bp.route('', methods=['GET'])
@require_auth
def list_tickets():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')

    svc = TicketService()
    result = run_async(
        svc.list_tickets,
        tenant_id=_get_tenant_id(),
        page=page, page_size=page_size, status=status, priority=priority
    )
    return jsonify(result.to_dict())


@ticket_bp.route('/<int:ticket_id>', methods=['GET'])
@require_auth
def get_ticket(ticket_id):
    svc = TicketService()
    result = run_async(svc.get_ticket, ticket_id, _get_tenant_id())
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@ticket_bp.route('/<int:ticket_id>', methods=['PUT'])
@require_auth
def update_ticket(ticket_id):
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    svc = TicketService()
    result = run_async(svc.update_ticket, ticket_id, _get_tenant_id(), data)
    status_code = 200 if result.status.value == "success" else 404
    return jsonify(result.to_dict()), status_code


@ticket_bp.route('/<int:ticket_id>/status', methods=['PUT'])
@require_auth
def change_ticket_status(ticket_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"code": 1001, "message": "status is required"}), 400

    svc = TicketService()
    result = run_async(svc.change_status, ticket_id, _get_tenant_id(), data['status'])
    return jsonify(result.to_dict())


@ticket_bp.route('/<int:ticket_id>/replies', methods=['POST'])
@require_auth
def add_reply(ticket_id):
    data = request.get_json()
    if not data or not data.get('content', '').strip():
        return jsonify({"code": 1001, "message": "回复内容不能为空"}), 400

    svc = TicketService()
    result = run_async(
        svc.add_reply,
        ticket_id=ticket_id,
        tenant_id=_get_tenant_id(),
        content=data['content'],
        is_internal=data.get('is_internal', False)
    )
    return jsonify(result.to_dict())