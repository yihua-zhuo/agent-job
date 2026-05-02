"""Authentication API - 同步封装 async 服务层"""
from flask import Blueprint, request, jsonify
from services.auth_service import AuthService
from services.tenant_service import TenantService
from services.user_service import UserService
from models.user import UserRole, UserStatus
from api._sync_helper import run_async
import re
import os

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _is_valid_email(email):
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))


@auth_bp.route('/register', methods=['POST'])
def register():
    """创建租户 + 初始管理员账号"""
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip()
    tenant_name = data.get('tenant_name', '').strip() or username + "'s Company"

    if not username:
        return jsonify({"code": 1001, "message": "用户名不能为空"}), 400
    if len(username) < 3:
        return jsonify({"code": 1001, "message": "用户名至少3个字符"}), 400
    if not password or len(password) < 6:
        return jsonify({"code": 1001, "message": "密码至少6个字符"}), 400
    if email and not _is_valid_email(email):
        return jsonify({"code": 1001, "message": "邮箱格式不正确"}), 400

    secret_key = os.environ.get('JWT_SECRET_KEY') or os.environ.get('SECRET_KEY')
    if not secret_key:
        return jsonify({"code": 500, "message": "JWT_SECRET_KEY not configured"}), 500

    try:
        result = _register_sync(username, password, email, tenant_name, secret_key, data.get('full_name'))
        if isinstance(result, tuple) and result[0] is None:
            err_msg, code = result[1], result[2]
            return jsonify({"code": code, "message": err_msg}), code
        return jsonify({"code": 200, "data": result}), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


def _register_sync(username, password, email, tenant_name, secret_key, full_name):
    """Synchronous wrapper for the full async registration flow."""
    async def _do():
        tenant_svc = TenantService()
        user_svc = UserService()
        auth_svc = AuthService(secret_key=secret_key)

        tenant_result = await tenant_svc.create_tenant(
            name=tenant_name,
            plan='starter',
            admin_email=email or None
        )
        if not tenant_result.success:
            return None, tenant_result.message, tenant_result.code
        tenant = tenant_result.data
        if isinstance(tenant, dict):
            tenant_id = tenant['id']
        else:
            tenant_id = tenant.id

        user_result = await user_svc.create_user(
            username=username,
            email=email or f"{username}@local",
            password=password,
            role=UserRole.ADMIN,
            tenant_id=tenant_id,
            full_name=full_name or username
        )
        if not user_result.success:
            return None, user_result.message, user_result.code

        user = user_result.data
        if user is None:
            return None, "用户创建失败", 500

        user_id = user.id if hasattr(user, 'id') and user.id else 0
        user_email = user.email if hasattr(user, 'email') else email

        token = await auth_svc.create_token(
            user_id=user_id,
            username=username,
            role='admin',
            tenant_id=tenant_id
        )

        return {
            "token": token,
            "user": {
                "id": user_id,
                "username": username,
                "email": user_email,
                "tenant_id": tenant_id,
            },
            "message": "注册成功"
        }

    return run_async(_do)


@auth_bp.route('/login', methods=['POST'])
def login():
    """账号密码登录"""
    data = request.get_json()
    if not data:
        return jsonify({"code": 1001, "message": "Request body is required"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"code": 1001, "message": "用户名和密码不能为空"}), 400

    secret_key = os.environ.get('JWT_SECRET_KEY') or os.environ.get('SECRET_KEY')
    if not secret_key:
        return jsonify({"code": 500, "message": "JWT_SECRET_KEY not configured"}), 500

    try:
        result = _login_sync(username, password, secret_key)
        if isinstance(result, tuple) and result[0] is None:
            err_msg, code = result[1], result[2]
            return jsonify({"code": code, "message": err_msg}), code
        return jsonify({"code": 200, "data": result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


def _login_sync(username, password, secret_key):
    """Synchronous wrapper for login flow."""
    async def _do():
        auth_svc = AuthService(secret_key=secret_key)
        user = await auth_svc.authenticate_user(username, password)
        if not user:
            return None, "用户名或密码错误", 401

        token = await auth_svc.create_token(
            user_id=user['id'],
            username=user['username'],
            role=user['role'],
            tenant_id=user.get('tenant_id')
        )
        return {
            "token": token,
            "user": {k: v for k, v in user.items() if k != 'password_hash'},
            "expires_at": "24h"
        }

    return run_async(_do)