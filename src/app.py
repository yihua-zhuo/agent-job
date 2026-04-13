from flask import Flask, jsonify
import os
import secrets
from src.api import register_routes
from src.internal.middleware.auth import require_auth, get_current_tenant_id
from src.internal.middleware.tenant import tenant_isolation_middleware, require_tenant


def create_app():
    app = Flask(__name__)
    # 生产环境必须设置 SECRET_KEY
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("SECRET_KEY environment variable is required in production")
        secret_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key

    # JWT 配置
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or secret_key
    app.config['JWT_ALGORITHM'] = 'HS256'

    # 注册租户隔离中间件（全局）
    app.before_request(tenant_isolation_middleware())

    # CORS 配置 - 生产环境禁止通配符
    from flask_cors import CORS
    cors_origins = os.environ.get('CORS_ORIGINS')
    if not cors_origins:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("CORS_ORIGINS environment variable is required in production")
        cors_origins = 'localhost'
    CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

    # 注册路由和中间件
    register_routes(app)

    # 导出 require_auth 和 require_tenant 供路由使用
    app.require_auth = require_auth
    app.require_tenant = require_tenant

    @app.route('/')
    def health():
        return jsonify({'status': 'ok', 'service': 'agent-job'})

    # 全局错误处理
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'code': 404, 'message': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'code': 500, 'message': 'Internal server error'}), 500

    return app


app = create_app()


if __name__ == '__main__':
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=8080, debug=debug)