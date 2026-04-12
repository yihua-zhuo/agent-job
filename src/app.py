from flask import Flask, jsonify
import os
from src.api import register_routes


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    register_routes(app)

    @app.route('/')
    def health():
        return jsonify({'status': 'ok', 'service': 'agent-job'})

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
