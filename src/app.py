from flask import Flask, jsonify
import os
import secrets
from src.api import register_routes


def create_app():
    app = Flask(__name__)
    # 生产环境必须设置 SECRET_KEY
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise ValueError("SECRET_KEY environment variable is required in production")
        secret_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key

    # CORS 配置
    from flask_cors import CORS
    cors_origins = os.environ.get('CORS_ORIGINS', '*')
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    register_routes(app)

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
