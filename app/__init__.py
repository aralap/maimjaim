from flask import Flask, redirect, request
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app import labels
from app.config import get_settings, is_development
from app.extensions import csrf, db, login_manager, migrate, oauth
from app.models import User
from app.oauth_setup import oauth_app_host, oauth_app_origin


def create_app(config_override: dict | None = None) -> Flask:
    get_settings.cache_clear()
    app = Flask(__name__)
    settings = get_settings()

    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_SECURE"] = (
        settings.oauth_redirect_uri.startswith("https://") or not is_development()
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SECURE"] = app.config["SESSION_COOKIE_SECURE"]
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["WTF_CSRF_ENABLED"] = True

    if settings.trust_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    if config_override:
        app.config.update(config_override)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    oauth.init_app(app)

    from app.oauth_setup import register_google_oauth

    register_google_oauth(settings)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from app.web.auth import bp as auth_bp
    from app.web.dashboard import bp as dashboard_bp
    from app.web.products import bp as products_bp
    from app.web.inventory import bp as inventory_bp
    from app.web.clients import bp as clients_bp
    from app.web.logs import bp as logs_bp
    from app.web.users import bp as users_bp
    from app.web.orders import bp as orders_bp
    from app.api.v1 import bp as api_v1_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    csrf.exempt(api_v1_bp)

    from app.seed import init_app as init_seed

    init_seed(app)
    _ensure_default_catalog(app)

    @app.before_request
    def redirect_to_oauth_host():
        """Keep OAuth session on the same host as OAUTH_REDIRECT_URI (fixes ngrok loops)."""
        if request.path.startswith("/api/") or request.endpoint == "web_dashboard.health":
            return None
        expected_host = oauth_app_host(settings)
        if not expected_host or request.host == expected_host:
            return None
        origin = oauth_app_origin(settings)
        target = f"{origin}{request.full_path}"
        if target.endswith("?"):
            target = target[:-1]
        return redirect(target)

    @app.before_request
    def require_approved_user():
        """Bloquea el acceso a usuarios pendientes de aprobación."""
        if not current_user.is_authenticated or current_user.is_active:
            return None
        allowed = {
            "web_auth.login",
            "web_auth.callback",
            "web_auth.pending",
            "web_auth.logout",
            "web_dashboard.health",
            "static",
        }
        if request.endpoint in allowed:
            return None
        if request.path.startswith("/api/"):
            return None
        return redirect(url_for("web_auth.pending"))

    @app.context_processor
    def inject_globals():
        return {
            "app_name": "MaimJaim",
            "labels": labels,
        }

    app.jinja_env.globals["labels"] = labels

    return app


def _ensure_default_catalog(app: Flask) -> None:
    """Carga el catálogo Maim Jaim si la base no tiene productos."""
    if app.config.get("TESTING"):
        return
    with app.app_context():
        from app.models import ProductVariant
        from app.services import ProductService

        if ProductVariant.query.count() == 0:
            ProductService.seed_default_catalog()

