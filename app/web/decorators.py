from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user, login_required


def approved_required(view):
    """Usuario autenticado y habilitado por un administrador."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_active:
            return redirect(url_for("web_auth.pending"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Solo administradores habilitados."""

    @wraps(view)
    def inner(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return view(*args, **kwargs)

    return approved_required(inner)
