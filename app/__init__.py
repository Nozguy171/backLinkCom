from flask import Flask, jsonify
from flask_cors import CORS

from app.api.admin import admin_bp
from app.api.auth import auth_bp
from app.api.categories import categories_bp
from app.api.chat import chat_bp
from app.api.health import health_bp
from app.api.promotions import promotions_bp
from app.api.submissions import submissions_bp
from app.api.suppliers import suppliers_bp
from app.api.videos import videos_bp
from app.config import Config
from app.extensions import db, jwt, migrate
from app.seed import register_seed_commands
from app.commands import register_commands

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"] or '*'}},
        supports_credentials=False,
    )

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    jwt.init_app(app)

    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(categories_bp, url_prefix='/api')
    app.register_blueprint(promotions_bp, url_prefix='/api')
    app.register_blueprint(suppliers_bp, url_prefix='/api')
    app.register_blueprint(videos_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(submissions_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    register_commands(app)
    register_seed_commands(app)

    @app.get('/')
    def index():
        return jsonify({
            'name': 'LinkCom.mx API',
            'status': 'ok',
            'docs_hint': 'Usa /api/health para healthcheck.'
        })

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({'error': 'Token inválido', 'details': reason}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({'error': 'Falta token', 'details': reason}), 401

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return jsonify({'error': 'Token expirado'}), 401

    return app
