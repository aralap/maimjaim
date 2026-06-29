from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.config import get_settings
from app.crypto import make_lookup
from app.extensions import db
from app.models import User
from app.oauth_setup import (
    exchange_google_token,
    google_oauth_configured,
    register_google_oauth,
)

bp = Blueprint("web_auth", __name__)


def _require_google_oauth():
    settings = get_settings()
    if not register_google_oauth(settings):
        flash(
            "Google OAuth no está configurado. Agregá GOOGLE_CLIENT_ID y "
            "GOOGLE_CLIENT_SECRET en tu archivo .env y reiniciá la app.",
            "error",
        )
        return None, settings
    from app.extensions import oauth

    return oauth.google, settings


@bp.route("/login")
def login():
    if current_user.is_authenticated:
        if not current_user.is_active:
            return redirect(url_for("web_auth.pending"))
        return redirect(url_for("web_dashboard.index"))

    settings = get_settings()
    if not google_oauth_configured(settings):
        return render_template("auth/login.html", oauth_configured=False)

    if request.args.get("start") != "1":
        return render_template("auth/login.html", oauth_configured=True)

    client, settings = _require_google_oauth()
    if client is None:
        return render_template("auth/login.html", oauth_configured=False)

    redirect_uri = settings.oauth_redirect_uri or url_for("web_auth.callback", _external=True)
    session.permanent = True
    session.modified = True
    return client.authorize_redirect(redirect_uri=redirect_uri)


@bp.route("/auth/callback")
def callback():
    code = request.args.get("code")
    if not code:
        flash("Falta el código de autorización de Google.", "error")
        return redirect(url_for("web_auth.login"))

    client, settings = _require_google_oauth()
    if client is None:
        return redirect(url_for("web_auth.login"))

    redirect_uri = settings.oauth_redirect_uri or url_for("web_auth.callback", _external=True)

    try:
        token = exchange_google_token(client, redirect_uri, code)
    except Exception as exc:
        flash(f"Error al iniciar sesión con Google: {exc}", "error")
        return redirect(url_for("web_auth.login"))

    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = client.userinfo(token=token)

    email = userinfo.get("email", "").lower()
    google_sub = userinfo.get("sub")
    name = userinfo.get("name", email)

    if not email or not google_sub:
        flash("No se pudo obtener la información del usuario de Google.", "error")
        return redirect(url_for("web_auth.login"))

    if settings.allowed_email_domain:
        domain = email.split("@")[-1]
        if domain != settings.allowed_email_domain.lower():
            flash("Tu dominio de email no está autorizado.", "error")
            return redirect(url_for("web_auth.login"))

    try:
        is_admin = email in settings.admin_email_set
        user = User.query.filter_by(google_sub_lookup=make_lookup(google_sub)).first()
        if not user:
            user = User(
                email=email,
                google_sub=google_sub,
                name=name,
                role="admin" if is_admin else "staff",
                is_active=is_admin,
            )
            db.session.add(user)
        else:
            user.email = email
            user.name = name
            if is_admin:
                user.role = "admin"
                user.is_active = True

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(
            f"No se pudo guardar el usuario en la base de datos: {exc}. "
            "Ejecutá: flask db upgrade",
            "error",
        )
        return redirect(url_for("web_auth.login"))

    session.permanent = True
    login_user(user, remember=True, force=True)

    from app.services import AuditService

    AuditService.log(
        "auth.login",
        "auth",
        f"Inicio de sesión: {user.name}",
        entity_id=user.id,
        user_id=user.id if user.is_active else None,
        details={"email": user.email, "role": user.role, "is_active": user.is_active},
    )
    db.session.commit()

    if not user.is_active:
        flash(
            "Tu cuenta está pendiente de aprobación. Un administrador debe habilitarla.",
            "info",
        )
        return redirect(url_for("web_auth.pending"))

    flash(f"¡Bienvenido/a, {user.name}!", "success")
    return redirect(url_for("web_dashboard.index"))


@bp.route("/pending")
@login_required
def pending():
    if current_user.is_active:
        return redirect(url_for("web_dashboard.index"))
    return render_template("auth/pending.html")


@bp.route("/logout")
@login_required
def logout():
    from app.extensions import db
    from app.services import AuditService

    AuditService.log(
        "auth.logout",
        "auth",
        f"Cierre de sesión: {current_user.name}",
        entity_id=current_user.id,
        user_id=current_user.id,
    )
    db.session.commit()
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("web_auth.login"))
